"""Read-only lossless Pepperstone quote capture for frozen quote-revision-sequence V2.

This collector deliberately computes no strategy features, returns, PnL, rankings,
or parameter selections. It first performs current execution-metadata and minimum-
volume expected-margin checks. Historical BID/ASK acquisition starts only if all
five frozen signal symbols are structurally capable of minimum-size participation
in the EUR200 account under the frozen gate.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import shutil
import time
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from google.protobuf.json_format import MessageToDict

from m6.ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAAssetListReq,
    ProtoOAExpectedMarginReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTickDataReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOAQuoteType
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL = "research_core_v3/state/QUOTE_REVISION_SEQUENCE_PRESSURE_ACQUISITION_PLAN_V2.json"
EXPECTED_PLAN_GIT_BLOB_SHA = "b9347b39164095e8744c2edc26fb7607ea4d6d13"
OUTPUT_FILENAME = "MXM_V3_QUOTE_REVISION_SEQUENCE_RAW_EVIDENCE_V2.zip"
BUNDLE_DIR = "MXM_V3_QUOTE_REVISION_SEQUENCE_RAW_EVIDENCE_V2"
TOOL_VERSION = "MXM_V3_QUOTE_REVISION_SEQUENCE_RAW_CAPTURE_V2"
EXPECTED_ACCOUNT_FINGERPRINT = "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
EXPECTED_SYMBOLS = {
    3: "EURJPY",
    9: "EURGBP",
    18: "AUDCAD",
    19: "GBPCAD",
    116: "JPN225",
}
PROTECTED_FORWARD_START = "2026-09-17T12:02:58Z"
MIN_HISTORICAL_INTERVAL_SECONDS = 0.22
MAX_HISTORICAL_REQUESTS = 20000
RAW_HEADER = ("timestamp_ms", "tick", "tie_order")
EUR200 = Decimal("200")


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


def _sha_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _deterministic_zip(root: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return _sha_file(target)


def _parse_hms(value: str) -> tuple[int, int, int]:
    hh, mm, ss = (int(x) for x in value.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
        raise CaptureContractError(f"invalid UTC time {value}")
    return hh, mm, ss


def _utc_window_ms(day: str, start_hms: str, end_hms: str, before: int, after: int) -> tuple[int, int]:
    d = datetime.fromisoformat(day).date()
    sh, sm, ss = _parse_hms(start_hms)
    eh, em, es = _parse_hms(end_hms)
    start = datetime(d.year, d.month, d.day, sh, sm, ss, tzinfo=timezone.utc) - timedelta(seconds=before)
    end = datetime(d.year, d.month, d.day, eh, em, es, tzinfo=timezone.utc) + timedelta(seconds=after)
    if end <= start:
        raise CaptureContractError("window end must follow start")
    protected = datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z", "+00:00"))
    if end >= protected:
        raise CaptureContractError("requested raw quote window crosses protected forward")
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def validate_plan_bytes(data: bytes) -> dict[str, Any]:
    if _git_blob_sha(data) != EXPECTED_PLAN_GIT_BLOB_SHA:
        raise CaptureContractError("quote revision V2 acquisition plan Git blob mismatch")
    plan = json.loads(data.decode("utf-8"))
    if plan.get("schema") != "mxm.research-core-v3.quote-revision-sequence-pressure-acquisition-plan.v2":
        raise CaptureContractError("wrong acquisition plan schema")
    if plan.get("status") != "FROZEN_PREOUTCOME_READ_ONLY_RAW_REPLAYABLE_ACQUISITION_SUPERSEDES_V1":
        raise CaptureContractError("acquisition plan is not the frozen V2 authority")
    if plan.get("execution_authorized") is not False:
        raise CaptureContractError("plan itself must remain pre-authorization")
    if plan.get("source_environment") != "Pepperstone - Europe LIVE":
        raise CaptureContractError("source environment mismatch")
    if plan.get("account_fingerprint_sha256") != EXPECTED_ACCOUNT_FINGERPRINT:
        raise CaptureContractError("account fingerprint mismatch")
    got = {int(x["symbol_id"]): str(x["symbol"]) for x in plan.get("signal_symbols", [])}
    if got != EXPECTED_SYMBOLS:
        raise CaptureContractError("frozen signal symbol identity set changed")
    cal = plan.get("calendar") or {}
    dates = list(cal.get("dates_utc") or [])
    if len(dates) != 30 or len(set(dates)) != 30:
        raise CaptureContractError("V2 calendar must contain exactly 30 unique dates")
    weekdays = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    months = set()
    for value in dates:
        d = datetime.fromisoformat(value).date()
        if d.weekday() not in weekdays:
            raise CaptureContractError("weekend date in frozen calendar")
        weekdays[d.weekday()] += 1
        months.add((d.year, d.month))
    if list(weekdays.values()) != [6, 6, 6, 6, 6] or len(months) != 12:
        raise CaptureContractError("weekday/month stratification changed")
    if cal.get("protected_forward_start_utc") != PROTECTED_FORWARD_START:
        raise CaptureContractError("protected forward boundary changed")
    windows = cal.get("windows_utc") or []
    if windows != [["00:00:00", "01:00:00"], ["07:00:00", "08:00:00"], ["13:00:00", "14:00:00"]]:
        raise CaptureContractError("frozen quote windows changed")
    acq = plan.get("acquisition") or {}
    required = {
        "raw_ticks_transferred_off_device": True,
        "raw_ticks_discarded_after_derivation": False,
        "device_computes_strategy_features": False,
        "device_computes_strategy_outcomes": False,
        "device_computes_pnl": False,
        "automatic_parameter_search": False,
        "automatic_additional_acquisition": False,
        "fill_authority": False,
        "orders": False,
        "account_mutation": False,
        "protected_forward_opened": False,
    }
    for key, expected in required.items():
        if acq.get(key) is not expected:
            raise CaptureContractError(f"capture contract mismatch: {key}")
    return plan


def load_plan(repo_root: Path | str) -> dict[str, Any]:
    data = (Path(repo_root) / PLAN_REL).read_bytes()
    return validate_plan_bytes(data)


def decode_tick_response(tick_data: list[Any], frm_ms: int, to_ms: int) -> list[tuple[int, int]]:
    """Decode cTrader newest-first delta timestamps into oldest-first lossless events."""
    if not tick_data:
        return []
    newest: list[tuple[int, int]] = []
    current = int(tick_data[0].timestamp)
    tick = int(tick_data[0].tick)
    if not (frm_ms <= current <= to_ms) or tick <= 0:
        raise CaptureContractError("malformed first historical tick")
    newest.append((current, tick))
    previous = current
    for item in tick_data[1:]:
        delta = int(item.timestamp)
        tick = int(item.tick)
        if delta < 0 or tick <= 0:
            raise CaptureContractError("malformed historical tick delta/price")
        current = previous - delta
        if current > previous or not (frm_ms <= current <= to_ms):
            raise CaptureContractError("historical tick chronology/range failure")
        newest.append((current, tick))
        previous = current
    return list(reversed(newest))


def _write_raw_gzip(path: Path, rows: list[tuple[int, int]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.writer(text, lineterminator="\n")
                writer.writerow(RAW_HEADER)
                last_ts = None
                tie = -1
                for ts, tick in rows:
                    if last_ts is not None and ts < last_ts:
                        raise CaptureContractError("raw rows not chronological")
                    tie = tie + 1 if ts == last_ts else 0
                    writer.writerow((str(ts), str(tick), str(tie)))
                    last_ts = ts
    tmp.replace(path)
    return {
        "rows": len(rows),
        "first_timestamp_ms": rows[0][0] if rows else None,
        "last_timestamp_ms": rows[-1][0] if rows else None,
        "sha256": _sha_file(path),
        "encoding": "gzip_csv_utf8",
        "fields": list(RAW_HEADER),
    }


class QuoteRevisionRawRunner:
    def __init__(
        self,
        *,
        plan: dict[str, Any],
        client_id: str,
        client_secret: str,
        access_token: str,
        config: dict[str, Any],
        repo_root: Path | str,
        progress=print,
        transport=None,
    ):
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.root = Path(repo_root)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(LIVE_HOST, LIVE_PORT, response_timeout=90)
        self.bundle = self.root / "quote_revision_sequence_v2_output" / BUNDLE_DIR
        self.work = self.root / ".quote_revision_sequence_v2_work" / EXPECTED_PLAN_GIT_BLOB_SHA[:16]
        self.zip_path = self.root / OUTPUT_FILENAME
        self._app = False
        self._account: int | None = None
        self._last_historical_send: float | None = None
        self._historical_requests = 0
        self._request_trace: list[dict[str, Any]] = []

    def _request(self, request: Any, *, historical: bool = False):
        require_read_only_request(type(request).__name__)
        if historical:
            now = time.monotonic()
            if self._last_historical_send is not None:
                wait = MIN_HISTORICAL_INTERVAL_SECONDS - (now - self._last_historical_send)
                if wait > 0:
                    time.sleep(wait)
            self._last_historical_send = time.monotonic()
            self._historical_requests += 1
            if self._historical_requests > MAX_HISTORICAL_REQUESTS:
                raise CaptureContractError("historical request safety ceiling exceeded")
        response = self.transport.request(request, timeout=90)
        if type(response).__name__ == "ProtoOAErrorRes":
            raise CaptureContractError(f"cTrader API error: {getattr(response, 'errorCode', 'UNKNOWN')}")
        return response

    def _restore(self):
        self.transport.connect()
        if self._app:
            self._request(ProtoOAApplicationAuthReq(clientId=self.client_id, clientSecret=self.client_secret))
        if self._account is not None:
            self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account, accessToken=self.access_token))

    def _send(self, request: Any, *, historical: bool = False, retries: int = 3):
        last = None
        for attempt in range(retries):
            try:
                return self._request(request, historical=historical)
            except Exception as exc:
                last = exc
                if attempt + 1 == retries:
                    break
                time.sleep(min(4.0, 2 ** attempt))
                try:
                    self.transport.close()
                    self._restore()
                except Exception as restore_exc:
                    last = restore_exc
        raise CaptureContractError(f"{type(request).__name__} failed: {redact_text(str(last))}")

    def _authorize_account(self) -> tuple[int, dict[str, Any], dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id, clientSecret=self.client_secret))
        self._app = True
        accounts = [
            _plain(x)
            for x in self._send(
                ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)
            ).ctidTraderAccount
        ]
        saved = self.config.get("ctid_trader_account_id")
        try:
            account = select_live_pepperstone_account(accounts, account_override=saved)
        except MappingError:
            selector = self.config.get("account_selector")
            if saved is not None or not callable(selector):
                raise
            account = select_live_pepperstone_account(
                accounts,
                account_override=int(selector(live_account_candidates(accounts))),
            )
        aid = int(account["ctidTraderAccountId"])
        self._account = aid
        if account_fingerprint(aid) != EXPECTED_ACCOUNT_FINGERPRINT:
            raise MappingError("LIVE account fingerprint differs from frozen Pepperstone authority")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid, accessToken=self.access_token))
        trader_msg = self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader
        trader = _plain(trader_msg)
        if "pepperstone" not in str(trader.get("brokerName", "")).lower() and "pepperstone" not in str(account.get("brokerTitleShort", "")).lower():
            raise MappingError("account is not verifiably Pepperstone")
        light = [
            _plain(x)
            for x in self._send(
                ProtoOASymbolsListReq(ctidTraderAccountId=aid, includeArchivedSymbols=False)
            ).symbol
        ]
        light_by_id = {int(x["symbolId"]): x for x in light}
        q = ProtoOASymbolByIdReq(ctidTraderAccountId=aid)
        q.symbolId.extend(sorted(EXPECTED_SYMBOLS))
        full_by_id = {int(x.symbolId): _plain(x) for x in self._send(q).symbol}
        return aid, trader, light_by_id, full_by_id

    def _preflight_execution_metadata(
        self,
        aid: int,
        trader: dict[str, Any],
        light_by_id: dict[int, dict[str, Any]],
        full_by_id: dict[int, dict[str, Any]],
    ) -> tuple[dict[str, Any], list[str]]:
        asset_res = self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid))
        assets = {_plain(x).get("assetId"): _plain(x) for x in asset_res.asset}
        deposit_id = trader.get("depositAssetId")
        deposit = assets.get(deposit_id)
        deposit_name = str((deposit or {}).get("name", ""))
        blockers: list[str] = []
        if deposit_name.upper() != "EUR":
            blockers.append(f"deposit asset is {deposit_name or 'UNKNOWN'}, expected EUR")

        symbols_meta = []
        for sid, name in EXPECTED_SYMBOLS.items():
            light = light_by_id.get(sid)
            full = full_by_id.get(sid)
            if light is None or full is None or str((light or {}).get("symbolName")) != name:
                blockers.append(f"identity mismatch {name}/{sid}")
                continue
            if light.get("enabled") is False or int(full.get("tradingMode", -1)) != 0:
                blockers.append(f"{name} is not new-entry tradable")
            try:
                min_volume = int(full["minVolume"])
                step_volume = int(full["stepVolume"])
                lot_size = int(full["lotSize"])
            except Exception:
                blockers.append(f"{name} missing minVolume/stepVolume/lotSize")
                continue
            if min_volume <= 0 or step_volume <= 0 or lot_size <= 0 or min_volume % step_volume != 0:
                blockers.append(f"{name} invalid executable volume lattice")
            commission_type = full.get("commissionType")
            legacy_commission = int(full.get("commission", 0) or 0)
            precise_rate = int(full.get("preciseTradingCommissionRate", 0) or 0)
            if commission_type is None or int(commission_type) not in (1, 2, 3, 4):
                blockers.append(f"{name} unresolved commission type")
            if legacy_commission != 0 and precise_rate <= 0:
                blockers.append(f"{name} nonzero commission lacks preciseTradingCommissionRate")

            req = ProtoOAExpectedMarginReq(ctidTraderAccountId=aid, symbolId=sid)
            req.volume.append(min_volume)
            margin_res = self._send(req)
            margin_plain = _plain(margin_res)
            money_digits = margin_plain.get("moneyDigits")
            margins = list(margin_res.margin)
            buy_eur = sell_eur = None
            if money_digits is None or len(margins) != 1:
                blockers.append(f"{name} expected-margin response incomplete")
            else:
                scale = Decimal(10) ** int(money_digits)
                buy_eur = Decimal(int(margins[0].buyMargin)) / scale
                sell_eur = Decimal(int(margins[0].sellMargin)) / scale
                if buy_eur >= EUR200 or sell_eur >= EUR200:
                    blockers.append(f"{name} minimum-size expected margin is not strictly below EUR200")

            selected_full_fields = {
                key: full.get(key)
                for key in (
                    "symbolId", "digits", "pipPosition", "enableShortSelling", "minVolume",
                    "stepVolume", "maxVolume", "lotSize", "tradingMode", "commission",
                    "commissionType", "preciseTradingCommissionRate", "minCommission",
                    "preciseMinCommission", "minCommissionType", "minCommissionAsset",
                    "pnlConversionFeeRate", "leverageId", "scheduleTimeZone", "schedule", "holiday",
                    "measurementUnits",
                )
            }
            symbols_meta.append({
                "symbol": name,
                "symbol_id": sid,
                "light_enabled": light.get("enabled"),
                "current_symbol_metadata": selected_full_fields,
                "expected_margin": {
                    "requested_raw_volume": min_volume,
                    "money_digits": money_digits,
                    "buy_margin_eur": str(buy_eur) if buy_eur is not None else None,
                    "sell_margin_eur": str(sell_eur) if sell_eur is not None else None,
                    "structural_eur200_gate_pass": (
                        buy_eur is not None and sell_eur is not None
                        and buy_eur < EUR200 and sell_eur < EUR200
                    ),
                },
            })

        payload = {
            "schema": "mxm.research-core-v3.quote-revision-sequence-pre-capture-execution-metadata.v2",
            "captured_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_environment": self.plan["source_environment"],
            "account_fingerprint_sha256": EXPECTED_ACCOUNT_FINGERPRINT,
            "deposit_asset": deposit_name,
            "signal_symbols": symbols_meta,
            "blockers": blockers,
            "historical_quote_requests_sent": 0,
            "strategy_features_computed": False,
            "strategy_outcomes_opened": False,
            "pnl_computed": False,
            "orders_placed": False,
            "account_mutation": False,
            "protected_forward_opened": False,
        }
        return payload, blockers

    def _fetch_complete_ticks(
        self,
        *,
        aid: int,
        sid: int,
        side_name: str,
        frm_ms: int,
        to_ms: int,
        depth: int = 0,
    ) -> list[tuple[int, int]]:
        side_value = ProtoOAQuoteType.Value(side_name)
        req = ProtoOAGetTickDataReq(
            ctidTraderAccountId=aid,
            symbolId=sid,
            type=side_value,
            fromTimestamp=frm_ms,
            toTimestamp=to_ms,
        )
        response = self._send(req, historical=True)
        decoded = decode_tick_response(list(response.tickData), frm_ms, to_ms)
        trace_index = len(self._request_trace)
        node = {
            "request_index": self._historical_requests,
            "symbol_id": sid,
            "side": side_name,
            "from_ms": frm_ms,
            "to_ms": to_ms,
            "depth": depth,
            "returned_count": len(decoded),
            "has_more": bool(response.hasMore),
            "used_for_raw_evidence": not bool(response.hasMore),
        }
        self._request_trace.append(node)
        if not bool(response.hasMore):
            return decoded
        if frm_ms >= to_ms:
            raise CaptureContractError(
                f"{sid}/{side_name}: one-millisecond saturated historical tick interval"
            )
        mid = (frm_ms + to_ms) // 2
        if mid < frm_ms or mid >= to_ms:
            raise CaptureContractError("invalid lossless hasMore split boundary")
        self._request_trace[trace_index]["split_mid_ms"] = mid
        left = self._fetch_complete_ticks(
            aid=aid, sid=sid, side_name=side_name, frm_ms=frm_ms, to_ms=mid, depth=depth + 1
        )
        right = self._fetch_complete_ticks(
            aid=aid, sid=sid, side_name=side_name, frm_ms=mid + 1, to_ms=to_ms, depth=depth + 1
        )
        if left and right and left[-1][0] >= right[0][0]:
            raise CaptureContractError("disjoint split chronology overlap")
        return left + right

    def _capture_raw_file(
        self,
        *,
        aid: int,
        symbol: str,
        sid: int,
        day: str,
        window_index: int,
        window: list[str],
        side_name: str,
    ) -> dict[str, Any]:
        before = int(self.plan["calendar"]["query_padding_before_seconds"])
        after = int(self.plan["calendar"]["query_padding_after_seconds"])
        frm_ms, to_ms = _utc_window_ms(day, window[0], window[1], before, after)
        safe_window = f"{window_index:02d}_{window[0][:2]}{window[0][3:5]}_{window[1][:2]}{window[1][3:5]}"
        rel = Path("raw_quotes") / f"{sid}_{symbol}" / day / f"{safe_window}_{side_name}.csv.gz"
        work_file = self.work / rel
        meta_file = work_file.with_suffix(work_file.suffix + ".meta.json")
        binding = {
            "plan_blob": EXPECTED_PLAN_GIT_BLOB_SHA,
            "symbol": symbol,
            "symbol_id": sid,
            "day": day,
            "window_index": window_index,
            "window": window,
            "side": side_name,
            "from_ms": frm_ms,
            "to_ms": to_ms,
        }
        if work_file.is_file() and meta_file.is_file():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("binding") == binding and meta.get("sha256") == _sha_file(work_file):
                self.progress(f"[RESUME] {symbol} {day} W{window_index} {side_name} rows={meta.get('rows', 0):,}")
                target = self.bundle / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(work_file, target)
                out = dict(meta)
                out["file"] = rel.as_posix()
                out["resumed"] = True
                return out

        rows = self._fetch_complete_ticks(
            aid=aid, sid=sid, side_name=side_name, frm_ms=frm_ms, to_ms=to_ms
        )
        stats = _write_raw_gzip(work_file, rows)
        meta = {
            "binding": binding,
            **stats,
            "requested_from_ms": frm_ms,
            "requested_to_ms": to_ms,
        }
        atomic_write_json(meta_file, meta)
        target = self.bundle / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work_file, target)
        out = dict(meta)
        out["file"] = rel.as_posix()
        out["resumed"] = False
        return out

    def _finalize_bundle(self, status: str, *, precapture: dict[str, Any], windows: list[dict[str, Any]]):
        atomic_write_json(self.bundle / "PRECAPTURE_EXECUTION_METADATA.json", precapture)
        atomic_write_json(self.bundle / "RAW_WINDOW_MANIFEST.json", {
            "schema": "mxm.research-core-v3.quote-revision-sequence-raw-window-manifest.v2",
            "status": status,
            "requested_window_side_files": 900,
            "files": windows,
            "all_requested_windows_preserved": len(windows) == 900 if status == "RAW_CAPTURE_COMPLETE" else False,
        })
        atomic_write_json(self.bundle / "REQUEST_SPLIT_MANIFEST.json", {
            "schema": "mxm.research-core-v3.quote-revision-sequence-request-split-manifest.v2",
            "historical_requests_completed": self._historical_requests,
            "request_trace": self._request_trace,
            "lossless_hasMore_policy": self.plan["acquisition"]["hasMore_policy"],
        })
        manifest = {
            "schema": "mxm.research-core-v3.quote-revision-sequence-raw-capture-bundle.v2",
            "status": status,
            "captured_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tool_version": TOOL_VERSION,
            "plan_git_blob_sha": EXPECTED_PLAN_GIT_BLOB_SHA,
            "source_environment": self.plan["source_environment"],
            "account_fingerprint_sha256": EXPECTED_ACCOUNT_FINGERPRINT,
            "signal_symbols": [EXPECTED_SYMBOLS[k] for k in sorted(EXPECTED_SYMBOLS)],
            "raw_window_side_files": len(windows),
            "historical_requests_completed": self._historical_requests,
            "raw_tick_values_in_bundle": status == "RAW_CAPTURE_COMPLETE",
            "strategy_features_computed": False,
            "strategy_outcomes_opened": False,
            "pnl_computed": False,
            "parameter_search_performed": False,
            "orders_placed": False,
            "account_mutation": False,
            "fill_authority": False,
            "protected_forward_opened": False,
        }
        atomic_write_json(self.bundle / "CAPTURE_MANIFEST.json", manifest)
        checks = []
        for path in sorted(p for p in self.bundle.rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256"):
            checks.append(f"{_sha_file(path)}  {path.relative_to(self.bundle).as_posix()}")
        (self.bundle / "CHECKSUMS.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
        scan_bundle_for_secrets(self.bundle, [self.client_secret, self.access_token])
        digest = _deterministic_zip(self.bundle, self.zip_path)
        self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
        return self.zip_path

    def run(self):
        self.work.mkdir(parents=True, exist_ok=True)
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True)
        self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect()
            self.progress("[1/3] Pepperstone Europe LIVE view-only auth + current EUR200 structural preflight")
            aid, trader, light, full = self._authorize_account()
            precapture, blockers = self._preflight_execution_metadata(aid, trader, light, full)
            atomic_write_json(self.bundle / "PRECAPTURE_EXECUTION_METADATA.json", precapture)
            if blockers:
                self.progress("[PRECATURE BLOCKED] No historical quote request sent.")
                return self._finalize_bundle("PRECAPTURE_BLOCKED_NO_QUOTES_REQUESTED", precapture=precapture, windows=[])

            self.progress("[2/3] Lossless raw BID/ASK capture only; no features/outcomes/PnL")
            windows_manifest: list[dict[str, Any]] = []
            dates = self.plan["calendar"]["dates_utc"]
            windows = self.plan["calendar"]["windows_utc"]
            total = len(EXPECTED_SYMBOLS) * len(dates) * len(windows) * 2
            done = 0
            for sid, symbol in EXPECTED_SYMBOLS.items():
                for day in dates:
                    for wi, window in enumerate(windows, 1):
                        for side in ("BID", "ASK"):
                            item = self._capture_raw_file(
                                aid=aid,
                                symbol=symbol,
                                sid=sid,
                                day=day,
                                window_index=wi,
                                window=window,
                                side_name=side,
                            )
                            windows_manifest.append(item)
                            done += 1
                            if done % 25 == 0 or done == total:
                                self.progress(
                                    f"[RAW {done}/{total}] hist_req={self._historical_requests} "
                                    f"last={symbol}/{day}/W{wi}/{side} rows={item.get('rows', 0):,}"
                                )
            self.progress("[3/3] Validating complete replayable raw evidence + deterministic ZIP")
            if len(windows_manifest) != 900:
                raise CaptureContractError("raw manifest does not contain exactly 900 requested side-window files")
            return self._finalize_bundle("RAW_CAPTURE_COMPLETE", precapture=precapture, windows=windows_manifest)
        finally:
            self.transport.close()

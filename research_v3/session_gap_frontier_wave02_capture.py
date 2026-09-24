"""Exact-scope, read-only BID/ASK tick collector for the Wave 02 structural screen."""
from __future__ import annotations

import csv
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from competition.ultra_fast_capture import QUOTE_TYPES
from m6.cost_evidence import decode_ctrader_tick_page, next_tick_page_to_ms
from m6.ctrader_capture import (
    CaptureContractError, MappingError, account_fingerprint, atomic_write_json,
    require_read_only_request,
    scan_bundle_for_secrets, select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq, ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq, ProtoOAGetTickDataReq,
    ProtoOASymbolByIdReq, ProtoOASymbolsListReq, ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL = "data/SESSION_GAP_FRONTIER_WAVE_02_M5_CAPTURE_PLAN_V1.json"
OUTPUT_FILENAME = "MXM_SESSION_GAP_FRONTIER_WAVE_02_M5_BID_ASK_CAPTURE.zip"
EXPECTED_SYMBOLS = {
    "EURGBP": 9, "JPN225": 116, "XAUUSD": 41, "SPY.US": 822,
    "AAPL.US-24": 2999, "NatGas": 251, "DOGEUSD": 324, "UKGILT-F": 7292,
}
HEADER = (
    "timestamp_utc", "symbol_id", "broker_symbol", "bid_open", "bid_high",
    "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close",
    "tick_volume", "spread", "trading_session_metadata",
)
EXPECTED_FIELDS = list(HEADER)


def _plain(message):
    return MessageToDict(message, preserving_proto_field_name=False, use_integers_for_enums=True)


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _ms(value):
    return int(value.timestamp() * 1000)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_plan(plan):
    if plan.get("schema") != "mxm.greenfield.session-gap-frontier-wave02-m5-capture-plan.v1":
        raise CaptureContractError("wrong Wave 02 capture plan schema")
    if plan.get("status") != "FROZEN_PRE_CAPTURE_PRE_SCREEN_NO_ECONOMICS":
        raise CaptureContractError("Wave 02 plan is not prospectively frozen")
    if plan.get("resolution") != "M5" or plan.get("fields") != EXPECTED_FIELDS:
        raise CaptureContractError("Wave 02 plan resolution or fields drift")
    observed = {str(x["broker_symbol"]): int(x["symbol_id"]) for x in plan.get("symbols") or []}
    if observed != EXPECTED_SYMBOLS:
        raise CaptureContractError("Wave 02 exact symbol identities drift")
    start, end = _utc(plan["interval"]["start_utc"]), _utc(plan["interval"]["end_utc"])
    if not start < end < _utc(plan["protected_forward_start"]):
        raise CaptureContractError("Wave 02 interval/protected boundary invalid")
    law = plan.get("capture_law") or {}
    if any(law.get(key) is not value for key, value in (
        ("read_only", True), ("orders_permitted", False),
        ("account_mutation_permitted", False), ("synthetic_fill_permitted", False),
        ("forward_fill_permitted", False), ("complete_bid_ask_pagination_required", True),
        ("explicit_bid_ask_timestamp_alignment_required", True),
    )):
        raise CaptureContractError("Wave 02 capture law is not fail-closed")
    if plan.get("economic_outcomes_opened") != 0 or plan.get("v2_attempts_consumed") != 0:
        raise CaptureContractError("Wave 02 plan is economically contaminated")
    return True


def _bucket_ticks(ticks, start_ms, end_ms):
    buckets = {}
    for tick in ticks:
        timestamp = int(tick.timestamp_ms)
        if timestamp < start_ms or timestamp >= end_ms:
            continue
        bucket = start_ms + ((timestamp - start_ms) // 300000) * 300000
        buckets.setdefault(bucket, []).append(float(tick.price))
    return buckets


def align_bid_ask_m5(bid_ticks, ask_ticks, *, start_utc, end_utc, symbol_id, broker_symbol):
    """Align independently paginated quote ticks; missing sides remain missing."""
    start, end = _ms(_utc(start_utc)), _ms(_utc(end_utc))
    bid, ask = _bucket_ticks(bid_ticks, start, end), _bucket_ticks(ask_ticks, start, end)
    rows = []
    for bucket in sorted(set(bid) & set(ask)):
        bp, ap = bid[bucket], ask[bucket]
        row = {
            "timestamp_utc": datetime.fromtimestamp(bucket / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "symbol_id": str(symbol_id), "broker_symbol": broker_symbol,
            "bid_open": str(bp[0]), "bid_high": str(max(bp)), "bid_low": str(min(bp)), "bid_close": str(bp[-1]),
            "ask_open": str(ap[0]), "ask_high": str(max(ap)), "ask_low": str(min(ap)), "ask_close": str(ap[-1]),
            "tick_volume": str(len(bp) + len(ap)),
            "spread": str(((ap[0] + ap[-1]) / 2) - ((bp[0] + bp[-1]) / 2)),
            "trading_session_metadata": "BROKER_NATIVE_TICK_OBSERVATION",
        }
        rows.append(row)
    return rows


class FrontierWave02CaptureRunner:
    def __init__(self, *, plan, client_id, client_secret, access_token, config, repo_root, progress=print, transport=None):
        validate_plan(plan)
        self.plan = dict(plan); self.client_id = client_id; self.client_secret = client_secret
        self.access_token = access_token; self.config = dict(config); self.root = Path(repo_root); self.progress = progress
        self.transport = transport or StdlibCTraderTransport(LIVE_HOST, LIVE_PORT, response_timeout=60)
        self.bundle = self.root / "session_gap_frontier_wave02_capture_output" / "MXM_SESSION_GAP_FRONTIER_WAVE_02_M5_BID_ASK_CAPTURE"
        self.zip_path = self.root / OUTPUT_FILENAME; self.account = None; self.last_request = 0.0

    def _send(self, request):
        require_read_only_request(type(request).__name__)
        delay = 0.25 - (time.monotonic() - self.last_request)
        if delay > 0: time.sleep(delay)
        self.last_request = time.monotonic()
        response = self.transport.request(request, timeout=60)
        if type(response).__name__ == "ProtoOAErrorRes":
            raise CaptureContractError(f"cTrader API error: {getattr(response, 'errorCode', 'UNKNOWN')}")
        return response

    def _ticks(self, aid, symbol_id, side, start_ms, end_ms):
        out = []
        window = 7 * 24 * 60 * 60 * 1000
        window_start = start_ms
        while window_start <= end_ms:
            window_end = min(end_ms, window_start + window - 1)
            page_to, previous = window_end, None
            while page_to >= window_start:
                response = self._send(ProtoOAGetTickDataReq(
                    ctidTraderAccountId=aid, symbolId=symbol_id, type=QUOTE_TYPES[side],
                    fromTimestamp=window_start, toTimestamp=page_to,
                ))
                page = decode_ctrader_tick_page([{"timestamp": int(x.timestamp), "tick": int(x.tick)} for x in response.tickData])
                out.extend(page)
                if not bool(response.hasMore): break
                if not page: raise CaptureContractError("hasMore returned with an empty tick page")
                next_to = next_tick_page_to_ms(page, current_from_ms=window_start, previous_oldest_ms=previous)
                if next_to is None or next_to >= page_to: raise CaptureContractError("tick pagination did not advance")
                previous = min(x.timestamp_ms for x in page); page_to = next_to
            window_start = window_end + 1
        return out

    def run(self):
        validate_plan(self.plan)
        self.bundle.mkdir(parents=True, exist_ok=True); raw = self.bundle / "raw"; raw.mkdir(exist_ok=True)
        self.transport.connect()
        try:
            self._send(ProtoOAApplicationAuthReq(clientId=self.client_id, clientSecret=self.client_secret))
            accounts = [_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
            account = select_live_pepperstone_account(accounts, account_override=self.config.get("ctid_trader_account_id"))
            aid = int(account["ctidTraderAccountId"]); self.account = aid
            if account_fingerprint(aid) != self.plan["account_fingerprint_sha256"]:
                raise MappingError("LIVE account fingerprint differs from accepted account")
            self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid, accessToken=self.access_token))
            trader = _plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
            if "pepperstone" not in str(trader.get("brokerName", "")).lower():
                raise MappingError("not verifiably Pepperstone")
            light = {int(x["symbolId"]): _plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid, includeArchivedSymbols=False)).symbol}
            query = ProtoOASymbolByIdReq(ctidTraderAccountId=aid); query.symbolId.extend(EXPECTED_SYMBOLS.values())
            full = {int(x.symbolId): _plain(x) for x in self._send(query).symbol}
            start, end = _ms(_utc(self.plan["interval"]["start_utc"])), _ms(_utc(self.plan["interval"]["end_utc"]))
            manifest = {"schema": "mxm.greenfield.session-gap-frontier-wave02-m5-bid-ask-bundle.v1", "status": "CAPTURE_COMPLETE_NON_ECONOMIC", "plan_ref": PLAN_REL, "plan_fields": self.plan["fields"], "resolution": "M5", "series": [], "orders_placed": False, "account_mutation": False, "economic_outcomes_opened": 0, "v2_attempts_consumed": 0}
            for name, sid in EXPECTED_SYMBOLS.items():
                if (
                    sid not in light or sid not in full
                    or light[sid].get("symbolName") != name
                    or light[sid].get("enabled") is False
                    or int(full[sid].get("tradingMode", -1)) != 0
                ):
                    raise MappingError(f"selected symbol mapping mismatch {name}/{sid}")
                rows = align_bid_ask_m5(self._ticks(aid, sid, "BID", start, end), self._ticks(aid, sid, "ASK", start, end), start_utc=self.plan["interval"]["start_utc"], end_utc=self.plan["interval"]["end_utc"], symbol_id=sid, broker_symbol=name)
                path = raw / f"{sid}_{name.replace('.', '_').replace('-', '_')}_M5_BID_ASK.csv"
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=HEADER); writer.writeheader(); writer.writerows(rows)
                manifest["series"].append({"broker_symbol": name, "symbol_id": sid, "file": path.relative_to(self.bundle).as_posix(), "row_count": len(rows), "sha256": _sha(path), "bid_ask_aligned": True, "synthetic_fill": False, "forward_fill": False})
            atomic_write_json(self.bundle / "capture_manifest.json", manifest)
            checks = [f"{_sha(path)}  {path.relative_to(self.bundle).as_posix()}" for path in sorted(self.bundle.rglob("*")) if path.is_file()]
            (self.bundle / "CHECKSUMS.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
            scan_bundle_for_secrets(self.bundle, [self.client_secret, self.access_token])
            with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for path in sorted(self.bundle.rglob("*")):
                    if path.is_file():
                        info = zipfile.ZipInfo(path.relative_to(self.bundle).as_posix(), (1980, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED; archive.writestr(info, path.read_bytes())
            return self.zip_path
        finally:
            self.transport.close()

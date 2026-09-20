"""Android-safe read-only cTrader Stage-B historical margin evidence capture."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict

from .ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
    sha256_bytes,
    sha256_file,
)
from .ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOADealListReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetDynamicLeverageByIDReq,
    ProtoOAMarginCallListReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from .ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from .stage_b_margin_evidence import (
    BUNDLE_SCHEMA,
    DEVELOPMENT_END_MS,
    DEVELOPMENT_START_MS,
    HISTORICAL_MIN_INTERVAL_SECONDS,
    MAX_ROWS,
    OUTPUT_FILENAME,
    TARGET_SYMBOLS,
    TOOL_VERSION,
    TRANSFERABLE_FULL_ROWS_MAX_BYTES,
    assert_transferable_privacy,
    deal_sort_key,
    deterministic_zip_directory,
    exhaust_window,
    initial_windows,
    jsonl_bytes,
    sanitize_deal,
    summarize_observations,
    validate_plan,
)

CURRENT_ONLY = "CURRENT_ONLY_NOT_HISTORICAL_AUTHORITY"


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


class StageBMarginHistoryRunner:
    def __init__(
        self,
        *,
        plan: Mapping[str, Any],
        client_id: str,
        client_secret: str,
        access_token: str,
        config: Mapping[str, Any],
        repo_root: Path | str,
        progress=print,
        transport: StdlibCTraderTransport | None = None,
    ):
        validate_plan(plan)
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.repo_root = Path(repo_root)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(
            LIVE_HOST, LIVE_PORT, response_timeout=60
        )
        self.output_dir = (
            self.repo_root
            / "stage_b_margin_capture_output"
            / "MXM_M6_STAGE_B_MARGIN_HISTORY_EVIDENCE_V1"
        )
        self.raw_local_dir = (
            self.repo_root
            / "stage_b_margin_raw_local"
            / "MXM_M6_STAGE_B_MARGIN_HISTORY_EVIDENCE_V1"
        )
        self.zip_path = self.repo_root / OUTPUT_FILENAME
        self._app_authorized = False
        self._authorized_account_id: int | None = None
        self._last_historical_send: float | None = None
        self._historical_requests = 0

    def _stage(self, text: str) -> None:
        self.progress(text)

    def _transport_request(self, request):
        require_read_only_request(type(request).__name__)
        response = self.transport.request(request, timeout=60)
        if type(response).__name__ == "ProtoOAErrorRes":
            raise CaptureContractError(
                "cTrader API error: "
                + str(getattr(response, "errorCode", "UNKNOWN"))
            )
        return response

    def _restore(self) -> None:
        self.transport.connect()
        if self._app_authorized:
            self._transport_request(
                ProtoOAApplicationAuthReq(
                    clientId=self.client_id,
                    clientSecret=self.client_secret,
                )
            )
        if self._authorized_account_id is not None:
            self._transport_request(
                ProtoOAAccountAuthReq(
                    ctidTraderAccountId=self._authorized_account_id,
                    accessToken=self.access_token,
                )
            )

    def _send(self, request, *, historical: bool = False, retries: int = 3):
        require_read_only_request(type(request).__name__)
        last: Exception | None = None
        for attempt in range(1, retries + 1):
            if historical:
                now = time.monotonic()
                if self._last_historical_send is not None:
                    wait = HISTORICAL_MIN_INTERVAL_SECONDS - (
                        now - self._last_historical_send
                    )
                    if wait > 0:
                        time.sleep(wait)
                self._last_historical_send = time.monotonic()
            try:
                response = self._transport_request(request)
                if historical:
                    self._historical_requests += 1
                return response
            except Exception as exc:
                last = exc
                if attempt >= retries:
                    break
                delay = min(8.0, float(2 ** (attempt - 1)))
                self._stage(
                    f"[RETRY] {type(request).__name__} "
                    f"{attempt}/{retries}; reconnect in {delay:.0f}s"
                )
                time.sleep(delay)
                try:
                    self.transport.close()
                    self._restore()
                except Exception as reconnect_exc:
                    last = reconnect_exc
        raise CaptureContractError(
            f"{type(request).__name__} failed after {retries} attempts: "
            f"{redact_text(str(last))}"
        )

    def run(self) -> Path:
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_local_dir.mkdir(parents=True, exist_ok=True)
        self.zip_path.unlink(missing_ok=True)
        try:
            self._stage("[1/5] Connecting read-only to Pepperstone Europe LIVE")
            self.transport.connect()
            self._workflow()
        except Exception as exc:
            self._stage("[BLOCKED] " + redact_text(str(exc)))
            raise
        finally:
            self.transport.close()
        return self.zip_path

    def _workflow(self) -> None:
        self._send(
            ProtoOAApplicationAuthReq(
                clientId=self.client_id,
                clientSecret=self.client_secret,
            )
        )
        self._app_authorized = True

        accounts_res = self._send(
            ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)
        )
        accounts = [_plain(x) for x in accounts_res.ctidTraderAccount]
        saved_account_id = self.config.get("ctid_trader_account_id")
        try:
            account = select_live_pepperstone_account(
                accounts, account_override=saved_account_id
            )
        except MappingError:
            selector = self.config.get("account_selector")
            if saved_account_id is not None or not callable(selector):
                raise
            selected_id = int(selector(live_account_candidates(accounts)))
            account = select_live_pepperstone_account(
                accounts, account_override=selected_id
            )

        account_id = int(account["ctidTraderAccountId"])
        self._authorized_account_id = account_id
        account_fingerprint_sha256 = account_fingerprint(account_id)

        self._send(
            ProtoOAAccountAuthReq(
                ctidTraderAccountId=account_id,
                accessToken=self.access_token,
            )
        )
        trader_res = self._send(
            ProtoOATraderReq(ctidTraderAccountId=account_id)
        )
        trader = _plain(trader_res.trader)
        broker_name = str(trader.get("brokerName", ""))
        if "pepperstone" not in broker_name.lower() and "pepperstone" not in str(
            account.get("brokerTitleShort", "")
        ).lower():
            raise MappingError("authorized LIVE account is not verifiably Pepperstone")

        selection_path = self.config.get("account_selection_path")
        if selection_path:
            local_selection = Path(selection_path)
            local_selection.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(
                local_selection,
                {
                    "schema": "mxm.greenfield.v2.local-ctrader-account-selection.v1",
                    "environment": "LIVE",
                    "broker": "Pepperstone",
                    "ctid_trader_account_id": account_id,
                    "transferable": False,
                },
            )
            try:
                local_selection.chmod(0o600)
            except OSError:
                pass

        self._stage("[2/5] Verifying frozen US500/NAS100 product identities")
        symbol_diag, leverage_diag = self._capture_current_symbol_and_leverage(
            account_id
        )
        margin_calls = self._capture_current_margin_calls(account_id)
        trader_diag = self._sanitize_trader_metadata(trader)

        current_diag = {
            "schema": "mxm.greenfield.v2.stage-b-current-margin-structural-diagnostics.v1",
            "classification": CURRENT_ONLY,
            "account_fingerprint_sha256": account_fingerprint_sha256,
            "environment": "Pepperstone - Europe LIVE",
            "trader_metadata": trader_diag,
            "symbols": symbol_diag,
            "dynamic_leverage": leverage_diag,
            "margin_calls": margin_calls,
            "historical_authority_claimed": False,
            "approximate_historical_margin_arithmetic_used": False,
        }
        assert_transferable_privacy(current_diag)

        self._stage(
            "[3/5] Capturing DEVELOPMENT historical deals with recursive hasMore bisection"
        )
        rows: list[dict[str, Any]] = []
        request_count = split_count = leaf_count = has_more_count = 0
        windows = initial_windows()
        for index, window in enumerate(windows, 1):
            if index == 1 or index == len(windows) or index % 10 == 0:
                self._stage(
                    f"  window {index}/{len(windows)} | "
                    f"historical requests={self._historical_requests}"
                )
            raw_rows, stats = exhaust_window(
                window,
                lambda leaf: self._fetch_deal_page(account_id, leaf),
            )
            request_count += stats.request_count
            split_count += stats.split_count
            leaf_count += stats.complete_leaf_windows
            has_more_count += stats.has_more_responses
            for raw in raw_rows:
                sanitized = sanitize_deal(raw)
                if sanitized is not None:
                    assert_transferable_privacy(sanitized)
                    rows.append(sanitized)

        rows.sort(key=deal_sort_key)
        summary = summarize_observations(rows)
        self._stage(
            "[4/5] Finalizing privacy-safe evidence and content commitments"
        )
        observations_payload = jsonl_bytes(rows)
        local_raw_path = self.raw_local_dir / "historical_margin_observations.jsonl"
        local_raw_path.write_bytes(observations_payload)
        raw_sha = sha256_file(local_raw_path)

        transferable_mode = "FULL_SANITIZED_TARGET_ROWS"
        transferable_observation_name = "historical_margin_observations.jsonl"
        if len(observations_payload) <= TRANSFERABLE_FULL_ROWS_MAX_BYTES:
            (self.output_dir / transferable_observation_name).write_bytes(
                observations_payload
            )
        else:
            transferable_mode = "COMPACT_MARGIN_OBSERVATIONS_RAW_RETAINED_LOCAL"
            transferable_observation_name = (
                "historical_margin_observations_compact.jsonl"
            )
            compact_rows = [
                {
                    "execution_utc": row["execution_utc"],
                    "execution_timestamp_ms": row["execution_timestamp_ms"],
                    "symbol": row["symbol"],
                    "symbol_id": row["symbol_id"],
                    "volume_cents": row["volume_cents"],
                    "filled_volume_cents": row["filled_volume_cents"],
                    "deal_status": row["deal_status"],
                    "margin_rate": row["margin_rate"],
                    "margin_rate_state": row["margin_rate_state"],
                }
                for row in rows
            ]
            compact_payload = jsonl_bytes(compact_rows)
            (self.output_dir / transferable_observation_name).write_bytes(
                compact_payload
            )

        current_path = self.output_dir / "current_structural_diagnostics.json"
        atomic_write_json(current_path, current_diag)

        summary_doc = {
            "schema": "mxm.greenfield.v2.stage-b-historical-margin-summary.v1",
            "classification": "EVIDENCE_ONLY_NO_STAGE_B_ECONOMICS",
            "development_start_ms": DEVELOPMENT_START_MS,
            "development_end_ms": DEVELOPMENT_END_MS,
            "initial_window_count": len(windows),
            "deal_list_request_count": request_count,
            "recursive_split_count": split_count,
            "complete_leaf_window_count": leaf_count,
            "has_more_response_count": has_more_count,
            "target_sanitized_deal_records": len(rows),
            "per_symbol": summary,
            "current_diagnostics_classification": CURRENT_ONLY,
            "historical_margin_authority_frozen": False,
            "stage_b_execution_authorized": False,
            "stage_b_economics_run": False,
            "protected_evidence_opened": False,
        }
        assert_transferable_privacy(summary_doc)
        summary_path = self.output_dir / "capture_summary.json"
        atomic_write_json(summary_path, summary_doc)

        evidence_files = {
            transferable_observation_name: sha256_file(
                self.output_dir / transferable_observation_name
            ),
            "current_structural_diagnostics.json": sha256_file(current_path),
            "capture_summary.json": sha256_file(summary_path),
        }
        commitments = {
            "schema": "mxm.greenfield.v2.stage-b-margin-content-commitments.v1",
            "transferable_mode": transferable_mode,
            "transferable_files_sha256": evidence_files,
            "full_sanitized_target_rows_local": {
                "sha256": raw_sha,
                "bytes": len(observations_payload),
                "row_count": len(rows),
                "retained_locally": True,
                "deletion_authorized": False,
                "included_in_transferable_bundle": (
                    transferable_mode == "FULL_SANITIZED_TARGET_ROWS"
                ),
            },
        }
        commitments_path = self.output_dir / "content_commitments.json"
        atomic_write_json(commitments_path, commitments)

        manifest = {
            "schema": BUNDLE_SCHEMA,
            "tool_version": TOOL_VERSION,
            "environment": "Pepperstone - Europe LIVE",
            "account_fingerprint_sha256": account_fingerprint_sha256,
            "oauth_scope": "accounts",
            "orders_placed": False,
            "account_mutation_present": False,
            "live_economic_execution": False,
            "stage_b_economics_run": False,
            "stage_b_execution_authorized": False,
            "economic_outcomes_opened": 0,
            "protected_evidence_opened": False,
            "development_interval_ms": {
                "from": DEVELOPMENT_START_MS,
                "to": DEVELOPMENT_END_MS,
            },
            "target_symbols": TARGET_SYMBOLS,
            "historical_requests": request_count,
            "summary": summary,
            "transferable_mode": transferable_mode,
            "content_commitments_sha256": sha256_file(commitments_path),
        }
        assert_transferable_privacy(manifest)
        atomic_write_json(self.output_dir / "manifest.json", manifest)

        scan_bundle_for_secrets(
            self.output_dir,
            [self.client_secret, self.access_token],
        )
        for path in self.output_dir.rglob("*"):
            if path.is_file():
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                assert_transferable_privacy(value)

        self._stage("[5/5] Building deterministic transferable ZIP")
        digest = deterministic_zip_directory(self.output_dir, self.zip_path)
        self._stage(f"[DONE] {self.zip_path.name} SHA256={digest}")

    def _fetch_deal_page(self, account_id: int, window):
        req = ProtoOADealListReq(
            ctidTraderAccountId=account_id,
            fromTimestamp=int(window.from_ms),
            toTimestamp=int(window.to_ms),
            maxRows=MAX_ROWS,
        )
        res = self._send(req, historical=True)
        return [_plain(x) for x in res.deal], bool(res.hasMore)

    def _capture_current_symbol_and_leverage(self, account_id: int):
        symbols_res = self._send(
            ProtoOASymbolsListReq(
                ctidTraderAccountId=account_id,
                includeArchivedSymbols=False,
            )
        )
        light_by_id = {
            int(x.symbolId): _plain(x)
            for x in symbols_res.symbol
            if getattr(x, "symbolId", None) is not None
        }
        req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
        req.symbolId.extend(sorted(TARGET_SYMBOLS.values()))
        res = self._send(req)
        full_by_id = {int(x.symbolId): _plain(x) for x in res.symbol}

        symbol_diag = {}
        leverage_ids = set()
        for expected_name, symbol_id in TARGET_SYMBOLS.items():
            light = light_by_id.get(symbol_id)
            full = full_by_id.get(symbol_id)
            if light is None or full is None:
                raise MappingError(
                    f"{expected_name} symbolId {symbol_id} missing from current LIVE metadata"
                )
            actual_name = str(light.get("symbolName", ""))
            if actual_name != expected_name:
                raise MappingError(
                    f"symbolId {symbol_id} identity drift: expected "
                    f"{expected_name}, got {actual_name!r}"
                )
            if light.get("enabled") is False:
                raise MappingError(f"{expected_name} is currently disabled")
            leverage_id = full.get("leverageId")
            if leverage_id is not None:
                leverage_ids.add(int(leverage_id))
            symbol_diag[expected_name] = {
                "symbol": expected_name,
                "symbol_id": symbol_id,
                "enabled": bool(light.get("enabled", True)),
                "leverage_id": int(leverage_id) if leverage_id is not None else None,
                "min_volume_cents": (
                    int(full["minVolume"])
                    if full.get("minVolume") is not None else None
                ),
                "step_volume_cents": (
                    int(full["stepVolume"])
                    if full.get("stepVolume") is not None else None
                ),
                "max_volume_cents": (
                    int(full["maxVolume"])
                    if full.get("maxVolume") is not None else None
                ),
                "classification": CURRENT_ONLY,
            }

        leverage_diag = {}
        for leverage_id in sorted(leverage_ids):
            leverage_res = self._send(
                ProtoOAGetDynamicLeverageByIDReq(
                    ctidTraderAccountId=account_id,
                    leverageId=leverage_id,
                )
            )
            leverage = _plain(leverage_res.leverage)
            leverage_diag[str(leverage_id)] = {
                "classification": CURRENT_ONLY,
                "leverage_id": int(leverage.get("leverageId", leverage_id)),
                "tiers": leverage.get("tiers", []),
                "historical_authority_claimed": False,
            }
        return symbol_diag, leverage_diag

    def _capture_current_margin_calls(self, account_id: int):
        res = self._send(
            ProtoOAMarginCallListReq(ctidTraderAccountId=account_id)
        )
        return {
            "classification": CURRENT_ONLY,
            "items": [_plain(x) for x in res.marginCall],
            "historical_authority_claimed": False,
        }

    @staticmethod
    def _sanitize_trader_metadata(trader: Mapping[str, Any]) -> dict[str, Any]:
        wanted = (
            "depositAssetId",
            "accessRights",
            "accountType",
            "registrationTimestamp",
            "moneyDigits",
            "leverageInCents",
            "totalMarginCalculationType",
            "maxLeverage",
            "isLimitedRisk",
            "limitedRiskMarginCalculationStrategy",
            "fairStopOut",
            "stopOutStrategy",
        )
        values = {key: trader[key] for key in wanted if key in trader}
        missing = [key for key in wanted if key not in trader]
        return {
            "classification": CURRENT_ONLY,
            "values": values,
            "unavailable_in_packaged_schema_or_response": missing,
            "historical_authority_claimed": False,
        }

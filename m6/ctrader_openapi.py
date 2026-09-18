"""Android-safe cTrader Open API capture runtime.

Uses official cTrader protobuf messages vendored from Spotware OpenApiPy 0.9.2 and a
Python-stdlib TLS/socket transport. It intentionally does not import Twisted, pyOpenSSL,
service_identity, cryptography, or ctrader_open_api.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict

from .broker_product_identity import (
    build_catalog as build_identity_catalog,
    build_current_catalog_artifact,
    format_preflight_matrix,
    relevant_symbol_ids,
    resolve_all_11,
)
from .ctrader_capture import (
    HISTORICAL_TARGET_RPS,
    PROTECTED_FORWARD_START,
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    canonical_json_bytes,
    deterministic_zip,
    discover_symbol_mapping,
    drop_secret_fields,
    ensure_full_symbol_enabled,
    format_broker_product_profiles,
    format_capture_progress,
    format_symbol_mapping_diagnostic,
    gap_diagnostics,
    historical_windows,
    load_resume_state,
    live_account_candidates,
    merge_chunk_rows,
    next_pagination_to_ms,
    normalize_trendbars,
    raw_csv_bytes,
    record_completed_chunk,
    resolve_profiled_broker_product,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
    sha256_bytes,
    build_asset_catalog,
    build_asset_class_catalog,
    build_symbol_category_catalog,
    sha256_file,
    validate_capture_plan,
    validate_transferable_bundle,
    validate_transferable_zip,
    verified_chunk_path,
    write_bundle_checksums,
)
from .ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAAssetClassListReq,
    ProtoOAAssetListReq,
    ProtoOAExpectedMarginReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTrendbarsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolCategoryListReq,
    ProtoOASymbolsForConversionReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from .ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from .ctrader_transport import (
    LIVE_HOST,
    LIVE_PORT,
    StdlibCTraderTransport,
    TransportError,
    runtime_transport_preflight,
)

TOOL_VERSION = "MXM_M6_CTRADER_CAPTURE_ANDROID_STDLIB_V3"
BUNDLE_SCHEMA = "mxm.greenfield.v2.ctrader-capture-bundle.v1"


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


def runtime_sdk_preflight() -> dict[str, Any]:
    """Compatibility alias retained for CI/tests; no external cTrader SDK is imported."""
    report = runtime_transport_preflight()
    report.update({
        "ctrader_open_api_version": "PROTO_MESSAGES_VENDOR_0.9.2",
        "official_generated_messages_source": "spotware/OpenApiPy tag 0.9.2",
        "live_host": LIVE_HOST,
        "live_port": LIVE_PORT,
        "tcp_protocol_heartbeat_available": True,
        "sdk_idle_heartbeat_path_verified": True,
    })
    return report


class OpenApiCaptureRunner:
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
        validate_capture_plan(plan)
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.repo_root = Path(repo_root)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(LIVE_HOST, LIVE_PORT)

        self._last_historical_send: float | None = None
        self._app_authorized = False
        self._authorized_account_id: int | None = None

        self.plan_sha = self.plan["plan_sha256"]
        self.bundle_name = f"MXM_PW02_CTRADER_CAPTURE_{self.plan_sha[:12]}"
        self.bundle_dir = self.repo_root / "capture_output" / self.bundle_name
        self.work_dir = self.repo_root / ".m6_capture_work" / self.bundle_name
        self.resume_path = self.work_dir / "resume.json"

        self._raw_results: dict[str, Any] = {}
        self._mapping: dict[str, Any] = {}
        self._full_symbols: dict[str, Any] = {}
        self._light_symbols: dict[str, Any] = {}
        self._expected_margin: dict[str, Any] = {}
        self._conversion_metadata: dict[str, Any] = {}
        self._conversion_raw_results: dict[str, Any] = {}
        self._account_evidence: dict[str, Any] = {}
        self._assets: list[dict[str, Any]] = []
        self._symbol_categories: list[dict[str, Any]] = []
        self._asset_classes: list[dict[str, Any]] = []
        self._archived_symbols: list[dict[str, Any]] = []
        self._broker_product_preflight: dict[str, Any] = {}
        self._broker_product_catalog: dict[str, Any] = {}

        self._run_started_monotonic = time.monotonic()
        self._historical_started_monotonic: float | None = None
        self._historical_requests_completed = 0
        self._resume_reused_chunks = 0
        self._progress_line_active = False
        self._progress_line_width = 0
        self._last_overall_percent = 0.0

    def _finish_progress_line(self) -> None:
        if self._progress_line_active and self.progress is print:
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._progress_line_active = False
        self._progress_line_width = 0

    def _stage(self, text: str) -> None:
        self._finish_progress_line()
        self.progress(text)

    def _emit_live_progress(
        self,
        *,
        overall_percent: float,
        stage: str,
        instrument: str,
        resolution: str,
        series_percent: float,
        completed_windows: int,
        total_windows: int,
        completed_chunks: int,
        rows_captured: int,
    ) -> None:
        overall = max(self._last_overall_percent, min(99.9, overall_percent))
        self._last_overall_percent = overall
        elapsed = time.monotonic() - self._run_started_monotonic
        if self._historical_started_monotonic is None:
            effective_rps = 0.0
        else:
            hist_elapsed = max(
                1e-9, time.monotonic() - self._historical_started_monotonic
            )
            effective_rps = self._historical_requests_completed / hist_elapsed
        line = format_capture_progress(
            overall_percent=overall,
            stage=stage,
            instrument=instrument,
            resolution=resolution,
            series_percent=series_percent,
            completed_windows=completed_windows,
            total_windows=total_windows,
            completed_chunks=completed_chunks,
            historical_requests_completed=self._historical_requests_completed,
            rows_captured=rows_captured,
            elapsed_seconds=elapsed,
            effective_rps=effective_rps,
            reused_chunks=self._resume_reused_chunks,
            eta_seconds=None,
        )
        if self.progress is print:
            padded = line.ljust(self._progress_line_width)
            sys.stdout.write("\r" + padded)
            sys.stdout.flush()
            self._progress_line_width = max(self._progress_line_width, len(line))
            self._progress_line_active = True
        else:
            self.progress(line)

    def _transport_request(self, request):
        require_read_only_request(type(request).__name__)
        response = self.transport.request(request, timeout=30)
        if type(response).__name__ == "ProtoOAErrorRes":
            raise CaptureContractError(
                f"cTrader API error: {getattr(response, 'errorCode', 'UNKNOWN')}"
            )
        return response

    def _restore_session_after_reconnect(self) -> None:
        self.transport.connect()
        if self._app_authorized:
            response = self._transport_request(
                ProtoOAApplicationAuthReq(
                    clientId=self.client_id,
                    clientSecret=self.client_secret,
                )
            )
            if type(response).__name__ == "ProtoOAErrorRes":
                raise CaptureContractError("cTrader application re-authentication failed")
        if self._authorized_account_id is not None:
            response = self._transport_request(
                ProtoOAAccountAuthReq(
                    ctidTraderAccountId=self._authorized_account_id,
                    accessToken=self.access_token,
                )
            )
            if type(response).__name__ == "ProtoOAErrorRes":
                raise CaptureContractError("cTrader account re-authentication failed")

    def _send(self, request, *, historical: bool = False, retries: int = 3):
        name = type(request).__name__
        require_read_only_request(name)
        last: Exception | None = None

        for attempt in range(1, retries + 1):
            if historical:
                if self._historical_started_monotonic is None:
                    self._historical_started_monotonic = time.monotonic()
                now = time.monotonic()
                if self._last_historical_send is not None:
                    wait = 0.21 - (now - self._last_historical_send)
                    if wait > 0:
                        time.sleep(wait)
                self._last_historical_send = time.monotonic()

            try:
                response = self._transport_request(request)
                if historical:
                    self._historical_requests_completed += 1
                return response
            except Exception as exc:
                last = exc
                if attempt >= retries:
                    break
                backoff = min(8.0, float(2 ** (attempt - 1)))
                self._stage(
                    f"[RETRY] {name} attempt {attempt}/{retries} failed; "
                    f"reconnecting in {backoff:.0f}s"
                )
                time.sleep(backoff)
                try:
                    self.transport.close()
                    self._restore_session_after_reconnect()
                except Exception as reconnect_exc:
                    last = reconnect_exc

        raise CaptureContractError(
            f"{name} failed after {retries} attempts: {redact_text(str(last))}"
        )

    def run(self) -> Path:
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._stage(
            f"[RATE] Historical target {HISTORICAL_TARGET_RPS:.2f} req/s "
            "(0.21 s pacing; official ceiling 5 req/s/connection)."
        )
        try:
            self._stage("[cTrader] Connecting to Pepperstone LIVE endpoint over Python stdlib TLS...")
            self.transport.connect()
            self._stage(
                "[cTrader] LIVE TLS connected; protobuf heartbeat is enabled. "
                "No trading subscriptions are used."
            )
            self._workflow()
        except Exception as exc:
            self._finish_progress_line()
            reason = redact_text(str(exc))
            self.progress("[BLOCKED] " + reason)
            self._write_partial_bundle(reason)
            raise
        finally:
            self.transport.close()
            self._finish_progress_line()

        return self.bundle_dir.parent / f"{self.bundle_name}.zip"

    def _workflow(self) -> None:
        self._stage("[1/5] Authorizing Open API application (LIVE / accounts scope)")
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
        accounts = [_plain(a) for a in accounts_res.ctidTraderAccount]
        saved_account_id = self.config.get("ctid_trader_account_id")
        try:
            account = select_live_pepperstone_account(
                accounts,
                account_override=saved_account_id,
            )
        except MappingError:
            selector = self.config.get("account_selector")
            if saved_account_id is not None or not callable(selector):
                raise
            selected_id = int(selector(live_account_candidates(accounts)))
            account = select_live_pepperstone_account(
                accounts,
                account_override=selected_id,
            )
        account_id = int(account["ctidTraderAccountId"])
        self._authorized_account_id = account_id
        self._account_evidence = {
            "account_fingerprint_sha256": account_fingerprint(account_id),
            "is_live": True,
            "broker_title_short": account.get("brokerTitleShort"),
            "source_environment": "Pepperstone - Europe LIVE",
            "raw_account_id_in_bundle": False,
            "trader_login_in_bundle": False,
        }

        self._send(
            ProtoOAAccountAuthReq(
                ctidTraderAccountId=account_id,
                accessToken=self.access_token,
            )
        )
        trader_res = self._send(ProtoOATraderReq(ctidTraderAccountId=account_id))
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
            atomic_write_json(local_selection, {
                "schema": "mxm.greenfield.v2.local-ctrader-account-selection.v1",
                "environment": "LIVE",
                "broker": "Pepperstone",
                "ctid_trader_account_id": account_id,
                "saved_at_unix": int(time.time()),
                "transferable": False,
            })
            try:
                local_selection.chmod(0o600)
            except OSError:
                pass

        self._account_evidence.update({
            "broker_name": broker_name,
            "deposit_asset_id": trader.get("depositAssetId"),
            "access_rights": trader.get("accessRights"),
            "account_type": trader.get("accountType"),
        })

        assets_res = self._send(
            ProtoOAAssetListReq(ctidTraderAccountId=account_id)
        )
        self._assets = [_plain(a) for a in assets_res.asset]

        categories_res = self._send(
            ProtoOASymbolCategoryListReq(ctidTraderAccountId=account_id)
        )
        self._symbol_categories = [
            _plain(x) for x in categories_res.symbolCategory
        ]

        asset_classes_res = self._send(
            ProtoOAAssetClassListReq(ctidTraderAccountId=account_id)
        )
        self._asset_classes = [
            _plain(x) for x in asset_classes_res.assetClass
        ]

        self._stage("[2/5] Building complete Pepperstone LIVE structural broker-product preflight")
        symbols_res = self._send(
            ProtoOASymbolsListReq(
                ctidTraderAccountId=account_id,
                includeArchivedSymbols=True,
            )
        )
        light = [_plain(s) for s in symbols_res.symbol]
        self._archived_symbols = [
            _plain(s) for s in getattr(symbols_res, "archivedSymbol", [])
        ]
        assets_by_id = build_identity_catalog(
            self._assets, ("assetId", "asset_id", "id")
        )
        categories_by_id = build_identity_catalog(
            self._symbol_categories, ("id", "symbolCategoryId", "symbol_category_id")
        )
        asset_classes_by_id = build_identity_catalog(
            self._asset_classes, ("id", "assetClassId", "asset_class_id")
        )

        # Structural relevance is evaluated over the complete CURRENT light-symbol
        # universe. Historical prices are not requested here and broker availability
        # cannot change PRIMARY_WAVE_02 membership.
        candidate_ids = relevant_symbol_ids(
            light,
            assets_by_id=assets_by_id,
            categories_by_id=categories_by_id,
            asset_classes_by_id=asset_classes_by_id,
        )
        full_plain_by_id: dict[int, dict[str, Any]] = {}
        sorted_ids = sorted(candidate_ids)
        for offset in range(0, len(sorted_ids), 64):
            batch = sorted_ids[offset : offset + 64]
            req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
            req.symbolId.extend(batch)
            res = self._send(req)
            for symbol in res.symbol:
                full_plain_by_id[int(symbol.symbolId)] = _plain(symbol)

        preflight = resolve_all_11(
            light,
            full_plain_by_id,
            archived_symbols=self._archived_symbols,
            assets_by_id=assets_by_id,
            categories_by_id=categories_by_id,
            asset_classes_by_id=asset_classes_by_id,
        )
        self._broker_product_preflight = preflight
        self._broker_product_catalog = build_current_catalog_artifact(
            account_environment="Pepperstone - Europe LIVE",
            broker="Pepperstone",
            account_fingerprint_sha256=self._account_evidence.get(
                "account_fingerprint_sha256"
            ),
            assets=self._assets,
            asset_classes=self._asset_classes,
            symbol_categories=self._symbol_categories,
            light_symbols=light,
            archived_symbols=self._archived_symbols,
            full_by_id=full_plain_by_id,
            preflight=preflight,
        )

        # Always print all 11 rows. One failure blocks auxiliary and historical capture.
        for line in format_preflight_matrix(preflight):
            self._stage(line)

        raw_by_canonical = {
            item["canonical_instrument"]: item
            for item in self.plan["unique_raw_capture_tasks"]
        }
        by_light_id = {
            int(item["symbolId"]): item
            for item in light
            if item.get("symbolId") is not None
        }
        for row in preflight["matrix"]:
            canonical = row["canonical"]
            bridge = preflight["bridge"][canonical]
            selected = bridge.get("selected_current_product")
            if row["status"] != "PASS" or not selected:
                continue
            symbol_id = int(selected["symbol_id"])
            mapped = by_light_id.get(symbol_id)
            full_plain = full_plain_by_id.get(symbol_id)
            if mapped is None or full_plain is None:
                # This is a structural inconsistency after preflight and must fail closed.
                bridge["status"] = "BLOCKED"
                bridge["confidence"] = "UNRESOLVED"
                row["status"] = "BLOCKED"
                row["mapping_evidence"] = "selected product disappeared after structural preflight"
                continue
            ensure_full_symbol_enabled(full_plain)
            self._light_symbols[canonical] = mapped
            self._full_symbols[canonical] = full_plain
            raw = raw_by_canonical[canonical]
            evidence = {
                "canonical_instrument": canonical,
                "broker_symbol": mapped.get("symbolName"),
                "description": mapped.get("description"),
                "symbol_id": symbol_id,
                "product_family": selected.get("product_family"),
                "enabled": bool(mapped.get("enabled")),
                "base_asset_id": mapped.get("baseAssetId"),
                "quote_asset_id": mapped.get("quoteAssetId"),
                "symbol_category_id": mapped.get("symbolCategoryId"),
                "category_name": selected.get("category_name"),
                "asset_class_id": selected.get("asset_class_id"),
                "asset_class_name": selected.get("asset_class_name"),
                "trading_mode": selected.get("trading_mode"),
                "mapping_source": bridge.get("selection_basis"),
                "mapping_policy": bridge.get("frozen_mapping_policy"),
                "supporting_official_public_source_ids": bridge.get(
                    "supporting_official_public_source_ids"
                ),
                "excluded_materially_different_products": bridge.get(
                    "excluded_materially_different_products"
                ),
                "selected_product_profile": selected,
                "raw_capture_id": raw["raw_capture_id"],
                "raw_identity_sha256": raw["raw_identity_sha256"],
                "resolution": raw["resolution"],
                "current_mapping_is_not_historical_metadata": True,
            }
            evidence["mapping_evidence_sha256"] = sha256_bytes(
                canonical_json_bytes(evidence)
            )
            self._mapping[canonical] = evidence

        passed_after_binding = sum(
            1 for row in preflight["matrix"] if row["status"] == "PASS"
        )
        if passed_after_binding != len(preflight["matrix"]):
            raise MappingError(
                f"BROKER PRODUCT PREFLIGHT: {passed_after_binding}/"
                f"{len(preflight['matrix'])} PASS — CAPTURE NOT STARTED"
            )
        if len(self._mapping) != 11:
            raise MappingError(
                f"BROKER PRODUCT PREFLIGHT: {len(self._mapping)}/11 PASS — CAPTURE NOT STARTED"
            )
        self._stage("BROKER PRODUCT PREFLIGHT: 11/11 PASS — historical capture gate opened")

        self._stage("[3/5] Capturing read-only structural / auxiliary evidence")
        self._capture_expected_margin(account_id)
        self._capture_conversion_metadata(account_id)

        self._stage("[4/5] Capturing 11 unique DEVELOPMENT raw market series")
        total = len(self.plan["unique_raw_capture_tasks"])
        for index, raw in enumerate(self.plan["unique_raw_capture_tasks"], 1):
            self._stage(
                f"  [{index}/{total}] "
                f"{raw['canonical_instrument']} {raw['resolution']}"
            )
            self._capture_raw_series(account_id, raw)

        self._stage("[5/5] Finalizing deterministic evidence bundle")
        self._write_final_bundle()
        self._stage(
            f"[DONE] {self.bundle_dir.parent / (self.bundle_name + '.zip')}"
        )

    def _capture_expected_margin(self, account_id: int) -> None:
        for canonical, mapped in self._mapping.items():
            full = self._full_symbols[canonical]
            min_volume = full.get("minVolume")
            if min_volume is None:
                self._expected_margin[canonical] = {
                    "state": "UNRESOLVED_NO_MIN_VOLUME_METADATA",
                    "eur200_feasibility": "UNRESOLVED",
                    "approximate_formula_used": False,
                    "order_placed": False,
                    "economic_conclusion": "NOT_EVALUATED",
                }
                continue
            try:
                req = ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account_id,
                    symbolId=int(mapped["symbol_id"]),
                )
                req.volume.append(int(min_volume))
                res = self._send(req)
                self._expected_margin[canonical] = {
                    "state": "CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT",
                    "requested_executable_volumes_cents": [int(min_volume)],
                    "volume_cents": int(min_volume),
                    "margin": [_plain(x) for x in res.margin],
                    "money_digits": getattr(res, "moneyDigits", None),
                    "eur200_feasibility": "UNRESOLVED_MINIMUM_EXECUTABLE_VOLUME_MARGIN_ONLY",
                    "eur200_feasibility_reason":
                        "The broker-native minimum-volume margin is current structural evidence. "
                        "Exact frozen Stage-B EUR200 feasibility depends on the causal executable "
                        "quantity at the applicable entry price/conversion state and is not inferred "
                        "with approximate leverage arithmetic.",
                    "approximate_formula_used": False,
                    "order_placed": False,
                    "economic_conclusion": "NOT_EVALUATED",
                }
            except Exception as exc:
                self._expected_margin[canonical] = {
                    "state": "UNRESOLVED_READ_ONLY_SCOPE_OR_API_REJECTION",
                    "reason": redact_text(str(exc)),
                    "eur200_feasibility": "UNRESOLVED",
                    "approximate_formula_used": False,
                    "scope_escalated": False,
                    "order_placed": False,
                    "economic_conclusion": "NOT_EVALUATED",
                }

    def _capture_conversion_metadata(self, account_id: int) -> None:
        assets_by_name = {
            str(a.get("name", "")).upper(): int(a["assetId"])
            for a in self._assets
            if a.get("name") and a.get("assetId") is not None
        }
        eur_id = assets_by_name.get("EUR")
        if eur_id is None:
            self._conversion_metadata["GLOBAL"] = {
                "state": "UNRESOLVED_EUR_ASSET_NOT_AVAILABLE",
                "historical_causal_conversion_rates": "UNRESOLVED",
            }
            return

        for source_name in ("USD", "JPY"):
            source_id = assets_by_name.get(source_name)
            if source_id is None:
                self._conversion_metadata[source_name] = {
                    "state": f"UNRESOLVED_{source_name}_ASSET_NOT_AVAILABLE",
                    "historical_causal_conversion_rates": "UNRESOLVED",
                }
                continue
            try:
                req = ProtoOASymbolsForConversionReq(
                    ctidTraderAccountId=account_id,
                    firstAssetId=source_id,
                    lastAssetId=eur_id,
                )
                res = self._send(req)
                chain = [_plain(x) for x in res.symbol]
                if not chain:
                    raise CaptureContractError(
                        f"{source_name}->EUR conversion chain is empty"
                    )
                ids = [int(x["symbolId"]) for x in chain]
                full_req = ProtoOASymbolByIdReq(
                    ctidTraderAccountId=account_id
                )
                full_req.symbolId.extend(ids)
                full_res = self._send(full_req)
                full_by_id = {
                    int(x.symbolId): _plain(x) for x in full_res.symbol
                }
                raw_refs = []
                for light in chain:
                    sid = int(light["symbolId"])
                    if sid not in full_by_id:
                        raise CaptureContractError(
                            f"conversion symbol metadata missing for {sid}"
                        )
                    ensure_full_symbol_enabled(full_by_id[sid])
                    if str(sid) not in self._conversion_raw_results:
                        result = self._capture_aux_conversion_series(
                            account_id=account_id,
                            symbol_id=sid,
                            broker_symbol=light.get("symbolName", str(sid)),
                            digits=int(full_by_id[sid].get("digits", 5)),
                        )
                        self._conversion_raw_results[str(sid)] = result
                    raw_refs.append(
                        self._conversion_raw_results[str(sid)]["aux_raw_id"]
                    )
                self._conversion_metadata[source_name] = {
                    "state": "CURRENT_CHAIN_AND_CONSTITUENT_DEVELOPMENT_BARS_CAPTURED",
                    "first_asset": source_name,
                    "first_asset_id": source_id,
                    "last_asset": "EUR",
                    "last_asset_id": eur_id,
                    "symbols": chain,
                    "auxiliary_raw_refs": raw_refs,
                    "historical_chain_point_in_time_validity":
                        "UNRESOLVED_CURRENT_CHAIN_NOT_PROVEN_HISTORICALLY_EFFECTIVE",
                    "historical_causal_conversion_rates":
                        "RAW_INPUTS_CAPTURED_BUT_NOT_PROMOTED_TO_VERIFIED_UNTIL_CHAIN_VALIDITY_IS_PROVEN",
                }
            except Exception as exc:
                self._conversion_metadata[source_name] = {
                    "state": "UNRESOLVED",
                    "reason": redact_text(str(exc)),
                    "historical_causal_conversion_rates": "UNRESOLVED",
                }

    def _capture_aux_conversion_series(
        self,
        *,
        account_id: int,
        symbol_id: int,
        broker_symbol: str,
        digits: int,
    ):
        safe_name = "".join(
            ch for ch in str(broker_symbol).upper() if ch.isalnum()
        ) or str(symbol_id)
        aux_id = f"PW02-AUX-CONV-{safe_name}-M15-S{symbol_id}"
        result = self._capture_series(
            account_id=account_id,
            symbol_id=symbol_id,
            resolution="M15",
            digits=digits,
            capture_id=aux_id,
            output_subdir="auxiliary/conversion_raw",
        )
        result.update({
            "aux_raw_id": aux_id,
            "broker_symbol": broker_symbol,
            "symbol_id": int(symbol_id),
            "classification": "DEVELOPMENT",
            "historical_chain_point_in_time_validity": "UNRESOLVED",
        })
        return result

    def _capture_raw_series(
        self,
        account_id: int,
        raw: Mapping[str, Any],
    ) -> None:
        canonical = raw["canonical_instrument"]
        result = self._capture_series(
            account_id=account_id,
            symbol_id=int(self._mapping[canonical]["symbol_id"]),
            resolution=raw["resolution"],
            digits=int(self._full_symbols[canonical].get("digits", 5)),
            capture_id=raw["raw_capture_id"],
            output_subdir="raw",
        )
        result.update({
            "raw_capture_id": raw["raw_capture_id"],
            "canonical_instrument": canonical,
            "source_environment":
                self.plan["raw_capture_defaults"]["source_environment"],
        })
        self._raw_results[raw["raw_capture_id"]] = result

    def _capture_series(
        self,
        *,
        account_id: int,
        symbol_id: int,
        resolution: str,
        digits: int,
        capture_id: str,
        output_subdir: str,
    ):
        defaults = self.plan["raw_capture_defaults"]
        interval = defaults["interval"]
        state = load_resume_state(self.resume_path, self.plan_sha)
        series_work = self.work_dir / capture_id
        series_work.mkdir(parents=True, exist_ok=True)
        windows = historical_windows(
            interval["start_utc"],
            interval["end_utc"],
            resolution,
        )
        total_windows = len(windows)
        chunk_paths: list[Path] = []
        completed_chunks = 0
        rows_so_far = 0

        if output_subdir == "raw":
            primary = self.plan["unique_raw_capture_tasks"]
            series_index = next(
                i
                for i, item in enumerate(primary)
                if item["raw_capture_id"] == capture_id
            )
            series_total = len(primary)
            stage_label = "PRIMARY"
            display_name = next(
                item["canonical_instrument"]
                for item in primary
                if item["raw_capture_id"] == capture_id
            )
            overall_base, overall_span = 40.0, 57.0
        else:
            series_index, series_total = 0, 1
            stage_label = "AUX-CONVERSION"
            display_name = capture_id.replace(
                "PW02-AUX-CONV-", ""
            ).split("-M15-", 1)[0]
            overall_base = max(23.0, self._last_overall_percent)
            overall_span = max(0.0, 40.0 - overall_base)

        for wi, (from_ms, window_to_ms) in enumerate(windows):
            page = 0
            page_to_ms = window_to_ms
            window_completed = False

            while page_to_ms >= from_ms:
                key = (
                    f"{capture_id}:{wi}:{page}:{from_ms}:{page_to_ms}"
                )
                resumed = verified_chunk_path(state, key)
                if resumed is not None:
                    chunk_paths.append(resumed)
                    item = state["chunks"][key]
                    completed_chunks += 1
                    rows_so_far += int(item.get("row_count", 0))
                    self._resume_reused_chunks += 1
                    has_more = bool(item.get("has_more"))
                    next_to = item.get("next_to_ms")
                    if has_more and next_to is not None:
                        page_to_ms = int(next_to)
                        page += 1
                    else:
                        window_completed = True

                    series_fraction = (
                        wi + (1.0 if window_completed else 0.0)
                    ) / max(1, total_windows)
                    if output_subdir == "raw":
                        overall = overall_base + overall_span * (
                            (series_index + series_fraction) / series_total
                        )
                    else:
                        overall = (
                            overall_base + overall_span * series_fraction
                        )
                    self._emit_live_progress(
                        overall_percent=overall,
                        stage=stage_label,
                        instrument=display_name,
                        resolution=resolution,
                        series_percent=series_fraction * 100.0,
                        completed_windows=wi + (
                            1 if window_completed else 0
                        ),
                        total_windows=total_windows,
                        completed_chunks=completed_chunks,
                        rows_captured=rows_so_far,
                    )
                    if window_completed:
                        break
                    continue

                req = ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account_id,
                    symbolId=int(symbol_id),
                    period=ProtoOATrendbarPeriod.Value(resolution),
                    fromTimestamp=from_ms,
                    toTimestamp=page_to_ms,
                    count=5000,
                )
                res = self._send(req, historical=True)
                trendbars = [_plain(x) for x in res.trendbar]
                rows = normalize_trendbars(
                    trendbars,
                    resolution=resolution,
                    digits=digits,
                    requested_start_utc=interval["start_utc"],
                    requested_end_utc=interval["end_utc"],
                    protected_start_utc=PROTECTED_FORWARD_START,
                )

                chunk_path = (
                    series_work / f"w{wi:04d}_p{page:04d}.csv"
                )
                chunk_path.write_bytes(raw_csv_bytes(rows))
                record_completed_chunk(
                    state,
                    chunk_key=key,
                    path=chunk_path,
                    raw_capture_id=capture_id,
                    request_from_ms=from_ms,
                    request_to_ms=page_to_ms,
                    page=page,
                    row_count=len(rows),
                )

                has_more = bool(getattr(res, "hasMore", False))
                next_to = (
                    next_pagination_to_ms(trendbars, from_ms)
                    if has_more
                    else None
                )
                state["chunks"][key]["has_more"] = has_more
                state["chunks"][key]["next_to_ms"] = next_to
                atomic_write_json(self.resume_path, state)

                chunk_paths.append(chunk_path)
                completed_chunks += 1
                rows_so_far += len(rows)
                window_completed = not has_more
                series_fraction = (
                    wi + (1.0 if window_completed else 0.0)
                ) / max(1, total_windows)

                if output_subdir == "raw":
                    overall = overall_base + overall_span * (
                        (series_index + series_fraction) / series_total
                    )
                else:
                    overall = overall_base + overall_span * series_fraction

                self._emit_live_progress(
                    overall_percent=overall,
                    stage=stage_label,
                    instrument=display_name,
                    resolution=resolution,
                    series_percent=series_fraction * 100.0,
                    completed_windows=wi + (
                        1 if window_completed else 0
                    ),
                    total_windows=total_windows,
                    completed_chunks=completed_chunks,
                    rows_captured=rows_so_far,
                )

                if not has_more:
                    break
                if next_to is None or next_to >= page_to_ms:
                    raise CaptureContractError(
                        f"{capture_id}: invalid historical pagination"
                    )
                page_to_ms = next_to
                page += 1

        rows = merge_chunk_rows(chunk_paths)
        out_dir = self.bundle_dir / output_subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / f"{capture_id}.csv"
        final_path.write_bytes(raw_csv_bytes(rows))
        return {
            "resolution": resolution,
            "requested_interval": interval,
            "row_count": len(rows),
            "first_timestamp_utc": (
                rows[0]["time_utc"] if rows else None
            ),
            "last_timestamp_utc": (
                rows[-1]["time_utc"] if rows else None
            ),
            "sha256": sha256_file(final_path),
            "file": final_path.relative_to(
                self.bundle_dir
            ).as_posix(),
            "gap_diagnostics": gap_diagnostics(rows, resolution),
            "completed_bars_only": True,
            "development_completion_cutoff_enforced": True,
            "bar_completion_must_be_lte_requested_end": True,
            "bar_completion_must_be_lt_protected_start": True,
            "protected_forward_rows_included": False,
            "resampling_performed": False,
            "synthetic_fill_performed": False,
            "forward_fill_performed": False,
        }

    def _auxiliary_status(self) -> dict[str, Any]:
        return {
            "current_symbol_metadata": {
                "state": "CAPTURED_CURRENT_SNAPSHOT_NOT_VERIFIED_HISTORY",
                "warning":
                    "Current commission/swap/session metadata is not historical cost evidence.",
            },
            "historical_financing_swap": {
                "state": "UNRESOLVED",
                "reason":
                    "No historical financing schedule is promoted from current Open API symbol metadata.",
            },
            "point_in_time_corporate_actions": {
                "state": "UNRESOLVED",
                "reason":
                    "No point-in-time corporate-action history was obtained by this Open API capture client.",
            },
            "wti_historical_contract_roll_semantics": {
                "state": "UNRESOLVED",
                "reason":
                    "Trendbars/current symbol metadata do not prove historical continuous-CFD roll construction.",
            },
            "historical_session_calendar_versions": {
                "state": "UNRESOLVED",
                "reason":
                    "Current schedule/holiday metadata is not relabelled as historical schedule truth.",
            },
            "expected_margin": self._expected_margin,
            "conversion_chain_metadata": self._conversion_metadata,
            "conversion_raw_development_series":
                self._conversion_raw_results,
        }

    def _common_evidence_files(self) -> None:
        evidence = self.bundle_dir / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            evidence / "account.json",
            self._account_evidence,
        )
        atomic_write_json(
            evidence / "broker_mapping.json",
            self._mapping,
        )
        atomic_write_json(
            evidence / "broker_product_catalog_current.json",
            drop_secret_fields(self._broker_product_catalog),
        )
        source_path = self.repo_root / "evidence" / "BROKER_PRODUCT_IDENTITY_SOURCES_V1.json"
        if not source_path.is_file():
            raise CaptureContractError(
                "broker product public-source provenance artifact missing from runtime package"
            )
        atomic_write_json(
            evidence / "BROKER_PRODUCT_IDENTITY_SOURCES_V1.json",
            json.loads(source_path.read_text(encoding="utf-8")),
        )
        bridge_policy_path = self.repo_root / "evidence" / "BROKER_PRODUCT_IDENTITY_BRIDGE_V1.json"
        if not bridge_policy_path.is_file():
            raise CaptureContractError(
                "broker product bridge policy artifact missing from runtime package"
            )
        atomic_write_json(
            evidence / "BROKER_PRODUCT_IDENTITY_BRIDGE_V1.json",
            json.loads(bridge_policy_path.read_text(encoding="utf-8")),
        )
        atomic_write_json(
            evidence / "symbol_metadata_current.json",
            drop_secret_fields(self._full_symbols),
        )
        atomic_write_json(
            evidence / "assets.json",
            self._assets,
        )
        atomic_write_json(
            evidence / "symbol_categories.json",
            self._symbol_categories,
        )
        atomic_write_json(
            evidence / "asset_classes.json",
            self._asset_classes,
        )
        atomic_write_json(
            evidence / "expected_margin.json",
            self._expected_margin,
        )
        atomic_write_json(
            evidence / "auxiliary_status.json",
            self._auxiliary_status(),
        )
        atomic_write_json(
            evidence / "candidate_bindings.json",
            self.plan["candidate_dataset_bindings"],
        )
        atomic_write_json(
            evidence / "gap_diagnostics.json",
            {
                "primary_raw": {
                    key: value.get("gap_diagnostics")
                    for key, value in sorted(
                        self._raw_results.items()
                    )
                },
                "auxiliary_conversion_raw": {
                    key: value.get("gap_diagnostics")
                    for key, value in sorted(
                        self._conversion_raw_results.items()
                    )
                },
                "gaps_are_reported_not_filled": True,
            },
        )

    def _write_final_bundle(self) -> None:
        self._common_evidence_files()
        provenance = {
            "schema": BUNDLE_SCHEMA,
            "tool_version": TOOL_VERSION,
            "active_plan":
                "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json",
            "plan_sha256": self.plan_sha,
            "source_environment": "Pepperstone - Europe LIVE",
            "transport": "PYTHON_STDLIB_TLS_SOCKET",
            "protobuf_messages_source":
                "packaged spotware/OpenApiPy tag 0.9.2 generated messages; "
                "required read-only message compatibility checked 2026-09-18 "
                "against current spotware/openapi-proto-messages",
            "oauth_scope": "accounts",
            "read_only": True,
            "orders_sent": 0,
            "account_mutations_sent": 0,
            "economic_evaluation_performed": False,
            "protected_evidence_opened": False,
            "development_classification_basis":
                "HISTORICAL_TIMESTAMP_NOT_DOWNLOAD_DATE",
            "protected_forward_start": PROTECTED_FORWARD_START,
            "unique_raw_capture_count": len(self._raw_results),
            "candidate_binding_count":
                len(self.plan["candidate_dataset_bindings"]),
            "raw_series": self._raw_results,
            "candidate_dataset_bindings":
                self.plan["candidate_dataset_bindings"],
            "secrets_in_bundle": False,
        }
        atomic_write_json(
            self.bundle_dir / "provenance_manifest.json",
            provenance,
        )
        (self.bundle_dir / "bundle_manifest.json").unlink(
            missing_ok=True
        )
        (self.bundle_dir / "CHECKSUMS.sha256").unlink(
            missing_ok=True
        )
        checksums = write_bundle_checksums(self.bundle_dir)
        atomic_write_json(
            self.bundle_dir / "bundle_manifest.json",
            {
                "schema": BUNDLE_SCHEMA,
                "plan_sha256": self.plan_sha,
                "checksums": checksums,
                "return_this_zip_to_chatgpt":
                    f"{self.bundle_name}.zip",
            },
        )
        write_bundle_checksums(self.bundle_dir)
        scan_bundle_for_secrets(
            self.bundle_dir,
            [self.client_secret, self.access_token],
        )
        zip_path = self.bundle_dir.parent / f"{self.bundle_name}.zip"
        deterministic_zip(self.bundle_dir, zip_path)
        validate_transferable_bundle(self.bundle_dir)
        validate_transferable_zip(zip_path)

    def _write_partial_bundle(self, reason: str) -> None:
        try:
            self._common_evidence_files()
            atomic_write_json(
                self.bundle_dir / "BLOCKED.json",
                {
                    "schema": BUNDLE_SCHEMA,
                    "state": "BLOCKED",
                    "reason": reason,
                    "economic_evaluation_performed": False,
                    "orders_sent": 0,
                    "account_mutations_sent": 0,
                    "protected_evidence_opened": False,
                },
            )
            write_bundle_checksums(self.bundle_dir)
            scan_bundle_for_secrets(
                self.bundle_dir,
                [self.client_secret, self.access_token],
            )
            deterministic_zip(
                self.bundle_dir,
                self.bundle_dir.parent / f"{self.bundle_name}.zip",
            )
        except Exception:
            pass

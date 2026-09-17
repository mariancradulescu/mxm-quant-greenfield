"""Official cTrader Open API runtime adapter for the M6 DEVELOPMENT capture.

Secrets remain local/in memory. Every outbound protobuf request passes the explicit
read-only allowlist in m6.ctrader_capture; this module contains no order request class.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict
from twisted.internet import defer, reactor, task
from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAAssetListReq,
    ProtoOAExpectedMarginReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTrendbarsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsForConversionReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod

from .ctrader_capture import (
    CaptureContractError,
    MappingError,
    PROTECTED_FORWARD_START,
    account_fingerprint,
    atomic_write_json,
    canonical_json_bytes,
    deterministic_zip,
    drop_secret_fields,
    ensure_full_symbol_enabled,
    gap_diagnostics,
    historical_windows,
    merge_chunk_rows,
    next_pagination_to_ms,
    normalize_trendbars,
    raw_csv_bytes,
    record_completed_chunk,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
    sha256_bytes,
    sha256_file,
    validate_capture_plan,
    verified_chunk_path,
    write_bundle_checksums,
)

TOOL_VERSION = "MXM_M6_CTRADER_CAPTURE_V1"
BUNDLE_SCHEMA = "mxm.greenfield.v2.ctrader-capture-bundle.v1"


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(message, preserving_proto_field_name=False, use_integers_for_enums=True)


class OpenApiCaptureRunner:
    def __init__(self, *, plan: Mapping[str, Any], client_id: str, client_secret: str,
                 access_token: str, config: Mapping[str, Any], repo_root: Path | str,
                 progress=print):
        validate_capture_plan(plan)
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.repo_root = Path(repo_root)
        self.progress = progress
        # Official non-historical limit is higher; use 45/s generally and independently
        # pace every historical request below the official 5/s historical limit.
        self.client = Client(EndPoints.PROTOBUF_LIVE_HOST, EndPoints.PROTOBUF_PORT,
                             TcpProtocol, numberOfMessagesToSendPerSecond=45)
        self._workflow_started = False
        self._last_historical_send: float | None = None
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
        self._failure: Exception | None = None

    def run(self) -> Path:
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.client.setConnectedCallback(self._connected)
        self.client.setDisconnectedCallback(self._disconnected)
        self.client.startService()
        reactor.run()
        if self._failure:
            raise self._failure
        return self.bundle_dir.parent / f"{self.bundle_name}.zip"

    def _connected(self, client):
        if self._workflow_started:
            return
        self._workflow_started = True
        d = self._workflow()
        d.addCallbacks(self._done, self._failed)

    def _disconnected(self, client, reason):
        self.progress("[cTrader] connection interrupted; reconnect/retry remains read-only.")

    def _done(self, result):
        self.client.stopService()
        if reactor.running:
            reactor.stop()
        return result

    def _failed(self, failure):
        self._failure = failure.value if hasattr(failure, "value") else RuntimeError(str(failure))
        self.progress("[BLOCKED] " + redact_text(str(self._failure)))
        try:
            self._write_partial_bundle(redact_text(str(self._failure)))
        finally:
            self.client.stopService()
            if reactor.running:
                reactor.stop()
        return failure

    @defer.inlineCallbacks
    def _send(self, request, *, historical: bool = False, retries: int = 3):
        name = type(request).__name__
        require_read_only_request(name)
        last = None
        for attempt in range(1, retries + 1):
            if historical:
                now = reactor.seconds()
                if self._last_historical_send is not None:
                    wait = 0.21 - (now - self._last_historical_send)
                    if wait > 0:
                        yield task.deferLater(reactor, wait, lambda: None)
                self._last_historical_send = reactor.seconds()
            try:
                envelope = yield self.client.send(request, responseTimeoutInSeconds=30)
                response = Protobuf.extract(envelope)
                if type(response).__name__ == "ProtoOAErrorRes":
                    raise CaptureContractError(
                        f"cTrader API error: {getattr(response, 'errorCode', 'UNKNOWN')}"
                    )
                return response
            except Exception as exc:
                last = exc
                if attempt >= retries:
                    break
                yield task.deferLater(reactor, min(8, 2 ** (attempt - 1)), lambda: None)
        raise CaptureContractError(
            f"{name} failed after {retries} attempts: {redact_text(str(last))}"
        )

    @defer.inlineCallbacks
    def _workflow(self):
        self.progress("[1/5] Authorizing Open API application (LIVE / accounts scope)")
        yield self._send(ProtoOAApplicationAuthReq(
            clientId=self.client_id, clientSecret=self.client_secret
        ))
        accounts_res = yield self._send(
            ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)
        )
        accounts = [_plain(a) for a in accounts_res.ctidTraderAccount]
        account = select_live_pepperstone_account(
            accounts, account_override=self.config.get("ctid_trader_account_id")
        )
        account_id = int(account["ctidTraderAccountId"])
        self._account_evidence = {
            "account_fingerprint_sha256": account_fingerprint(account_id),
            "is_live": True,
            "broker_title_short": account.get("brokerTitleShort"),
            "source_environment": "Pepperstone - Europe LIVE",
            "raw_account_id_in_bundle": False,
            "trader_login_in_bundle": False,
        }
        yield self._send(ProtoOAAccountAuthReq(
            ctidTraderAccountId=account_id, accessToken=self.access_token
        ))
        trader_res = yield self._send(ProtoOATraderReq(ctidTraderAccountId=account_id))
        trader = _plain(trader_res.trader)
        broker_name = str(trader.get("brokerName", ""))
        if "pepperstone" not in broker_name.lower() and "pepperstone" not in str(
            account.get("brokerTitleShort", "")
        ).lower():
            raise MappingError("authorized LIVE account is not verifiably Pepperstone")
        self._account_evidence.update({
            "broker_name": broker_name,
            "deposit_asset_id": trader.get("depositAssetId"),
            "access_rights": trader.get("accessRights"),
            "account_type": trader.get("accountType"),
        })
        assets_res = yield self._send(ProtoOAAssetListReq(ctidTraderAccountId=account_id))
        self._assets = [_plain(a) for a in assets_res.asset]

        self.progress("[2/5] Resolving exact ENABLED Pepperstone symbols")
        symbols_res = yield self._send(ProtoOASymbolsListReq(
            ctidTraderAccountId=account_id, includeArchivedSymbols=False
        ))
        light = [_plain(s) for s in symbols_res.symbol]
        overrides = self.config.get("symbol_overrides") or {}
        from .ctrader_capture import resolve_symbol_mapping
        for raw in self.plan["unique_raw_capture_tasks"]:
            canonical = raw["canonical_instrument"]
            mapped = resolve_symbol_mapping(canonical, light, exact_override=overrides.get(canonical))
            symbol_id = int(mapped["symbolId"])
            self._light_symbols[canonical] = mapped
            evidence = {
                "canonical_instrument": canonical,
                "broker_symbol": mapped.get("symbolName"),
                "symbol_id": symbol_id,
                "enabled": bool(mapped.get("enabled")),
                "raw_capture_id": raw["raw_capture_id"],
                "raw_identity_sha256": raw["raw_identity_sha256"],
                "resolution": raw["resolution"],
            }
            evidence["mapping_evidence_sha256"] = sha256_bytes(canonical_json_bytes(evidence))
            self._mapping[canonical] = evidence
        full_req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
        full_req.symbolId.extend([int(v["symbol_id"]) for v in self._mapping.values()])
        full_res = yield self._send(full_req)
        by_id = {int(s.symbolId): s for s in full_res.symbol}
        for canonical, mapped in self._mapping.items():
            sid = int(mapped["symbol_id"])
            if sid not in by_id:
                raise MappingError(f"{canonical}: full symbol metadata missing")
            plain = _plain(by_id[sid])
            ensure_full_symbol_enabled(plain)
            self._full_symbols[canonical] = plain

        self.progress("[3/5] Capturing read-only structural / auxiliary evidence")
        yield self._capture_expected_margin(account_id)
        yield self._capture_conversion_metadata(account_id)

        self.progress("[4/5] Capturing 11 unique DEVELOPMENT raw market series")
        total = len(self.plan["unique_raw_capture_tasks"])
        for index, raw in enumerate(self.plan["unique_raw_capture_tasks"], 1):
            self.progress(f"  [{index}/{total}] {raw['canonical_instrument']} {raw['resolution']}")
            yield self._capture_raw_series(account_id, raw)

        self.progress("[5/5] Finalizing deterministic evidence bundle")
        self._write_final_bundle()
        self.progress(f"[DONE] {self.bundle_dir.parent / (self.bundle_name + '.zip')}")

    @defer.inlineCallbacks
    def _capture_expected_margin(self, account_id: int):
        for canonical, mapped in self._mapping.items():
            full = self._full_symbols[canonical]
            min_volume = full.get("minVolume")
            if min_volume is None:
                self._expected_margin[canonical] = {
                    "state": "UNRESOLVED_NO_MIN_VOLUME_METADATA",
                    "economic_conclusion": "NOT_EVALUATED",
                }
                continue
            try:
                req = ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account_id, symbolId=int(mapped["symbol_id"])
                )
                req.volume.append(int(min_volume))
                res = yield self._send(req)
                self._expected_margin[canonical] = {
                    "state": "CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT",
                    "volume_cents": int(min_volume),
                    "margin": [_plain(x) for x in res.margin],
                    "money_digits": getattr(res, "moneyDigits", None),
                    "approximate_formula_used": False,
                    "order_placed": False,
                    "economic_conclusion": "NOT_EVALUATED",
                }
            except Exception as exc:
                self._expected_margin[canonical] = {
                    "state": "UNRESOLVED_READ_ONLY_SCOPE_OR_API_REJECTION",
                    "reason": redact_text(str(exc)),
                    "scope_escalated": False,
                    "order_placed": False,
                    "economic_conclusion": "NOT_EVALUATED",
                }

    @defer.inlineCallbacks
    def _capture_conversion_metadata(self, account_id: int):
        """Capture current USD/JPY->EUR chain plus constituent DEVELOPMENT M15 bars.

        Current chain selection is never promoted to historically point-in-time valid.
        """
        assets_by_name = {
            str(a.get("name", "")).upper(): int(a["assetId"])
            for a in self._assets if a.get("name") and a.get("assetId") is not None
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
                    ctidTraderAccountId=account_id, firstAssetId=source_id, lastAssetId=eur_id
                )
                res = yield self._send(req)
                chain = [_plain(x) for x in res.symbol]
                if not chain:
                    raise CaptureContractError(f"{source_name}->EUR conversion chain is empty")
                ids = [int(x["symbolId"]) for x in chain]
                full_req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
                full_req.symbolId.extend(ids)
                full_res = yield self._send(full_req)
                full_by_id = {int(x.symbolId): _plain(x) for x in full_res.symbol}
                raw_refs = []
                for light in chain:
                    sid = int(light["symbolId"])
                    if sid not in full_by_id:
                        raise CaptureContractError(f"conversion symbol metadata missing for {sid}")
                    ensure_full_symbol_enabled(full_by_id[sid])
                    if str(sid) not in self._conversion_raw_results:
                        result = yield self._capture_aux_conversion_series(
                            account_id=account_id, symbol_id=sid,
                            broker_symbol=light.get("symbolName", str(sid)),
                            digits=int(full_by_id[sid].get("digits", 5)),
                        )
                        self._conversion_raw_results[str(sid)] = result
                    raw_refs.append(self._conversion_raw_results[str(sid)]["aux_raw_id"])
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
                    "state": "UNRESOLVED", "reason": redact_text(str(exc)),
                    "historical_causal_conversion_rates": "UNRESOLVED",
                }

    @defer.inlineCallbacks
    def _capture_aux_conversion_series(self, *, account_id: int, symbol_id: int,
                                       broker_symbol: str, digits: int):
        safe_name = "".join(ch for ch in str(broker_symbol).upper() if ch.isalnum()) or str(symbol_id)
        aux_id = f"PW02-AUX-CONV-{safe_name}-M15-S{symbol_id}"
        result = yield self._capture_series(
            account_id=account_id, symbol_id=symbol_id, resolution="M15", digits=digits,
            capture_id=aux_id, output_subdir="auxiliary/conversion_raw",
        )
        result.update({
            "aux_raw_id": aux_id, "broker_symbol": broker_symbol, "symbol_id": int(symbol_id),
            "classification": "DEVELOPMENT",
            "historical_chain_point_in_time_validity": "UNRESOLVED",
        })
        return result

    @defer.inlineCallbacks
    def _capture_raw_series(self, account_id: int, raw: Mapping[str, Any]):
        canonical = raw["canonical_instrument"]
        result = yield self._capture_series(
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
            "source_environment": self.plan["raw_capture_defaults"]["source_environment"],
        })
        self._raw_results[raw["raw_capture_id"]] = result

    @defer.inlineCallbacks
    def _capture_series(self, *, account_id: int, symbol_id: int, resolution: str,
                        digits: int, capture_id: str, output_subdir: str):
        from .ctrader_capture import load_resume_state
        defaults = self.plan["raw_capture_defaults"]
        interval = defaults["interval"]
        state = load_resume_state(self.resume_path, self.plan_sha)
        series_work = self.work_dir / capture_id
        series_work.mkdir(parents=True, exist_ok=True)
        chunk_paths = []
        for wi, (from_ms, window_to_ms) in enumerate(
            historical_windows(interval["start_utc"], interval["end_utc"], resolution)
        ):
            page = 0
            page_to_ms = window_to_ms
            while page_to_ms >= from_ms:
                key = f"{capture_id}:{wi}:{page}:{from_ms}:{page_to_ms}"
                resumed = verified_chunk_path(state, key)
                if resumed is not None:
                    chunk_paths.append(resumed)
                    item = state["chunks"][key]
                    if item.get("has_more") and item.get("next_to_ms") is not None:
                        page_to_ms = int(item["next_to_ms"])
                        page += 1
                        continue
                    break
                req = ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account_id, symbolId=int(symbol_id),
                    period=ProtoOATrendbarPeriod.Value(resolution),
                    fromTimestamp=from_ms, toTimestamp=page_to_ms, count=5000,
                )
                res = yield self._send(req, historical=True)
                trendbars = [_plain(x) for x in res.trendbar]
                rows = normalize_trendbars(
                    trendbars, resolution=resolution, digits=digits,
                    requested_start_utc=interval["start_utc"],
                    requested_end_utc=interval["end_utc"],
                    protected_start_utc=PROTECTED_FORWARD_START,
                )
                chunk_path = series_work / f"w{wi:04d}_p{page:04d}.csv"
                chunk_path.write_bytes(raw_csv_bytes(rows))
                record_completed_chunk(
                    state, chunk_key=key, path=chunk_path, raw_capture_id=capture_id,
                    request_from_ms=from_ms, request_to_ms=page_to_ms, page=page,
                    row_count=len(rows),
                )
                has_more = bool(getattr(res, "hasMore", False))
                next_to = next_pagination_to_ms(trendbars, from_ms) if has_more else None
                state["chunks"][key]["has_more"] = has_more
                state["chunks"][key]["next_to_ms"] = next_to
                atomic_write_json(self.resume_path, state)
                chunk_paths.append(chunk_path)
                if not has_more:
                    break
                if next_to is None or next_to >= page_to_ms:
                    raise CaptureContractError(f"{capture_id}: invalid historical pagination")
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
            "first_timestamp_utc": rows[0]["time_utc"] if rows else None,
            "last_timestamp_utc": rows[-1]["time_utc"] if rows else None,
            "sha256": sha256_file(final_path),
            "file": final_path.relative_to(self.bundle_dir).as_posix(),
            "gap_diagnostics": gap_diagnostics(rows, resolution),
            "completed_bars_only": True,
            "protected_forward_rows_included": False,
            "resampling_performed": False,
            "synthetic_fill_performed": False,
            "forward_fill_performed": False,
        }

    def _auxiliary_status(self) -> dict[str, Any]:
        return {
            "current_symbol_metadata": {
                "state": "CAPTURED_CURRENT_SNAPSHOT_NOT_VERIFIED_HISTORY",
                "warning": "Current commission/swap/session metadata is not historical cost evidence.",
            },
            "historical_financing_swap": {
                "state": "UNRESOLVED",
                "reason": "No historical financing schedule is promoted from current Open API symbol metadata.",
            },
            "point_in_time_corporate_actions": {
                "state": "UNRESOLVED",
                "reason": "No point-in-time corporate-action history was obtained by this Open API capture client.",
            },
            "wti_historical_contract_roll_semantics": {
                "state": "UNRESOLVED",
                "reason": "Trendbars/current symbol metadata do not prove historical continuous-CFD roll construction.",
            },
            "historical_session_calendar_versions": {
                "state": "UNRESOLVED",
                "reason": "Current schedule/holiday metadata is not relabelled as historical schedule truth.",
            },
            "expected_margin": self._expected_margin,
            "conversion_chain_metadata": self._conversion_metadata,
            "conversion_raw_development_series": self._conversion_raw_results,
        }

    def _common_evidence_files(self):
        evidence = self.bundle_dir / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        atomic_write_json(evidence / "account.json", self._account_evidence)
        atomic_write_json(evidence / "broker_mapping.json", self._mapping)
        atomic_write_json(evidence / "symbol_metadata_current.json", drop_secret_fields(self._full_symbols))
        atomic_write_json(evidence / "assets.json", self._assets)
        atomic_write_json(evidence / "expected_margin.json", self._expected_margin)
        atomic_write_json(evidence / "auxiliary_status.json", self._auxiliary_status())

    def _write_final_bundle(self):
        self._common_evidence_files()
        provenance = {
            "schema": BUNDLE_SCHEMA,
            "tool_version": TOOL_VERSION,
            "active_plan": "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json",
            "plan_sha256": self.plan_sha,
            "source_environment": "Pepperstone - Europe LIVE",
            "oauth_scope": "accounts",
            "read_only": True,
            "orders_sent": 0,
            "account_mutations_sent": 0,
            "economic_evaluation_performed": False,
            "protected_evidence_opened": False,
            "development_classification_basis": "HISTORICAL_TIMESTAMP_NOT_DOWNLOAD_DATE",
            "protected_forward_start": PROTECTED_FORWARD_START,
            "unique_raw_capture_count": len(self._raw_results),
            "candidate_binding_count": len(self.plan["candidate_dataset_bindings"]),
            "raw_series": self._raw_results,
            "candidate_dataset_bindings": self.plan["candidate_dataset_bindings"],
            "secrets_in_bundle": False,
        }
        atomic_write_json(self.bundle_dir / "provenance_manifest.json", provenance)
        # Remove prior finalization files so a resumed run produces the same manifest from
        # current evidence rather than recursively hashing an older manifest.
        (self.bundle_dir / "bundle_manifest.json").unlink(missing_ok=True)
        (self.bundle_dir / "CHECKSUMS.sha256").unlink(missing_ok=True)
        checksums = write_bundle_checksums(self.bundle_dir)
        atomic_write_json(self.bundle_dir / "bundle_manifest.json", {
            "schema": BUNDLE_SCHEMA,
            "plan_sha256": self.plan_sha,
            "checksums": checksums,
            "return_this_zip_to_chatgpt": f"{self.bundle_name}.zip",
        })
        write_bundle_checksums(self.bundle_dir)
        scan_bundle_for_secrets(self.bundle_dir, [self.client_secret, self.access_token])
        deterministic_zip(self.bundle_dir, self.bundle_dir.parent / f"{self.bundle_name}.zip")

    def _write_partial_bundle(self, reason: str):
        try:
            self._common_evidence_files()
            atomic_write_json(self.bundle_dir / "BLOCKED.json", {
                "schema": BUNDLE_SCHEMA, "state": "BLOCKED", "reason": reason,
                "economic_evaluation_performed": False, "orders_sent": 0,
                "account_mutations_sent": 0, "protected_evidence_opened": False,
            })
            write_bundle_checksums(self.bundle_dir)
            scan_bundle_for_secrets(self.bundle_dir, [self.client_secret, self.access_token])
            deterministic_zip(self.bundle_dir, self.bundle_dir.parent / f"{self.bundle_name}.zip")
        except Exception:
            pass

"""Research Core V3 authentic sparse event-time friction capture.

Read-only Pepperstone LIVE Open API collector for the 14 DEVELOPMENT regions that
passed the dependence/multiplicity maxT screen. It never places orders, never opens
protected-forward data, never changes the frozen candidate semantics, and never treats
quote observations as executed fills.

Raw BID/ASK chunks remain on the device. The transferable bundle contains only exact
window-level quote states, current identity metadata, hashes, and provenance.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict

from m6.cost_evidence import (
    BoundaryQuoteIndex,
    DecodedTick,
    HISTORICAL_MIN_INTERVAL_SECONDS,
    OFFICIAL_TICK_MAX_WINDOW_MS,
    QUOTE_TYPES,
    atomic_write_bytes,
    canonical_tick_rows,
    decode_ctrader_tick_page,
    deterministic_zip_directory,
    next_tick_page_to_ms,
    tick_csv_bytes,
    verified_resume_chunk,
)
from m6.ctrader_capture import (
    CaptureContractError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    redact_text,
    require_read_only_request,
    sha256_file,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTickDataReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

TOOL_VERSION = "MXM_RESEARCH_CORE_V3_MAXT14_FRICTION_CAPTURE_V2"
PLAN_REL = "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V2.json"
SCOPE_ROOT_REL = "research_core_v3/state"
WORK_REL = ".mxm_v3_maxt14_friction_work"
OUTPUT_REL = "v3_friction_output/MXM_V3_MAXT14_FRICTION_EVIDENCE_V1"
TRANSFER_NAME = "MXM_V3_MAXT14_FRICTION_EVIDENCE_V1.zip"
REBIND_PROPOSAL_NAME = "MXM_V3_ACCOUNT_IDENTITY_REBIND_PROPOSAL_V1.json"


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


ERROR_RESPONSE_TYPES = {"ProtoOAErrorRes", "ProtoErrorRes"}
TRANSIENT_API_ERROR_CODES = {
    "BLOCKED_PAYLOAD_TYPE",
    "CANT_ROUTE_REQUEST",
    "TIMEOUT_ERROR",
    "RATE_LIMIT",
    "TOO_MANY_REQUESTS",
}
HISTORY_CONTEXT_TERMS = (
    "histor", "tick", "quote", "retention", "archive", "requested period",
    "requested range", "time range", "date range",
)
HISTORY_UNAVAILABLE_TERMS = (
    "not available", "unavailable", "no data", "no ticks", "no tick",
    "not retained", "retention limit", "retention period", "outside",
    "older than", "too old", "available range",
)


class CTraderAPIResponseError(CaptureContractError):
    def __init__(
        self, code: str, description: str, retry_after_seconds: int = 0
    ):
        self.code = str(code or "UNKNOWN")
        self.description = str(description or "")
        self.retry_after_seconds = max(0, int(retry_after_seconds or 0))
        detail = f"{self.code}: {redact_text(self.description)}".rstrip(": ")
        super().__init__(f"cTrader API error: {detail}")


class BrokerHistoryUnavailable(CaptureContractError):
    def __init__(self, api_error: CTraderAPIResponseError):
        self.code = api_error.code
        self.description = api_error.description
        super().__init__(
            "cTrader explicitly reports requested historical quote data unavailable: "
            f"{self.code}: {redact_text(self.description)}"
        )


def classify_ctrader_api_error(
    error_code: str, description: str, *, historical: bool
) -> str:
    """Conservative error policy: only explicit historical unavailability degrades."""
    code = str(error_code or "UNKNOWN").strip().upper()
    desc = " ".join(str(description or "").lower().split())
    if code in TRANSIENT_API_ERROR_CODES:
        return "TRANSIENT_RETRY"
    if historical:
        has_context = any(term in desc for term in HISTORY_CONTEXT_TERMS)
        unavailable = any(term in desc for term in HISTORY_UNAVAILABLE_TERMS)
        if has_context and unavailable:
            return "EXPLICIT_BROKER_HISTORY_UNAVAILABLE"
    return "FAIL_CLOSED"


def account_identity_recovery_decision(
    expected_fingerprint: str,
    authorized_fingerprints: list[str],
    auth_mode: str,
) -> str:
    """Choose the next account-identity action without inspecting any market history."""
    matches = sum(
        1 for value in authorized_fingerprints if str(value) == str(expected_fingerprint)
    )
    if matches == 1:
        return "MATCH_FROZEN_ACCOUNT"
    if matches > 1:
        return "FAIL_CLOSED_DUPLICATE_FROZEN_ACCOUNT_IDENTITY"
    if "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION" not in str(auth_mode):
        return "FORCE_FRESH_OAUTH"
    return "REBIND_REVIEW_REQUIRED"


def build_account_rebind_proposal_document(
    plan: Mapping[str, Any],
    account_evidence: Mapping[str, Any],
    symbol_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a sanitized proposal; this never changes the frozen authority."""
    old_fp = str(
        plan["broker_identity"]["accepted_account_fingerprint_sha256"]
    )
    new_fp = str(account_evidence.get("account_fingerprint_sha256") or "")
    if len(new_fp) != 64 or new_fp == old_fp:
        raise CaptureContractError("account rebind proposal requires a distinct valid fingerprint")
    if str(account_evidence.get("environment")) != "Pepperstone - Europe LIVE":
        raise CaptureContractError("account rebind environment is not Pepperstone Europe LIVE")
    if "pepperstone" not in str(account_evidence.get("broker_name") or "").lower():
        raise CaptureContractError("account rebind broker identity is not Pepperstone")
    expected = {
        (str(t["symbol"]), int(t["symbol_id"])) for t in plan["targets"]
    }
    observed = {
        (str(v.get("symbol")), int(v.get("symbol_id", 0)))
        for v in symbol_evidence.values()
        if v.get("identity") == "EXACT_ACCEPTED_SYMBOL_ID_NAME_CURRENT_ENABLED"
    }
    if observed != expected:
        raise CaptureContractError(
            "account rebind requires exact current applicability for all 14 frozen symbols"
        )
    prior = plan.get("recovered_prior_evidence_audit") or {}
    if prior.get("direct_historical_tick_coverage_for_selected_14") != "NONE_FOUND":
        raise CaptureContractError(
            "account rebind cannot be auto-proposed after prior selected-14 account evidence"
        )
    symbol_binding = _sha_bytes(
        _canonical(
            [
                {
                    "symbol": symbol,
                    "symbol_id": sid,
                    "identity": symbol_evidence[symbol]["identity"],
                    "current_metadata_sha256": _sha_bytes(
                        _canonical(
                            symbol_evidence[symbol].get(
                                "current_metadata_only_not_historical_cost_truth"
                            ) or {}
                        )
                    ),
                }
                for symbol, sid in sorted(expected)
            ]
        )
    )
    proposal = {
        "schema": "mxm.research-core-v3.account-identity-rebind-proposal.v1",
        "source_plan_binding_sha256": plan["binding_sha256"],
        "source_accepted_account_fingerprint_sha256": old_fp,
        "proposed_account_fingerprint_sha256": new_fp,
        "environment": "Pepperstone - Europe LIVE",
        "broker_verified": True,
        "oauth_scope": "accounts",
        "exact_symbol_id_name_enabled_verified": True,
        "verified_symbol_count": len(expected),
        "symbol_applicability_binding_sha256": symbol_binding,
        "raw_account_id_embedded": False,
        "historical_bid_ask_capture_started": False,
        "protected_forward_opened": False,
        "candidate_identity_changed": False,
        "development_surface_changed": False,
        "account_specific_friction_evidence_reused_across_accounts": False,
        "rebind_scientifically_eligible": True,
        "authority_change_performed": False,
        "scientific_basis": (
            "The gross DEVELOPMENT surface and candidate regions are account-independent "
            "at this stage; selected-14 historical friction remains unresolved. Rebinding "
            "is eligible only before historical quote capture, after Pepperstone LIVE "
            "identity and exact 14-symbol applicability are reverified. The frozen account "
            "authority must be durably rebound before any historical BID/ASK request."
        ),
        "next_required_step": (
            "DURABLY_REBIND_THE_FROZEN_V3_ACQUISITION_ACCOUNT_FINGERPRINT_"
            "AND_REBUILD_THE_ANDROID_PACKAGE_BEFORE_CAPTURE"
        ),
    }
    proposal["binding_sha256"] = _sha_bytes(_canonical(proposal))
    return proposal


def history_coverage_for_window(
    record: Mapping[str, Any], start_ms: int, end_ms: int
) -> str:
    """Classify exact-window overlap with explicit broker-unavailable history."""
    start_ms, end_ms = int(start_ms), int(end_ms)
    if end_ms <= start_ms:
        raise CaptureContractError("invalid exact-window range")
    overlaps: list[tuple[int, int]] = []
    for item in record.get("broker_history_unavailable_ranges") or []:
        left = max(start_ms, int(item["from_ms"]))
        right = min(end_ms, int(item["to_ms"]))
        if right > left:
            overlaps.append((left, right))
    if not overlaps:
        return "REQUEST_COMPLETED"
    overlaps.sort()
    merged: list[list[int]] = []
    for left, right in overlaps:
        if not merged or left > merged[-1][1]:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    unavailable_ms = sum(right - left for left, right in merged)
    if unavailable_ms >= end_ms - start_ms:
        return "BROKER_HISTORY_UNAVAILABLE"
    return "PARTIAL_BROKER_HISTORY_UNAVAILABLE"


@dataclass(frozen=True)
class ExactWindow:
    index: int
    start_ms: int
    end_ms: int

    @property
    def boundary_ms(self) -> int:
        return self.start_ms + 2_000


@dataclass(frozen=True)
class AcquisitionBlock:
    index: int
    start_ms: int
    end_ms: int
    windows: tuple[ExactWindow, ...]


def decode_delta_windows(encoded: list[list[int]]) -> list[tuple[int, int]]:
    previous = 0
    out: list[tuple[int, int]] = []
    for pair in encoded:
        if not isinstance(pair, list) or len(pair) != 2:
            raise CaptureContractError("packed friction window encoding malformed")
        delta, duration = int(pair[0]), int(pair[1])
        start = previous + delta
        end = start + duration
        if start < 0 or end < start:
            raise CaptureContractError("packed friction window boundary invalid")
        out.append((start, end))
        previous = start
    return out


def coalesce_exact_windows(
    windows: list[tuple[int, int]],
    *,
    max_gap_ms: int,
    max_block_span_ms: int,
) -> list[AcquisitionBlock]:
    """Transport-only grouping. Original exact windows remain the analysis authority."""
    if max_gap_ms < 0 or max_block_span_ms <= 0:
        raise CaptureContractError("invalid transport coalescing parameters")
    exact = [
        ExactWindow(index=i, start_ms=int(start), end_ms=int(end))
        for i, (start, end) in enumerate(windows)
    ]
    if not exact:
        return []
    for left, right in zip(exact, exact[1:]):
        if right.start_ms < left.start_ms:
            raise CaptureContractError("exact windows are not chronological")

    groups: list[list[ExactWindow]] = []
    current = [exact[0]]
    for window in exact[1:]:
        proposed_start = current[0].start_ms
        gap = window.start_ms - current[-1].end_ms
        proposed_end = max(current[-1].end_ms, window.end_ms)
        if gap <= max_gap_ms and proposed_end - proposed_start <= max_block_span_ms:
            current.append(window)
        else:
            groups.append(current)
            current = [window]
    groups.append(current)
    return [
        AcquisitionBlock(
            index=i,
            start_ms=group[0].start_ms,
            end_ms=max(x.end_ms for x in group),
            windows=tuple(group),
        )
        for i, group in enumerate(groups)
    ]


def _read_tick_csv(path: Path) -> list[DecodedTick]:
    ticks: list[DecodedTick] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticks.append(DecodedTick(int(row["timestamp_ms"]), int(row["raw_tick"])))
    return ticks


def _safe_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class V3MaxT14FrictionRunner:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        access_token: str,
        config: Mapping[str, Any],
        repo_root: Path | str,
        progress=print,
        transport: StdlibCTraderTransport | None = None,
    ):
        self.repo_root = Path(repo_root)
        self.plan_path = self.repo_root / PLAN_REL
        if not self.plan_path.is_file():
            raise CaptureContractError("V3 maxT14 friction plan missing")
        self.plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self._validate_plan()

        self.client_id = str(client_id)
        self.client_secret = str(client_secret)
        self.access_token = str(access_token)
        self.config = dict(config)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(
            LIVE_HOST, LIVE_PORT, response_timeout=60
        )

        self.work_dir = self.repo_root / WORK_REL
        self.raw_root = self.work_dir / "chunks"
        self.resume_path = self.work_dir / "resume.json"
        self.network_cache_path = self.work_dir / "network_endpoint_cache.json"
        self.output_dir = self.repo_root / OUTPUT_REL
        self.transfer_path = self.output_dir.parent / TRANSFER_NAME

        self.scope_by_symbol = self._load_scopes_and_blocks()
        self.resume = self._load_or_initialize_resume()
        self._load_network_endpoint_cache()

        self._last_historical_send: float | None = None
        self._historical_requests = 0
        self._historical_unavailable_responses = 0
        self._resume_reused_chunks = 0
        # Logical authorization intent is separate from auth on the current TLS session.
        # New transport sessions replay required auth exactly once; live sessions do not.
        self._logical_app_authorized = False
        self._logical_account_id: int | None = None
        self._session_app_authorized = False
        self._session_account_authorized_id: int | None = None
        self._account_evidence: dict[str, Any] = {}
        self._symbol_evidence: dict[str, Any] = {}
        self._started = time.monotonic()

    def _stage(self, message: str) -> None:
        self.progress(message)

    def _validate_plan(self) -> None:
        p = self.plan
        if p.get("status") != "FROZEN_READ_ONLY_AUTHENTIC_QUOTE_ACQUISITION_PLAN":
            raise CaptureContractError("V3 friction plan status is not frozen/read-only")
        expected = p.get("binding_sha256")
        unsigned = dict(p)
        unsigned.pop("binding_sha256", None)
        if _sha_bytes(_canonical(unsigned)) != expected:
            raise CaptureContractError("V3 friction plan binding hash mismatch")
        broker = p["broker_identity"]
        if broker.get("oauth_scope") != "accounts":
            raise CaptureContractError("OAuth scope must remain accounts/view-only")
        if broker.get("orders") is not False or broker.get("account_mutation") is not False:
            raise CaptureContractError("read-only broker contract violated")
        if p["acquisition"].get("protected_forward_opened") is not False:
            raise CaptureContractError("protected-forward flag is not closed")
        if p["acquisition"].get("fill_authority") is not False:
            raise CaptureContractError("quote capture may not claim fill authority")
        if len(p["targets"]) != 14:
            raise CaptureContractError("maxT14 target count changed")
        if p.get("schema") == "mxm.research-core-v3.maxt14-authentic-friction-acquisition.v2":
            rebind = p.get("account_identity_rebind") or {}
            if rebind.get("research_scope_changed") is not False:
                raise CaptureContractError("account rebind may not change research scope")
            if rebind.get("historical_bid_ask_capture_started_before_rebind") is not False:
                raise CaptureContractError("account rebind occurred after historical capture")
            if rebind.get("raw_account_id_persisted") is not False:
                raise CaptureContractError("raw account ID may not enter rebind authority")

    def _load_scopes_and_blocks(self) -> dict[str, dict[str, Any]]:
        from datetime import datetime

        root = self.repo_root / SCOPE_ROOT_REL
        archives = {x["path"]: x for x in self.plan["scope_archives"]}
        verified_archives: set[str] = set()
        result: dict[str, dict[str, Any]] = {}
        coalesce = self.plan["acquisition"]["transport_coalescing"]
        protected_ms = int(
            datetime.fromisoformat(
                self.plan["authority"]["protected_forward_start"].replace("Z", "+00:00")
            ).timestamp()
            * 1000
        )
        for target in self.plan["targets"]:
            archive_name = target["archive"]
            archive_path = root / archive_name
            if archive_name not in archives or not archive_path.is_file():
                raise CaptureContractError(f"scope archive missing: {archive_name}")
            if archive_name not in verified_archives:
                if sha256_file(archive_path) != archives[archive_name]["sha256"]:
                    raise CaptureContractError(f"scope archive hash mismatch: {archive_name}")
                verified_archives.add(archive_name)
            with zipfile.ZipFile(archive_path) as zf:
                blob = zf.read(target["shard"])
            if _sha_bytes(blob) != target["shard_sha256"]:
                raise CaptureContractError(f"{target['symbol']}: packed shard hash mismatch")
            doc = json.loads(gzip.decompress(blob))
            if int(doc["symbol_id"]) != int(target["symbol_id"]):
                raise CaptureContractError(f"{target['symbol']}: scope symbolId mismatch")
            if str(doc["symbol"]) != str(target["symbol"]):
                raise CaptureContractError(f"{target['symbol']}: scope symbol name mismatch")
            windows = decode_delta_windows(doc["quote_windows_delta_ms"])
            if len(windows) != int(target["windows"]):
                raise CaptureContractError(f"{target['symbol']}: exact window count mismatch")
            blocks = coalesce_exact_windows(
                windows,
                max_gap_ms=int(coalesce["maximum_gap_ms"]),
                max_block_span_ms=int(coalesce["maximum_block_span_ms"]),
            )
            for block in blocks:
                if block.end_ms - block.start_ms > OFFICIAL_TICK_MAX_WINDOW_MS:
                    raise CaptureContractError("coalesced block exceeds cTrader max request span")
                if block.end_ms >= protected_ms:
                    raise CaptureContractError("coalesced block reaches protected-forward")
            result[target["symbol"]] = {
                "target": target,
                "windows": windows,
                "blocks": blocks,
                "packed_scope_sha256": target["shard_sha256"],
            }
        if sum(len(x["windows"]) for x in result.values()) != int(
            self.plan["selection"]["selected_exact_quote_windows"]
        ):
            raise CaptureContractError("selected exact-window total mismatch")
        return result

    def acquisition_geometry_summary(self) -> dict[str, Any]:
        by_symbol = {}
        total_blocks = total_exact_ms = total_acquisition_ms = 0
        for symbol, scope in self.scope_by_symbol.items():
            blocks = scope["blocks"]
            windows = scope["windows"]
            exact_ms = sum(end - start for start, end in windows)
            acquisition_ms = sum(block.end_ms - block.start_ms for block in blocks)
            by_symbol[symbol] = {
                "exact_windows": len(windows),
                "transport_blocks": len(blocks),
                "exact_window_ms": exact_ms,
                "acquisition_block_ms": acquisition_ms,
                "transport_requests_before_pagination_bid_ask": 2 * len(blocks),
            }
            total_blocks += len(blocks)
            total_exact_ms += exact_ms
            total_acquisition_ms += acquisition_ms
        return {
            "symbols": len(by_symbol),
            "exact_windows": sum(x["exact_windows"] for x in by_symbol.values()),
            "transport_blocks": total_blocks,
            "base_bid_ask_requests_before_pagination": 2 * total_blocks,
            "exact_window_ms": total_exact_ms,
            "acquisition_block_ms": total_acquisition_ms,
            "overfetch_ratio_by_time": (
                total_acquisition_ms / total_exact_ms if total_exact_ms else None
            ),
            "by_symbol": by_symbol,
        }

    def _resume_contract(self) -> dict[str, Any]:
        geometry = self.acquisition_geometry_summary()
        value = {
            "schema": "mxm.research-core-v3.maxt14-friction-resume.v1",
            "tool_version": TOOL_VERSION,
            "plan_binding_sha256": self.plan["binding_sha256"],
            "accepted_account_fingerprint_sha256": self.plan["broker_identity"][
                "accepted_account_fingerprint_sha256"
            ],
            "transport_geometry_sha256": _sha_bytes(_canonical(geometry)),
        }
        value["binding_sha256"] = _sha_bytes(_canonical(value))
        return value

    def _load_or_initialize_resume(self) -> dict[str, Any]:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        expected = self._resume_contract()
        existing = None
        if self.resume_path.is_file():
            try:
                existing = json.loads(self.resume_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = None
        mismatch = (
            not isinstance(existing, dict)
            or existing.get("contract") != expected
            or not isinstance(existing.get("completed"), dict)
        )
        if mismatch:
            if any(self.work_dir.iterdir()):
                tag = "unknown"
                if isinstance(existing, dict):
                    tag = str(
                        (existing.get("contract") or {}).get("binding_sha256") or "unknown"
                    )[:12]
                stale = self.work_dir.parent / f"{self.work_dir.name}.stale_{tag}"
                suffix = 1
                while stale.exists():
                    stale = self.work_dir.parent / f"{self.work_dir.name}.stale_{tag}_{suffix}"
                    suffix += 1
                self.work_dir.rename(stale)
                self.work_dir.mkdir(parents=True, exist_ok=True)
            existing = {
                "schema": "mxm.research-core-v3.maxt14-friction-resume-state.v1",
                "contract": expected,
                "completed": {},
            }
            atomic_write_json(self.resume_path, existing)
        return existing

    def _load_network_endpoint_cache(self) -> None:
        if not self.network_cache_path.is_file():
            return
        try:
            value = json.loads(self.network_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if value.get("host") != LIVE_HOST or int(value.get("port", 0)) != LIVE_PORT:
            return
        self.transport.seed_cached_endpoints(value.get("endpoints") or [])

    def _persist_network_endpoint_cache(self) -> None:
        endpoints = [[host, int(port)] for host, port in self.transport.cached_endpoints]
        if endpoints:
            atomic_write_json(
                self.network_cache_path,
                {
                    "schema": "mxm.research-core-v3.ctrader-endpoint-cache.v1",
                    "host": LIVE_HOST,
                    "port": LIVE_PORT,
                    "endpoints": endpoints,
                    "role": "OPERATIONAL_RECONNECT_CACHE_NOT_RESEARCH_EVIDENCE",
                },
            )

    def _transport_request(self, request):
        require_read_only_request(type(request).__name__)
        response = self.transport.request(request, timeout=60)
        if type(response).__name__ in ERROR_RESPONSE_TYPES:
            raise CTraderAPIResponseError(
                str(getattr(response, "errorCode", "UNKNOWN") or "UNKNOWN"),
                str(getattr(response, "description", "") or ""),
                int(getattr(response, "retryAfter", 0) or 0),
            )
        return response

    def _restore_session(self) -> None:
        """Open a new transport session and replay logically required auth once."""
        self.transport.connect()
        self._persist_network_endpoint_cache()
        self._session_app_authorized = False
        self._session_account_authorized_id = None

        if self._logical_app_authorized:
            self._transport_request(
                ProtoOAApplicationAuthReq(
                    clientId=self.client_id, clientSecret=self.client_secret
                )
            )
            self._session_app_authorized = True

        if self._logical_account_id is not None:
            if not self._session_app_authorized:
                raise CaptureContractError(
                    "account session restore requires application authentication"
                )
            self._transport_request(
                ProtoOAAccountAuthReq(
                    ctidTraderAccountId=self._logical_account_id,
                    accessToken=self.access_token,
                )
            )
            self._session_account_authorized_id = self._logical_account_id

    def _ensure_application_authenticated(self) -> None:
        """Authenticate the application at most once on the current live session."""
        if not bool(getattr(self.transport, "connected", False)):
            self._restore_session()
        if self._session_app_authorized:
            return
        self._send(
            ProtoOAApplicationAuthReq(
                clientId=self.client_id, clientSecret=self.client_secret
            )
        )
        self._logical_app_authorized = True
        self._session_app_authorized = True

    def _ensure_account_authenticated(self, account_id: int) -> None:
        """Authenticate one logical account once per session; never switch silently."""
        account_id = int(account_id)
        self._ensure_application_authenticated()
        if self._session_account_authorized_id == account_id:
            return
        if (
            self._logical_account_id is not None
            and int(self._logical_account_id) != account_id
        ):
            raise CaptureContractError(
                "attempted to switch authenticated cTrader account within one runner"
            )
        self._send(
            ProtoOAAccountAuthReq(
                ctidTraderAccountId=account_id,
                accessToken=self.access_token,
            )
        )
        self._logical_account_id = account_id
        self._session_account_authorized_id = account_id

    def _send(self, request, *, historical: bool = False, retries: int = 4):
        require_read_only_request(type(request).__name__)
        last: Exception | None = None
        for attempt in range(1, retries + 1):
            if historical:
                now = time.monotonic()
                if self._last_historical_send is not None:
                    delay = HISTORICAL_MIN_INTERVAL_SECONDS - (
                        now - self._last_historical_send
                    )
                    if delay > 0:
                        time.sleep(delay)
                self._last_historical_send = time.monotonic()
            try:
                response = self._transport_request(request)
                if historical:
                    self._historical_requests += 1
                return response
            except CTraderAPIResponseError as exc:
                policy = classify_ctrader_api_error(
                    exc.code, exc.description, historical=historical
                )
                if policy == "EXPLICIT_BROKER_HISTORY_UNAVAILABLE":
                    self._historical_unavailable_responses += 1
                    raise BrokerHistoryUnavailable(exc) from None
                if policy == "FAIL_CLOSED":
                    raise CaptureContractError(
                        f"{type(request).__name__} broker API error is not safely "
                        f"classifiable as transient or historical unavailability: "
                        f"{exc.code}: {redact_text(exc.description)}"
                    ) from None
                last = exc
                if attempt >= retries:
                    break
                delay = max(
                    min(8.0, float(2 ** (attempt - 1))),
                    float(exc.retry_after_seconds),
                )
                self._stage(
                    f"[RETRY] {type(request).__name__} transient broker error "
                    f"{exc.code} attempt {attempt}/{retries}; retry in {delay:.1f}s"
                )
                time.sleep(delay)
            except Exception as exc:
                last = exc
                if attempt >= retries:
                    break
                delay = min(8.0, float(2 ** (attempt - 1)))
                self._stage(
                    f"[RETRY] {type(request).__name__} transport attempt "
                    f"{attempt}/{retries}: {redact_text(str(exc))}"
                )
                time.sleep(delay)
            try:
                self.transport.close()
                self._restore_session()
            except Exception as reconnect_exc:
                last = reconnect_exc
        raise CaptureContractError(
            f"{type(request).__name__} failed after {retries} attempts: "
            f"{redact_text(str(last))}"
        )

    def _authorized_live_accounts(self) -> list[dict[str, Any]]:
        """Return LIVE accounts after idempotent application auth."""
        if not bool(getattr(self.transport, "connected", False)):
            self._restore_session()
        self._ensure_application_authenticated()
        accounts_res = self._send(
            ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)
        )
        accounts = [_plain(x) for x in accounts_res.ctidTraderAccount]
        return [dict(x) for x in live_account_candidates(accounts)]

    def _verify_account_and_targets(
        self, account: Mapping[str, Any]
    ) -> int:
        account_id = int(account["ctidTraderAccountId"])
        fingerprint = account_fingerprint(account_id)
        self._ensure_account_authenticated(account_id)
        trader_res = self._send(ProtoOATraderReq(ctidTraderAccountId=account_id))
        trader = _plain(trader_res.trader)
        broker_name = str(trader.get("brokerName") or "")
        broker_short = str(account.get("brokerTitleShort") or "")
        if "pepperstone" not in (broker_name + " " + broker_short).lower():
            raise CaptureContractError("authorized account is not verifiably Pepperstone")

        symbols_res = self._send(
            ProtoOASymbolsListReq(
                ctidTraderAccountId=account_id, includeArchivedSymbols=False
            )
        )
        light_by_id = {int(x.symbolId): _plain(x) for x in symbols_res.symbol}
        target_ids = sorted(int(x["symbol_id"]) for x in self.plan["targets"])
        req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
        req.symbolId.extend(target_ids)
        full_res = self._send(req)
        full_by_id = {int(x.symbolId): _plain(x) for x in full_res.symbol}

        safe_fields = (
            "symbolId", "digits", "pipPosition", "lotSize", "minVolume", "stepVolume",
            "maxVolume", "commission", "commissionType", "preciseTradingCommissionRate",
            "minCommission", "minCommissionAsset", "leverageId", "tradingMode",
            "schedule", "swapLong", "swapShort", "swapCalculationType",
            "swapTime", "swapPeriod", "swap3DaysRollover",
        )
        evidence: dict[str, Any] = {}
        for target in self.plan["targets"]:
            symbol = target["symbol"]
            sid = int(target["symbol_id"])
            light = light_by_id.get(sid)
            full = full_by_id.get(sid)
            if light is None or full is None:
                raise CaptureContractError(f"{symbol}: accepted symbolId {sid} is not current")
            if str(light.get("symbolName") or "") != symbol:
                raise CaptureContractError(f"{symbol}: exact symbolId/name mapping changed")
            if not bool(light.get("enabled")):
                raise CaptureContractError(f"{symbol}: symbol is no longer enabled")
            if full.get("tradingMode", 0) not in (0, "0", None):
                raise CaptureContractError(f"{symbol}: current trading mode is not ENABLED")
            evidence[symbol] = {
                "symbol": symbol,
                "symbol_id": sid,
                "identity": "EXACT_ACCEPTED_SYMBOL_ID_NAME_CURRENT_ENABLED",
                "current_metadata_only_not_historical_cost_truth": {
                    key: _safe_number(full.get(key))
                    for key in safe_fields
                    if key in full
                },
            }

        self._account_evidence = {
            "account_fingerprint_sha256": fingerprint,
            "environment": "Pepperstone - Europe LIVE",
            "broker_name": broker_name or broker_short,
            "oauth_scope": "accounts",
            "raw_account_id_in_bundle": False,
            "orders": False,
            "account_mutation": False,
        }
        self._symbol_evidence = evidence
        return account_id

    def probe_account_identity(self, auth_mode: str) -> dict[str, Any]:
        """Resolve only account/symbol identity. Never sends historical tick requests."""
        accounts = self._authorized_live_accounts()
        expected = self.plan["broker_identity"][
            "accepted_account_fingerprint_sha256"
        ]
        fingerprints = [
            account_fingerprint(int(account["ctidTraderAccountId"]))
            for account in accounts
        ]
        decision = account_identity_recovery_decision(
            expected, fingerprints, auth_mode
        )
        result: dict[str, Any] = {
            "decision": decision,
            "authorized_live_accounts": accounts,
            "authorized_live_account_count": len(accounts),
            "expected_fingerprint_sha256": expected,
            "historical_requests": self._historical_requests,
        }
        if decision == "MATCH_FROZEN_ACCOUNT":
            matches = [
                account
                for account in accounts
                if account_fingerprint(int(account["ctidTraderAccountId"]))
                == expected
            ]
            account_id = self._verify_account_and_targets(matches[0])
            result["verified_account_id_local_only"] = account_id
            result["verified_account_fingerprint_sha256"] = expected
            result["verified_symbol_count"] = len(self._symbol_evidence)
        if self._historical_requests != 0:
            raise CaptureContractError(
                "account identity probe attempted historical market data"
            )
        return result

    def capture_has_started(self) -> bool:
        completed = self.resume.get("completed")
        if isinstance(completed, dict) and completed:
            return True
        if self.raw_root.exists() and any(
            path.is_file() for path in self.raw_root.rglob("*")
        ):
            return True
        if self.transfer_path.is_file():
            return True
        if self.output_dir.exists() and any(
            path.is_file() for path in self.output_dir.rglob("*")
        ):
            return True
        return False

    def write_account_rebind_proposal(self, account_id: int) -> Path:
        """Verify a different LIVE account, emit sanitized proposal, and stop before capture."""
        if self.capture_has_started():
            raise CaptureContractError(
                "account identity rebind is blocked because V3 friction capture data already exists"
            )
        accounts = self._authorized_live_accounts()
        selected = [
            account
            for account in accounts
            if int(account["ctidTraderAccountId"]) == int(account_id)
        ]
        if len(selected) != 1:
            raise CaptureContractError(
                "selected local LIVE account is not uniquely authorized by the fresh token"
            )
        self._verify_account_and_targets(selected[0])
        if self._historical_requests != 0:
            raise CaptureContractError(
                "account rebind review attempted historical market data"
            )
        proposal = build_account_rebind_proposal_document(
            self.plan, self._account_evidence, self._symbol_evidence
        )
        target = self.output_dir.parent / REBIND_PROPOSAL_NAME
        atomic_write_json(target, proposal)
        return target

    def _authenticate_and_verify_targets(self) -> int:
        self._stage("[1/4] Verifying exact Pepperstone LIVE account and 14 symbol identities")
        accounts = self._authorized_live_accounts()
        expected_fingerprint = self.plan["broker_identity"][
            "accepted_account_fingerprint_sha256"
        ]
        matching_accounts = [
            account
            for account in accounts
            if account_fingerprint(int(account["ctidTraderAccountId"]))
            == expected_fingerprint
        ]
        if len(matching_accounts) != 1:
            raise CaptureContractError(
                "the exact accepted Pepperstone LIVE research account is not uniquely authorized "
                "under this read-only token"
            )
        account_id = self._verify_account_and_targets(matching_accounts[0])
        self._stage(
            "[PREFLIGHT PASS] accepted account fingerprint and all 14 exact symbol IDs verified"
        )
        return account_id

    def _chunk_path(
        self, symbol: str, side: str, block: AcquisitionBlock
    ) -> Path:
        return (
            self.raw_root
            / symbol
            / side
            / f"{block.index:05d}_{block.start_ms}_{block.end_ms}.csv"
        )

    def _chunk_key(self, symbol: str, side: str, block: AcquisitionBlock) -> str:
        return f"{symbol}:{side}:{block.index}:{block.start_ms}:{block.end_ms}"

    def _capture_block_side(
        self,
        account_id: int,
        target: Mapping[str, Any],
        side: str,
        block: AcquisitionBlock,
    ) -> dict[str, Any]:
        symbol = str(target["symbol"])
        key = self._chunk_key(symbol, side, block)
        path = self._chunk_path(symbol, side, block)
        saved = self.resume["completed"].get(key)
        if isinstance(saved, dict) and verified_resume_chunk(
            path, str(saved.get("sha256") or "")
        ):
            self._resume_reused_chunks += 1
            return dict(saved)

        page_to = int(block.end_ms)
        previous_oldest = None
        ticks: list[DecodedTick] = []
        pages = 0
        fallback_count = 0
        unavailable_ranges: list[dict[str, Any]] = []
        while page_to >= block.start_ms:
            request = ProtoOAGetTickDataReq(
                ctidTraderAccountId=account_id,
                symbolId=int(target["symbol_id"]),
                type=int(QUOTE_TYPES[side]),
                fromTimestamp=int(block.start_ms),
                toTimestamp=int(page_to),
            )
            try:
                response = self._send(request, historical=True)
            except BrokerHistoryUnavailable as exc:
                description = redact_text(exc.description)
                unavailable_ranges.append({
                    "from_ms": int(block.start_ms),
                    "to_ms": int(page_to),
                    "error_code": exc.code,
                    "description": description,
                    "description_sha256": _sha_bytes(description.encode("utf-8")),
                    "classification": "EXPLICIT_BROKER_HISTORY_UNAVAILABLE",
                })
                self._stage(
                    f"[HISTORY UNAVAILABLE] {symbol} {side} block={block.index} "
                    f"{block.start_ms}..{page_to} | {exc.code} | continuing"
                )
                break
            pages += 1
            decoded = decode_ctrader_tick_page(
                [{"timestamp": int(x.timestamp), "tick": int(x.tick)}
                 for x in response.tickData]
            )
            ticks.extend(decoded)
            if not bool(getattr(response, "hasMore", False)):
                break
            if not decoded:
                raise CaptureContractError(
                    f"{symbol} {side}: hasMore returned with empty tick page"
                )
            oldest = min(x.timestamp_ms for x in decoded)
            next_to = next_tick_page_to_ms(
                decoded,
                current_from_ms=int(block.start_ms),
                previous_oldest_ms=previous_oldest,
            )
            if next_to is None:
                break
            if previous_oldest is not None and next_to < oldest:
                fallback_count += 1
            previous_oldest = oldest
            if next_to >= page_to:
                raise CaptureContractError(
                    f"{symbol} {side}: tick pagination did not make progress"
                )
            page_to = int(next_to)

        rows = canonical_tick_rows(
            ticks,
            requested_from_ms=int(block.start_ms),
            requested_to_ms=int(block.end_ms),
        )
        payload = tick_csv_bytes(rows)
        atomic_write_bytes(path, payload)
        if unavailable_ranges:
            capture_status = (
                "PARTIAL_BROKER_HISTORY_UNAVAILABLE"
                if rows else "BROKER_HISTORY_UNAVAILABLE"
            )
        elif rows:
            capture_status = "REQUEST_COMPLETED_WITH_TICKS"
        else:
            capture_status = "REQUEST_COMPLETED_NO_TICKS"
        record = {
            "key": key,
            "symbol": symbol,
            "symbol_id": int(target["symbol_id"]),
            "region_sha256": str(target["region_sha256"]),
            "quote_type": side,
            "block_index": block.index,
            "from_ms": block.start_ms,
            "to_ms": block.end_ms,
            "exact_windows_in_block": len(block.windows),
            "row_count": len(rows),
            "page_count": pages,
            "pagination_boundary_fallback_count": fallback_count,
            "capture_status": capture_status,
            "broker_history_unavailable_ranges": unavailable_ranges,
            "sha256": _sha_bytes(payload),
        }
        self.resume["completed"][key] = record
        atomic_write_json(self.resume_path, self.resume)
        return record

    def _capture_all(self, account_id: int) -> list[dict[str, Any]]:
        geometry = self.acquisition_geometry_summary()
        total = int(geometry["base_bid_ask_requests_before_pagination"])
        self._stage(
            "[2/4] Capturing authentic historical BID/ASK blocks | "
            f"{geometry['transport_blocks']} blocks | {total} base side-requests before pagination | "
            f"{geometry['exact_windows']} exact windows retained"
        )
        records: list[dict[str, Any]] = []
        done = 0
        for target in self.plan["targets"]:
            symbol = target["symbol"]
            blocks = self.scope_by_symbol[symbol]["blocks"]
            self._stage(
                f"[SYMBOL] {symbol} id={target['symbol_id']} | "
                f"{len(blocks)} transport blocks | {target['windows']} exact windows"
            )
            for block in blocks:
                for side in ("BID", "ASK"):
                    record = self._capture_block_side(
                        account_id, target, side, block
                    )
                    records.append(record)
                    done += 1
                    if done == 1 or done % 100 == 0 or done == total:
                        elapsed = max(0.001, time.monotonic() - self._started)
                        self._stage(
                            f"[CAPTURE] {done}/{total} base chunks | "
                            f"requests={self._historical_requests} | "
                            f"reused={self._resume_reused_chunks} | "
                            f"elapsed={elapsed/60.0:.1f}m"
                        )
        return records

    @staticmethod
    def _price(value: float | None) -> str:
        if value is None:
            return ""
        return format(float(value), ".10f").rstrip("0").rstrip(".")

    def _write_exact_window_evidence(
        self, symbol: str, scope: Mapping[str, Any]
    ) -> dict[str, Any]:
        derived = self.output_dir / "derived"
        derived.mkdir(parents=True, exist_ok=True)
        path = derived / f"{symbol}_EXACT_WINDOW_QUOTES.csv.gz"
        target = scope["target"]
        delays = [int(x) for x in self.plan["acquisition"]["delay_sensitivity_seconds"]]
        fieldnames = [
            "symbol", "symbol_id", "exact_window_index", "window_start_ms",
            "boundary_ms", "window_end_ms", "region_sha256",
            "bid_history_coverage", "ask_history_coverage",
        ]
        for delay in delays:
            prefix = f"d{delay}s"
            fieldnames.extend(
                [
                    f"{prefix}_bid", f"{prefix}_ask", f"{prefix}_spread",
                    f"{prefix}_bid_timestamp_ms", f"{prefix}_ask_timestamp_ms",
                    f"{prefix}_bid_age_ms", f"{prefix}_ask_age_ms",
                    f"{prefix}_availability",
                ]
            )
        fieldnames.extend(
            [
                "first_post_boundary_timestamp_ms",
                "first_post_boundary_side",
                "first_post_boundary_bid",
                "first_post_boundary_ask",
                "first_post_boundary_delay_ms",
            ]
        )
        row_count = missing_at_boundary = stale_at_boundary = negative_spread = 0
        block_count = 0
        with gzip.open(path, "wt", encoding="utf-8", newline="", compresslevel=9) as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for block in scope["blocks"]:
                bid_path = self._chunk_path(symbol, "BID", block)
                ask_path = self._chunk_path(symbol, "ASK", block)
                bid_key = self._chunk_key(symbol, "BID", block)
                ask_key = self._chunk_key(symbol, "ASK", block)
                bid_record = self.resume["completed"].get(bid_key)
                ask_record = self.resume["completed"].get(ask_key)
                for record, raw_path in ((bid_record, bid_path), (ask_record, ask_path)):
                    if not isinstance(record, dict) or not verified_resume_chunk(
                        raw_path, str(record.get("sha256") or "")
                    ):
                        raise CaptureContractError(
                            f"{symbol}: finalization missing hash-verified raw chunk"
                        )
                bids = _read_tick_csv(bid_path)
                asks = _read_tick_csv(ask_path)
                index = BoundaryQuoteIndex(bids, asks)
                for window in block.windows:
                    bid_history_coverage = history_coverage_for_window(
                        bid_record, window.start_ms, window.end_ms
                    )
                    ask_history_coverage = history_coverage_for_window(
                        ask_record, window.start_ms, window.end_ms
                    )
                    row = {
                        "symbol": symbol,
                        "symbol_id": int(target["symbol_id"]),
                        "exact_window_index": window.index,
                        "window_start_ms": window.start_ms,
                        "boundary_ms": window.boundary_ms,
                        "window_end_ms": window.end_ms,
                        "region_sha256": target["region_sha256"],
                        "bid_history_coverage": bid_history_coverage,
                        "ask_history_coverage": ask_history_coverage,
                    }
                    for delay in delays:
                        prefix = f"d{delay}s"
                        checkpoint_ms = window.boundary_ms + delay * 1000
                        state = index.causal_state_at_boundary(checkpoint_ms)
                        bid_ok = (
                            state.bid_timestamp_ms is not None
                            and state.bid_timestamp_ms >= window.start_ms
                        )
                        ask_ok = (
                            state.ask_timestamp_ms is not None
                            and state.ask_timestamp_ms >= window.start_ms
                        )
                        bid = state.bid if bid_ok else None
                        ask = state.ask if ask_ok else None
                        bid_ts = state.bid_timestamp_ms if bid_ok else None
                        ask_ts = state.ask_timestamp_ms if ask_ok else None
                        bid_age = checkpoint_ms - bid_ts if bid_ts is not None else None
                        ask_age = checkpoint_ms - ask_ts if ask_ts is not None else None
                        if bid_ok and ask_ok:
                            availability = "CAUSAL_TWO_SIDED_AVAILABLE"
                            spread = float(ask) - float(bid)
                        elif bid_ok:
                            availability = "MISSING_ASK"
                            spread = None
                        elif ask_ok:
                            availability = "MISSING_BID"
                            spread = None
                        else:
                            availability = "MISSING_BOTH_SIDES"
                            spread = None
                        row.update(
                            {
                                f"{prefix}_bid": self._price(bid),
                                f"{prefix}_ask": self._price(ask),
                                f"{prefix}_spread": self._price(spread),
                                f"{prefix}_bid_timestamp_ms": "" if bid_ts is None else bid_ts,
                                f"{prefix}_ask_timestamp_ms": "" if ask_ts is None else ask_ts,
                                f"{prefix}_bid_age_ms": "" if bid_age is None else bid_age,
                                f"{prefix}_ask_age_ms": "" if ask_age is None else ask_age,
                                f"{prefix}_availability": availability,
                            }
                        )
                        if spread is not None and spread < 0:
                            negative_spread += 1
                        if delay == 0:
                            if availability != "CAUSAL_TWO_SIDED_AVAILABLE":
                                missing_at_boundary += 1
                            elif max(int(bid_age or 0), int(ask_age or 0)) > int(
                                self.plan["acquisition"]["quote_age_limit_seconds"]
                            ) * 1000:
                                stale_at_boundary += 1
                    post = index.first_post_any(window.boundary_ms)
                    if post is not None and post.timestamp_ms > window.end_ms:
                        post = None
                    row.update(
                        {
                            "first_post_boundary_timestamp_ms": (
                                "" if post is None else post.timestamp_ms
                            ),
                            "first_post_boundary_side": "" if post is None else post.side,
                            "first_post_boundary_bid": (
                                "" if post is None else self._price(post.bid_price)
                            ),
                            "first_post_boundary_ask": (
                                "" if post is None else self._price(post.ask_price)
                            ),
                            "first_post_boundary_delay_ms": (
                                "" if post is None else post.delay_ms
                            ),
                        }
                    )
                    writer.writerow(row)
                    row_count += 1
                block_count += 1
                if block_count % 250 == 0:
                    self._stage(
                        f"[DERIVE] {symbol} blocks={block_count}/{len(scope['blocks'])} "
                        f"exact_rows={row_count}"
                    )
        return {
            "path": path.relative_to(self.output_dir).as_posix(),
            "rows": row_count,
            "sha256": sha256_file(path),
            "missing_two_sided_at_boundary": missing_at_boundary,
            "two_sided_but_older_than_2s_at_boundary": stale_at_boundary,
            "negative_spread_states_across_delays": negative_spread,
            "fill_authority": False,
            "raw_ticks_embedded": False,
        }

    def _assert_no_secret_literal(self) -> None:
        secrets = [
            x.encode("utf-8")
            for x in (self.client_id, self.client_secret, self.access_token)
            if x
        ]
        for path in self.output_dir.rglob("*"):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            for secret in secrets:
                if len(secret) >= 4 and secret in raw:
                    raise CaptureContractError(
                        f"secret literal detected in transferable evidence file {path.name}"
                    )

    def _finalize(self, records: list[dict[str, Any]]) -> Path:
        self._stage("[3/4] Deriving exact-window quote evidence; raw ticks remain local")
        if self.output_dir.exists():
            import shutil
            shutil.rmtree(self.output_dir)
        (self.output_dir / "evidence").mkdir(parents=True, exist_ok=True)

        derived: dict[str, Any] = {}
        for target in self.plan["targets"]:
            symbol = target["symbol"]
            derived[symbol] = self._write_exact_window_evidence(
                symbol, self.scope_by_symbol[symbol]
            )

        geometry = self.acquisition_geometry_summary()
        atomic_write_json(
            self.output_dir / "evidence" / "account_identity.json",
            self._account_evidence,
        )
        atomic_write_json(
            self.output_dir / "evidence" / "current_symbol_identity_metadata.json",
            {
                "classification": "CURRENT_IDENTITY_AND_STRUCTURAL_METADATA_ONLY_NOT_HISTORICAL_COST_TRUTH",
                "symbols": self._symbol_evidence,
            },
        )
        unavailability_events = []
        for rec in records:
            for item in rec.get("broker_history_unavailable_ranges") or []:
                unavailability_events.append({
                    "symbol": rec["symbol"],
                    "symbol_id": int(rec["symbol_id"]),
                    "region_sha256": rec["region_sha256"],
                    "quote_type": rec["quote_type"],
                    "block_index": int(rec["block_index"]),
                    "requested_from_ms": int(rec["from_ms"]),
                    "requested_to_ms": int(rec["to_ms"]),
                    **item,
                })
        availability_path = (
            self.output_dir / "evidence" / "broker_history_availability.json"
        )
        availability_doc = {
            "schema": "mxm.research-core-v3.broker-history-availability.v1",
            "classification": (
                "AUTHENTIC_BROKER_RESPONSE_PROVENANCE_NOT_ZERO_COST_NOT_SYNTHETIC_DATA"
            ),
            "error_policy": {
                "transient_network_or_rate_limit": "RETRY_AND_RESUME",
                "authentication_account_or_symbol_identity_failure": "FAIL_CLOSED",
                "explicit_broker_history_unavailable": "RECORD_UNAVAILABILITY_AND_CONTINUE",
                "unknown_or_ambiguous_api_error": "FAIL_CLOSED_PRESERVE_PROGRESS",
            },
            "event_count": len(unavailability_events),
            "events": unavailability_events,
        }
        atomic_write_json(availability_path, availability_doc)

        ordered_raw = sorted(
            [{
                "symbol": rec["symbol"],
                "quote_type": rec["quote_type"],
                "block_index": int(rec["block_index"]),
                "sha256": rec["sha256"],
                "row_count": int(rec["row_count"]),
                "capture_status": rec.get("capture_status"),
                "broker_history_unavailable_ranges": (
                    rec.get("broker_history_unavailable_ranges") or []
                ),
            } for rec in records],
            key=lambda x: (x["symbol"], x["quote_type"], x["block_index"]),
        )
        raw_commitment = _sha_bytes(_canonical(ordered_raw))
        manifest = {
            "schema": "mxm.research-core-v3.maxt14-friction-evidence-bundle.v2",
            "tool_version": TOOL_VERSION,
            "plan_binding_sha256": self.plan["binding_sha256"],
            "source_corrected_region_assessment_sha256": self.plan["authority"][
                "corrected_region_assessment_sha256"
            ],
            "source_corrected_friction_scope_plan_sha256": self.plan["authority"][
                "corrected_friction_scope_plan_sha256"
            ],
            "account_fingerprint_sha256": self._account_evidence[
                "account_fingerprint_sha256"
            ],
            "protected_forward_opened": False,
            "candidate_outcomes_opened": False,
            "orders": False,
            "account_mutation": False,
            "fill_authority": False,
            "economic_certification": False,
            "candidate_freeze_authority": False,
            "raw_chunks_retained_locally": True,
            "raw_ticks_embedded_in_transfer_bundle": False,
            "raw_chunk_count": len(records),
            "raw_tick_rows": sum(int(x["row_count"]) for x in records),
            "raw_ordered_commitment_sha256": raw_commitment,
            "historical_api_requests_completed": self._historical_requests,
            "historical_api_explicit_unavailable_responses": (
                self._historical_unavailable_responses
            ),
            "resume_chunks_reused": self._resume_reused_chunks,
            "geometry": geometry,
            "broker_history_availability_evidence": {
                "path": availability_path.relative_to(self.output_dir).as_posix(),
                "sha256": sha256_file(availability_path),
                "event_count": len(unavailability_events),
            },
            "coverage_semantics": {
                "REQUEST_COMPLETED": (
                    "broker request covered the exact window; zero ticks remains an "
                    "authentic observation, not zero spread"
                ),
                "PARTIAL_BROKER_HISTORY_UNAVAILABLE": (
                    "some requested time in the exact window was explicitly unavailable"
                ),
                "BROKER_HISTORY_UNAVAILABLE": (
                    "the exact requested window was covered by explicit broker "
                    "history-unavailable provenance"
                ),
            },
            "bundle_integrity_is_not_economic_sufficiency": True,
            "derived_exact_window_evidence": derived,
            "next_required_step": (
                "VERIFY_BUNDLE_AND_APPLY_ONLY_AUTHENTIC_POINT_IN_TIME_APPLICABLE_COST_"
                "AND_EXECUTION_COMPONENTS;KEEP_UNRESOLVED_WHERE_SIGN_CAN_CHANGE"
            ),
        }
        manifest["binding_sha256"] = _sha_bytes(_canonical(manifest))
        atomic_write_json(
            self.output_dir / "evidence" / "provenance_manifest.json", manifest
        )

        checksum_lines = []
        for path in sorted(
            p for p in self.output_dir.rglob("*")
            if p.is_file() and p.name != "CHECKSUMS.sha256"
        ):
            checksum_lines.append(
                f"{sha256_file(path)}  {path.relative_to(self.output_dir).as_posix()}"
            )
        (self.output_dir / "CHECKSUMS.sha256").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
        self._assert_no_secret_literal()
        digest = deterministic_zip_directory(self.output_dir, self.transfer_path)
        self._stage(f"[BUNDLE] {self.transfer_path}")
        self._stage(f"[SHA256] {digest}")
        return self.transfer_path

    def run(self) -> Path:
        try:
            account_id = self._authenticate_and_verify_targets()
            records = self._capture_all(account_id)
            result = self._finalize(records)
            self._stage("[4/4] COMPLETE — no order, no protected-forward, no candidate freeze")
            return result
        finally:
            try:
                self.transport.close()
            finally:
                self.access_token = ""


def local_geometry_preflight(repo_root: Path | str) -> dict[str, Any]:
    """No network, credentials, or broker call. Used by CI and Android preflight."""
    runner = object.__new__(V3MaxT14FrictionRunner)
    runner.repo_root = Path(repo_root)
    runner.plan_path = runner.repo_root / PLAN_REL
    runner.plan = json.loads(runner.plan_path.read_text(encoding="utf-8"))
    runner._validate_plan()
    runner.scope_by_symbol = runner._load_scopes_and_blocks()
    geometry = runner.acquisition_geometry_summary()
    if geometry["symbols"] != 14 or geometry["exact_windows"] != 691_919:
        raise CaptureContractError("V3 maxT14 geometry preflight count mismatch")
    return geometry

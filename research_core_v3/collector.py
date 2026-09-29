from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from competition.frontier_data_capture import (
    FrontierDataCaptureRunner,
    _deterministic_zip,
    _plain,
    _sha_file,
)
from m6.ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest

PEER_INDEX_REL = "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json"
EPOCH45_AUDIT_REL = "evidence/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_V1.json"
EPOCH46_PLAN_REL = "data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json"
FEASIBILITY_REL = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"

AUTHORITATIVE_FRONTIER = 1576
EXPECTED_COHORTS = 41
EXPECTED_FRESH_EPOCH46_REPRESENTATIVES = 34
EXPECTED_LEGACY_SINGLETON_COHORTS = 7
EXPECTED_ACCEPTED_IDENTITY_EXCLUSION = 45

START_UTC = "2025-12-15T00:00:00Z"
END_UTC = "2026-03-15T23:59:59Z"
PROTECTED_FORWARD_START_UTC = "2026-09-17T12:02:58Z"
OUTPUT_FILENAME = "MXM_RESEARCH_CORE_V3_PEPPERSTONE_M5_WAVE_00.zip"
BUNDLE_DIR = "MXM_RESEARCH_CORE_V3_PEPPERSTONE_M5_WAVE_00"
TOOL_VERSION = "MXM_RESEARCH_CORE_V3_PEPPERSTONE_M5_STDLIB_V1"
PLAN_SCHEMA = "mxm.research-core-v3.pepperstone-m5-wave-plan.v1"
PAYLOAD_SCHEMA = "mxm.research-core-v3.pepperstone-m5-capture-bundle.v1"


def _load(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _sha256_file(root: Path, rel: str) -> str:
    return hashlib.sha256((root / rel).read_bytes()).hexdigest()


def _canonical_hash(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k != "plan_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _accepted_epoch45_ids(audit: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    coverage = audit.get("accepted_coverage") or {}
    for scope in coverage.get("scope_details") or []:
        for sid in scope.get("eligible_exact_identity_ids") or []:
            ids.add(int(sid))
    return ids


def _median(values: list[float]) -> float:
    if not values:
        raise CaptureContractError("empty cohort candidate pool")
    vals = sorted(float(x) for x in values)
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2.0


def _proxy(identity: dict[str, Any]) -> float:
    value = identity.get("capital_efficiency_proxy_schedule_minutes_per_minimum_margin_eur")
    if value is None:
        raise CaptureContractError(f"missing capital-efficiency proxy for {identity.get('broker_symbol')}")
    return float(value)


def _margin(identity: dict[str, Any]) -> float:
    value = identity.get("minimum_directional_margin_eur")
    return float(value) if value is not None else float("inf")


def _choose_nearest_median(pool: list[dict[str, Any]]) -> dict[str, Any]:
    med = _median([_proxy(x) for x in pool])
    return min(
        pool,
        key=lambda x: (
            abs(_proxy(x) - med),
            _margin(x),
            int(x["symbol_id"]),
        ),
    )


def build_wave0_plan(root: Path) -> dict[str, Any]:
    root = Path(root)
    peer = _load(root, PEER_INDEX_REL)
    audit = _load(root, EPOCH45_AUDIT_REL)
    epoch46 = _load(root, EPOCH46_PLAN_REL)
    feasibility = _load(root, FEASIBILITY_REL)

    identities = peer.get("identities") or []
    cohorts = (peer.get("coverage") or {}).get("cohorts") or []
    if len(identities) != AUTHORITATIVE_FRONTIER:
        raise CaptureContractError("V3 peer index no longer binds the exact 1576 frontier")
    if len(cohorts) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 peer index no longer has exactly 41 structural cohorts")
    if int((feasibility.get("current_counts") or {}).get("current_eligible_post_exclusion_frontier") or -1) != AUTHORITATIVE_FRONTIER:
        raise CaptureContractError("current Pepperstone feasibility authority no longer binds 1576 eligible identities")

    accepted_ids = _accepted_epoch45_ids(audit)
    if len(accepted_ids) != EXPECTED_ACCEPTED_IDENTITY_EXCLUSION:
        raise CaptureContractError("Epoch45 accepted identity exclusion set is not exactly 45")

    groups: dict[str, list[dict[str, Any]]] = {}
    for x in identities:
        if x.get("current_entry_accessible") is not True:
            raise CaptureContractError("peer index contains identity outside current-entry-accessible frontier")
        if x.get("directional_feasibility") != "BOTH_FEASIBLE":
            raise CaptureContractError("peer index contains identity outside both-direction feasible frontier")
        cohort = str(x.get("peer_candidate_cohort_id") or "")
        if not cohort:
            raise CaptureContractError("peer index identity missing cohort")
        groups.setdefault(cohort, []).append(x)
    if len(groups) != EXPECTED_COHORTS:
        raise CaptureContractError("identity grouping does not reproduce 41 cohorts")

    chosen: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    singleton_recap: list[dict[str, Any]] = []
    for cohort_id in sorted(groups):
        cohort_members = groups[cohort_id]
        remaining = [x for x in cohort_members if int(x["symbol_id"]) not in accepted_ids]
        if remaining:
            pick = _choose_nearest_median(remaining)
            role = "FRESH_EPOCH46_COMPATIBLE_REPRESENTATIVE"
            fresh.append(pick)
        else:
            if len(cohort_members) != 1:
                raise CaptureContractError(f"closed cohort is not singleton: {cohort_id}")
            pick = cohort_members[0]
            role = "LEGACY_SINGLETON_RECAPTURE_FOR_REPO_BYTE_MATERIALIZATION"
            singleton_recap.append(pick)
        chosen.append(
            {
                "broker_symbol": str(pick["broker_symbol"]),
                "symbol_id": int(pick["symbol_id"]),
                "peer_candidate_cohort_id": cohort_id,
                "selection_role": role,
                "history_completeness_at_selection": pick.get("history_completeness"),
                "minimum_executable_volume": pick.get("minimum_executable_volume"),
                "minimum_directional_margin_eur": pick.get("minimum_directional_margin_eur"),
                "schedule_minutes_per_week": pick.get("schedule_minutes_per_week"),
                "structural_stratum": dict(pick.get("peer_coherence_metadata") or {}),
            }
        )

    if len(fresh) != EXPECTED_FRESH_EPOCH46_REPRESENTATIVES:
        raise CaptureContractError("fresh V3 Wave0 selection does not reproduce 34 open Epoch46 cohorts")
    if len(singleton_recap) != EXPECTED_LEGACY_SINGLETON_COHORTS:
        raise CaptureContractError("V3 Wave0 does not have exactly seven legacy singleton cohorts")

    old = {(int(x["symbol_id"]), str(x["broker_symbol"])) for x in (epoch46.get("symbols") or [])}
    now = {(int(x["symbol_id"]), str(x["broker_symbol"])) for x in fresh}
    if now != old:
        raise CaptureContractError("fresh deterministic Wave0 selection no longer reproduces accepted Epoch46 outcome-blind selection")

    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "status": "FROZEN_DETERMINISTIC_OUTCOME_BLIND_V3_WAVE_00",
        "role": "DEVELOPMENT_ONLY",
        "wave_index": 0,
        "source_environment": str(feasibility["source_environment"]),
        "account_fingerprint_sha256": str(feasibility["account_fingerprint_sha256"]),
        "resolution": "M5",
        "authoritative_frontier": AUTHORITATIVE_FRONTIER,
        "structural_cohort_count": EXPECTED_COHORTS,
        "selection_law": {
            "basis": "ONE_REPRESENTATIVE_PER_STRUCTURAL_COHORT_OUTCOME_BLIND",
            "epoch45_accepted_identity_exclusion_count": len(accepted_ids),
            "fresh_cohort_rule": "exclude every current eligible identity with any accepted Epoch45 M5 scope; choose remaining identity nearest remaining-cohort capital-efficiency median; tie break lower minimum directional margin then lower symbol_id",
            "legacy_singleton_rule": "if no non-accepted identity remains, recapture the unique accepted singleton only to materialize authentic raw bytes for V3",
            "fresh_selection_must_equal_accepted_epoch46_wave01": True,
            "market_outcomes_used": False,
            "winner_identity_used": False,
        },
        "interval": {
            "start_utc": START_UTC,
            "end_utc": END_UTC,
            "weeks": 13,
        },
        "protected_forward_start": PROTECTED_FORWARD_START_UTC,
        "capture_law": {
            "read_only": True,
            "orders_permitted": False,
            "account_mutation_permitted": False,
            "forward_fill_permitted": False,
            "synthetic_fill_permitted": False,
            "protected_rows_permitted": False,
            "exhaust_pagination": True,
            "preserve_authentic_gaps": True,
            "strict_timestamp_order": True,
            "reject_conflicting_duplicates": True,
            "verify_ohlc_invariants": True,
            "window_days": 7,
        },
        "symbols": chosen,
        "source_bindings": {
            "peer_index_ref": PEER_INDEX_REL,
            "peer_index_git_blob_sha1": "0910fa14264054b4913077f5dffa74dc2569749d",
            "peer_index_sha256": _sha256_file(root, PEER_INDEX_REL),
            "epoch45_audit_ref": EPOCH45_AUDIT_REL,
            "epoch45_audit_sha256": _sha256_file(root, EPOCH45_AUDIT_REL),
            "epoch46_plan_ref": EPOCH46_PLAN_REL,
            "epoch46_plan_sha256": _sha256_file(root, EPOCH46_PLAN_REL),
            "feasibility_ref": FEASIBILITY_REL,
            "feasibility_sha256": _sha256_file(root, FEASIBILITY_REL),
        },
        "protected_forward_opened": False,
        "economic_outcomes_opened": 0,
        "strategy_returns_computed": False,
        "pnl_computed": False,
        "winner_selection_performed": False,
    }
    plan["plan_sha256"] = _canonical_hash(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan: dict[str, Any]) -> bool:
    if plan.get("schema") != PLAN_SCHEMA:
        raise CaptureContractError("wrong V3 M5 plan schema")
    if plan.get("status") != "FROZEN_DETERMINISTIC_OUTCOME_BLIND_V3_WAVE_00":
        raise CaptureContractError("V3 M5 plan is not frozen Wave0")
    if plan.get("role") != "DEVELOPMENT_ONLY" or plan.get("resolution") != "M5":
        raise CaptureContractError("V3 Wave0 is DEVELOPMENT M5 only")
    if int(plan.get("authoritative_frontier") or -1) != AUTHORITATIVE_FRONTIER:
        raise CaptureContractError("V3 Wave0 frontier mismatch")
    if int(plan.get("structural_cohort_count") or -1) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 Wave0 cohort count mismatch")
    symbols = plan.get("symbols") or []
    if len(symbols) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 Wave0 must contain exactly 41 identities")
    if len({int(x["symbol_id"]) for x in symbols}) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 Wave0 symbol IDs are not unique")
    if len({str(x["broker_symbol"]) for x in symbols}) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 Wave0 symbol names are not unique")
    if len({str(x["peer_candidate_cohort_id"]) for x in symbols}) != EXPECTED_COHORTS:
        raise CaptureContractError("V3 Wave0 cohort assignments are not unique")
    if plan.get("plan_sha256") != _canonical_hash(plan):
        raise CaptureContractError("V3 Wave0 plan hash mismatch")
    law = plan.get("capture_law") or {}
    required = {
        "read_only": True,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "forward_fill_permitted": False,
        "synthetic_fill_permitted": False,
        "protected_rows_permitted": False,
        "exhaust_pagination": True,
        "preserve_authentic_gaps": True,
        "strict_timestamp_order": True,
        "reject_conflicting_duplicates": True,
        "verify_ohlc_invariants": True,
    }
    for key, value in required.items():
        if law.get(key) is not value:
            raise CaptureContractError(f"V3 Wave0 capture law mismatch: {key}")
    if plan.get("protected_forward_opened") is not False:
        raise CaptureContractError("protected-forward state is not closed")
    if int(plan.get("economic_outcomes_opened") or 0) != 0:
        raise CaptureContractError("V3 Wave0 plan is economically contaminated")
    return True


def _copy_enriched_csv(source: Path, target: Path, broker_symbol: str, symbol_id: int) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source.open("r", encoding="utf-8", newline="") as src, target.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src)
        fields = ("broker_symbol", "symbol_id", "time_utc", "open", "high", "low", "close", "tick_volume")
        writer = csv.DictWriter(dst, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            writer.writerow(
                {
                    "broker_symbol": broker_symbol,
                    "symbol_id": symbol_id,
                    "time_utc": row["time_utc"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "tick_volume": row.get("tick_volume", "0"),
                }
            )
            count += 1
    return count


class V3PepperstoneM5Runner(FrontierDataCaptureRunner):
    def __init__(
        self,
        *,
        plan: dict[str, Any],
        client_id: str,
        client_secret: str,
        access_token: str,
        config: dict[str, Any],
        repo_root: str | Path,
        progress=print,
        transport=None,
    ):
        validate_plan(plan)
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.root = Path(repo_root)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(LIVE_HOST, LIVE_PORT, response_timeout=60)
        self.bundle = self.root / "research_core_v3_capture_output" / BUNDLE_DIR
        self.work = self.root / ".research_core_v3_capture_work" / self.plan["plan_sha256"][:16]
        self.zip_path = self.root / OUTPUT_FILENAME
        self._app = False
        self._account = None
        self._last_hist = None

    def _workflow(self) -> None:
        self.progress("[1/3] Pepperstone LIVE read-only auth + exact V3 Wave0 identity binding")
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
                accounts, account_override=int(selector(live_account_candidates(accounts)))
            )
        aid = int(account["ctidTraderAccountId"])
        self._account = aid
        if account_fingerprint(aid) != self.plan["account_fingerprint_sha256"]:
            raise MappingError("LIVE account fingerprint differs from V3 Pepperstone authority")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid, accessToken=self.access_token))
        trader = _plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName", "")).lower() and "pepperstone" not in str(
            account.get("brokerTitleShort", "")
        ).lower():
            raise MappingError("not verifiably Pepperstone")

        light = [
            _plain(x)
            for x in self._send(
                ProtoOASymbolsListReq(ctidTraderAccountId=aid, includeArchivedSymbols=False)
            ).symbol
        ]
        light_by_id = {int(x["symbolId"]): x for x in light}
        ids = [int(x["symbol_id"]) for x in self.plan["symbols"]]
        full: dict[int, dict[str, Any]] = {}
        for start in range(0, len(ids), 64):
            req = ProtoOASymbolByIdReq(ctidTraderAccountId=aid)
            req.symbolId.extend(ids[start : start + 64])
            for item in self._send(req).symbol:
                full[int(item.symbolId)] = _plain(item)
        for spec in self.plan["symbols"]:
            sid = int(spec["symbol_id"])
            name = str(spec["broker_symbol"])
            li = light_by_id.get(sid)
            fu = full.get(sid)
            if li is None or fu is None or str(li.get("symbolName")) != name:
                raise MappingError(f"V3 Wave0 identity mapping mismatch {name}/{sid}")

        self.progress("[2/3] Capturing exact 41-cohort authentic M5 DEVELOPMENT surface")
        results: list[dict[str, Any]] = []
        raw_dir = self.bundle / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        total_rows = 0
        for i, spec in enumerate(self.plan["symbols"], 1):
            sid = int(spec["symbol_id"])
            name = str(spec["broker_symbol"])
            done, meta = self._capture_one(aid, spec, full[sid])
            target = raw_dir / done.name
            copied = _copy_enriched_csv(done, target, name, sid)
            if copied != int(meta["row_count"]):
                raise CaptureContractError(f"V3 Wave0 row-count mismatch after enrichment: {name}")
            enriched = dict(meta)
            enriched["file"] = target.relative_to(self.bundle).as_posix()
            enriched["sha256"] = _sha_file(target)
            enriched["peer_candidate_cohort_id"] = spec["peer_candidate_cohort_id"]
            enriched["selection_role"] = spec["selection_role"]
            enriched["structural_stratum"] = spec["structural_stratum"]
            enriched["current_enabled_at_recapture"] = light_by_id[sid].get("enabled")
            enriched["current_trading_mode_at_recapture"] = full[sid].get("tradingMode")
            results.append(enriched)
            total_rows += copied
            self.progress(f"[SERIES {i}/{EXPECTED_COHORTS} PASS] {name} rows={copied:,}")

        payload = {
            "schema": PAYLOAD_SCHEMA,
            "status": "AUTHENTIC_PEPPERSTONE_M5_V3_WAVE_00_CAPTURE_COMPLETE",
            "tool_version": TOOL_VERSION,
            "plan_sha256": self.plan["plan_sha256"],
            "wave_index": 0,
            "source_environment": self.plan["source_environment"],
            "account_fingerprint_sha256": self.plan["account_fingerprint_sha256"],
            "resolution": "M5",
            "classification": "DEVELOPMENT_ONLY",
            "requested_interval": self.plan["interval"],
            "protected_forward_start": self.plan["protected_forward_start"],
            "requested_identity_count": len(self.plan["symbols"]),
            "total_m5_rows": total_rows,
            "series": results,
            "source_bindings": self.plan["source_bindings"],
            "orders_placed": False,
            "account_mutation": False,
            "protected_forward_opened": False,
            "economic_outcomes_opened": 0,
            "strategy_returns_computed": False,
            "pnl_computed": False,
            "winner_selection_performed": False,
        }
        payload_path = self.bundle / "V3_CAPTURE_PAYLOAD.json"
        atomic_write_json(payload_path, payload)
        manifest = build_capture_manifest(
            capture_session_id=f"research-core-v3-wave00-{self.plan['plan_sha256'][:16]}",
            capture_schema=PAYLOAD_SCHEMA,
            tool_version=TOOL_VERSION,
            account_fingerprint=self.plan["account_fingerprint_sha256"],
            source_environment=self.plan["source_environment"],
            capture_start_utc=self.plan["interval"]["start_utc"],
            capture_end_utc=self.plan["interval"]["end_utc"],
            completion_state="COMPLETE",
            canonical_payloads={"V3_CAPTURE_PAYLOAD.json": payload_path.read_bytes()},
            original_collector_package_sha256=self.config.get("collector_package_sha256"),
            read_only_assertion=True,
            economic_outcomes_opened=0,
            orders_placed=False,
            account_mutation=False,
            protected_evidence_opened=False,
        )
        atomic_write_json(self.bundle / "CAPTURE_MANIFEST.json", manifest)
        checks = []
        for path in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name != "CHECKSUMS.sha256"):
            checks.append(f"{_sha_file(path)}  {path.relative_to(self.bundle).as_posix()}")
        (self.bundle / "CHECKSUMS.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
        scan_bundle_for_secrets(self.bundle, [self.client_secret, self.access_token])

        self.progress("[3/3] Deterministic transferable V3 raw-data ZIP")
        digest = _deterministic_zip(self.bundle, self.zip_path)
        self.progress(f"[DONE] {self.zip_path.name} SHA256={digest} rows={total_rows:,}")

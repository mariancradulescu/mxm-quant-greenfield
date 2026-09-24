"""Read-only exact-scope M5 trendbar capture for the CROSSALIGN prerequisite screen."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from m6.ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    redact_text,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTrendbarsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from research_v3.broker_native_frontier_development_capture import (
    BrokerNativeFrontierDevelopmentRunner,
    _plain,
    current_symbol_state,
)

PLAN_REL = "data/CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_PLAN_V1.json"
OUTPUT_FILENAME = "MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1.zip"
BUNDLE_DIR = "MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1"
TOOL_VERSION = "MXM_CROSSALIGN_FOUR_SYMBOL_M5_ANDROID_V1"
EXPECTED_SYMBOLS = {"AUDJPY": 11, "AUS200": 117, "Brent-F": 2923, "BCHUSD": 326}


def validate_plan(plan):
    if plan.get("schema") != "mxm.greenfield.crossalign-four-symbol-m5-capture-plan.v1":
        raise CaptureContractError("wrong CROSSALIGN plan schema")
    if plan.get("status") != "FROZEN_PRE_CAPTURE_NON_ECONOMIC":
        raise CaptureContractError("CROSSALIGN plan is not frozen")
    if plan.get("resolution") != "M5":
        raise CaptureContractError("CROSSALIGN collector is M5-only")
    observed = {str(x["broker_symbol"]): int(x["symbol_id"]) for x in plan.get("symbols") or []}
    if observed != EXPECTED_SYMBOLS:
        raise CaptureContractError("CROSSALIGN exact symbol identity drift")
    if plan.get("fields") != [
        "timestamp_utc", "open", "high", "low", "close", "tick_volume"
    ]:
        raise CaptureContractError("CROSSALIGN fields must be single-price trendbar fields")
    law = plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False:
        raise CaptureContractError("CROSSALIGN collector is not read-only")
    if law.get("account_mutation_permitted") is not False or law.get("synthetic_fill_permitted") is not False:
        raise CaptureContractError("CROSSALIGN mutation/fill law drift")
    if plan.get("economic_outcomes_opened") != 0 or plan.get("v2_attempts_consumed") != 0:
        raise CaptureContractError("CROSSALIGN plan is economically contaminated")
    return True


class CrossAlignmentCaptureRunner(BrokerNativeFrontierDevelopmentRunner):
    """Reuse only the proven pagination primitive; all scope and output bindings are local."""

    def __init__(self, *, plan, client_id, client_secret, access_token, config,
                 repo_root, progress=print, transport=None):
        validate_plan(plan)
        self.plan = dict(plan)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.config = dict(config)
        self.root = Path(repo_root)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(
            LIVE_HOST, LIVE_PORT, response_timeout=60
        )
        self.bundle = self.root / "crossalign_capture_output" / BUNDLE_DIR
        self.work = self.root / ".crossalign_capture_work"
        self.zip_path = self.root / OUTPUT_FILENAME
        self._app = False
        self._account = None
        self._last_hist = None

    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only account binding")
        self._send(ProtoOAApplicationAuthReq(
            clientId=self.client_id, clientSecret=self.client_secret
        ))
        self._app = True
        accounts = [
            _plain(x) for x in self._send(
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
            raise MappingError("LIVE account fingerprint differs from accepted account")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid, accessToken=self.access_token))
        trader = _plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName", "")).lower() and \
                "pepperstone" not in str(account.get("brokerTitleShort", "")).lower():
            raise MappingError("not verifiably Pepperstone")

        light = {
            int(x["symbolId"]): x for x in [
                _plain(y) for y in self._send(
                    ProtoOASymbolsListReq(
                        ctidTraderAccountId=aid, includeArchivedSymbols=False
                    )
                ).symbol
            ]
        }
        ids = [int(x["symbol_id"]) for x in self.plan["symbols"]]
        query = ProtoOASymbolByIdReq(ctidTraderAccountId=aid)
        query.symbolId.extend(ids)
        full = {int(x.symbolId): _plain(x) for x in self._send(query).symbol}
        states = {}
        for spec in self.plan["symbols"]:
            state = current_symbol_state(spec, light.get(int(spec["symbol_id"])),
                                         full.get(int(spec["symbol_id"])))
            states[int(spec["symbol_id"])] = state

        self.progress("[2/3] Capturing exact four-symbol M5 trendbars")
        raw_dir = self.bundle / "raw"
        raw_dir.mkdir(parents=True)
        results = []
        for spec in self.plan["symbols"]:
            sid = int(spec["symbol_id"])
            name = str(spec["broker_symbol"])
            state = states[sid]
            if not state["current_mapping_available"]:
                results.append({
                    "broker_symbol": name, "symbol_id": sid, "resolution": "M5",
                    "requested_interval": self.plan["interval"],
                    "capture_status": "CURRENT_MAPPING_UNAVAILABLE_NO_REQUEST",
                    "row_count": 0, "current_symbol_state": state,
                    "synthetic_fill": False, "forward_fill": False,
                })
                continue
            try:
                source, meta = self._capture_one(
                    aid, spec, full[sid], state
                )
                destination = raw_dir / source.name
                shutil.copyfile(source, destination)
                meta = dict(meta)
                meta["file"] = destination.relative_to(self.bundle).as_posix()
                results.append(meta)
            except Exception as exc:
                results.append({
                    "broker_symbol": name, "symbol_id": sid, "resolution": "M5",
                    "requested_interval": self.plan["interval"],
                    "capture_status": "SERIES_CAPTURE_ERROR_RETRYABLE",
                    "row_count": 0, "current_symbol_state": state,
                    "error_type": type(exc).__name__, "error": redact_text(str(exc)),
                    "synthetic_fill": False, "forward_fill": False,
                })

        manifest = {
            "schema": "mxm.greenfield.crossalign-four-symbol-m5-bundle.v1",
            "status": ("CAPTURE_COMPLETE_NON_ECONOMIC" if all(
                x.get("capture_status") == "SERIES_CAPTURE_COMPLETE" for x in results
            ) else "CAPTURE_INCOMPLETE_RETRYABLE"),
            "tool_version": TOOL_VERSION,
            "plan_ref": PLAN_REL,
            "resolution": "M5",
            "requested_interval": self.plan["interval"],
            "series": results,
            "series_summary": {
                "planned": len(self.plan["symbols"]),
                "completed": sum(x.get("capture_status") == "SERIES_CAPTURE_COMPLETE"
                                 for x in results),
                "retryable_errors": sum(x.get("capture_status") == "SERIES_CAPTURE_ERROR_RETRYABLE"
                                        for x in results),
            },
            "bid_ask_transferred": False,
            "returns_computed": False,
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "orders_placed": False,
            "account_mutation": False,
            "protected_evidence_opened": False,
        }
        atomic_write_json(self.bundle / "capture_manifest.json", manifest)
        checksums = []
        for path in sorted(x for x in self.bundle.rglob("*") if x.is_file()):
            checksums.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
                f"{path.relative_to(self.bundle).as_posix()}"
            )
        (self.bundle / "CHECKSUMS.sha256").write_text("\n".join(checksums) + "\n")
        scan_bundle_for_secrets(self.bundle)
        from competition.frontier_data_capture import _deterministic_zip
        _deterministic_zip(self.bundle, self.zip_path)

    def run(self):
        self.work.mkdir(parents=True, exist_ok=True)
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True)
        self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect()
            self._workflow()
        finally:
            self.transport.close()
        return self.zip_path

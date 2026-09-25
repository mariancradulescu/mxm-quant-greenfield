"""Read-only 3-symbol M5 DEVELOPMENT capture for Epoch22 replacement representatives."""
from __future__ import annotations
import hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path

from competition.frontier_data_capture import (
    FrontierDataCaptureRunner,_deterministic_zip,_plain,_sha_file,_utc,canonical_plan_sha
)
from m6.ctrader_capture import (
    CaptureContractError,MappingError,account_fingerprint,atomic_write_json,
    live_account_candidates,scan_bundle_for_secrets,select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAGetAccountListByAccessTokenReq,
    ProtoOASymbolByIdReq,ProtoOASymbolsListReq,ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest

PLAN_REL="data/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_PLAN_EPOCH22_V1.json"
OUTPUT_FILENAME="MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip"
BUNDLE_DIR="MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1"
TOOL_VERSION="MXM_CURRENT_FRONTIER_REPLACEMENT_M5_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="a573cbcf19897c50f9ae2ad971dc308529578604c583d57d2e836906b0c25b5f"
EXPECTED_IDENTITIES=(("CXMT.CN-PERP",7427),("ERICB.SE",5352),("XAUUSD-F",2924))

def validate_plan(plan):
    if plan.get("schema")!="mxm.greenfield.current-frontier-replacement-development-m5-plan.v1":
        raise CaptureContractError("wrong replacement development plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_NON_ECONOMIC":
        raise CaptureContractError("replacement plan is not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA:
        raise CaptureContractError("replacement plan hash mismatch")
    if plan.get("resolution")!="M5":raise CaptureContractError("replacement capture is M5-only")
    got=tuple(sorted((str(x["broker_symbol"]),int(x["symbol_id"])) for x in plan.get("symbols") or []))
    if got!=tuple(sorted(EXPECTED_IDENTITIES)):
        raise CaptureContractError("replacement capture must contain the exact three frozen identities")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0 or plan.get("protected_evidence_opened") is not False:
        raise CaptureContractError("replacement plan is economically contaminated")
    start=_utc(plan["interval"]["start_utc"]);end=_utc(plan["interval"]["end_utc"]);protected=_utc(plan["protected_forward_start"])
    if not start<end<protected:raise CaptureContractError("replacement development interval/protected boundary invalid")
    law=plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False or law.get("account_mutation_permitted") is not False:
        raise CaptureContractError("replacement capture law is not read-only")
    return True

class CurrentFrontierReplacementDevelopmentRunner(FrontierDataCaptureRunner):
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan)
        self.plan=dict(plan);self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token
        self.config=dict(config);self.root=Path(repo_root);self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"current_frontier_replacement_output"/BUNDLE_DIR
        self.work=self.root/".current_frontier_replacement_work"/EXPECTED_PLAN_SHA[:16]
        self.zip_path=self.root/OUTPUT_FILENAME;self._app=False;self._account=None;self._last_hist=None

    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only auth + frozen identity binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]);self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]:
            raise MappingError("LIVE account fingerprint differs from Epoch22 accepted broker authority")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]
        L={int(x["symbolId"]):x for x in light};ids=[int(x["symbol_id"]) for x in self.plan["symbols"]];full={}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend(ids)
        for x in self._send(q).symbol:full[int(x.symbolId)]=_plain(x)
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]);name=spec["broker_symbol"];li=L.get(sid);fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name:raise MappingError(f"replacement mapping mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:raise MappingError(f"replacement identity no longer new-entry tradable: {name}")

        self.progress("[2/3] Capturing frozen 13-week M5 interval for 3 replacement representatives")
        results=[];raw_dir=self.bundle/"raw";raw_dir.mkdir(parents=True,exist_ok=True)
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])])
            target=raw_dir/done.name;shutil.copyfile(done,target);meta=dict(meta);meta["file"]=target.relative_to(self.bundle).as_posix();results.append(meta)
            self.progress(f"[SERIES {i}/3 PASS] {spec['broker_symbol']} rows={meta['row_count']:,}")
        captured_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        manifest={
            "schema":"mxm.greenfield.current-frontier-replacement-m5-bundle.v1",
            "status":"M5_REPLACEMENT_DEVELOPMENT_CAPTURE_COMPLETE",
            "captured_utc":captured_utc,"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,
            "selection_ref":self.plan["selection_ref"],"current_structural_registry_ref":self.plan["current_structural_registry_ref"],
            "canonical_current_broker_payload_sha256":self.plan["canonical_current_broker_payload_sha256"],
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],
            "resolution":"M5","requested_interval":self.plan["interval"],"series":results,
            "orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0
        }
        payload_path=self.bundle/"capture_manifest.json";atomic_write_json(payload_path,manifest)
        identity_manifest=build_capture_manifest(
            capture_session_id=f"epoch22-replacement-{EXPECTED_PLAN_SHA[:16]}",
            capture_schema=manifest["schema"],tool_version=TOOL_VERSION,
            account_fingerprint=self.plan["account_fingerprint_sha256"],source_environment=self.plan["source_environment"],
            capture_start_utc=self.plan["interval"]["start_utc"],capture_end_utc=captured_utc,completion_state="COMPLETE",
            canonical_payloads={"capture_manifest.json":payload_path.read_bytes()},
            original_collector_package_sha256=None,read_only_assertion=True,economic_outcomes_opened=0,
            orders_placed=False,account_mutation=False,protected_evidence_opened=False
        )
        atomic_write_json(self.bundle/"CAPTURE_MANIFEST.json",identity_manifest)
        checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"):
            checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        self.progress("[3/3] Deterministic transferable ZIP")
        digest=_deterministic_zip(self.bundle,self.zip_path)
        self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")

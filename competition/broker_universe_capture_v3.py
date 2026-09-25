"""Resumable read-only exhaustive CURRENT Pepperstone universe capture.

V3 preserves the V2 payload schema but adds transport-independent CAPTURE_MANIFEST,
time-based heartbeat progress, and local fail-closed process-level resume.
"""
from __future__ import annotations
import hashlib,json,math,shutil,time,uuid
from pathlib import Path
from datetime import datetime,timezone
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict
from competition.broker_universe_capture import (
    OUTPUT_FILENAME,STARTING_CAPITAL_EUR,FEASIBLE,INFEASIBLE,UNRESOLVED,
    _plain,_zip,account_execution_semantics,classify_direction,coverage_bucket,
    directional_summary,entry_eligibility,product_type,schedule_minutes_per_week,
)
from competition.capture_runtime import (
    CaptureCheckpoint,CaptureProgress,CaptureResumeError,CONTRACT_VERSION,
    canonical_hash,new_checkpoint,validate_resume,utc_now,
)
from research_v3.capture_identity import build_capture_manifest, canonical_json_bytes, sha256_bytes
from m6.ctrader_capture import (
    CaptureContractError,MappingError,account_fingerprint,atomic_write_json,
    live_account_candidates,redact_text,require_read_only_request,scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAAssetClassListReq,
    ProtoOAAssetListReq,ProtoOAExpectedMarginReq,ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetDynamicLeverageByIDReq,ProtoOAMarginCallListReq,ProtoOASymbolByIdReq,
    ProtoOASymbolCategoryListReq,ProtoOASymbolsListReq,ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport

TOOL_VERSION="MXM_COMPETITION_BROKER_UNIVERSE_ANDROID_STDLIB_V3"
COLLECTOR_SCHEMA_VERSION="broker-universe-resumable-v3"
PAYLOAD_SCHEMA="mxm.greenfield.v2.broker-native-competition-universe-capture.v2"
PAYLOAD_STATUS="CURRENT_ACCOUNT_NATIVE_EXHAUSTIVE_READ_ONLY_CAPTURE_DIRECTIONAL"
COHERENCE_TOLERANCE_SECONDS=3600
METADATA_BATCH_SIZE=64
CHECKPOINT_EVERY_MARGIN_ROWS=10

def _read_json(path:Path,default):
    if not path.is_file():return default
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:raise CaptureResumeError(f"corrupt partial state: {path.name}") from exc

def _write_partial(path:Path,value:Any)->str:
    atomic_write_json(path,value)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def remaining_ids(all_ids,completed_ids):
    completed={int(x) for x in completed_ids}
    return [int(x) for x in all_ids if int(x) not in completed]

def merge_partial_rows(existing:Mapping[str,Any],fresh:Mapping[str,Any])->dict[str,Any]:
    out={str(k):v for k,v in existing.items()}
    for k,v in fresh.items():
        k=str(k)
        if k in out and out[k]!=v:raise CaptureResumeError(f"conflicting resumed row for {k}")
        out[k]=v
    return out

def symbol_universe_hash(light)->str:
    rows=sorted(
        (int(x.get("symbolId") or 0),str(x.get("symbolName") or ""),x.get("enabled"))
        for x in light
    )
    return canonical_hash(rows)

class BrokerUniverseCaptureRunnerV3:
    def __init__(self,*,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None,clock=time.monotonic):
        self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token;self.config=dict(config)
        self.root=Path(repo_root);self.emit=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.out=self.root/"competition_broker_capture_output"/"MXM_COMPETITION_BROKER_UNIVERSE_V2"
        self.work=self.root/".competition_broker_universe_work_v3"
        self.zip_path=self.root/OUTPUT_FILENAME
        self.checkpoints=CaptureCheckpoint(self.work/"CAPTURE_CHECKPOINT.json")
        self.progress=CaptureProgress(progress,heartbeat_seconds=float(self.config.get("capture_heartbeat_seconds",15.0)),clock=clock)
        self._app=False;self._account=None;self._resume_doc=None;self._capture_start_utc=None

    def _request(self,request):
        require_read_only_request(type(request).__name__)
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            raise CaptureContractError(f"cTrader API error: {getattr(response,'errorCode','UNKNOWN')}")
        self.progress.success()
        return response

    def _restore(self):
        self.transport.connect();self.progress.reconnect()
        if self._app:self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))

    def _send(self,request,retries=3):
        last=None
        for n in range(retries):
            try:return self._request(request)
            except Exception as exc:
                last=exc;self.progress.retry()
                if n+1==retries:break
                time.sleep(min(4.0,2**n))
                try:self.transport.close();self._restore()
                except Exception as restore_exc:last=restore_exc
        raise CaptureContractError(f"{type(request).__name__} failed: {redact_text(str(last))}")

    def _save_checkpoint(self,doc,*,partial_hashes=None):
        doc=dict(doc);doc["retry_count"]=self.progress.retry_count;doc["reconnect_count"]=self.progress.reconnect_count
        doc["last_checkpoint_epoch"]=time.time()
        if partial_hashes:doc.setdefault("partial_payload_hashes",{}).update(partial_hashes)
        self.checkpoints.save(doc);self._resume_doc=doc

    def _init_or_resume(self,*,fingerprint,universe_hash):
        prior=self.checkpoints.load()
        if prior is None:
            doc=new_checkpoint(
                capture_session_id=str(uuid.uuid4()),collector_schema_version=COLLECTOR_SCHEMA_VERSION,
                tool_version=TOOL_VERSION,capture_contract_version=CONTRACT_VERSION,
                account_fingerprint=fingerprint,capture_start_utc=utc_now(),
                observed_symbol_universe_hash=universe_hash,
            )
            self._save_checkpoint(doc);self._capture_start_utc=doc["capture_start_utc"]
            return doc,{"resume_allowed":False,"refresh_time_sensitive_expected_margin":False}
        decision=validate_resume(
            prior,account_fingerprint=fingerprint,collector_schema_version=COLLECTOR_SCHEMA_VERSION,
            tool_version=TOOL_VERSION,capture_contract_version=CONTRACT_VERSION,
            observed_symbol_universe_hash=universe_hash,
            coherence_tolerance_seconds=int(self.config.get("capture_coherence_tolerance_seconds",COHERENCE_TOLERANCE_SECONDS)),
        )
        self._capture_start_utc=prior["capture_start_utc"];self._resume_doc=dict(prior)
        self.emit(f"[RESUME] session={prior['capture_session_id']} decision={decision['reason']}")
        return dict(prior),decision

    def run(self):
        self.work.mkdir(parents=True,exist_ok=True)
        self.zip_path.unlink(missing_ok=True)
        try:self.transport.connect();self._workflow()
        finally:self.transport.close()
        return self.zip_path

    def _workflow(self):
        self.progress.configure("auth_account_setup",6,substage="application auth")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True;self.progress.update(1)
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount];self.progress.update(2)
        saved=self.config.get("ctid_trader_account_id")
        try:account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]);self._account=aid;fingerprint=account_fingerprint(aid);self.progress.update(3)
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token));self.progress.update(4)
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader);self.progress.update(5)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        try:margin_calls={"state":"CAPTURED","items":[_plain(x) for x in self._send(ProtoOAMarginCallListReq(ctidTraderAccountId=aid)).marginCall]}
        except Exception as exc:margin_calls={"state":"UNRESOLVED","items":[],"reason":redact_text(str(exc))}
        self.progress.update(6);self.progress.mark_phase_complete()

        self.progress.configure("symbol_list_acquisition",4,substage="asset classes and current symbols")
        assets=[_plain(x) for x in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset];self.progress.update(1)
        classes=[_plain(x) for x in self._send(ProtoOAAssetClassListReq(ctidTraderAccountId=aid)).assetClass];self.progress.update(2)
        categories=[_plain(x) for x in self._send(ProtoOASymbolCategoryListReq(ctidTraderAccountId=aid)).symbolCategory];self.progress.update(3)
        sr=self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=True))
        light=[_plain(x) for x in sr.symbol];archived=[_plain(x) for x in getattr(sr,"archivedSymbol",[])];self.progress.update(4);self.progress.mark_phase_complete()
        universe_hash=symbol_universe_hash(light)
        cp,resume=self._init_or_resume(fingerprint=fingerprint,universe_hash=universe_hash)

        ids=sorted({int(x["symbolId"]) for x in light if x.get("symbolId") is not None})
        full_path=self.work/"full_symbol_metadata.json";full={int(k):v for k,v in _read_json(full_path,{}).items()}
        completed_meta={int(x) for x in cp.get("completed_symbol_ids") or []}
        batches=math.ceil(len(ids)/METADATA_BATCH_SIZE)
        self.progress.configure("detailed_symbol_metadata_batches",batches,completed=len(completed_meta)//METADATA_BATCH_SIZE,substage="ProtoOASymbolById")
        done_batches=set(int(x) for x in cp.get("completed_symbol_metadata_batches") or [])
        for bi,start in enumerate(range(0,len(ids),METADATA_BATCH_SIZE)):
            batch=ids[start:start+METADATA_BATCH_SIZE]
            if bi in done_batches and all(x in full for x in batch):
                self.progress.update(bi+1,current_identifier=f"batch:{bi}:reused")
                continue
            q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend(batch)
            got={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
            if any(x not in got for x in batch):raise CaptureContractError(f"metadata batch {bi} incomplete")
            full.update(got);done_batches.add(bi);completed_meta.update(batch)
            h=_write_partial(full_path,{str(k):full[k] for k in sorted(full)})
            cp["active_phase"]="DETAILED_SYMBOL_METADATA";cp["completed_symbol_metadata_batches"]=sorted(done_batches);cp["completed_symbol_ids"]=sorted(completed_meta)
            self._save_checkpoint(cp,partial_hashes={"full_symbol_metadata.json":h})
            self.progress.update(bi+1,current_identifier=f"batch:{bi}")
        self.progress.mark_phase_complete()

        A={str(x.get("assetId")):x for x in assets};C={str(x.get("id")):x for x in classes};G={str(x.get("id")):x for x in categories}
        account_ccy=str((A.get(str(trader.get("depositAssetId"))) or {}).get("name") or "UNKNOWN").upper()
        account_semantics=account_execution_semantics(trader,account_ccy,margin_calls)
        accessible_ids=[]
        leverage_ids=set()
        light_by_id={int(x.get("symbolId") or 0):x for x in light}
        for sid in ids:
            f=full.get(sid,{})
            if f.get("leverageId") is not None:leverage_ids.add(int(f["leverageId"]))
            buy_ok,sell_ok=entry_eligibility(light_by_id[sid],f)
            if buy_ok is True and f.get("minVolume") is not None and int(f["minVolume"])>0:accessible_ids.append(sid)

        margins_path=self.work/"expected_margins.json";margins={int(k):v for k,v in _read_json(margins_path,{}).items()}
        completed_margin={int(x) for x in cp.get("completed_expected_margin_symbol_ids") or []}
        if resume.get("refresh_time_sensitive_expected_margin"):
            margins={};completed_margin=set()
            margins_path.unlink(missing_ok=True)
            cp["completed_expected_margin_symbol_ids"]=[]
        self.progress.configure("expected_margin_identities",len(accessible_ids),completed=len(completed_margin),substage="directional min-volume ExpectedMargin")
        for pos,sid in enumerate(accessible_ids,1):
            if sid in completed_margin and sid in margins:
                self.progress.update(pos,current_identifier=sid);continue
            f=full[sid];mv=int(f["minVolume"]);buy_ok,sell_ok=entry_eligibility(light_by_id[sid],f)
            try:
                q=ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,symbolId=sid);q.volume.append(mv);r=self._send(q)
                raw=[_plain(x) for x in r.margin];digits=int(getattr(r,"moneyDigits",0) or 0);row=raw[0] if raw else {}
                buy=float(row["buyMargin"])/(10**digits) if row.get("buyMargin") is not None and account_ccy=="EUR" else None
                sell=float(row["sellMargin"])/(10**digits) if row.get("sellMargin") is not None and account_ccy=="EUR" else None
                m={"state":"CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT","volume_cents":mv,"money_digits":digits,"raw_margin":raw,
                   "buy_margin_eur":buy,"sell_margin_eur":sell,"buy_margin_pct_eur200":round(buy/2,6) if buy is not None else None,
                   "sell_margin_pct_eur200":round(sell/2,6) if sell is not None else None,
                   "buy_feasibility":classify_direction(buy,buy_ok),"sell_feasibility":classify_direction(sell,sell_ok)}
                m["directional_summary"]=directional_summary(m["buy_feasibility"],m["sell_feasibility"]);margins[sid]=m
            except Exception as exc:
                margins[sid]={"state":"BROKER_OR_MARGIN_UNRESOLVED","reason":redact_text(str(exc)),"volume_cents":mv,
                              "buy_feasibility":UNRESOLVED,"sell_feasibility":classify_direction(None,sell_ok),"directional_summary":"UNRESOLVED"}
            completed_margin.add(sid)
            if pos%CHECKPOINT_EVERY_MARGIN_ROWS==0 or pos==len(accessible_ids):
                h=_write_partial(margins_path,{str(k):margins[k] for k in sorted(margins)})
                cp["active_phase"]="EXPECTED_MARGIN";cp["completed_expected_margin_symbol_ids"]=sorted(completed_margin)
                self._save_checkpoint(cp,partial_hashes={"expected_margins.json":h})
            self.progress.update(pos,current_identifier=sid)
        self.progress.mark_phase_complete()

        for sid in ids:
            if sid in margins:continue
            f=full.get(sid,{});buy_ok,sell_ok=entry_eligibility(light_by_id[sid],f);mv=f.get("minVolume")
            margins[sid]={"state":"NOT_REQUESTED_NO_CURRENT_NEW_ENTRY_OR_NO_MIN_VOLUME","volume_cents":mv,
                          "buy_feasibility":classify_direction(None,buy_ok),"sell_feasibility":classify_direction(None,sell_ok)}
            margins[sid]["directional_summary"]=directional_summary(margins[sid]["buy_feasibility"],margins[sid]["sell_feasibility"])

        lev_path=self.work/"dynamic_leverage.json";lev=_read_json(lev_path,{})
        completed_lev={int(x) for x in cp.get("completed_leverage_ids") or []}
        if resume.get("refresh_time_sensitive_expected_margin"):
            lev={};completed_lev=set();lev_path.unlink(missing_ok=True)
        self.progress.configure("leverage_ids",len(leverage_ids),completed=len(completed_lev),substage="dynamic leverage")
        for pos,lid in enumerate(sorted(leverage_ids),1):
            if lid in completed_lev and str(lid) in lev:self.progress.update(pos,current_identifier=lid);continue
            try:lev[str(lid)]=_plain(self._send(ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=aid,leverageId=lid)).leverage)
            except Exception as exc:lev[str(lid)]={"state":"UNRESOLVED","reason":redact_text(str(exc))}
            completed_lev.add(lid);h=_write_partial(lev_path,lev);cp["active_phase"]="LEVERAGE";cp["completed_leverage_ids"]=sorted(completed_lev);self._save_checkpoint(cp,partial_hashes={"dynamic_leverage.json":h})
            self.progress.update(pos,current_identifier=lid)
        self.progress.mark_phase_complete()

        self.progress.configure("final_validation",1,substage="assemble and validate canonical payload")
        directional_counts={"BUY":{FEASIBLE:0,INFEASIBLE:0,UNRESOLVED:0},"SELL":{FEASIBLE:0,INFEASIBLE:0,UNRESOLVED:0},"SUMMARY":{"BOTH_FEASIBLE":0,"BUY_ONLY":0,"SELL_ONLY":0,"NEITHER_FEASIBLE":0,"UNRESOLVED":0}}
        records=[];accessible=0
        for item in sorted(light,key=lambda x:int(x.get("symbolId") or 0)):
            sid=int(item.get("symbolId") or 0);f=full.get(sid,{})
            cat=G.get(str(item.get("symbolCategoryId")),{})
            aclass=(C.get(str(cat.get("assetClassId"))) or {}).get("name")
            name=str(item.get("symbolName") or "");minutes=schedule_minutes_per_week(f.get("schedule") or [])
            buy_ok,sell_ok=entry_eligibility(item,f)
            if buy_ok is True or sell_ok is True:accessible+=1
            m=margins.get(sid,{"state":"BROKER_OR_MARGIN_UNRESOLVED","buy_feasibility":UNRESOLVED,"sell_feasibility":UNRESOLVED,"directional_summary":"UNRESOLVED"})
            buy_state=m.get("buy_feasibility",classify_direction(m.get("buy_margin_eur"),buy_ok));sell_state=m.get("sell_feasibility",classify_direction(m.get("sell_margin_eur"),sell_ok));summary=directional_summary(buy_state,sell_state)
            directional_counts["BUY"][buy_state]+=1;directional_counts["SELL"][sell_state]+=1;directional_counts["SUMMARY"][summary]+=1
            quote=(A.get(str(item.get("quoteAssetId"))) or {}).get("name")
            records.append({
                "symbol_id":sid,"broker_symbol":name,"description":item.get("description"),"asset_class":aclass,"product_type":product_type(name,aclass),
                "base_asset":(A.get(str(item.get("baseAssetId"))) or {}).get("name"),"quote_asset":quote,"enabled":item.get("enabled"),"trading_mode":f.get("tradingMode"),
                "buy_eligible_current":buy_ok,"enable_short_selling":f.get("enableShortSelling"),"sell_eligible_current":sell_ok,
                "buy_feasibility":buy_state,"sell_feasibility":sell_state,"directional_feasibility_summary":summary,
                "min_volume_cents":f.get("minVolume"),"step_volume_cents":f.get("stepVolume"),"max_volume_cents":f.get("maxVolume"),"max_exposure":f.get("maxExposure"),
                "lot_size":f.get("lotSize"),"pip_position":f.get("pipPosition"),"digits":f.get("digits"),"measurement_units":f.get("measurementUnits"),
                "commission_type":f.get("commissionType"),"commission":f.get("commission"),"precise_trading_commission_rate":f.get("preciseTradingCommissionRate"),
                "min_commission":f.get("minCommission"),"precise_min_commission":f.get("preciseMinCommission"),"min_commission_type":f.get("minCommissionType"),"min_commission_asset":f.get("minCommissionAsset"),
                "pnl_conversion_fee_rate":f.get("pnlConversionFeeRate"),"quote_matches_deposit_currency":None if quote is None or account_ccy=="UNKNOWN" else str(quote).upper()==account_ccy,
                "swap_long":f.get("swapLong"),"swap_short":f.get("swapShort"),"swap_calculation_type":f.get("swapCalculationType"),"swap_rollover_3_days":f.get("swapRollover3Days"),
                "rollover_commission":f.get("rolloverCommission"),"rollover_commission_3_days":f.get("rolloverCommission3Days"),"skip_rollover_days":f.get("skipRolloverDays"),
                "swap_period":f.get("swapPeriod"),"swap_time":f.get("swapTime"),"skip_swap_periods":f.get("skipSWAPPeriods"),"charge_swap_at_weekends":f.get("chargeSwapAtWeekends"),
                "guaranteed_stop_loss":f.get("guaranteedStopLoss"),"schedule_time_zone":f.get("scheduleTimeZone"),"schedule":f.get("schedule") or [],"holiday":f.get("holiday") or [],
                "schedule_minutes_per_week":minutes,"coverage_bucket":coverage_bucket(minutes),"leverage_id":f.get("leverageId"),
                "dynamic_leverage":lev.get(str(f.get("leverageId"))) if f.get("leverageId") is not None else None,
                "expected_margin_at_min_volume":m,
            })
        if len({x["symbol_id"] for x in records})!=len(records) or len({x["broker_symbol"] for x in records})!=len(records):
            raise CaptureContractError("duplicate current broker identity detected during final validation")
        unresolved_accessible=sum(1 for x in records if (x["buy_eligible_current"] or x["sell_eligible_current"]) and x["expected_margin_at_min_volume"].get("state")!="CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT")
        if unresolved_accessible:raise CaptureContractError(f"accessible ExpectedMargin incomplete: {unresolved_accessible}")
        capture_end=utc_now()
        artifact={"schema":PAYLOAD_SCHEMA,"status":PAYLOAD_STATUS,"captured_utc":capture_end,"capture_start_utc":self._capture_start_utc,"tool_version":TOOL_VERSION,
                  "source_environment":"Pepperstone - Europe LIVE","account_fingerprint_sha256":fingerprint,"account_currency":account_ccy,"starting_capital_eur":STARTING_CAPITAL_EUR,
                  "full_account_current_symbol_inventory_claimed":True,"current_symbol_count":len(light),"current_new_entry_accessible_count":accessible,"archived_symbol_count":len(archived),
                  "directional_classification_counts_all_current_symbols":directional_counts,"account_execution_semantics":account_semantics,
                  "symbols":records,"archived_symbols":archived,"asset_classes":classes,"symbol_categories":categories,"assets":assets,"dynamic_leverage_by_id":lev,
                  "historical_margin_authority_claimed":False,"economic_outcomes_opened":0,"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False}
        self.progress.update(1);self.progress.mark_phase_complete()

        if self.out.exists():shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        payload_path=self.out/"BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json";atomic_write_json(payload_path,artifact)
        payload_bytes=payload_path.read_bytes()
        manifest=build_capture_manifest(
            capture_session_id=cp["capture_session_id"],capture_schema=PAYLOAD_SCHEMA,tool_version=TOOL_VERSION,
            account_fingerprint=fingerprint,source_environment="Pepperstone - Europe LIVE",
            capture_start_utc=self._capture_start_utc,capture_end_utc=capture_end,completion_state="COMPLETE",
            canonical_payloads={payload_path.name:payload_bytes},
            original_collector_package_sha256=self.config.get("collector_package_sha256"),
            read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,account_mutation=False,protected_evidence_opened=False,
        )
        atomic_write_json(self.out/"CAPTURE_MANIFEST.json",manifest)

        self.progress.configure("secret_scan",1,substage="final transferable secret scan")
        scan_bundle_for_secrets(self.out,[self.client_secret,self.access_token]);self.progress.update(1);self.progress.mark_phase_complete()
        self.progress.configure("deterministic_packaging",1,substage="deterministic ZIP")
        digest=_zip(self.out,self.zip_path);self.progress.update(1)
        cp["active_phase"]="COMPLETE";cp["completion_state"]="COMPLETE";cp["capture_end_utc"]=capture_end
        cp["canonical_payload_sha256"]=sha256_bytes(payload_bytes);cp["final_zip_sha256"]=digest
        self._save_checkpoint(cp)
        self.progress.mark_finalized()
        self.emit(f"[DONE] {self.zip_path.name} SHA256={digest} canonical_payload_sha256={cp['canonical_payload_sha256']}")

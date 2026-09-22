"""One read-only exhaustive CURRENT Pepperstone symbol/margin capture for competition architecture."""
from __future__ import annotations
import hashlib,json,shutil,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from m6.ctrader_capture import CaptureContractError,MappingError,account_fingerprint,atomic_write_json,live_account_candidates,redact_text,require_read_only_request,scan_bundle_for_secrets,select_live_pepperstone_account
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAAssetClassListReq,ProtoOAAssetListReq,ProtoOAExpectedMarginReq,ProtoOAGetAccountListByAccessTokenReq,ProtoOAGetDynamicLeverageByIDReq,ProtoOASymbolByIdReq,ProtoOASymbolCategoryListReq,ProtoOASymbolsListReq,ProtoOATraderReq
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport

OUTPUT_FILENAME="MXM_COMPETITION_BROKER_UNIVERSE_V1.zip"
TOOL_VERSION="MXM_COMPETITION_BROKER_UNIVERSE_ANDROID_STDLIB_V1"
STARTING_CAPITAL_EUR=200.0

def _plain(m): return MessageToDict(m,preserving_proto_field_name=False,use_integers_for_enums=True)
def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def _zip(root,target):
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(x for x in root.rglob("*") if x.is_file()):
            i=zipfile.ZipInfo(p.relative_to(root).as_posix(),(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o644<<16
            z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return _sha(target)

def schedule_minutes_per_week(schedule):
    if not schedule:return None
    total=0
    for x in schedule:
        try:a,b=int(x["startSecond"]),int(x["endSecond"])
        except (KeyError,TypeError,ValueError):return None
        if b<a:return None
        total+=b-a+1
    return round(total/60.0,3)

def coverage_bucket(m):
    if m is None:return "UNKNOWN"
    if m>=8500:return "NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE"
    if m>=6000:return "NEAR_24X5_MULTI_SESSION_SCHEDULE"
    if m>=3500:return "EXTENDED_MULTI_SESSION_SCHEDULE"
    return "REGIONAL_OR_CASH_SESSION_SCHEDULE"

def classify_margin(buy,sell):
    if buy is None or sell is None or buy<0 or sell<0:return "BROKER_OR_MARGIN_UNRESOLVED"
    return "EUR200_MIN_VOLUME_FEASIBLE" if max(buy,sell)<=STARTING_CAPITAL_EUR else "EUR200_MIN_VOLUME_INFEASIBLE"

def product_type(name,aclass):
    a=aclass or "UNKNOWN"
    if name.endswith("-24"):return "EXTENDED_HOURS_SHARE_CFD"
    if name.endswith("-F"):return "FORWARD_OR_FUTURES_STYLE_CFD"
    if "Perpetual" in a or "PERP" in name.upper():return "PERPETUAL_CFD"
    return {"Forex (Spot)":"FX_SPOT_OR_MARGIN_CFD","Indices (Spot)":"CASH_INDEX_CFD","Metals (Spot)":"SPOT_METAL_CFD","Energies (Spot)":"SPOT_ENERGY_CFD","Crypto Currency (Spot)":"SPOT_CRYPTO_CFD","US Equities":"STANDARD_CASH_SHARE_CFD","GB Equities":"STANDARD_CASH_SHARE_CFD","AU Equities":"STANDARD_CASH_SHARE_CFD","ETFs":"ETF_CFD"}.get(a,"OTHER_OR_TEST_CFD")

class BrokerUniverseCaptureRunner:
    def __init__(self,*,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token; self.config=dict(config)
        self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.out=self.root/"competition_broker_capture_output"/"MXM_COMPETITION_BROKER_UNIVERSE_V1"
        self.zip_path=self.root/OUTPUT_FILENAME; self._app=False; self._account=None
    def _request(self,r):
        require_read_only_request(type(r).__name__)
        x=self.transport.request(r,timeout=60)
        if type(x).__name__=="ProtoOAErrorRes":raise CaptureContractError(f"cTrader API error: {getattr(x,'errorCode','UNKNOWN')}")
        return x
    def _restore(self):
        self.transport.connect()
        if self._app:self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))
    def _send(self,r,retries=3):
        last=None
        for n in range(retries):
            try:return self._request(r)
            except Exception as e:
                last=e
                if n+1==retries:break
                time.sleep(min(4.0,2**n))
                try:self.transport.close();self._restore()
                except Exception as e2:last=e2
        raise CaptureContractError(f"{type(r).__name__} failed: {redact_text(str(last))}")
    def run(self):
        if self.out.exists():shutil.rmtree(self.out)
        self.out.mkdir(parents=True); self.zip_path.unlink(missing_ok=True)
        try:self.transport.connect();self._workflow()
        finally:self.transport.close()
        return self.zip_path
    def _workflow(self):
        self.progress("[1/4] Pepperstone Europe LIVE read-only auth")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret)); self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]); self._account=aid; fingerprint=account_fingerprint(aid)
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():raise MappingError("not verifiably Pepperstone")
        self.progress("[2/4] Exhaustive current symbol metadata")
        assets=[_plain(x) for x in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]
        classes=[_plain(x) for x in self._send(ProtoOAAssetClassListReq(ctidTraderAccountId=aid)).assetClass]
        categories=[_plain(x) for x in self._send(ProtoOASymbolCategoryListReq(ctidTraderAccountId=aid)).symbolCategory]
        sr=self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=True))
        light=[_plain(x) for x in sr.symbol]; archived=[_plain(x) for x in getattr(sr,"archivedSymbol",[])]
        ids=sorted({int(x["symbolId"]) for x in light if x.get("symbolId") is not None}); full={}
        for i in range(0,len(ids),64):
            q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend(ids[i:i+64])
            for x in self._send(q).symbol:full[int(x.symbolId)]=_plain(x)
        A={str(x.get("assetId")):x for x in assets}; C={str(x.get("id")):x for x in classes}; G={str(x.get("id")):x for x in categories}
        account_ccy=str((A.get(str(trader.get("depositAssetId"))) or {}).get("name") or "UNKNOWN").upper()
        self.progress("[3/4] Min-volume ExpectedMargin + leverage")
        margins={}; leverage_ids=set()
        for n,item in enumerate(light,1):
            sid=int(item.get("symbolId") or 0); f=full.get(sid,{})
            if f.get("leverageId") is not None:leverage_ids.add(int(f["leverageId"]))
            tradable=item.get("enabled") is not False and int(f.get("tradingMode",-1))==0
            mv=f.get("minVolume")
            if not tradable or mv is None or int(mv)<=0:continue
            try:
                q=ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,symbolId=sid);q.volume.append(int(mv));r=self._send(q)
                raw=[_plain(x) for x in r.margin]; digits=int(getattr(r,"moneyDigits",0) or 0); row=raw[0] if raw else {}
                buy=float(row["buyMargin"])/(10**digits) if row.get("buyMargin") is not None and account_ccy=="EUR" else None
                sell=float(row["sellMargin"])/(10**digits) if row.get("sellMargin") is not None and account_ccy=="EUR" else None
                margins[sid]={"state":"CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT","volume_cents":int(mv),"money_digits":digits,"raw_margin":raw,"buy_margin_eur":buy,"sell_margin_eur":sell,"buy_margin_pct_eur200":round(buy/2,6) if buy is not None else None,"sell_margin_pct_eur200":round(sell/2,6) if sell is not None else None,"feasibility":classify_margin(buy,sell)}
            except Exception as e:margins[sid]={"state":"BROKER_OR_MARGIN_UNRESOLVED","reason":redact_text(str(e)),"volume_cents":int(mv),"feasibility":"BROKER_OR_MARGIN_UNRESOLVED"}
            if n%100==0:self.progress(f"  margin {n}/{len(light)}")
        lev={}
        for lid in sorted(leverage_ids):
            try:lev[str(lid)]=_plain(self._send(ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=aid,leverageId=lid)).leverage)
            except Exception as e:lev[str(lid)]={"state":"UNRESOLVED","reason":redact_text(str(e))}
        records=[]; counts={"EUR200_MIN_VOLUME_FEASIBLE":0,"EUR200_MIN_VOLUME_INFEASIBLE":0,"BROKER_OR_MARGIN_UNRESOLVED":0}; tradable_count=0
        for item in sorted(light,key=lambda x:int(x.get("symbolId") or 0)):
            sid=int(item.get("symbolId") or 0); f=full.get(sid,{})
            cat=G.get(str(item.get("symbolCategoryId")),{})
            aclass=(C.get(str(cat.get("assetClassId"))) or {}).get("name")
            name=str(item.get("symbolName") or ""); minutes=schedule_minutes_per_week(f.get("schedule") or [])
            tradable=item.get("enabled") is not False and int(f.get("tradingMode",-1))==0
            m=margins.get(sid,{"state":"NOT_REQUESTED_NOT_TRADABLE_OR_NO_MIN_VOLUME","feasibility":"BROKER_OR_MARGIN_UNRESOLVED"})
            state=m.get("feasibility","BROKER_OR_MARGIN_UNRESOLVED") if tradable else "BROKER_OR_MARGIN_UNRESOLVED"
            if tradable:tradable_count+=1;counts[state]=counts.get(state,0)+1
            records.append({"symbol_id":sid,"broker_symbol":name,"description":item.get("description"),"asset_class":aclass,"product_type":product_type(name,aclass),"base_asset":(A.get(str(item.get("baseAssetId"))) or {}).get("name"),"quote_asset":(A.get(str(item.get("quoteAssetId"))) or {}).get("name"),"enabled":item.get("enabled",True),"trading_mode":f.get("tradingMode"),"tradable_current":tradable,"min_volume_cents":f.get("minVolume"),"step_volume_cents":f.get("stepVolume"),"max_volume_cents":f.get("maxVolume"),"lot_size":f.get("lotSize"),"pip_position":f.get("pipPosition"),"digits":f.get("digits"),"commission_type":f.get("commissionType"),"commission":f.get("commission"),"precise_trading_commission_rate":f.get("preciseTradingCommissionRate"),"min_commission":f.get("minCommission"),"swap_long":f.get("swapLong"),"swap_short":f.get("swapShort"),"charge_swap_at_weekends":f.get("chargeSwapAtWeekends"),"schedule_time_zone":f.get("scheduleTimeZone"),"schedule":f.get("schedule") or [],"schedule_minutes_per_week":minutes,"coverage_bucket":coverage_bucket(minutes),"leverage_id":f.get("leverageId"),"dynamic_leverage":lev.get(str(f.get("leverageId"))) if f.get("leverageId") is not None else None,"expected_margin_at_min_volume":m,"feasibility":state})
        artifact={"schema":"mxm.greenfield.v2.broker-native-competition-universe-capture.v1","status":"CURRENT_ACCOUNT_NATIVE_EXHAUSTIVE_READ_ONLY_CAPTURE","captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"tool_version":TOOL_VERSION,"source_environment":"Pepperstone - Europe LIVE","account_fingerprint_sha256":fingerprint,"account_currency":account_ccy,"starting_capital_eur":STARTING_CAPITAL_EUR,"full_account_current_symbol_inventory_claimed":True,"current_symbol_count":len(light),"current_tradable_count":tradable_count,"archived_symbol_count":len(archived),"classification_counts_among_current_tradable":counts,"symbols":records,"archived_symbols":archived,"asset_classes":classes,"symbol_categories":categories,"assets":assets,"dynamic_leverage_by_id":lev,"historical_margin_authority_claimed":False,"economic_outcomes_opened":0,"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False}
        atomic_write_json(self.out/"BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V1.json",artifact)
        scan_bundle_for_secrets(self.out,[self.client_secret,self.access_token])
        self.progress("[4/4] Deterministic transferable ZIP")
        digest=_zip(self.out,self.zip_path);self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")

"""Current full-universe read-only snapshot, encrypted before any outcome work."""
import os,json,gzip,base64,csv,io,pathlib,tempfile,time,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.multiscale_regime_v1.runtime_v1 import gate,e,rt,P
from research_core_v4.owner_recovery_v1.readback_v1 import describe
from competition.broker_universe_capture import _plain,entry_eligibility,product_type,account_execution_semantics,schedule_minutes_per_week
PHASE='GATE'
def class_product(name,c):
    typ=product_type(name,c)
    if typ=='OTHER_OR_TEST_CFD' and c and 'Equities' in c:return 'STANDARD_CASH_SHARE_CFD'
    return typ
def cached(key,fp,tmp):
    old=json.loads((e.a.ROOT/'research_core_v4/synchronized_breadth_v1/EXECUTION_V1.json').read_text())
    blob=base64.b64decode((e.a.ROOT/'research_core_v4/synchronized_breadth_v1/CONTRACT_METADATA_V1.mxmenc.b64').read_text(),validate=True)
    e.w.old.need(e.a.sha(blob)==old['contract_ciphertext_sha256'],'CONTRACT_CIPHER')
    raw=gzip.decompress(e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp));e.w.old.need(e.a.sha(raw)==old['contract_csv_sha256'],'CONTRACT_PLAIN')
    rows=list(csv.DictReader(io.StringIO(raw.decode())));e.w.old.need(len(rows)==1641,'CONTRACT_COUNT')
    for r in rows:r['source']='CAPTURED_CURRENT_2026_09_22_NOT_HISTORICAL';r['buy_eligible_current']=r['buy_feasibility']=='EUR200_MIN_VOLUME_FEASIBLE';r['sell_eligible_current']=r['sell_feasibility']=='EUR200_MIN_VOLUME_FEASIBLE';r['product_type']=class_product(r['broker_symbol'],r['asset_class'])
    return rows
def eligibility(r):
    reasons=[]
    try:
        if r.get('buy_eligible_current') is not True or r.get('sell_eligible_current') is not True:reasons.append('NOT_BOTH_CURRENT_NEW_ENTRY_DIRECTIONS')
        if any(int(r[k])<=0 for k in ('min_volume_cents','step_volume_cents','lot_size')):reasons.append('NONPOSITIVE_VOLUME_LATTICE')
        if r['product_type']=='OTHER_OR_TEST_CFD':reasons.append('UNRESOLVED_PRODUCT_OR_TEST')
        if max(float(r['buy_margin_eur']),float(r['sell_margin_eur']))>50:reasons.append('MINIMUM_TICKET_MARGIN_GT50EUR')
    except (KeyError,ValueError,TypeError):reasons.append('MISSING_CONTRACT_OR_MARGIN')
    return not reasons,reasons
def aggregate(rows,master):
    out={};ids={m['symbol_id'] for m in master}
    for r in rows:
        c=r.get('asset_class') or 'UNKNOWN';v=out.setdefault(c,{'symbols':0,'accepted_M5_identities':0,'eligible':0,'eligible_with_accepted_M5':0,'exclusions':Counter(),'margins':[],'volume_lattices':Counter(),'commission_contracts':Counter(),'swap_evidence':Counter(),'leverage_ids':Counter()})
        ok,why=eligibility(r);sid=int(r['symbol_id']);v['symbols']+=1;v['accepted_M5_identities']+=int(sid in ids);v['eligible']+=int(ok);v['eligible_with_accepted_M5']+=int(ok and sid in ids);v['exclusions'].update(why)
        try:v['margins'].append(max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])))
        except (ValueError,TypeError,KeyError):pass
        v['volume_lattices'][tuple(str(r.get(k)) for k in ('min_volume_cents','step_volume_cents','lot_size'))]+=1
        v['commission_contracts'][tuple(str(r.get(k)) for k in ('commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type','min_commission_asset','pnl_conversion_fee_pct'))]+=1
        v['swap_evidence']['CURRENT_VALUES_CAPTURED' if r.get('swap_long') not in ('',None) and r.get('swap_short') not in ('',None) else 'UNKNOWN']+=1;v['leverage_ids'][str(r.get('leverage_id'))]+=1
    for v in out.values():
        v['worst_minimum_margin_eur']=describe(v.pop('margins'))
        for k in ('volume_lattices','commission_contracts'):v[k]=[{'contract':list(a),'symbols':b} for a,b in sorted(v[k].items())]
    return out
def capture(master):
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from m6.ctrader_transport import StdlibCTraderTransport,LIVE_HOST,LIVE_PORT
    from m6.ctrader_capture import require_read_only_request
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
    creds=[os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]
    if not all(creds):return None,{'status':'MISSING_RUNNER_CREDENTIALS','requests':0}
    tr=StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=30);rate=RateLimiter(min_interval=.25);count=0;started=time.monotonic();raw={};rows=[]
    def send(req):
        nonlocal count
        require_read_only_request(type(req).__name__);e.w.old.need(count<6500 and time.monotonic()-started<2100,'CURRENT_CAPTURE_BUDGET')
        rate.before_send();count+=1;r=tr.request(req,timeout=30)
        if type(r).__name__=='ProtoOAErrorRes':raise RuntimeError('BROKER_READ_ONLY_ERROR')
        return r
    try:
        tr.connect();aid=authenticate_segment(tr,*creds);count+=3
        assets=[_plain(x) for x in send(m.ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]
        classes=[_plain(x) for x in send(m.ProtoOAAssetClassListReq(ctidTraderAccountId=aid)).assetClass]
        cats=[_plain(x) for x in send(m.ProtoOASymbolCategoryListReq(ctidTraderAccountId=aid)).symbolCategory]
        sr=send(m.ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=True));light=[_plain(x) for x in sr.symbol]
        trader=_plain(send(m.ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        raw.update(assets=assets,classes=classes,categories=cats,light=light,trader=trader)
        A={str(x['assetId']):x for x in assets};C={str(x['id']):x for x in classes};G={str(x['id']):x for x in cats}
        currency=(A.get(str(trader.get('depositAssetId'))) or {}).get('name');e.w.old.need(currency=='EUR','CURRENT_MARGIN_CURRENCY')
        full={};sids=sorted(int(x['symbolId']) for x in light)
        for k in range(0,len(sids),64):
            q=m.ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend(sids[k:k+64])
            for x in send(q).symbol:full[int(x.symbolId)]=_plain(x)
        raw['full']=full
        margins={};lev={};errors=Counter()
        raw['margins']=margins;raw['leverage']=lev
        for item in sorted(light,key=lambda x:int(x['symbolId'])):
            sid=int(item['symbolId']);f=full.get(sid,{});b,s=entry_eligibility(item,f);minv=f.get('minVolume');mar={}
            if b is True and minv is not None and int(minv)>0:
                try:
                    q=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,symbolId=sid);q.volume.append(int(minv));res=send(q)
                    if not res.HasField('moneyDigits'):raise ValueError('MISSING_MONEY_DIGITS')
                    match=[x for x in res.margin if int(x.volume)==int(minv)]
                    if len(match)!=1:raise ValueError('MARGIN_VOLUME')
                    x=match[0];mar={'buy':int(x.buyMargin)/10**res.moneyDigits if x.HasField('buyMargin') else None,'sell':int(x.sellMargin)/10**res.moneyDigits if x.HasField('sellMargin') else None,'raw':_plain(res)}
                except Exception as exc:errors[type(exc).__name__]+=1;mar={'buy':None,'sell':None,'failure_class':type(exc).__name__}
            margins[sid]=mar
        for lid in sorted({int(f['leverageId']) for f in full.values() if 'leverageId' in f}):
            try:lev[str(lid)]=_plain(send(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=aid,leverageId=lid)).leverage)
            except Exception as exc:lev[str(lid)]={'failure_class':type(exc).__name__}
        units={1:'USD_PER_MILLION_USD',2:'USD_PER_LOT',3:'PERCENTAGE_OF_VALUE',4:'QUOTE_PER_LOT'}
        for item in light:
            sid=int(item['symbolId']);f=full.get(sid,{});cat=G.get(str(item.get('symbolCategoryId')),{});c=C.get(str(cat.get('assetClassId')),{}).get('name');name=item.get('symbolName','');b,s=entry_eligibility(item,f);mar=margins[sid];typ=f.get('commissionType');prec=f.get('preciseTradingCommissionRate');rateval=float(prec)/(1e5 if typ==3 else 1e8) if prec is not None else float(f['commission'])/(100 if typ==3 else 100) if f.get('commission') is not None else None
            minimum=float(f['preciseMinCommission'])/1e8 if f.get('preciseMinCommission') is not None else float(f['minCommission'])/100 if f.get('minCommission') is not None else None
            r={'symbol_id':sid,'broker_symbol':name,'asset_class':c or 'UNKNOWN','product_type':class_product(name,c),'base_asset':A.get(str(item.get('baseAssetId')),{}).get('name'),'quote_asset':A.get(str(item.get('quoteAssetId')),{}).get('name'),'buy_eligible_current':b,'sell_eligible_current':s,'buy_margin_eur':mar.get('buy'),'sell_margin_eur':mar.get('sell'),'commission_rate_normalized':rateval,'commission_rate_unit':units.get(typ),'min_commission_normalized':minimum,'min_commission_type':f.get('minCommissionType'),'min_commission_asset':f.get('minCommissionAsset'),'pnl_conversion_fee_pct':float(f['pnlConversionFeeRate'])/100 if 'pnlConversionFeeRate' in f else None,'source':'CURRENT_READ_ONLY_CAPTURE_2026_10_10'}
            for dest,src in [('min_volume_cents','minVolume'),('step_volume_cents','stepVolume'),('lot_size','lotSize'),('max_volume_cents','maxVolume'),('swap_long','swapLong'),('swap_short','swapShort'),('swap_calculation_type','swapCalculationType'),('swap_period','swapPeriod'),('swap_time','swapTime'),('swap_rollover_3_days','swapRollover3Days'),('leverage_id','leverageId'),('schedule_time_zone','scheduleTimeZone')]:r[dest]=f.get(src)
            r['schedule']=f.get('schedule',[]);r['holiday']=f.get('holiday',[]);rows.append(r)
        raw={'assets':assets,'classes':classes,'categories':cats,'light':light,'archived':[_plain(x) for x in sr.archivedSymbol],'full':full,'margins':margins,'leverage':lev,'trader':trader}
        return {'rows':rows,'private_native_evidence':raw},{'status':'CURRENT_CAPTURE_COMPLETE','requests':count,'captured_utc':datetime.now(timezone.utc).isoformat(),'margin_errors':dict(errors),'account_semantics':account_execution_semantics(trader,currency,{'state':'NOT_REQUESTED'}),'money_currency':currency}
    except Exception as exc:
        return None,{'status':'CURRENT_CAPTURE_BLOCKED','failure_class':type(exc).__name__,'requests':count,'partial_native_evidence':raw}
    finally:tr.close()
def main():
    global PHASE
    os.umask(0o077);head,auth=gate('costuniverse');master,*_=e.w.old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-current-cost-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'COST_KEY');prior=cached(key,fp,tmp)
        PHASE='READ_ONLY_CURRENT_CAPTURE';fresh,status=capture(master);rows=fresh['rows'] if fresh else prior
        summary={'schema':'mxm.private.full.universe.current.cost.v1','source_status':{k:v for k,v in status.items() if k!='partial_native_evidence'},'active_symbol_metadata_rows':len(rows),'accepted_scientific_identities':1576,'metadata_matched_master':len({int(r['symbol_id']) for r in rows}&{m['symbol_id'] for m in master}),'by_asset_class':aggregate(rows,master),'prospective_structural_eligible':sum(eligibility(r)[0] for r in rows),'historical_contract_terms':'UNKNOWN;CAPTURED_CURRENT_ONLY','historical_spread':'ONLY_EXISTING_CONDITIONAL_AIDR_QUOTES;NOT_FULL_UNIVERSE','real_fills':0,'orders':0,'protected_forward':False,'net_certification':False,'capture_date_is_point_in_time_history':False,'volume_units':'API_CENTS;UNITS=VOLUME/100;LOTS=VOLUME/LOT_SIZE','risk':'MARGIN_NOT_STOP_LOSS_OR_FREE_CAPITAL;MIN_TICKET_MARGIN_SCREEN50EUR_IS25PCT_OF200'}
        PHASE='ENCRYPTED_CURRENT_EVIDENCE';rt.output(head,auth,tmp,key,'costuniverse',{'summary':summary,'metadata_rows':rows,'current_native_evidence':fresh,'capture_status':status,'authenticated_cached_rows':prior},summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None

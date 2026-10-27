"""Reuse existing contemporary estimates only, not price responses or trading eligibility."""
import base64,json,os,subprocess,tempfile
from decimal import Decimal as D
from pathlib import Path
from .common import need
from .universe_commission_checks import terms
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/current_margin/MxmCurrentMargin.csproj'
FULL=('symbolId','commissionType','minCommissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionAsset','minVolume','maxVolume','stepVolume','lotSize')
def extract(p):
    from m6.ctrader_transport import decode_envelope,extract_payload
    def decode(b64):
        env=decode_envelope(base64.b64decode(b64,validate=True));msg=extract_payload(env)
        need(env.IsInitialized() and msg.IsInitialized(),'MARGIN_INITIALIZED_MESSAGE');return env,msg
    responses={}
    for r in p['receipts']:
        _,msg=decode(r['response_wire']);responses.setdefault(r['request_type'],[]).append(msg)
    assets={int(a.assetId):a.name for a in responses['ProtoOAAssetListReq'][0].asset}
    trader=responses['ProtoOATraderReq'][0].trader
    need(assets.get(int(trader.depositAssetId))=='EUR','MARGIN_ACCOUNT_ASSET')
    lights={int(s.symbolId):s for s in responses['ProtoOASymbolsListReq'][0].symbol}
    fulls={int(s.symbolId):s for s in responses['ProtoOASymbolByIdReq'][0].symbol}
    rows={}
    for r in p['receipts']:
        if r['request_type']!='ProtoOAExpectedMarginReq':continue
        reqenv,req=decode(r['request_wire']);resenv,res=decode(r['response_wire']);sid=int(req.symbolId)
        need(type(req).__name__=='ProtoOAExpectedMarginReq' and type(res).__name__=='ProtoOAExpectedMarginRes' and
          reqenv.clientMsgId==resenv.clientMsgId==r['client_msg_id'] and int(req.ctidTraderAccountId)==int(res.ctidTraderAccountId)==p['account'] and
          sid in (1,2,250) and sid not in rows and list(req.volume)==[int(fulls[sid].minVolume)] and len(res.margin)==1,'MARGIN_EXACT_CORRELATION_AND_MINIMUM')
        full=fulls[sid];raw={k:(getattr(full,k) if k=='minCommissionAsset' else int(getattr(full,k))) for k in FULL if full.HasField(k)}
        light=lights[sid];quote=assets.get(int(light.quoteAssetId),'') if light.HasField('quoteAssetId') else ''
        m=res.margin[0]
        rows[sid]={'symbol_id':sid,'symbol_name':light.symbolName,'deposit_asset':'EUR','quote_asset':quote,
          'minimum_volume':int(req.volume[0]),'full':raw,'margin':{'volume':int(m.volume),'buy':int(m.buyMargin),'sell':int(m.sellMargin),
          'money_digits':int(res.moneyDigits) if res.HasField('moneyDigits') else None}}
    need(set(rows)=={1,2,250},'MARGIN_COMPLETE_FIXED_PANEL')
    return [rows[s] for s in (1,2,250)]
def reference(items):
    result=[]
    for i in items:
        margin=None;fee=None;ms='MARGIN_UNRESOLVED';fs='COST_UNRESOLVED';m=i['margin'];digits=m['money_digits']
        if (type(digits) is int and 0<=digits<=28 and i['deposit_asset']=='EUR' and i['symbol_id']>0 and
            i['minimum_volume']==i['full'].get('minVolume')==m['volume'] and m['volume']>0 and m['buy']>0 and m['sell']>0):
            buy,sell=[D(m[k])/D(10)**digits for k in ('buy','sell')]
            gate=lambda v:'FAILS_NECESSARY_MARGIN_ONLY_BOUND' if v>80 else 'PASSES_NECESSARY_MARGIN_ONLY_BOUND_NOT_ENTRY_ADMISSION'
            margin=dict(SymbolId=i['symbol_id'],VolumeCents=m['volume'],MoneyDigits=digits,BuyEur=buy,SellEur=sell,BuyMarginOnlyGate=gate(buy),SellMarginOnlyGate=gate(sell),FullEntryAdmission=False,HistoricalApplicability=False,ActualBrokerCharge=False)
            ms='DATED_MARGIN_ESTIMATE_ONLY'
        try:fee=terms(i);fs='DATED_TERMS_ONLY_FEE_EUR_UNRESOLVED'
        except (ValueError,KeyError,TypeError):pass
        result.append(dict(symbol_id=i['symbol_id'],margin_status=ms,margin=margin,fee_status=fs,terms=fee,round_trip_fee_eur=None,full_entry_admission=False,stop_risk_proven=False,dated_historical_terms_proven=False))
    return result
def run_report(items,framework='net8.0'):
    with tempfile.TemporaryDirectory() as d:
        a=Path(d)/'in';b=Path(d)/'out';a.write_text(json.dumps(items))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--framework',framework,'--no-build','--',str(a),str(b)],capture_output=True,check=True,env={**os.environ,'DOTNET_ROLL_FORWARD':'Major'})
        return json.loads(b.read_bytes(),parse_float=D)

def run(items,framework='net8.0'):
    return run_report(items,framework)['rows']

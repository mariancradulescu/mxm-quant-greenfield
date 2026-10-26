"""Existing metadata only and artificial fill arithmetic; no trading research."""
import base64,hashlib,json,subprocess,tempfile,zlib
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE='research_core_v4/state/NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64'
SHA='cdbfe0478771277fd6f258c269e324d5cc65308c9831ebcae26a4a8bdb503335'
RAW_SHA='4ceb988206c6caf5c0077d12201e9043c5bd640c63fd645c20273fafa9fcb63f'
PROJECT='research_core_v4/laboratory/csharp/commission/MxmCommission.csproj'
def need(ok,why):
    if not ok:raise ValueError('UNIVERSE_COMMISSION_'+why)
def digest(b):return hashlib.sha256(b).hexdigest()
def integer(v):
    need(type(v) is int or isinstance(v,str) and v.lstrip('-').isdigit(),'EXACT_INTEGER');return int(v)
def terms(item):
    f=item['full'];ident=item['symbol_id'];quote=item['quote_asset']
    need(integer(f['symbolId'])==ident and ident>0 and isinstance(quote,str) and quote.strip() and len(quote)<=64,'IDENTITY')
    kind,minimum_kind=integer(f['commissionType']),integer(f['minCommissionType']);need(kind in (1,2,3,4) and minimum_kind in (1,2),'UNITS')
    rate,minimum=[integer(f[k]) for k in ('preciseTradingCommissionRate','preciseMinCommission')]
    low,high,step,lot=[integer(f[k]) for k in ('minVolume','maxVolume','stepVolume','lotSize')]
    need(min(rate,minimum)>=0 and low>0 and high>=low and step>0 and low%step==0 and lot>0,'VOLUME_OR_RATE')
    asset=f['minCommissionAsset'] if minimum_kind==1 else quote
    need(isinstance(asset,str) and asset.strip() and len(asset)<=64,'MINIMUM_ASSET')
    return dict(SymbolId=ident,QuoteAsset=quote,Kind=kind,PreciseRate=rate,MinimumKind=minimum_kind,PreciseMinimum=minimum,MinimumAsset=asset,MinimumVolume=low,MaximumVolume=high,StepVolume=step,LotSize=lot,Rate=D(rate)/(100000 if kind==3 else 100000000),Minimum=D(minimum)/100000000)
def fee(item,t):
    f=item['fill'];volume=f['volume_cents'];price=D(f['price']);need(type(volume) is int and t['MinimumVolume']<=volume<=t['MaximumVolume'] and volume%t['StepVolume']==0 and price>0,'FILL')
    units=D(volume)/100;rate=t['Rate'];kind=t['Kind']
    if kind==1:
        fx=D(f['usd_per_quote']);need(fx>0,'NOTIONAL_FX');base=units*price*fx*rate/1000000;asset='USD'
    elif kind==2:base=D(volume)*rate/t['LotSize'];asset='USD'
    elif kind==3:base=units*price*rate/100;asset=t['QuoteAsset']
    else:base=D(volume)*rate/t['LotSize'];asset=t['QuoteAsset']
    def convert(value,currency):
        if not value:return D(0)
        fx=D(f['cost_eur_per_asset'][currency]);need(fx>0,'FX');return value*fx
    b,m=convert(base,asset),convert(t['Minimum'],t['MinimumAsset'])
    return dict(BaseFee=base,BaseAsset=asset,BaseFeeEur=b,MinimumFee=t['Minimum'],MinimumAsset=t['MinimumAsset'],MinimumFeeEur=m,UnroundedFeeEur=max(b,m),HistoricalCostProven=False,BrokerChargeProven=False)
def run(items):
    with tempfile.TemporaryDirectory() as tmp:
        a=Path(tmp)/'in';b=Path(tmp)/'out';a.write_text(json.dumps(items))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--framework','net8.0','--no-build','--',str(a),str(b)],check=True,capture_output=True)
        return json.loads(b.read_bytes(),parse_float=D)
def reconcile(items,actual):
    need(len(items)==len(actual),'COUNT')
    for item,a in zip(items,actual):
        expected=terms(item);need(a['status']=='EXPLICIT_TERMS_DECODED_NOT_HISTORICAL_CERTIFICATION' and a['terms']==expected,'EVERY_TERM')
        need(a['priced']==(fee(item,expected) if 'fill' in item else None),'EVERY_ARTIFICIAL_FEE')
    return True
def snapshot():
    encoded=(ROOT/SOURCE).read_bytes();need(digest(encoded)==SHA,'SOURCE_SHA');raw=zlib.decompress(base64.b64decode(encoded));need(digest(raw)==RAW_SHA,'DECODED_SHA');source=json.loads(raw)
    need(source['schema']=='mxm.v4.quote-scope-current-metadata.v1' and source['deposit_asset']=='EUR' and len(source['rows'])==1576 and source['historical_requests_sent']==0 and source['orders_sent']==0 and source['features_computed'] is False and source['responses_computed'] is False,'SOURCE_SCOPE')
    assets={integer(a['assetId']):a['name'] for a in source['asset_metadata']};need(len(assets)==len(source['asset_metadata']),'UNIQUE_ASSET_IDENTITY');items=[];seen=set()
    for r in source['rows']:
        ident=r['symbol_id'];light=r['current_light_metadata'];need(ident not in seen and integer(light['symbolId'])==ident and light['symbolName']==r['symbol'],'ROSTER_IDENTITY');seen.add(ident)
        items.append({'symbol_id':ident,'quote_asset':assets[integer(light['quoteAssetId'])],'full':r['current_full_metadata']})
    return source,items
def main():
    source,items=snapshot();actual=run(items);reconcile(items,actual)
    result={'schema':'mxm.universe-commission-source-reception.v1','source':SOURCE,'source_sha256':SHA,'decoded_source_sha256':RAW_SHA,'metadata_capture_utc':source['completed_utc'],'instruments':len(items),'commission_types':dict(sorted(Counter(i['full']['commissionType'] for i in items).items())),
      'all_terms_independently_reconciled':True,'reconciled_terms_canonical_sha256':digest(json.dumps(actual,default=str,sort_keys=True,separators=(',',':')).encode()),'source_metadata_not_current_terms':True,'historical_costs_proven':False,'market_prices_read':False,'market_account_replay':False,'new_models':0,'new_economic_outcomes':0,'new_broker_requests':0,'orders':0,'hard21_proven':False,'economic_edge_proven':False,'native_ctrader_runtime_reception':False}
    print('MXM_UNIVERSE_COMMISSION '+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

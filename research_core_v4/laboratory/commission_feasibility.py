"""One fixed NONMARKET cost-floor scenario; no prices, models or account paths."""
import json,hashlib,subprocess,tempfile
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
from .universe_commission_checks import ROOT,snapshot,terms,SOURCE,SHA,RAW_SHA
PROJECT='research_core_v4/laboratory/csharp/commission_account/MxmCommissionAccount.csproj'
POLICY={'schema':'mxm.minimum-commission-floor-scenario.v1','source_sha256':SHA,'initial_capital_eur':'200','risk_fraction_reference':'0.02','cost_eur_per_usd':'0.9','cost_eur_per_eur':'1','volume':'EXACT_SOURCE_MINIMUM','entry_count_hurdle':21,'unresolved_components':'RETAIN_AS_UNKNOWN_NOT_FREE','price_dependent_base_fees':'NOT_ESTIMATED','model_trials':0}
POLICY_SHA=hashlib.sha256(json.dumps(POLICY,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def reference(item):
    t=terms(item);unknown=set();fx={'USD':D('.9'),'EUR':D(1)}
    def convert(value,asset):
        if not value:return D(0)
        if asset in fx:return value*fx[asset]
        unknown.add('MISSING_COST_FX_'+asset);return D(0)
    minimum=convert(t['Minimum'],t['MinimumAsset']);base=D(0)
    if t['Kind'] in (2,4):base=convert(D(t['MinimumVolume'])/t['LotSize']*t['Rate'],'USD' if t['Kind']==2 else t['QuoteAsset'])
    elif t['Rate']!=0:unknown.add('PRICE_DEPENDENT_BASE_FEE')
    return {'KnownPerFillFloorEur':max(minimum,base),'CompleteFeeKnownWithoutPrice':not unknown,'Unresolved':sorted(unknown)}
def classify(floor):
    budget=D(POLICY['initial_capital_eur'])*D(POLICY['risk_fraction_reference'])
    if 2*floor['KnownPerFillFloorEur']>=budget:return 'ROUNDTRIP_FEE_FLOOR_EXHAUSTS_INITIAL_REFERENCE_RISK'
    if not floor['CompleteFeeKnownWithoutPrice']:return 'COST_UNRESOLVED_NOT_ELIGIBLE'
    return 'FEE_HURDLE_ONLY_NOT_FULL_ADMISSION'
def main():
    source,items=snapshot()
    with tempfile.TemporaryDirectory() as t:
        i=Path(t)/'in';o=Path(t)/'out';i.write_text(json.dumps(items))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--','--floors',str(i),str(o)],capture_output=True,check=True)
        rows=json.loads(o.read_bytes(),parse_float=D)
    expected=[reference(i) for i in items]
    if rows!=expected:raise ValueError('EVERY_FEE_FLOOR_RECONCILIATION')
    counts=Counter(classify(r) for r in rows)
    hurdle=sum(21*r['KnownPerFillFloorEur']>=200 for r in rows)
    result={'schema':'mxm.commission-floor-feasibility-public.v1','source':SOURCE,'source_sha256':SHA,'decoded_source_sha256':RAW_SHA,'snapshot_utc':source['completed_utc'],'scenario':POLICY,'scenario_sha256':POLICY_SHA,
      'source_instruments':len(rows),'all_floors_independently_reconciled':True,'classification_counts':dict(sorted(counts.items())),'entry_commissions_only_21_entry_hurdle_exceeds_initial_cash_count':hurdle,
      'cash_hurdle_is_not_universal_infeasibility':True,'no_trade_eligibility_or_winner_roster_created':True,'market_prices_read':False,'market_account_replay':False,'historical_costs_proven':False,'actual_fx_or_broker_charges_proven':False,'hard21_proven':False,'economic_edge_proven':False,'new_directional_models':0,'new_market_economic_outcomes':0,'new_broker_requests':0,'orders':0}
    print('MXM_COMMISSION_FEASIBILITY '+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

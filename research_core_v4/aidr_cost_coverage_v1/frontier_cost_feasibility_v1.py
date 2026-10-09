"""Authentic source-scoped quote/contract feasibility; no event returns or selection.

Prior winner-first acquisition is selection-exposed. Sampled spread statistics
are descriptive only, never an AIDR cost, execution quote or historic fee.
"""
import csv,gzip,hashlib,io,json,math,pathlib,statistics,zipfile
from collections import Counter
from research_core_v4.aidr_cost_coverage_v1.compile_cost_availability_v1 import HASHES,START,END,two,canonical

def diagnostic(root,repo):
    root=pathlib.Path(root);repo=pathlib.Path(repo)
    for name,h in HASHES.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
    master=json.loads((repo/'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json').read_text());md={r['symbol_id']:r for r in master}
    with (root/'BROKER_NATIVE_COMPETITION_OPPORTUNITY_MAP_V2.csv').open() as f:contracts={int(r['symbol_id']):r for r in csv.DictReader(f)}
    records=[]
    for name in HASHES:
        if not name.endswith('.zip'):continue
        z=zipfile.ZipFile(root/name)
        for member in z.namelist():
            if member.startswith('derived/') and member.endswith('.jsonl.gz'):
                hours=[json.loads(line) for line in gzip.decompress(z.read(member)).splitlines()];symbol=hours[0]['symbol_id'];observations=[];all_rows=0;bad=0;fresh=0;weeks=Counter();clock={}
                for hour in hours:
                    for row in hour['rows']:
                        t=row['boundary_ms']
                        if not START<=t<END:continue
                        all_rows+=1;q=row['d0s']
                        assert t not in clock,'DUPLICATE_SOURCE_CLOCK'
                        clock[t]=q
                        if not two(q['bid'],q['ask']):bad+=1;continue
                        v=10000*math.log(float(q['ask'])/float(q['bid']));assert math.isfinite(v) and v>=0;observations.append(v);fresh+=q['fresh'] is True;weeks[(t-START)//604800000]+=1
                valid_pairs=[(t,t+3600000) for t,q in clock.items() if t+3600000 in clock and two(q['bid'],q['ask']) and two(clock[t+3600000]['bid'],clock[t+3600000]['ask'])]
                c=contracts.get(symbol,{})
                records.append({'source':name,'source_sha256':HASHES[name],'member':member,'member_sha256':hashlib.sha256(z.read(member)).hexdigest(),'symbol_id':symbol,'symbol':md.get(symbol,{}).get('symbol',hours[0]['symbol']),'in_master1576':symbol in md,'asset_class':md.get(symbol,{}).get('asset_class','OUTSIDE_MASTER'),'sampled_boundary_rows':all_rows,'valid_two_sided_quotes':len(observations),'invalid_two_sided_quotes':bad,'declared_fresh_quotes':fresh,'valid_quotes_by_fixed_week':[weeks[w] for w in range(4)],'sampled_log_spread_bps_min':min(observations) if observations else None,'sampled_log_spread_bps_median':statistics.median(observations) if observations else None,'sampled_log_spread_bps_max':max(observations) if observations else None,'generic_exact_one_hour_quote_pairs':len(valid_pairs),'generic_pair_warning':'NO_SCIENTIFIC_EVENT_INTERSECTION','current_contract_snapshot':{k:c.get(k) for k in ('buy_feasibility','sell_feasibility','buy_margin_eur','sell_margin_eur','min_volume_cents','step_volume_cents','commission_type','commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_asset','pnl_conversion_fee_pct','schedule_minutes_per_week')},'historic_terms_certified':False,'fills_observed':False})
    eligible=[r for r in records if r['in_master1576'] and r['sampled_log_spread_bps_median'] is not None]
    classes={c:{'sampled_source_symbol_cells':sum(r['asset_class']==c for r in eligible),'valid_two_sided_quotes':sum(r['valid_two_sided_quotes'] for r in eligible if r['asset_class']==c),'median_of_source_symbol_medians_bps':statistics.median(r['sampled_log_spread_bps_median'] for r in eligible if r['asset_class']==c)} for c in sorted({r['asset_class'] for r in eligible})}
    return {'schema':'mxm.private.cost.first.frontier.feasibility.v1','source_sha256':HASHES,'authenticated_sources':8,'records':records,'class_diagnostics':classes,'master_identities_with_sampled_quotes':len({r['symbol_id'] for r in eligible}),'selection_exposure':'GLOBAL/WAVE2/WINNER_FIRST_PRIOR_ACQUISITION_WAS_SELECTION_EXPOSED;NO_NEW_POPULATION_OR_CONFIRMATION','ranking_rule':'NO_SYMBOL_OR_MECHANISM_SELECTION_FROM_THIS_DIAGNOSTIC','net_edge_established':False,'EUR200_historical_survival_certified':False,'HARD21_executed_entries':0,'independent_questions':{'TREND_OR_STATE_PERSISTENCE':'NEW_H1_SIGN_TRANSITION_STATE_CONDITIONAL_FOUR_HOUR_PREQUENTIAL_PREDICTION_VS_UNCONDITIONAL_DRIFT;FIX_BEFORE_OUTCOMES','RELATIVE_VALUE':'REQUIRES_AUTHORITATIVE_LINKAGE_AND_MULTI_LEG_COSTS_BEFORE_NUMERIC_RESEARCH','CARRY':'REQUIRES_POINT_IN_TIME_FINANCING_NOT_CURRENT_SWAP_SNAPSHOT','QUOTE_LIQUIDITY':'SAMPLED_D0_SPREADS_DO_NOT_ESTABLISH_QUOTE_SEQUENCE_OR_PREDICTION'},'remaining_costs':'EVENT_MATCHED_SPREAD;RAZOR_TERMS;CONVERSION;FILL/SLIPPAGE;FINANCING;SIMULTANEOUS_MARGIN'}

if __name__=='__main__':
    import sys
    result=diagnostic(sys.argv[1],sys.argv[2]);pathlib.Path(sys.argv[3]).write_bytes(canonical(result))
    print(json.dumps({'verified_sources':8,'sampled_source_symbol_cells':len(result['records']),'master_identities_with_sampled_quotes':result['master_identities_with_sampled_quotes'],'class_diagnostics':result['class_diagnostics']},sort_keys=True))

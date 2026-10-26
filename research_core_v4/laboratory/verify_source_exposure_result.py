"""Immutable offline readback of the public source-only native GitHub result.
Verifies original Git blob, source/run identity and refusal of economic promotion.
No broker access, no secret, no model/price replay.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RECEIPT=ROOT/'docs/economic-development/20261027/source-exposure-40415845622/receipt.json'
ORIGINAL_BLOB='30397fecc50877f804c31fbed264937a7ca6369c'
ORIGINAL_HEAD='49958f462b5b57bdd7d7ad74a4a2b1facab2e8ae'
EXPECTED={'W35':(39946364621,683022,379584,69609,309975,45802),
          'W36':(40276181331,761196,421150,72952,348198,50135),
          'W37':(39917922508,685474,408017,126734,281283,74446)}
def need(condition,reason):
    if not condition:raise ValueError('SOURCE_CENSUS_ORIGINAL_'+reason)
def verify(path=RECEIPT):
    path=Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=10000,'BOUNDED_REGULAR_RECEIPT')
    raw=path.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
    need(blob==ORIGINAL_BLOB,'EXACT_NATIVE_PUBLIC_RESULT_BLOB')
    receipt=json.loads(raw)
    need(receipt['schema']=='mxm.source-exposure-observation-census.v1' and
         receipt['run_id']==40415845622 and receipt['source_sha']==ORIGINAL_HEAD and
         receipt['fixed_age_ms']==receipt['fixed_inter_group_gap_ms']==5000 and
         receipt['fixed_observed_span_ms']==300000,'NATIVE_PROVENANCE_OR_FROZEN_SOURCE_POLICY')
    need(set(receipt['profiles'])==set(EXPECTED) and
         receipt['original_runs']=={k:v[0] for k,v in EXPECTED.items()},'EXACT_WEEK_ROSTER')
    rows=groups=good=bad=0
    for week,expect in EXPECTED.items():
        p=receipt['profiles'][week]
        identity=(p['source_run'],p['rows_verified'],p['observed_groups'],
                  p['healthy_observation_groups'],p['unavailable_observation_groups'],
                  p['observed_qualified_stretches'])
        need(identity==expect and p['observed_groups']==
             p['healthy_observation_groups']+p['unavailable_observation_groups'] and
             p['observed_stretches_at_least_5min']==0 and
             p['longest_qualified_observation_span_bucket']=='LESS_THAN_5_MINUTES' and
             p['declared_age_and_group_gap_ms']==5000 and
             p['declared_span_ms']==300000 and
             p['between_observation_liquidity_proven'] is False and
             p['broker_fills_proven'] is False and
             p['historical_execution_costs_proven'] is False and
             p['economic_model_executed'] is False and p['orders']==0,
             'ORIGINAL_WEEK_QUALITY_AND_NONPROMOTION_'+week)
        rows+=p['rows_verified'];groups+=p['observed_groups']
        good+=p['healthy_observation_groups'];bad+=p['unavailable_observation_groups']
    need(rows==2129692 and groups==1208751 and good==269295 and bad==939456 and
         receipt['source_groups_reconciled']==groups,'ORIGINAL_THREE_WEEK_FULL_RECONCILIATION')
    for key in ('no_interpolation_or_dropped_unavailable_groups',
                'observed_stretches_not_broker_executable_continuity',
                'no_price_or_timestamps_published'):
        need(receipt[key] is True,'FALSE_EXPOSURE_CONTINUITY_PROMOTION_'+key)
    for key in ('hard21_proven','after_cost_edge_proven','cloud_activated'):
        need(receipt[key] is False,'FALSE_PROFIT_OR_RUNTIME_PROMOTION_'+key)
    for key in ('market_outcomes','economic_replays','new_directional_models','new_broker_requests','orders'):
        need(receipt[key]==0,'NO_RESEARCH_OR_BROKER_SIDE_EFFECT_'+key)
    return {'schema':'mxm.immutable-source-census-verification.v1',
      'original_run':receipt['run_id'],'source_head':ORIGINAL_HEAD,'blob_sha1':ORIGINAL_BLOB,
      'sources':len(EXPECTED),'raw_events_authenticated':rows,
      'groups':groups,'healthy_observation_groups':good,'unavailable_observation_groups':bad,
      'five_minute_qualified_stretches':0,
      'no_economic_replay':True,'historical_execution_liquidity_proven':False,
      'robust_after_cost_edge_proven':False,'native_ctrader_reception_proven':False,
      'orders':0}
if __name__=='__main__':
    print('MXM_ORIGINAL_EXPOSURE_RECEIPT_VERIFIED '+json.dumps(verify(),sort_keys=True))

"""Receive exact original public source-census artifact offline; no custody/replay."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/gbpusd-source-exposure-40452507002'
ARCHIVE_SHA='e8ca07f6af7db4f8acfdfc0fafef95e0530630893ddc2e79e3c5071ceb200d77'
RECEIPT_SHA='4d955f02fc2902240bb9a92b14520d66505c77c60ab3fa8d3eb64c17541ad65e'
HEAD='01ee51857fc3c98baba05893c9bd67b0b29eda5f'
def need(ok,why):
    if not ok:raise ValueError('GBP_SOURCE_RESULT_'+why)
def regular(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=10000,'BOUNDED_REGULAR_FILE')
    return path.read_bytes()
def verify(folder=FOLDER):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER')
    archive=base64.b64decode(regular(folder/'artifact.zip.b64').strip(),validate=True)
    need(len(archive)==865 and hashlib.sha256(archive).hexdigest()==ARCHIVE_SHA,'ORIGINAL_NATIVE_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(z.namelist()==['receipt.json'] and z.infolist()[0].file_size==1342,'EXACT_NATIVE_MEMBER')
        raw=z.read('receipt.json')
    need(regular(folder/'receipt.json')==raw and hashlib.sha256(raw).hexdigest()==RECEIPT_SHA,'EXACT_ORIGINAL_RECEIPT_COPY')
    r=json.loads(raw);p=r['profile']
    need(r['schema']=='mxm.gbpusd-source-exposure-census.v1' and r['run_id']==40452507002 and
      r['source_sha']==HEAD and r['original_run']==40179011821 and r['symbol']=='GBPUSD' and
      r['iso_week']=='2026-W37' and r['partition']=='DEVELOPMENT_ALREADY_EXPOSED','ORIGINAL_PROVENANCE')
    need(r['fixed_age_ms']==r['fixed_inter_group_gap_ms']==p['declared_age_and_group_gap_ms']==5000 and
      r['fixed_observed_span_ms']==p['declared_span_ms']==300000,'UNCHANGED_CONSUMER_CONTRACT')
    need((p['source_run'],p['rows_verified'],p['observed_groups'],p['healthy_observation_groups'],
      p['unavailable_observation_groups'],p['observed_qualified_stretches'],p['observed_stretches_at_least_5min'],
      p['max_groups_in_one_stretch'])==(40179011821,1275114,812355,685704,126651,104600,6,2511) and
      p['healthy_observation_groups']+p['unavailable_observation_groups']==p['observed_groups'] and
      p['longest_qualified_observation_span_bucket']=='AT_LEAST_5_MINUTES' and
      p['unavailability_categories']==['CROSSED_BOOK','LOCKED_BOOK_CONSUMER_REJECTS','STALE_SIDE'],
      'ALL_ORIGINAL_SOURCE_COUNTS')
    for k in ('after_cost_edge_proven','between_observation_liquidity_proven','cloud_activated','hard21_proven'):
        need(r[k] is False,'NO_PROMOTION_'+k)
    for k in ('between_observation_liquidity_proven','broker_fills_proven','economic_model_executed','historical_execution_costs_proven'):
        need(p[k] is False,'NO_PROFILE_PROMOTION_'+k)
    for k in ('economic_replays','market_outcomes','new_broker_requests','new_directional_models','orders'):
        need(type(r[k]) is int and r[k]==0,'NO_SIDE_EFFECT_'+k)
    need(p['orders']==0 and r['all_original_groups_retained'] is True and
      r['no_price_or_timestamps_published'] is True and
      r['next_action']=='REQUIRE_EXPOSURE_PATH_AND_DATED_COST_ADMISSION_BEFORE_MODEL','SOURCE_ONLY_CONSEQUENCE')
    return {'schema':'mxm.immutable-gbpusd-source-verification.v1','run_id':r['run_id'],
      'head':HEAD,'original_artifact':12711101126,'original_archive_sha256':ARCHIVE_SHA,
      'events':1275114,'groups':812355,'healthy_groups':685704,'unavailable_groups':126651,
      'observed_stretches_at_least_5min':6,'economic_edge_proven':False,'hard21_proven':False,
      'native_ctrader_operational_reception_proven':False,'orders':0}
if __name__=='__main__':print('MXM_ORIGINAL_GBP_SOURCE_RESULT '+json.dumps(verify(),sort_keys=True))

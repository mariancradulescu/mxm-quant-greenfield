"""Audit durable NONOUTCOME output bytes only; never opens the M5 corpus."""
import base64,gzip,hashlib,io,json,os,urllib.request
import numpy as np
from pathlib import Path
from research_core_v4.current_wave_support_worker_v1 import SOURCES,G,need
S='research_core_v4/state/STRICT_PREOUTCOME_V2_'
REPO='mariancradulescu/mxm-quant-greenfield'
def get(path):
 need(path.startswith('/repos/'+REPO+'/'),'OUTPUT_AUDIT_GITHUB_ONLY')
 r=urllib.request.Request('https://api.github.com'+path,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(r,timeout=120) as f:return json.load(f)
def check_scalars(obj):
 forbidden={'open','high','low','close','tick_volume','raw_rows','raw_prices','raw_tick_volume_values','feature_values','response_values','return_values','return_signs','return_magnitudes','pnl','sharpe','effect_estimates','correlations','regressions','information_coefficients','p_values','candidate_ranking','winner_selection'}
 if isinstance(obj,dict):
  for k,v in obj.items():need(str(k).lower() not in forbidden,'FORBIDDEN_OUTPUT_FIELD');check_scalars(v)
 elif isinstance(obj,list):
  for v in obj:check_scalars(v)
 else:need(type(obj) in (str,int,bool,type(None)),'NONINTEGER_NUMERIC_OUTPUT')
def main():
 d=json.loads(Path(S+'CURRENT_WAVE_SUPPORT_RESULT_V1.json').read_bytes());head=d['durable_checkpoint_head'];expected={'event_masks.npz','support_counts.json.gz','dependence_geometry.json.gz'}
 need({e['ref'].split('/')[-1] for e in d['outputs']}==expected,'EXACT_OUTPUT_INVENTORY')
 verified=[]
 for e in d['outputs']:
  need(e['ref'].startswith('support_only_v1/results/'),'NONOUTCOME_PATH_ONLY')
  info=get('/repos/'+REPO+'/contents/'+e['ref']+'?ref='+head);blob=get('/repos/'+REPO+'/git/blobs/'+info['sha']);raw=base64.b64decode(blob['content'])
  need(len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256'],'DURABLE_OUTPUT_SHA256')
  if e['ref'].endswith('.npz'):
   z=np.load(io.BytesIO(raw),allow_pickle=False);keys={s+'__'+str(h)+'__'+k for s in SOURCES for h in ([12] if s==SOURCES[4] else [1,12]) for k in ('baseline','feature','response','joint','causal_unknown')}|{'baseline_geometric','peer_response_1','peer_response_12'}
   need(set(z.files)==keys,'EXACT_PACKED_MASK_SCHEMA')
   for k in z.files:
    a=z[k];need(a.dtype==np.uint8 and a.shape==(1575,84 if k.startswith(SOURCES[4]) else G//8),'EXACT_PACKED_MASK_DOMAIN')
    if k.endswith('causal_unknown'):need(bool(np.all(a==255)),'CAUSAL_UNKNOWN_NOT_PROMOTED')
  else:
   obj=json.loads(gzip.decompress(raw));check_scalars(obj)
   if e['ref'].endswith('support_counts.json.gz'):
    need(len(obj['per_candidate_identity_context_horizon'])==1575*9,'EXACT_SUPPORT_RECORD_DOMAIN')
    need(all(x['causal_pass_count']==0 and x['causal_false_count']==0 and x['causal_unknown_count']==x['potential_event_count'] for x in obj['per_candidate_identity_context_horizon']),'THREE_STATE_ARCHIVE_LAW')
    need({s:sum(x['geometric_joint_count'] for x in obj['per_candidate_identity_context_horizon'] if x['source']==s) for s in SOURCES}==d['source_geometric_joint_counts'],'COUNT_MANIFEST_PARITY')
  verified.append(e['sha256']);raw=None
 print('DURABLE_NONOUTCOME_OUTPUT_AUDIT='+json.dumps({'status':'PASS','hashes_verified':verified,'packed_mask_fields':48,'identity_horizon_records':14175,'numeric_features':0,'numeric_responses':0,'raw_rows':0,'causal_pass':0,'original_market_assets_opened':0}),flush=True)
if __name__=='__main__':main()

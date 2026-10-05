"""Transport and structural verification only; never summarize support decisions."""
from pathlib import Path
import json, gzip, hashlib, pickle, io, base64, subprocess
import numpy as np
P=Path(__file__).resolve().parent; R=P.parents[1]
CACHE=R.parent/'v6_verified_cache.pkl'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,o): (P/name).write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def ih(X,D): return hashlib.sha256(np.asarray(X,dtype='<f8').tobytes()+np.asarray(D,dtype='<f8').tobytes()).hexdigest()
def main():
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 assert head=='c415673dfca55140fc9d332939776eb53432db6d'
 m=json.loads((P/'ACTUAL_PREDICTOR_ORACLE_RAW_V1_PARTS_MANIFEST.json').read_text()); parts=[];chunks=[]
 assert len(m['parts'])==12
 for i,x in enumerate(m['parts']):
  assert x['path']==f'research_core_v4/triad_v6/ACTUAL_PREDICTOR_ORACLE_RAW_V1.parts/part{i:03}.bin'
  b=(R/x['path']).read_bytes(); s=hashlib.sha256(b).hexdigest()
  assert len(b)==x['size'] and s==x['sha256'],x['path']
  parts.append(dict(path=x['path'],bytes=len(b),sha256=s,verified=True));chunks.append(b)
 b=b''.join(chunks); digest=hashlib.sha256(b).hexdigest()
 assert len(b)==22765478==m['original_bytes']
 assert digest==m['original_sha256']=='d8bdaf9a5ce3c1e7417351d7fcc6768a5031592f28342140043e8ac559d34abd'
 raw=json.loads(gzip.decompress(b)) # exactly one gzip-decompression/JSON parse
 assert raw['schema']=='TRIAD_V6_ACTUAL_PREDICTOR_ORACLE_RAW_V1'
 source={'input_geometry_gzip_sha256':'ACTUAL_CAUSAL_INPUT_GEOMETRY_V1.json.gz','oracle_source_sha256':'high_precision_projection_oracle_v1.py','support_certificate_source_sha256':'one_sided_numerical_certificate_v1.py','builder_sha256':'build_actual_predictor_geometry_v1.py','audit_source_sha256':'audit_actual_predictor_support_v1.py'}
 bindings={}
 for k,f in source.items():
  s=sha(P/f);assert s==raw[k],f;bindings['research_core_v4/triad_v6/'+f]=s
 f='research_core_v4/triad_v4/canonical_projection_jacobi_v1.cpp';s=sha(R/f);assert s==raw['projection_kernel_sha256'];bindings[f]=s
 for f,s in json.loads((P/'INHERITED_IMMUTABLE_BINDINGS_V1.json').read_text())['bindings'].items(): assert sha(R/f)==s,f
 g=json.loads(gzip.decompress((P/'ACTUAL_CAUSAL_INPUT_GEOMETRY_V1.json.gz').read_bytes()))
 assert g['schema']=='TRIAD_V6_ACTUAL_CAUSAL_INPUT_GEOMETRY_V1'
 assert g['support_plan_sha256']==sha(P/'ACTUAL_PREDICTOR_SUPPORT_AUDIT_PLAN_V1.json')
 support=json.loads((R/'research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json').read_text())
 mb=base64.b64decode(support['actual_masks_npz_base64']);ms=hashlib.sha256(mb).hexdigest()
 assert ms==g['full_clock_timestamp_mask_sha256']==support['actual_masks_npz_sha256']=='e319b504bc397f0d12152df681e8f00d28e8c2cf304be9a508a43c84ff1c9107'
 masks={k:v for k,v in np.load(io.BytesIO(mb),allow_pickle=False).items()}
 design=json.loads((R/'research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json').read_text())
 assert raw['requested_geometries']==g['total_geometries']==len(g['geometries'])==len(raw['requested_to_exact_input_hash'])==55648
 assert g['full_cohort_geometries']==len(g['full_clock_geometries'])==3552
 assert g['leaveout_geometries']==52096
 records={}
 for x in raw['measurements']:
  key=x['input_sha256'];assert key not in records,'duplicate measurement';records[key]=x
 assert len(records)==raw['unique_geometries'] and set(records)==set(raw['requested_to_exact_input_hash'])
 fullkeys=set(); groups={i:[] for i in range(3552)}
 for i,f in enumerate(g['full_clock_geometries']):
  key=(f['day'],f['clock'],f['cohort']);assert key not in fullkeys;fullkeys.add(key)
  assert 0<=f['day']<210 and 0<=f['clock']<8 and 0<=f['cohort']<3
  assert masks['causal_cohort_clock'][90+f['day'],f['clock'],f['cohort']]
  assert f['input_sha256']==ih(f['X'],f['D'])
 assert len(fullkeys)==int(masks['causal_cohort_clock'][90:].sum())==3552
 for i,x in enumerate(g['geometries']):
  assert x['index']==i; f=g['full_clock_geometries'][x['full_index']]
  assert all(x[k]==f[k] for k in ['day','clock','cohort'])
  keep=[j for j,t in enumerate(f['targets']) if t!=x['excluded_target']]
  key=ih([f['X'][j] for j in keep],[f['D'][j] for j in keep])
  assert x['n']==len(keep) and key==x['input_sha256']==raw['requested_to_exact_input_hash'][i]
  assert key in records;groups[x['full_index']].append(x['excluded_target'])
 for i,f in enumerate(g['full_clock_geometries']):
  expected=[None]+design['universe']['cohort_target_ids'][design['universe']['cohorts'][f['cohort']]]
  assert groups[i]==expected
 counters={k:raw[k] for k in ['future_Y_reads','future_real_signed_response_computations','real_response_openings','full_null_trials','full_power_trials']}
 assert all(v==0 for v in counters.values()) and g['future_Y_computed']==0
 # Verified in-memory objects cached solely to avoid decompressing/parsing the raw twice.
 # This is not an authoritative input; interpreter verifies the durable bytes again.
 CACHE.write_bytes(pickle.dumps({'raw':raw,'geometry':g,'masks':masks,'design':design,'support':support},protocol=5))
 paths=list(bindings)+['research_core_v4/triad_v6/ACTUAL_PREDICTOR_ORACLE_RAW_V1_PARTS_MANIFEST.json','research_core_v4/triad_v6/ACTUAL_PREDICTOR_SUPPORT_AUDIT_PLAN_V1.json','research_core_v4/triad_v6/FIXTURE_GATE_SUMMARY_V1.json','research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json','research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json']
 record={'schema':'TRIAD_V6_INTERRUPTED_RAW_RECOVERY_INTEGRITY_V1','starting_head':head,'live_head_at_reconciliation':head,'newer_pre_recovery_commits':0,'integrity_pass':True,'parts':parts,'reconstructed_bytes':len(b),'reconstructed_sha256':digest,'gzip_decompression':'PASS','raw_schema':raw['schema'],'raw_decompression_and_JSON_parse_count':1,'input_bindings':{f:sha(R/f) for f in paths},'input_geometry_sha256':raw['input_geometry_gzip_sha256'],'mask_sha256':ms,'requested_geometries':55648,'mapping_count':55648,'unique_exact_input_geometries':len(records),'full_cohort_geometries':3552,'leaveout_geometries':52096,'missing_measurements':0,'duplicate_measurements':0,'conflicting_measurements':0,'all_exact_input_hashes_recomputed':True,'every_frozen_leaveout_verified':True,'counters':counters,'support_decisions_not_summarized':True,'cache_sha256':sha(CACHE),'cache_policy':'Derived local parsed-object cache; durable raw bytes remain authority; no oracle rerun','recovery_checker_sha256':sha(Path(__file__))}
 write('INTERRUPTED_SESSION_RECOVERY_INTEGRITY_V1.json',record)
 write('INTERRUPTED_SESSION_RECOVERY_AUTHORITY_V1.json',{'schema':'TRIAD_V6_INTERRUPTED_RECOVERY_AUTHORITY_V1','starting_head':head,'integrity_record_sha256':sha(P/'INTERRUPTED_SESSION_RECOVERY_INTEGRITY_V1.json'),'scope':'Freeze mechanical interpreter, execute once, persist numerical support verdict, stop','oracle_recomputation_authorized':False,'real_response_authorized':False,'Monte_Carlo_authorized':False,'V7_authorized':False,'dual_layer_build_authorized':False})
 print(json.dumps({k:record[k] for k in ['integrity_pass','requested_geometries','unique_exact_input_geometries','mapping_count','input_geometry_sha256']}))
if __name__=='__main__': main()

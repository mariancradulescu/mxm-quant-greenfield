from pathlib import Path
import json, hashlib, gzip, subprocess, ast, base64, io, sys
import numpy as np
R=Path(sys.argv[1]).resolve();P=R/'research_core_v4/triad_v6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True).strip()
start='c415673dfca55140fc9d332939776eb53432db6d';head=git('rev-parse','HEAD')
integrity=read(P/'INTERRUPTED_SESSION_RECOVERY_INTEGRITY_V1.json');freeze=read(P/'INTERPRETER_FREEZE_V1.json');authority=read(P/'NUMERICAL_PRODUCTION_AUTHORITY_V1.json');interpretation=read(P/'ACTUAL_NUMERICAL_SUPPORT_INTERPRETATION_V1.json');summary=read(P/'ACTUAL_NUMERICAL_SUPPORT_SUMMARY_V1.json');state=read(R/'research_core_v4/state/V4_STATE.json')
checks={}
for f,s in authority['input_bindings'].items():assert sha(R/f)==s,f
checks['all_authority_bindings_exact_head']=True
assert sha(P/'NUMERICAL_PRODUCTION_AUTHORITY_V1.json')==interpretation['numerical_production_authority_sha256']==state['current_authority']['sha256']
assert state['current_authority']['interpretation_sha256']==sha(P/'ACTUAL_NUMERICAL_SUPPORT_INTERPRETATION_V1.json')
checks['canonical_current_authority_and_interpretation_bound']=True
changed=git('diff','--name-only',start,head).splitlines()
assert all(f.startswith('research_core_v4/triad_v6/') or f=='research_core_v4/state/V4_STATE.json' for f in changed)
old=json.loads(subprocess.check_output(['git','show',start+':research_core_v4/state/V4_STATE.json'],cwd=R))
allowed={'status','current_next_action_type','next_action','stop_boundary'}
assert set(state)-set(old)=={'current_authority'} and not(set(old)-set(state))
assert all(state[k]==v for k,v in old.items() if k not in allowed)
checks['V1_V5_all_historical_fields_and_existing_V6_files_unchanged']=True
for f in git('ls-tree','-r','--name-only',start,'research_core_v4/triad_v6').splitlines():assert git('rev-parse',start+':'+f)==git('rev-parse',head+':'+f),f
assert read(P/'FIXTURE_GATE_SUMMARY_V1.json')['all_pass']
checks['fixture_PASS_and_every_frozen_V6_source_artifact_unchanged']=True
b=b''
for x in integrity['parts']:
 z=(R/x['path']).read_bytes();assert len(z)==x['bytes'] and hashlib.sha256(z).hexdigest()==x['sha256'];b+=z
assert len(b)==22765478 and hashlib.sha256(b).hexdigest()==integrity['reconstructed_sha256']
checks['raw_transport_reverified_without_decompression_or_oracle']=True
# Validate the new support artifact, never decompress/parse the oracle again.
rawbytes=gzip.decompress((P/'ACTUAL_NUMERICAL_SUPPORT_RAW_RESULT_V1.json.gz').read_bytes());support=json.loads(rawbytes)
assert hashlib.sha256(rawbytes).hexdigest()==summary['full_raw_result_JSON_sha256']
assert sha(P/'ACTUAL_NUMERICAL_SUPPORT_RAW_RESULT_V1.json.gz')==summary['full_raw_result_gzip_sha256']
assert {k:v for k,v in support.items() if k!='whole_clock_audit'}=={k:v for k,v in summary.items() if k not in ['full_raw_result_JSON_sha256','full_raw_result_gzip_sha256']}
assert support['support_interpretation_execution_count']==1
v2=read(R/'research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json');mb=base64.b64decode(v2['actual_masks_npz_base64']);assert hashlib.sha256(mb).hexdigest()==integrity['mask_sha256'];m=np.load(io.BytesIO(mb),allow_pickle=False)
availability=np.zeros((210,8,3),bool);seen=set()
for x in support['whole_clock_audit']:
 key=(x['day'],x['clock'],x['cohort']);assert key not in seen;seen.add(key)
 assert x['required_geometries']==[24,12,11][x['cohort']]
 assert x['numerically_usable']==(x['production_safe_geometries']==x['required_geometries'])
 availability[key]=x['numerically_usable']
assert len(seen)==3552 and len(support['leaf_support'])==12
assert sum(x['required_geometries'] for x in support['whole_clock_audit'])==55648
for leaf in support['leaf_support']:
 ci=['G10_MONETARY_TRIADS','MANAGED_EXTENSION_TRIADS','OTHER_EXTENSION_TRIADS'].index(leaf['cohort']);hi=[15,30,60,240].index(leaf['horizon_minutes'])
 daily=(availability[:,:,ci]&m['full_clock_horizon'][90:,:,ci,hi]).sum(axis=1)
 assert daily.tolist()==leaf['daily_complete_clock_counts']
 valid=daily>=4;blocks=[int(x.sum()) for x in valid.reshape(15,14)];thirds=[int(x.sum()) for x in valid.reshape(3,70)]
 assert blocks==leaf['block_day_counts'] and thirds==leaf['third_day_counts']
 assert int(daily.sum())==leaf['valid_complete_clocks'] and int(valid.sum())==leaf['valid_days']
 assert leaf['supported_blocks']==sum(x>=7 for x in blocks)
 assert leaf['pass']==(leaf['supported_blocks']>=12 and all(x>=42 for x in thirds))
 inherited=next(x for x in v2['leaf_support'] if x['cohort']==leaf['cohort'] and x['horizon_minutes']==leaf['horizon_minutes'])
 assert leaf['inherited_minimum90day_matured_training_rows']==inherited['minimum90day_matured_training_rows'] and leaf['inherited_maximum90day_matured_training_rows']==inherited['maximum90day_matured_training_rows']
checks['support_result_all12_leaves_original_calendar_and_nuisance_counts_verified']=True
assert support['all_actual_safety_certificates_pass'] and support['complete_12_leaf_support_pass'] and all(x['pass'] for x in support['leaf_support'])
assert interpretation['status']==authority['status']==state['status']
assert not any(authority[k] for k in ['Monte_Carlo_authorized','real_response_authorized','future_real_signed_response_authorized','new_acquisition_authorized','confirmation_authorized','protected_forward_authorized','trading_authorized'])
assert all(support[k]==0 for k in ['full_null_trials','full_power_trials','future_Y_reads','future_real_signed_response_computations','real_response_openings','broker_contacts','historical_requests','new_acquisition','candidate_frozen_count','orders'])
for f in [P/'recover_raw_integrity_v1.py',P/'interpret_actual_predictor_support_v1.py']:ast.parse(f.read_text())
checks['zero_response_MC_acquisition_confirmation_trading_and_syntax']=True
record={'schema':'TRIAD_V6_RECOVERY_EXACT_HEAD_VALIDATION_V1','validated_authority_head':head,'validated_authority_tree_sha':git('rev-parse','HEAD^{tree}'),'checks':checks,'all_pass':True,'support_interpreter_reexecuted':False,'oracle_reexecuted':False,'oracle_raw_decompressed_or_parsed_again':False,'final_head_resolution':'Commit containing this validation record; its only difference from validated_authority_head must be this record. Final ref and this exact delta are checked after publication.','validation_sha256_bindings':{str(f.relative_to(R)):sha(f) for f in P.iterdir() if f.is_file()},'validator_sha256':sha(Path(__file__))}
print(json.dumps(record,indent=2,sort_keys=True))

"""Accept the audited device-local proof; never read private raw or call a broker."""
import hashlib,json,math,re,zipfile
from pathlib import Path
from research_core_v4.quote_probe_decision_law_v1 import load_bound,decide
from V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY import canonical,proof_sanitized
NAMES={'CHECKPOINT_INTEGRITY_PROOF.json','LOSSLESS_RECONSTRUCTION_PROOF.json','PRIVATE_PROOF_MANIFEST.json','RAW_HASH_TREE.json','SUPPORT_MATRIX_RECOMPUTATION_PROOF.json','TRANSPORT_RECOMPUTATION_PROOF.json','CHECKSUMS.sha256'}
PREFIX='MXM_V4_QUOTE_SUPPORT_PRIVATE_PROOF_V1/'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def sealed(v):return dict(v,checkpoint_sha256=sha(canonical(v)))
def read_return(path,names,prefix):
 with zipfile.ZipFile(path) as z:
  entries=z.namelist();require(len(entries)==len(set(entries)) and z.testzip() is None,'ZIP integrity')
  require(set(entries) in [names,names|{prefix}|{prefix+n for n in names}],'unexpected member')
  files={n:z.read(n) for n in names}
  if prefix in entries:
   for n in names:require(z.read(prefix+n)==files[n],'conflicting duplicate wrapper')
 checks={}
 for line in files['CHECKSUMS.sha256'].decode().splitlines():
  h,n=line.split('  ');require(n in names-{'CHECKSUMS.sha256'} and n not in checks,'checksum entry');checks[n]=h
 require(set(checks)==names-{'CHECKSUMS.sha256'},'checksum coverage')
 for n,h in checks.items():require(sha(files[n])==h,'checksum mismatch')
 return files,len(entries)
def intake(root,path,compact):
 root=Path(root);path=Path(path);compact=Path(compact)
 prep=json.loads((root/'research_core_v4/state/QUOTE_SUPPORT_PRIVATE_PROOF_VERIFIER_PREPARATION_V1.json').read_bytes())
 accepted=json.loads((root/'research_core_v4/state/QUOTE_SUPPORT_PROBE_RETURN_INTAKE_V1.json').read_bytes())
 for n,h in prep['source_file_sha256'].items():require(sha((root/n).read_bytes())==h,'audited verifier source')
 package=root.parent/prep['android_verifier_package']['filename'];require(sha(package.read_bytes())==prep['android_verifier_package']['sha256'],'verifier package SHA')
 with zipfile.ZipFile(package) as z:
  prefix='MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/';manifest=z.read(prefix+'PRIVATE_PROOF_PACKAGE_MANIFEST.json');a_raw=z.read(prefix+'PRIVATE_PROOF_AUTHORITY_V1.json');a=json.loads(a_raw)
  for n,h in json.loads(manifest)['file_sha256'].items():require(sha(z.read(prefix+n))==h,'verifier internal binding')
 files,members=read_return(path,NAMES,PREFIX);values={n:json.loads(b) for n,b in files.items() if n.endswith('.json')}
 for v in values.values():proof_sanitized(v)
 m=values['PRIVATE_PROOF_MANIFEST.json'];c=values['CHECKPOINT_INTEGRITY_PROOF.json'];l=values['LOSSLESS_RECONSTRUCTION_PROOF.json'];tree=values['RAW_HASH_TREE.json'];support=values['SUPPORT_MATRIX_RECOMPUTATION_PROOF.json'];transport=values['TRANSPORT_RECOMPUTATION_PROOF.json']
 require(m['schema']=='mxm.v4.quote-support-private-proof.v1' and m['status']=='PASS_PRIVATE_EVIDENCE','PASS proof schema')
 for k in ['checkpoint_integrity','lossless_reconstruction','exact1120_complete','exact1155_wire_attempts','support_matrix_hash_match','raw_manifest_hash_match','evidence_unchanged']:require(m[k] is True,'proof flag '+k)
 require(m['network_calls']==0 and type(m['network_calls']) is int and m['pnl_computed'] is False and m['response_values_computed'] is False,'forbidden activity')
 require(m['verifier_package_manifest_sha256']==sha(manifest) and m['private_proof_authority_sha256']==sha(a_raw) and m['accepted_probe_manifest_sha256']==a['accepted_probe_manifest_sha256'],'exact audited verifier authority')
 require(m['accepted_compact_file_sha256']==a['compact_file_sha256'] and m['plan_sha256']==a['plan_sha256'],'compact/plan authority')
 recovery_raw=(root/'research_core_v4/state/DECODER_RECOVERY_AUTHORITY_V1.json').read_bytes();recovery=json.loads(recovery_raw)
 require(m['decoder_recovery_authority_sha256']==sha(recovery_raw),'recovery authority')
 require(m['evidence_tree_sha256_before']==m['evidence_tree_sha256_after']==tree['evidence_tree_sha256'],'private tree unchanged')
 def hash_ok(h):return isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) is not None
 require(hash_ok(tree['evidence_tree_sha256']) and hash_ok(tree['private_registry_sha256']),'private hash syntax')
 require(sha(compact.read_bytes())==accepted['input_zip']['sha256']==a['compact_zip_sha256'],'accepted compact outer hash')
 compact_names=set(accepted['input_zip']['file_sha256']);compact_files,_=read_return(compact,compact_names,'MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1/')
 for n,h in accepted['input_zip']['file_sha256'].items():require(sha(compact_files[n])==h,'compact file hash')
 metrics=json.loads(compact_files['TRANSPORT_METRICS.json']);raw=json.loads(compact_files['LOCAL_RAW_CHUNK_SHA256_MANIFEST.json']);execution=json.loads(compact_files['PROBE_EXECUTION_MANIFEST.json']);matrix=json.loads(compact_files['SUPPORT_ONLY_MATRIX.json']);schedule=json.loads(compact_files['SCHEDULE_PREFLIGHT.json'])
 require(tree['verified_raw_chunk_sha256']=={r['request_id']:r['raw_sha256'] for r in raw} and len(raw)==1120,'exact raw hash tree')
 expected_nodes={f"nodes/{r['request_id']}/{t['from_ms']}_{t['to_ms']}.json.gz" for r in metrics['logical_requests'] for t in r['traces']}
 require(set(tree['verified_node_sha256'])==expected_nodes and len(expected_nodes)==1154 and all(hash_ok(h) for h in tree['verified_node_sha256'].values()),'exact node tree')
 require(c['sealed_completed_records']==c['sealed_raw_payloads']==1120 and c['sealed_node_records']==1154 and c['journal_attempts']==c['journal_outcomes']==1155,'sealed counts')
 require(c['original_attempt_charged'] is True and c['replacement_attempts']==1 and c['original_replacement_payload_equality_proven'] is False and c['later_terminal_stop_absent'] is True and hash_ok(c['replacement_request_sha256']),'original recovery preserved')
 require(c['original_archive_hashes']['terminal_transport_stop.json']==recovery['original_stop_sha256'],'original STOP hash')
 active=c['original_active_seconds_charged'];current=c['current_active_seconds']
 require(type(active) in (int,float) and math.isfinite(active) and 0<active<=current<=7200 and type(current) in (int,float) and math.isfinite(current) and current>=a['minimum_completion_active_seconds'],'cumulative actual active time')
 require(c['original_archive_hashes']['active_seconds.json']==sha(canonical(sealed({'active_seconds':active}))),'exact original active bytes/value')
 require(c['original_archive_hashes']['current_schedule_preflight.json']==sha(canonical(sealed(schedule))),'original schedule seal bytes')
 first=metrics['wire_attempts'][0];attempt={k:first[k] for k in ['attempt_index','request_id','from_ms','to_ms','depth','retry_index']};attempt['status']='SENT_OR_ACK_UNKNOWN'
 require(c['original_archive_hashes']['wire_attempts.jsonl']==sha(canonical(sealed(attempt))+b'\n') and c['original_archive_hashes']['wire_outcomes.jsonl']==sha(canonical(sealed(first))+b'\n'),'original journal prefix bytes')
 require(l['logical_requests_reconstructed']==1120 and l['ticks']==accepted['observed_transport']['ticks'] and l['empty_completed_responses']==69 and l['exact_ordered_event_equality'] is True and l['exact_trace_equality'] is True and l['disjoint_complete_split_geometry'] is True and l['saturated_1ms'] is False,'lossless proof counts/geometry')
 require(support['sha256']==support['expected_sha256']==a['compact_file_sha256']['SUPPORT_ONLY_MATRIX.json'] and support['exact_match'] is True and support['identity_week_rows']==560 and support['response_values_read'] is False and support['economic_statistics_computed'] is False,'support proof')
 require(transport['transport_metrics_sha256']==a['compact_file_sha256']['TRANSPORT_METRICS.json'] and transport['raw_manifest_sha256']==a['compact_file_sha256']['LOCAL_RAW_CHUNK_SHA256_MANIFEST.json'] and transport['exact_compact_matches'] is True and transport['logical_base_requests']==1120 and transport['wire_attempts']==1155,'transport proof')
 law,plan=load_bound(root);verification=dict(accepted['verification'],checkpoint_integrity=True,lossless_reconstruction=True);decision=decide(law,plan,execution,matrix,verification)
 require(decision==accepted['conditional_support_only_decision_if_missing_private_proof_is_satisfied'],'frozen conditional decision parity')
 return {'schema':'mxm.v4.private-proof-return-intake.v1','status':'ACCEPTED_AUDITED_DEVICE_LOCAL_PRIVATE_PROOF','verifier_source_head':'b928417a8e928f3aea2a0f7cd9889d8aa157debe','input_zip':{'filename':path.name,'sha256':sha(path.read_bytes()),'size_bytes':path.stat().st_size,'members':members,'identical_duplicate_wrapper':members==15,'file_sha256':{n:sha(b) for n,b in files.items()}},'proof_provenance':'Private raw/checkpoints independently reread by the audited zero-network verifier on the original device. Work verified returned checksums, exact executable/authority bindings, all raw hashes and node paths against accepted compact evidence; Work did not receive or reread raw prices. This is a device-local verification attestation, not a cryptographic remote execution attestation.','verification':verification,'device_proof_summary':{'completed_requests':1120,'node_records':1154,'historical_attempts':1155,'ticks':l['ticks'],'empty_requests':69,'original_active_seconds_charged':active,'current_active_seconds_checkpoint':current,'exactly_one_replacement':True,'original_stop_preserved':True,'original_payload_equality_not_proven':True,'private_tree_unchanged_sha256':tree['evidence_tree_sha256'],'network_calls':0},'frozen_decision':decision,'support_readout':accepted['support_readout'],'no_more_acquisition_authorized':True,'work_broker_contacts':0,'work_historical_requests':0,'real_raw_quote_prices_opened_in_Work':0,'scientific_response_computations':0,'pnl_computed':False}

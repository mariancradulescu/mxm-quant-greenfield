"""Byte-preserving raw-result verification. Standard library; no scientific imports.

Digest the original UTF-8 bytes with only the top-level self member and its
adjacent comma removed. Never sort/re-serialize decoded nested mappings.
All real publication evidence is independently hash/identity pinned.
"""
from pathlib import Path
import argparse,base64,hashlib,io,json,re,subprocess,zipfile

REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='performance-research-v3-20260922'
PARENT='976f4336edce6362e03cc4b323e4de6270d47ab3'
ARM='007ad067b9c920f0ea5e8b44fb2046061eac628b'
FENCE='371cacad941d94a0d1bd96e624e8b48e2fa8a3c9'
RUN=37109343154
ARTIFACT=11269670040
ZIP_SHA='5ed3fb6a53f54f6ac5e773f34049767bb829aa8baf18e480562221efc08c4e00'
RAW_SHA='77462da0329b21dd981896c3ab31f3383ef8f092948ac1c6c61a6c148e630208'
SELF_SHA='9e6c552549f4334e3d4b0b91ad537b9e44db098e5a4b151264b0e02e37378fbb'
MEMBERS={
 'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json':RAW_SHA,
 'prepared.json':'acd21f7876ed8a5131d14ba0b7f98b23218f0a5c5d191710623f7637520f5571',
 'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json.opening.lock':'1cb924858cf9cf6a3248f41d2aa27a19f5d517a703adb4caba35d8da3ccb3a64',
 'failure-classification.json':'d5b054841ca76f17b4338c320c2a3981a4de6dfb24c5bcc3a0dccdb1ecea6b1b'}
RAW_NAME='FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'
SELF_FIELD='raw_result_sha256_without_self_field'
RESULT_REL='research_core_v4/state/'+RAW_NAME
ARM_REL='research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ARM_V1.json'
FENCE_REL='research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ATTEMPT_LOCK_V1.txt'
PUB_REL='research_core_v4/state/V4_CANONICAL_RESULT_PUBLICATION_V1.json'
AUDIT_REL='research_core_v4/state/V4_PUBLICATION_ONLY_RECOVERY_AUDIT_V1.json'
PREPARED_REL='research_core_v4/state/V4_PUBLICATION_ONLY_PREPARED_V1.json'
FAILURE_REL='research_core_v4/state/V4_PUBLICATION_ONLY_FAILURE_CLASSIFICATION_V1.json'
STATE_REL='research_core_v4/state/V4_STATE.json'

def require(condition,message):
 if not condition:raise PermissionError('PUBLICATION_ONLY_FAIL_CLOSED '+message)
def sha(data):return hashlib.sha256(data).hexdigest()
def unique_pairs(pairs):
 out={}
 for key,value in pairs:
  require(key not in out,'duplicate JSON member')
  out[key]=value
 return out

def original_byte_self_digest(raw):
 """Return verified root metadata; hash original slices, not decoded values.

The frozen producer emits compact top-level JSON with one terminating newline.
JSONDecoder locates member boundaries (including escaped/unicode strings and
nested objects); decoded outcome values are never examined or rewritten.
 """
 require(isinstance(raw,bytes),'original bytes required')
 text=raw.decode('utf-8',errors='strict')
 require(text.startswith('{') and text.endswith('}\n'),'producer framing')
 decoder=json.JSONDecoder(object_pairs_hook=unique_pairs)
 members=[];document={};pos=1
 while text[pos]!='}':
  start=pos;key,pos=decoder.raw_decode(text,pos)
  require(isinstance(key,str) and key not in document,'root key/duplicate')
  require(text[pos]==':','compact root colon');pos+=1
  value,pos=decoder.raw_decode(text,pos)
  document[key]=value;members.append((key,start,pos))
  if text[pos]==',':pos+=1
  else:require(text[pos]=='}','root delimiter');break
 require(pos==len(text)-2,'single root object/no trailing data')
 indices=[i for i,(key,_,_) in enumerate(members) if key==SELF_FIELD]
 require(len(indices)==1,'one top-level self digest')
 index=indices[0];_,start,end=members[index]
 declared=document[SELF_FIELD]
 require(isinstance(declared,str) and re.fullmatch('[0-9a-f]{64}',declared) is not None,'self digest format')
 if index+1<len(members):end=members[index+1][1]
 elif index>0:start=members[index-1][2]
 # Convert character offsets to byte offsets; exclusion uses ORIGINAL raw bytes.
 a=len(text[:start].encode('utf-8'));b=len(text[:end].encode('utf-8'))
 without_self=raw[:a]+raw[b:]
 calculated=sha(without_self)
 require(calculated==declared,'producer self digest')
 return document,{'producer_self_digest':declared,'byte_preserving_self_digest':calculated,'original_raw_sha256':sha(raw),'removed_byte_span':[a,b]}

def verify_candidate_metadata(raw,prepared):
 document,proof=original_byte_self_digest(raw)
 require(document.get('schema')=='mxm.research-core-v4.development-response-result.v2','result schema')
 require(document.get('execution_provenance')==prepared['provenance'],'prepared provenance mismatch')
 for flag in ('confirmation_execution_authorized','broker_acquisition_authorized','candidate_promotion_authorized'):
  require(document.get(flag) is False,'unauthorized scope flag')
 # This return is used only for structural validation; no scientific fields output.
 return document,proof

def real_expected():
 return {'repository':REPO,'branch':BRANCH,'certified_parent':PARENT,'arm_commit':ARM,'fence_commit':FENCE,
  'run_id':RUN,'artifact_id':ARTIFACT,'artifact_name':f'v4-raw-recovery-{RUN}-1','artifact_zip_sha256':ZIP_SHA,
  'member_hashes':dict(MEMBERS),'raw_size':592982,'producer_self_digest':SELF_SHA}

def verify_evidence(archive,identity,run,history,arm_raw,fence_raw,expected,existing_result=None,accepted_count=0):
 require(existing_result is None,'second/already-present canonical result')
 require(accepted_count==0,'canonical count must be zero before publication')
 require(identity.get('repository')==expected['repository'],'artifact repository')
 require(identity.get('id')==expected['artifact_id'] and identity.get('name')==expected['artifact_name'],'artifact identity')
 require(identity.get('expired') is False,'expired artifact')
 require(identity.get('digest')=='sha256:'+expected['artifact_zip_sha256'],'artifact API digest')
 origin=identity.get('workflow_run',{})
 require(origin.get('id')==expected['run_id'] and origin.get('head_sha')==expected['arm_commit'] and origin.get('head_branch')==expected['branch'],'artifact workflow ownership')
 require(run.get('id')==expected['run_id'] and run.get('run_attempt')==1 and run.get('head_sha')==expected['arm_commit'],'original run/first attempt')
 require(run.get('status')=='completed' and run.get('conclusion')=='failure','original failed run retained')
 require(run.get('path')=='.github/workflows/v4-greenfield-recovery-v4.yml','original installed workflow')
 require(history=={'branch_head':expected['fence_commit'],'fence_commit':expected['fence_commit'],'fence_parent':expected['arm_commit'],'arm_commit':expected['arm_commit'],'arm_parent':expected['certified_parent']},'exact ARM/fence/parent history')
 require(sha(archive)==expected['artifact_zip_sha256'],'artifact ZIP bytes')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  require(len(z.namelist())==4 and set(z.namelist())==set(expected['member_hashes']),'exact unique four artifact members')
  require(all(not i.is_dir() and i.file_size<20_000_000 for i in z.infolist()),'artifact member bounds')
  members={name:z.read(name) for name in z.namelist()}
 for name,want in expected['member_hashes'].items():require(sha(members[name])==want,'artifact member hash '+name)
 raw=members[RAW_NAME];require(len(raw)==expected['raw_size'],'raw byte size')
 prepared=json.loads(members['prepared.json'],object_pairs_hook=unique_pairs)
 failure=json.loads(members['failure-classification.json'],object_pairs_hook=unique_pairs)
 arm=json.loads(arm_raw,object_pairs_hook=unique_pairs);fence=json.loads(fence_raw,object_pairs_hook=unique_pairs)
 require(arm.get('pre_arm_parent_head')==expected['certified_parent'],'ARM certified parent')
 require(arm.get('accepted_canonical_result_limit')==1 and arm.get('automatic_retry') is False,'ARM singleton boundary')
 require(fence.get('arm_commit')==expected['arm_commit'] and fence.get('arm_document_sha256')==sha(arm_raw),'fence exact ARM bytes')
 require(fence.get('owner_run_id')==str(expected['run_id']) and fence.get('owner_run_attempt')==1,'fence owner')
 require(fence.get('prepared_sha256')==sha(members['prepared.json']),'fence prepared digest')
 require(fence.get('canonical_result_limit')==1 and fence.get('automatic_retry') is False,'fence singleton boundary')
 require(members[RAW_NAME+'.opening.lock']==(prepared['provenance']['authority_sha256']+'\n').encode(),'original local opening-lock authority')
 require(failure.get('classification')=='RAW_RESULT_RECOVERABLE_PUBLICATION_ONLY_NO_RECOMPUTATION' and failure.get('arm_commit')==expected['arm_commit'] and failure.get('fence_commit')==expected['fence_commit'] and failure.get('owner_run_id')==str(expected['run_id']),'failure provenance')
 require(failure.get('automatic_retry') is False and failure.get('market_outcome_interpreted') is False,'failure boundary')
 document,proof=verify_candidate_metadata(raw,prepared)
 require(proof['producer_self_digest']==expected['producer_self_digest'],'pinned producer self digest')
 require(prepared.get('response_opened') is False,'original prepared stage')
 return members,proof

def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args])
def history_at_fence(root):
 head=git(root,'rev-parse','HEAD').decode().strip()
 fence_parent=git(root,'rev-list','--parents','-n','1',FENCE).decode().split()
 arm_parent=git(root,'rev-list','--parents','-n','1',ARM).decode().split()
 require(len(fence_parent)==2 and len(arm_parent)==2,'single parents')
 return {'branch_head':head,'fence_commit':fence_parent[0],'fence_parent':fence_parent[1],'arm_commit':arm_parent[0],'arm_parent':arm_parent[1]}

def verify_canonical(root):
 """Post-result integrity validation only; never imports any execution code."""
 expected=real_expected();head=git(root,'rev-parse','HEAD').decode().strip()
 parents=git(root,'rev-list','--parents','-n','1','HEAD').decode().split()
 require(len(parents)==2 and parents[1]==FENCE,'atomic exact-fence successor')
 arm_raw=(root/ARM_REL).read_bytes();fence_raw=(root/FENCE_REL).read_bytes()
 require(arm_raw==git(root,'show',ARM+':'+ARM_REL),'existing ARM unchanged')
 require(fence_raw==git(root,'show',FENCE+':'+FENCE_REL),'existing fence unchanged')
 raw=(root/RESULT_REL).read_bytes();require(sha(raw)==RAW_SHA and len(raw)==592982,'canonical original raw bytes')
 prepared_raw=(root/PREPARED_REL).read_bytes();require(sha(prepared_raw)==MEMBERS['prepared.json'],'durable prepared bytes')
 failure_raw=(root/FAILURE_REL).read_bytes();require(sha(failure_raw)==MEMBERS['failure-classification.json'],'durable original failure bytes')
 prepared=json.loads(prepared_raw,object_pairs_hook=unique_pairs)
 _,proof=verify_candidate_metadata(raw,prepared);require(proof['producer_self_digest']==SELF_SHA,'canonical producer digest')
 publication=json.loads((root/PUB_REL).read_bytes(),object_pairs_hook=unique_pairs)
 audit=json.loads((root/AUDIT_REL).read_bytes(),object_pairs_hook=unique_pairs)
 fence=json.loads(fence_raw);arm=json.loads(arm_raw)
 require(fence['prepared_sha256']==sha(prepared_raw),'canonical prepared/fence binding')
 require(fence['arm_document_sha256']==sha(arm_raw) and fence['arm_commit']==ARM and fence['owner_run_id']==str(RUN),'canonical fence ownership')
 require(arm['pre_arm_parent_head']==PARENT,'canonical ARM parent')
 for field,value in {'certified_pre_arm_parent':PARENT,'arm_commit':ARM,'fence_commit':FENCE,'original_workflow_run_id':RUN,'artifact_id':ARTIFACT,'artifact_zip_sha256':ZIP_SHA,'result_sha256':RAW_SHA,'embedded_producer_self_digest':SELF_SHA,'prepared_sha256':MEMBERS['prepared.json'],'failure_classification_sha256':MEMBERS['failure-classification.json'],'local_opening_lock_sha256':MEMBERS[RAW_NAME+'.opening.lock'],'accepted_canonical_result_count':1,'accepted_canonical_result_limit':1,'interpretation_performed':False,'no_recomputation':True,'automatic_retry':False}.items():require(publication.get(field)==value,'publication field '+field)
 require(publication.get('accepted_canonical_result_count_transition')=={'from':0,'to':1},'single count transition')
 require(publication.get('prepared')==prepared,'published prepared provenance')
 require(publication.get('publication_only_recovery_audit_sha256')==sha((root/AUDIT_REL).read_bytes()),'audit hash binding')
 require(sha(base64.b64decode(audit['original_local_opening_lock_base64'],validate=True))==MEMBERS[RAW_NAME+'.opening.lock'],'archived original local lock bytes')
 require(audit.get('status')=='PASS_PUBLICATION_ONLY_RECOVERY_NO_RECOMPUTATION' and audit.get('scientific_interpretation_performed') is False,'publication audit status')
 require(audit['synthetic_proof']['status']=='PASS' and audit['synthetic_proof']['scientific_response_calls']==0,'outcome-blind synthetic proof')
 for rel,want in audit['recovery_control_files_sha256'].items():require(sha((root/rel).read_bytes())==want,'recovery control '+rel)
 state=json.loads((root/STATE_REL).read_bytes());p=state['recovery_v4_preparation'];fw=state['first_wave']
 require(p['accepted_canonical_result_count']==1 and p['accepted_canonical_result_limit']==1,'canonical singleton count')
 require(p['arm_present'] is True and p['attempt_lock_present'] is True and p['canonical_result_present'] is True and p['process_attempts_started']==1,'reconciled real durable history')
 require(p['real_execution_authorized'] is False and p['automatic_retry'] is False,'no future execution/retry')
 require(fw['development_execution_completed'] is True and fw['development_raw_result_persisted'] is True and fw['development_result_interpreted'] is False and fw['current_recovery_execution_authorized'] is False,'uninterpreted completed state')
 require(git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD','--',ARM_REL,FENCE_REL)==b'','no new/replaced ARM or fence')
 return {'status':'PASS_POST_RESULT_PUBLICATION_ONLY_INTEGRITY','head':head,'canonical_result_sha256':RAW_SHA,'accepted_canonical_result_count':1,'scientific_recomputation':False,'interpretation_performed':False}

def main():
 a=argparse.ArgumentParser();a.add_argument('--verify-canonical',type=Path,required=True);x=a.parse_args()
 print(json.dumps(verify_canonical(x.verify_canonical.resolve()),sort_keys=True))
if __name__=='__main__':main()

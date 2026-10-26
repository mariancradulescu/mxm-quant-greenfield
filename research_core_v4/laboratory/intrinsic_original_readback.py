"""No-key readback of two exact original artifacts; never evaluate or decrypt."""
import base64,hashlib,io,json,os,subprocess,zipfile
from pathlib import Path
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-intrinsic-original-evidence-readback.yml'
RUN=40285218660
SOURCE='b5b14da063a40f93797b8bc8a15537fe79489215'
SCIENCE='61da70636bd4eb9a316ab7c7365836290f510be510e3d862247da493d6135b12'
REPAIR='f7d3d65c8bc74031e9107c9a3acd2063483d8b625c2834adf42268fb9cac1d3f'
ARCHIVES={
 12633527925:('result',4612,'9fda9674189738ee71af4d4d813d4dbb85279011955000fc1fe81cf678699ea5'),
 12633662447:('evaluator',60510,'80fdea408955dc860a9f70c06e044c1c1f7ddab830b580a381592f5191b9bb3c')}
def need(ok,why):
    if not ok:raise ValueError('ORIGINAL_INTRINSIC_READBACK_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read_bundle(raw,kind,expected_size,expected_sha):
    need(len(raw)==expected_size and sha(raw)==expected_sha,'ORIGINAL_ZIP')
    allowed={'receipt.json','recovery.json','full-result.mxmenc'} if kind=='result' else {
      'MxmIntrinsicAccount.dll','MxmIntrinsicAccount.deps.json','MxmIntrinsicAccount.runtimeconfig.json'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==3 and set(z.namelist())==allowed and sum(i.file_size for i in z.infolist())<2000000,'MEMBERS')
        files={n:z.read(n) for n in z.namelist()}
    return files
def main():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')=='original-byte-readback' and
      os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'CONTEXT')
    need(not any(os.environ.get(k) for k in ('R3_CUSTODY_PRIVATE_KEY_PEM','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',
      'SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'NO_CUSTODY_BROKER_WRITER_KEYS')
    code=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(code==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'EXACT_CHECKOUT')
    route=GetOnly()
    need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==code,'OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'UNCHANGED_AUTHORITY')
    own=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(own['total_count']==len(own['workflow_runs'])==1 and own['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and own['workflow_runs'][0]['run_attempt']==1,'ONE_READBACK')
    original=route.json('actions/runs/'+str(RUN))
    need(original['head_sha']==SOURCE and original['run_attempt']==1 and original['status']=='completed' and original['conclusion']=='success','ORIGINAL_NATIVE_RUN')
    archives={};summaries={}
    for ident,(kind,size,digest) in ARCHIVES.items():
        meta=route.json('actions/artifacts/'+str(ident))
        need(meta['id']==ident and meta['workflow_run']['id']==RUN and meta['workflow_run']['head_sha']==SOURCE and
          meta['size_in_bytes']==size and meta['digest']=='sha256:'+digest and not meta['expired'],'ORIGINAL_NATIVE_ARTIFACT')
        raw=route.data('actions/artifacts/'+str(ident)+'/zip',limit=1000000)
        files=read_bundle(raw,kind,size,digest);archives[ident]=(raw,files)
        summaries[str(ident)]={'kind':kind,'archive_bytes':size,'archive_sha256':digest,
          'members':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in files.items()}}
    result=archives[12633527925][1];evaluator=archives[12633662447][1]
    r=json.loads(result['receipt.json']);recovery=json.loads(result['recovery.json'])
    need(r['schema']=='mxm.intrinsic-account-public.v1' and r['run_id']==RUN and r['source_sha']==SOURCE and r['spec_sha256']==SCIENCE and
      r['source_rows_verified']==2129692 and r['models']==r['cost_scenarios']==1 and r['disposition']=='DATA_LIMITED' and
      r['gates']=={'complete_three_week_account':False} and r['fresh_csharp_processes_executed']==1 and
      r['independent_all_decisions_and_money_reconciled'] is True and r['orders']==r['new_broker_requests']==0 and
      all(r[k] is False for k in ('hard21_proven','economic_edge_proven','historical_costs_proven','native_ctrader_runtime_reception','cloud_activated','canonical_V2_C033_changed')),'ORIGINAL_RESULT_NO_PROMOTION')
    need(sha(result['full-result.mxmenc'])==r['ciphertext_sha256']=='c7b1a021a283d7265645c312fddd1bcc2ff59f211f8278f837f1c4a2c10843d3' and
      r['private_sha256']=='f509969a84b83703ef3babc185dd542a4eb2bdaa2b6f3007db1b062b2734637a','ORIGINAL_CIPHER')
    need(recovery['recovery_run']==RUN and recovery['original_failed_run']==40283113616 and recovery['original_failed_job']==121440966951 and
      recovery['source_sha']==SOURCE and recovery['original_policy_spec_sha256']==SCIENCE and recovery['technical_recovery_spec_sha256']==REPAIR and
      recovery['original_economic_execution']=='SKIPPED' and recovery['scientific_parameters_changed'] is False and
      recovery['original_native_attempt_refunded'] is False and recovery['new_scientific_model'] is False,'ORIGINAL_RECOVERY')
    need(recovery['evaluator_dll_sha256']==sha(evaluator['MxmIntrinsicAccount.dll']) and evaluator['MxmIntrinsicAccount.dll'].startswith(b'MZ') and
      json.loads(evaluator['MxmIntrinsicAccount.runtimeconfig.json'])['runtimeOptions']['tfm']=='net8.0','EXACT_COMPILED_ASSEMBLY')
    public={n:base64.b64encode(result[n]).decode() for n in ('receipt.json','recovery.json')}
    print('MXM_ORIGINAL_SUMMARY '+json.dumps({'schema':'mxm.intrinsic-original-byte-readback.v1','readback_run':int(os.environ['GITHUB_RUN_ID']),
      'readback_source_sha':code,'original_run':RUN,'original_source_sha':SOURCE,'artifacts':summaries,'public_original_json_b64':public,
      'decrypted':False,'economic_rerun':False,'orders':0,'broker_requests':0},sort_keys=True),flush=True)
    for ident,(raw,_) in archives.items():
        for index,offset in enumerate(range(0,len(raw),16384)):
            part=raw[offset:offset+16384]
            print('MXM_ORIGINAL_PART '+json.dumps({'artifact_id':ident,'index':index,'bytes':len(part),'sha256':sha(part),'b64':base64.b64encode(part).decode()},sort_keys=True),flush=True)
if __name__=='__main__':main()

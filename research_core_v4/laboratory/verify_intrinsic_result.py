"""Offline verification of ORIGINAL bytes. Never decrypt, build, or replay a model."""
import base64, hashlib, io, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261026/intrinsic-result-40285218660'
MANIFEST_SHA='dc1b53d78e4f83071d62b732aba046891952a5ab6dcb084cdf51f4b2bd3f2eaa'
SCIENCE='61da70636bd4eb9a316ab7c7365836290f510be510e3d862247da493d6135b12'
REPAIR='f7d3d65c8bc74031e9107c9a3acd2063483d8b625c2834adf42268fb9cac1d3f'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('INTRINSIC_ORIGINAL_'+why)
def read(folder,name,limit):
    p=Path(folder)/name
    need(not p.is_symlink() and p.is_file() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE')
    return p.read_bytes()
def verify(folder=FOLDER,code_root=ROOT):
    raw=read(folder,'MANIFEST.json',20000);need(sha(raw)==MANIFEST_SHA,'MANIFEST')
    m=json.loads(raw);files={}
    need(m['original_run']==40285218660 and m['readback_run']==40286679891 and m['readback_job']==121451871522,'NATIVE_PROVENANCE')
    for aid,a in m['artifacts'].items():
        b64=read(folder,a['kind']+'.zip.b64',100000)
        need(b64.endswith(b'\n') and b'\n' not in b64[:-1],'CANONICAL_BASE64')
        b=base64.b64decode(b64[:-1],validate=True)
        need(len(b)==a['archive_bytes'] and sha(b)==a['archive_sha256'],'EXACT_ORIGINAL_ZIP')
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            need(len(z.namelist())==3 and set(z.namelist())==set(a['members']) and sum(i.file_size for i in z.infolist())<2000000,'BOUNDED_UNIQUE_ZIP_MEMBERS')
            for n,v in a['members'].items():
                data=z.read(n);need(len(data)==v['bytes'] and sha(data)==v['sha256'],'EXACT_ORIGINAL_MEMBER');files[n]=data
    for n in ('receipt.json','recovery.json'):need(read(folder,n,5000)==files[n],'PUBLIC_COPY')
    r=json.loads(files['receipt.json']);c=json.loads(files['recovery.json'])
    need(r['disposition']=='DATA_LIMITED' and r['gates']=={'complete_three_week_account':False} and r['fresh_csharp_processes_executed']==1,'NO_THREE_WEEK_PROMOTION')
    need(r['source_rows_verified']==2129692 and r['independent_all_decisions_and_money_reconciled'] and r['models']==r['cost_scenarios']==1,'EXACT_EVALUATED_PATH')
    need(r['run_id']==m['original_run'] and r['source_sha']==m['original_source_sha'] and r['spec_sha256']==SCIENCE,'RESULT_PROVENANCE')
    need(r['orders']==r['new_broker_requests']==0 and all(r[k] is False for k in ('economic_edge_proven','hard21_proven','historical_costs_proven','native_ctrader_runtime_reception','cloud_activated','canonical_V2_C033_changed')),'NO_PROMOTION')
    need(sha(files['full-result.mxmenc'])==r['ciphertext_sha256'] and r['private_sha256']=='f509969a84b83703ef3babc185dd542a4eb2bdaa2b6f3007db1b062b2734637a','CIPHER_COMMITMENT')
    need(c['recovery_run']==m['original_run'] and c['original_failed_run']==40283113616 and c['original_failed_job']==121440966951 and c['original_economic_execution']=='SKIPPED','FAILED_ATTEMPT_RETAINED')
    need(c['original_policy_spec_sha256']==SCIENCE and c['technical_recovery_spec_sha256']==REPAIR and all(c[k] is False for k in ('scientific_parameters_changed','new_scientific_model','original_native_attempt_refunded')),'UNCHANGED_SCIENCE')
    need(c['evaluator_dll_sha256']==sha(files['MxmIntrinsicAccount.dll']) and files['MxmIntrinsicAccount.dll'].startswith(b'MZ') and json.loads(files['MxmIntrinsicAccount.runtimeconfig.json'])['runtimeOptions']['tfm']=='net8.0','SAME_ORIGINAL_ASSEMBLY')
    diagnostic_raw=read(folder,'source-compatibility-public.json',10000)
    need(sha(diagnostic_raw)=='802921071493c31af07003161b1d099b25eb05137479b61aad8165cd85753d25','ORIGINAL_DIAGNOSTIC_READBACK')
    diagnostic=json.loads(diagnostic_raw)
    need(diagnostic['run_id']==40296107836 and diagnostic['source_sha']=='d8b04a5df0f16925b9bf686c57e3f2be071aa946' and diagnostic['original_economic_run']==40285218660 and diagnostic['original_fault_verified']=='OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE','DIAGNOSTIC_PROVENANCE')
    need(diagnostic['economic_rerun'] is False and diagnostic['new_models']==diagnostic['new_economic_outcomes']==diagnostic['new_broker_requests']==diagnostic['orders']==0,'DIAGNOSTIC_NOT_NEW_ECONOMICS')
    applicability={}
    for n,want in [('original-scientific-spec.json',SCIENCE),('original-technical-recovery.json',REPAIR)]:
        b=read(folder,n,20000);need(sha(b)==want,'ORIGINAL_PRECOMMIT');p=json.loads(b)
        applicability[n]=all((Path(code_root)/k).is_file() and sha((Path(code_root)/k).read_bytes())==h for k,h in p['implementation_sha256'].items())
    return {'schema':'mxm.intrinsic-original-offline-verification.v1','original_archives_verified':True,'original_compiled_assembly_preserved':True,'native_source_diagnostic_preserved':True,'current_pinned_dependencies_match':all(applicability.values()),'private_plaintext_digest_attested_only':True,'disposition':r['disposition'],'complete_three_week_account':False,'economic_edge_proven':False,'hard21_proven':False,'native_ctrader_runtime_reception':False,'decrypted':False,'economic_rerun':False,'orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))

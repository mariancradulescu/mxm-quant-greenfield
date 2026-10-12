"""Copy existing saved economic and contract evidence; no gate, model or metric replay."""
import os,json,pathlib,tempfile,subprocess
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
P='research_core_v4/information_source_investigation_v1/';e=rt.e;PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def main():
 global PHASE
 os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'SOURCE_READBACK_V1.json')).read_text())
 need(a['authority']=='OWNER_INFORMATION_FRONTIER_INVESTIGATION_20261012','AUTHORITY');need(not any(a[k] for k in ('model_execution','economic_recalculation','broker_requests','orders','protected_forward','Cloud_changes')),'READBACK_ONLY')
 need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-information-source-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
 for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'BINDING')
 old=subprocess.check_output(['git','ls-tree','-r',a['base_head']],cwd=e.a.ROOT,text=True).splitlines();new=set(subprocess.check_output(['git','ls-tree','-r',h],cwd=e.a.ROOT,text=True).splitlines());need(all(r in new for r in old),'OLD_FILES_PRESERVED');e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
 with tempfile.TemporaryDirectory(prefix='mxm-source-readback-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='EXISTING_RESULT_COPY';saved,sp=load_asset(key,fp,tmp,a['saved_economic_source']);archive,ap=load_asset(key,fp,tmp,a['contract_source'])
  need(saved['summary']['source_head']==a['saved_head'],'SOURCE_HEAD');ids={x['sid'] for x in saved['all_saved_instrument_economic_support']};need(len(ids)==len(saved['all_saved_instrument_economic_support']),'UNIQUE_IDENTITIES')
  rows={r['sid']:r for r in archive['all_identity_status']};contracts=[{'row':rows[sid],'native_full':archive['catalog']['full'][str(sid)]} for sid in sorted(ids)]
  PHASE='ENCRYPTED_COPY_DELIVERY';relay(h,a,tmp,{'schema':'mxm.private.saved.contract.source.readback.v1','source_head':h,'input_provenance':[sp,ap],'instrument_economics':saved['all_saved_instrument_economic_support'],'native_contracts':contracts,'prior_gates_reexecuted':False,'metrics_recalculated':False,'source_schema':list(archive),'model_calls':0,'broker_requests':0,'orders':0})
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1) from None

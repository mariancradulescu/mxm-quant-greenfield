"""One-use saved economic evidence audit; no market API, models or old kernels."""
import os,json,tempfile,pathlib,subprocess
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from .reduce_v1 import reduce_saved
P='research_core_v4/predictive_feasibility_stopgo_v1/';e=rt.e;PHASE='GATE'
def need(ok,code):e.w.old.need(bool(ok),code)
def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h)
    auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());design=json.loads((e.a.ROOT/(P+'DESIGN_FREEZE_V1.json')).read_text());history=json.loads((e.a.ROOT/(P+'HISTORY_RECONCILIATION_V1.json')).read_text())
    need(auth['authority']=='EXPLICIT_OWNER_PREDICTIVE_FRONTIER_STOPGO_20261012','OWNER_AUTHORITY')
    need(not any(auth[k] for k in ('orders','protected_forward','broker_requests','closed_kernel_calls','cloud_changes','authentication_changes')),'OWNER_LIMITS')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-predictive-feasibility-stopgo-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
    e.a.ancestor(auth['base_head'],h);e.a.ancestor(auth['design_commit'],h)
    for p,s in {**history['file_sha256'],**auth['bindings']}.items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_BINDING')
    inventory=lambda ref:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
    old=inventory(auth['base_head']);new=inventory(h);need(all(new.get(p)==s for p,s in old.items()),'ALL_OLD_FILES_PRESERVED')
    ledger=json.loads((e.a.ROOT/'research_core_v4/state/POST_QUOTE_V4_CLOSURE_LEDGER_V2.json').read_text());need(len(ledger['nodes'])==len(history['historical_nodes'])==51,'HISTORY51')
    need({n['id'] for n in ledger['nodes']}=={n['id'] for n in history['historical_nodes']},'HISTORY_IDENTITY')
    e.w.old.verify_science();need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-predictive-feasibility-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY')
        PHASE='AUTHENTIC_SAVED_EVIDENCE';saved,sp=load_asset(key,fp,tmp,auth['stage_A_source']);archive,ap=load_asset(key,fp,tmp,auth['cost_frequency_source']);matched,mp=load_asset(key,fp,tmp,auth['matched_source'])
        need(saved['summary']['source_head']==auth['stage_A_head'],'STAGE_A_SOURCE');need(archive['summary']['source_head']==auth['cost_frequency_head'],'COST_SOURCE');need(matched['summary']['source_head']==auth['base_head'],'MATCHED_SOURCE_HEAD')
        PHASE='NUMERIC_ECONOMIC_AND_INFORMATION_GATE';detail,summary=reduce_saved(saved,archive,matched,design)
        summary.update(source_head=h,design_commit=auth['design_commit'],input_provenance=[sp,ap,mp],history_node_count=len(history['historical_nodes']),history_bound_file_count=len(history['file_sha256']),all_existing_file_count=len(old),all_existing_files_preserved=True,design_sha256=e.w.old.filehash(P+'DESIGN_FREEZE_V1.json'),history_sha256=e.w.old.filehash(P+'HISTORY_RECONCILIATION_V1.json'))
        PHASE='ENCRYPTED_OWNER_EVIDENCE';rt.output(h,auth,tmp,key,'predictivefeasibility',detail,summary)
        PHASE='ENCRYPTED_SESSION_RELAY';relay(h,auth,tmp,summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1) from None

"""Credential-free whole-workflow admission; not an economic certificate.

Original workflow bytes are retained in the source snapshot and Git history.
Only the existing five R7 role workflows may retain credential environments.
This CI guard strengthens trusted review; it cannot make editable status-check
workflows an organization-level required-workflow rule.
"""
import hashlib,json,os,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOTS=ROOT/'verification/workflow-boundary'
CI='.github/workflows/mxm-r3-isolation-install-ci.yml'
SOURCE_REF='mxm-r3-workflow-boundary-source-20261021'
REPO='mariancradulescu/mxm-quant-greenfield'
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
ACTIVE={'.github/workflows/'+name for name in (
    'mxm-integrated-p0.yml','mxm-integrated-p0-recovery.yml',
    'mxm-r3-certify-v3.yml','mxm-r3-chronology-reception.yml',
    'mxm-r3-pepperstone-access-reception.yml')}

def require(value,code):
    if not value:raise ValueError(code)

def baseline(mode):
    require(mode in ('main','exec'),'BOUNDARY_MODE')
    return json.loads((SNAPSHOTS/(mode+'_workflows.json')).read_bytes())

def baseline_json(mode,name):
    path='.github/workflows/'+name
    require(path in baseline(mode),'BOUNDARY_BASELINE_PATH')
    return baseline(mode)[path]

def readonly(permissions):
    return permissions=='read-all' or (type(permissions) is dict and
        all(v in ('read','none') for v in permissions.values()))

def legacy_privileged(raw):
    doc=yaml.load(raw,Loader=yaml.BaseLoader)
    require(type(doc) is dict and type(doc.get('jobs')) is dict,'BOUNDARY_WORKFLOW_SCHEMA')
    # Also reject expressions, aliases and inherited/reusable secret routes by
    # admitting complete workflow bytes, rather than matching one secret name.
    if re.search(r'\bsecrets\s*[.\[]',raw):return True
    if not readonly(doc.get('permissions')):return True
    for job in doc['jobs'].values():
        if 'environment' in job or 'uses' in job:return True
        if not readonly(job.get('permissions',doc.get('permissions'))):return True
    return False

def quarantine(path):
    return json.dumps({'name':'MXM retired completed legacy route: '+Path(path).stem,
        'on':{'workflow_dispatch':{}},'permissions':{},'jobs':{
            'retired-policy-stop':{'if':'${{ false }}','runs-on':'ubuntu-24.04',
                'timeout-minutes':1,'steps':[{'run':'echo MXM_RETIRED_ROUTE_NO_KEY_NO_REPLAY'}]}}},indent=2)+'\n'

def desired_workflows(mode):
    result={}
    for path,raw in baseline(mode).items():
        if path==CI:continue
        result[path]=quarantine(path) if path not in ACTIVE and legacy_privileged(raw) else raw
    return result

def build_ci(source,mode,witness):
    require(re.fullmatch('[a-f0-9]{40}',source or ''),'BOUNDARY_SOURCE_ID')
    ci=json.loads(baseline(mode)[CI]);steps=ci['jobs']['shared-catalogue-regression']['steps']
    steps.insert(2,{'uses':CHECKOUT,'with':{'ref':source,'path':'boundary','persist-credentials':False}})
    exact=next(s for s in steps if s.get('name')=='Verify exact generated source/workflow/credential boundaries')
    for name in ('mxm-r3-secret-isolation.yml','mxm-r3-checkpoint20-readback.yml'):
        original="(installed/'"+name+"').read_bytes()"
        historical="subprocess.check_output(['python3','verification/R3_WORKFLOW_BOUNDARY.py','baseline',"+repr(mode)+","+repr(name)+"],cwd='../boundary')"
        require(original in exact['run'],'BOUNDARY_CI_BASELINE_ASSERTION')
        exact['run']=exact['run'].replace(original,historical)
    steps.insert(-1,{'name':'Whole-workflow namespace, retired routes and frozen boundary source',
        'working-directory':'boundary',
        'run':'python3 verification/R3_WORKFLOW_BOUNDARY.py verify ../installation '+mode+' '+source+'\npython3 verification/R3_WORKFLOW_BOUNDARY.py self-test',
        'env':{'GH_TOKEN':'${{ github.token }}','R3_BOUNDARY_CONTROL_WITNESS':json.dumps(witness,separators=(',',':'))}})
    return json.dumps(ci,indent=2)+'\n'

def verify_root(root,mode,source,witness):
    root=Path(root);directory=root/'.github/workflows'
    require(not (root/'.github').is_symlink() and not directory.is_symlink(),'BOUNDARY_DIRECTORY_SYMLINK')
    paths={str(p.relative_to(root)) for p in directory.iterdir() if p.suffix.lower() in ('.yml','.yaml')}
    expected=desired_workflows(mode);expected[CI]=build_ci(source,mode,witness)
    require(paths==set(expected),'BOUNDARY_WORKFLOW_INVENTORY')
    for path,raw in expected.items():
        file=root/path
        require(file.is_file() and not file.is_symlink(),'BOUNDARY_WORKFLOW_FILE_TYPE')
        require(file.read_bytes()==raw.encode(),'BOUNDARY_WORKFLOW_BYTES:'+path)
    return {'schema':'mxm.whole-workflow-admission.v1','mode':mode,
        'workflow_count':len(expected),'source_sha':source,
        'retired_paths':[p for p in expected if p!=CI and expected[p]!=baseline(mode).get(p)],
        'active_credential_workflows':sorted(ACTIVE),'keys_accessed':0,'writes':0,
        'orders':0,'economic_outcomes':0,'integral_laboratory_acceptance':False}

def instant(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(d.tzinfo is not None,'BOUNDARY_POLICY_TIMEZONE')
    return d.astimezone(timezone.utc)

def verify_seal(route,source,witness):
    require(route.json('git/ref/heads/'+SOURCE_REF)['object']['sha']==source,'BOUNDARY_SOURCE_REF_MOVED')
    require(type(witness) is dict and witness.get('bypass_actors')==[],'BOUNDARY_ADMIN_WITNESS')
    observed=route.json('rulesets/'+str(witness['id']))
    fields=('id','target','source_type','source','enforcement','conditions','rules')
    require(all(k in observed and observed[k]==witness.get(k) for k in fields) and
        instant(observed['updated_at'])==instant(witness['updated_at']),'BOUNDARY_POLICY_LIVE_DRIFT')
    require(observed.get('bypass_actors',[])==[] and witness['target']=='branch' and
        witness['source_type']=='Repository' and witness['source']==REPO and
        witness['enforcement']=='active' and witness['conditions'].get('ref_name')==
        {'include':['refs/heads/'+SOURCE_REF],'exclude':[]} and
        {'creation','update','deletion','non_fast_forward'}<={r['type'] for r in witness['rules']},
        'BOUNDARY_EXACT_NO_BYPASS_SEAL')

def native_verify(root,mode,source):
    require(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_EVENT_NAME')=='pull_request'
        and os.environ.get('GITHUB_JOB')=='shared-catalogue-regression' and
        os.environ.get('GITHUB_RUN_ATTEMPT')=='1','BOUNDARY_NATIVE_CONTEXT')
    require(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CUSTODY_PRIVATE_KEY_PEM',
        'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CTRADER_ACCESS_TOKEN')),'BOUNDARY_NO_CREDENTIALS')
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==source and
        subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode==0,'BOUNDARY_CLEAN_FROZEN_CHECKOUT')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    witness=json.loads(os.environ['R3_BOUNDARY_CONTROL_WITNESS'])
    verify_seal(GetOnly(),source,witness)
    print('MXM_NATIVE_WORKFLOW_BOUNDARY '+json.dumps(verify_root(root,mode,source,witness),sort_keys=True),flush=True)

def self_test():
    import importlib.util,unittest
    spec=importlib.util.spec_from_file_location('boundary_tests',ROOT/'verification/test_r3_workflow_boundary.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    # Make immutable repository imports available with a direct script entry.
    sys.path.insert(0,str(ROOT))
    action=sys.argv[1]
    if action=='baseline':print(baseline_json(sys.argv[2],sys.argv[3]),end='')
    elif action=='self-test':raise SystemExit(self_test())
    elif action=='verify':native_verify(*sys.argv[2:])
    else:raise SystemExit('BOUNDARY_COMMAND')

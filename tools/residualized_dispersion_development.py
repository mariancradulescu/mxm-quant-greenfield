"""One exact-parent request, no replay, no response before all frozen gates."""
import argparse,json,os,platform,subprocess,tempfile
from pathlib import Path
from research_core_v4 import residualized_dispersion_v1 as v
from tools.residualized_dispersion_preoutcome import ROOT,DESIGN,environment,network_fence,load_accepted
REQUEST='research_core_v4/state/RESIDUALIZED_DISPERSION_OPENING_REQUEST_V1.json'
FREEZE='research_core_v4/state/RESIDUALIZED_DISPERSION_PREOUTCOME_FREEZE_V1.json'
RAW='research_core_v4/state/RESIDUALIZED_DISPERSION_RAW_RESULT_V1.json'

def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args]).decode().strip()
def authority():
    v.require((ROOT/REQUEST).is_file(),'NO_REAL_OPENING_AUTHORITY')
    r=json.loads((ROOT/REQUEST).read_bytes());f=json.loads((ROOT/FREEZE).read_bytes())
    v.require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','REPLAY_DENIED')
    v.require(os.environ.get('GITHUB_EVENT_NAME')=='push','push only')
    v.require(git('rev-parse','HEAD')==os.environ['GITHUB_SHA'],'trigger exact HEAD')
    v.require(git('rev-parse','HEAD^')==r['preoutcome_freeze_head'],'immutable exact parent freeze')
    v.require(git('diff','--name-only','HEAD^','HEAD')==REQUEST,'only singleton opening request allowed')
    v.require(not (ROOT/RAW).exists(),'canonical result already exists')
    v.require(r['real_development_authorized'] is True and r['maximum_openings']==1,'bounded authority')
    v.require(f['all_preoutcome_gates_pass'] is True and f['real_response_opened'] is False,'preoutcome gates')
    for path,h in r['file_sha256'].items():v.require(v.sha((ROOT/path).read_bytes())==h,'frozen source '+path)
    v.require(platform.python_version()==r['python_version'] and v.np.__version__==r['numpy_version'],'numeric environment')
    s=json.loads((ROOT/'research_core_v4/state/V4_STATE.json').read_bytes())
    v.require(s['governance']['candidate_frozen_count']==0 and s['governance']['protected_forward_opened'] is False,'boundaries')
    calibration=json.loads((ROOT/'research_core_v4/state/RESIDUALIZED_DISPERSION_CALIBRATION_V1.json').read_bytes())
    support=json.loads((ROOT/'research_core_v4/state/RESIDUALIZED_DISPERSION_SUPPORT_V1.json').read_bytes())
    v.require(calibration['pass'] is True and support['pass'] is True,'persisted green gates')
    return r,support

def run(raw,out):
    r,accepted_support=authority();d=json.loads((ROOT/DESIGN).read_bytes())
    from research_core_v4.asymmetric_recovery_v4_gate import decrypt_verify
    decrypt_verify(raw);os.environ.pop('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',None);network_fence()
    series=load_accepted(raw,d);support,population=v.prepare(series,d)
    v.require(support['pass'] is True,'reproduced support failed')
    for key in ['population_sha256','models_sha256','joint_blocks','contexts']:v.require(support[key]==accepted_support[key],'exact accepted support '+key)
    result=v.raw_result(series,d,support,population,authorized=True)
    result.update(trigger_head=os.environ['GITHUB_SHA'],preoutcome_freeze_head=r['preoutcome_freeze_head'],run_id=int(os.environ['GITHUB_RUN_ID']),run_attempt=1,
                  environment=environment(),source_binding=r['file_sha256'])
    # Do not infer or interpret here. Durable upload and canonical publication first.
    out.write_bytes(v.canonical(result)+b'\n')
    print(json.dumps({'status':'RAW_COMPLETE_NOT_INTERPRETED','run_id':result['run_id'],'response_openings':1}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='residualized-dispersion-real-once-') as td: run(Path(td)/'raw',Path(a.output))

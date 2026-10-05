"""Accepted local decryption, then network-denied causal support only."""
import argparse,json,os,platform,sys,tempfile
from pathlib import Path
from research_core_v4 import online_change_v1 as v
ROOT=Path(__file__).resolve().parents[1]
DESIGN='research_core_v4/state/ONLINE_CHANGE_DESIGN_V1.json'
REQUEST='research_core_v4/state/ONLINE_CHANGE_PREOUTCOME_REQUEST_V1.json'

def binding():
    r=json.loads((ROOT/REQUEST).read_bytes())
    for p,h in r['file_sha256'].items(): v.require(v.sha((ROOT/p).read_bytes())==h,'source binding '+p)
    v.require(platform.python_version()==r['python_version'],'interpreter binding')
    v.require(v.np.__version__==r['numpy_version'],'numpy binding')
    v.require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','replay denied')
    s=json.loads((ROOT/'research_core_v4/state/V4_STATE.json').read_bytes())
    v.require(s['governance']['candidate_frozen_count']==0 and s['governance']['protected_forward_opened'] is False,'governance')
    return r

def network_fence():
    def deny(event,args):
        if event.startswith('socket.') or event in ['urllib.Request','subprocess.Popen','os.system']:
            raise PermissionError('NETWORK_OR_PROCESS_DENIED_AFTER_DECRYPTION')
    sys.addaudithook(deny)

def load_accepted(raw,d):
    return {c:{sid:v.read_series(raw/f'{sid}_M5.csv') for sid in ids} for c,ids in d['memberships'].items()}

def environment():
    return {'python':platform.python_version(),'numpy':v.np.__version__,'platform':platform.platform(),
            'executable_sha256':v.sha(Path(sys.executable).read_bytes()),
            'numpy_binary_hashes':{str(p.relative_to(Path(v.np.__file__).parent)):v.sha(p.read_bytes()) for p in Path(v.np.__file__).parent.rglob('*.so')}}

def run(raw,out):
    request=binding();d=json.loads((ROOT/DESIGN).read_bytes())
    from research_core_v4.asymmetric_recovery_v4_gate import decrypt_verify
    decrypt_verify(raw);os.environ.pop('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',None)
    network_fence()
    def deny(*args,**kwargs): raise PermissionError('REAL_RESPONSE_DISABLED_PREOUTCOME')
    v.response=deny;v.raw_result=deny;v.interpret=deny
    support,_=v.prepare(load_accepted(raw,d),d)
    support.update(trigger_head=os.environ['GITHUB_SHA'],run_id=int(os.environ['GITHUB_RUN_ID']),run_attempt=1,
                   source_binding=request['file_sha256'],environment=environment(),new_data_acquired=False)
    out.write_bytes(v.canonical(support)+b'\n')
    print(json.dumps({'support_pass':support['pass'],'joint_blocks':support['joint_blocks'],'response_opened':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='online-change-accepted-') as td: run(Path(td)/'raw',Path(a.output))

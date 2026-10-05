"""Machine-only reuse of accepted inputs. Output contains support geometry only."""
import argparse,json,os,platform,socket,sys,tempfile,math,statistics
from pathlib import Path
from research_core_v4 import factor_residual_v1 as f
ROOT=Path(__file__).resolve().parents[1]
DESIGN='research_core_v4/state/FACTOR_RESIDUAL_DESIGN_V1.json'
REQUEST='research_core_v4/state/FACTOR_RESIDUAL_PREOUTCOME_REQUEST_V1.json'
def run(raw,output):
 request=json.loads((ROOT/REQUEST).read_bytes());design=json.loads((ROOT/DESIGN).read_bytes())
 for rel,h in request['file_sha256'].items():f.require(f.sha((ROOT/rel).read_bytes())==h,'preoutcome source binding')
 f.require(platform.python_version()==request['python_version'],'preoutcome interpreter binding')
 f.require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','no workflow replay')
 f.require(request['real_response_authorized'] is False and design['synthetic_only'] is False,'preoutcome only')
 # Decryption takes place ONLY in GitHub with the already configured private key.
 from research_core_v4.asymmetric_recovery_v4_gate import decrypt_verify
 decrypt_verify(raw)
 os.environ.pop('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',None)
 denied=[0]
 def deny(event,args):
  if event.startswith('socket.') or event in ['urllib.Request','subprocess.Popen','os.system']:
   denied[0]+=1;raise PermissionError('NETWORK_DENIED_AFTER_LOCAL_DECRYPTION')
 sys.addaudithook(deny)
 def no_response(*args,**kwargs):raise PermissionError('REAL_RESPONSE_ACCESSOR_DISABLED_IN_PREOUTCOME_JOB')
 for name in ['response','block_means','inference','evaluate_synthetic_only']:setattr(f,name,no_response)
 series={c:{sid:f.read_series(raw/f'{sid}_M5.csv') for sid in ids} for c,ids in design['memberships'].items()}
 report,_=f.prepare(series,design)
 f.require(denied[0]==0,'unexpected network attempt')
 report['environment']={'python':platform.python_version(),'platform':platform.platform(),'executable_sha256':f.sha(Path(sys.executable).read_bytes()),'math_binary_sha256':f.sha(Path(math.__file__).read_bytes()),'statistics_source_sha256':f.sha(Path(statistics.__file__).read_bytes())}
 report.update(trigger_head=os.environ['GITHUB_SHA'],run_id=int(os.environ['GITHUB_RUN_ID']),run_attempt=1,python_version=platform.python_version(),new_data_acquired=False,source_binding=request['file_sha256'],accepted_series_sha256={str(v['symbol_id']):v['series_sha256'] for v in design['accepted_series']})
 output.write_bytes(f.canonical(report)+b'\n')
 print(json.dumps({'status':'PREOUTCOME_SUPPORT_ONLY_COMPLETE','run_id':report['run_id'],'response_opened':False,'contexts':{c:{h:v['support_pass'] for h,v in hs.items()} for c,hs in report['contexts'].items()}},sort_keys=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
 with tempfile.TemporaryDirectory(prefix='v4-factor-local-') as d:run(Path(d)/'raw',Path(a.output))

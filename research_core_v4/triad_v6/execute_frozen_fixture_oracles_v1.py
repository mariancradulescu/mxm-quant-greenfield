"""Execute frozen 100/160-digit oracle and unchanged V4 kernel. V6 RAW only."""
from pathlib import Path
import gzip,json,hashlib,subprocess,tempfile,time,traceback
from high_precision_projection_oracle_v1 import oracle
P=Path(__file__).resolve().parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((P/n).read_text())
binding=read('UNCHANGED_CANDIDATE_BINDING_V1.json')
for key,path in [('source_sha256',R/binding['source_ref']),('math_contract_sha256',P/'MATHEMATICAL_PROJECTION_CONTRACT_V1.json'),('oracle_spec_sha256',P/'HIGH_PRECISION_ORACLE_SPEC_V1.json'),('reliability_law_sha256',P/'ONE_SIDED_PRODUCTION_SUPPORT_CONTRACT_V1.json'),('input_manifest_sha256',P/'FROZEN_INPUT_MANIFEST_V1.json'),('toolchain_sha256',P/'ORACLE_TOOLCHAIN_BINDING_V1.json')]:assert sha(path)==binding[key],path
for path,s in read('INHERITED_IMMUTABLE_BINDINGS_V1.json')['bindings'].items():assert sha(R/path)==s,path
rawpath=R/'research_core_v4/triad_v4/PROJECTION_FIXTURE_RAW_V1.json.gz';frozen=json.loads(gzip.decompress(rawpath.read_bytes()));manifest=read('FROZEN_INPUT_MANIFEST_V1.json');assert sha(rawpath)==manifest['raw_gzip_sha256']
stdin=[]
for f,m in zip(frozen['fixtures'],manifest['fixtures']):
 payload=json.dumps({'X':f['X'],'D':f['D']},sort_keys=True,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(payload).hexdigest()==m['binary64_input_json_sha256'] and f['id']==m['id']
 stdin.append(str(len(f['X'])));stdin.extend(' '.join(format(float(v),'.17g') for v in [*row,f['D'][i]]) for i,row in enumerate(f['X']))
assert len(manifest['fixtures'])==len(frozen['fixtures'])==537
with tempfile.TemporaryDirectory(prefix='triad_v6_frozen_') as tmp:
 binary=Path(tmp)/'candidate';flags=read('ORACLE_TOOLCHAIN_BINDING_V1.json')['candidate_compile_flags'];compile_result=subprocess.run(['g++',*flags,str(R/binding['source_ref']),'-o',str(binary)],check=True,text=True,capture_output=True);binarysha=sha(binary)
 result=subprocess.run([str(binary)],input='\n'.join(stdin)+'\n',check=True,text=True,capture_output=True);candidates=[json.loads(line) for line in result.stdout.splitlines()]
assert len(candidates)==537
rows=[];start=time.perf_counter()
for index,(f,m,candidate) in enumerate(zip(frozen['fixtures'],manifest['fixtures'],candidates)):
 row={'id':f['id'],'n':len(f['X']),'input_sha256':m['binary64_input_json_sha256'],'X':f['X'],'D':f['D'],'historical_Python':f['canonical'],'frozen_V4_Jacobi':f['cpp'],'Jacobi':candidate,'candidate_output_bit_identical_to_V4':candidate==f['cpp'],'oracles':{}}
 for digits in [100,160]:
  try:row['oracles'][str(digits)]=oracle(f['X'],f['D'],digits)
  except Exception as e:row['oracles'][str(digits)]={'status':'NUMERICAL_ORACLE_AMBIGUOUS_EXCEPTION','accepted':False,'exception':type(e).__name__,'detail':str(e),'traceback':traceback.format_exc()}
 rows.append(row)
 if (index+1)%25==0:print(json.dumps({'completed_fixture_indices':index+1,'total':537,'elapsed_seconds':time.perf_counter()-start,'interpretation':'NOT_PERFORMED'}),flush=True)
raw={'schema':'TRIAD_V6_FROZEN_ORACLE_FIXTURE_RAW_V1','candidate_binding_sha256':sha(P/'UNCHANGED_CANDIDATE_BINDING_V1.json'),'oracle_source_sha256':sha(P/'high_precision_projection_oracle_v1.py'),'runner_sha256':sha(Path(__file__)),'binary_sha256':binarysha,'compile_stderr':compile_result.stderr,'compile_stdout':compile_result.stdout,'fixtures':rows,'fixture_count':537,'elapsed_seconds':time.perf_counter()-start,'interpretation':'PENDING_DURABLE_RAW_PERSISTENCE','full_null_trials':0,'full_power_trials':0,'real_Y_reads':0,'actual_predictor_audit_count':0}
payload=(json.dumps(raw,indent=2,sort_keys=True,allow_nan=False)+'\n').encode();(P/'ORACLE_FIXTURE_RAW_V1.json').write_bytes(payload);(P/'ORACLE_FIXTURE_RAW_V1.json.gz').write_bytes(gzip.compress(payload,mtime=0));print(json.dumps({'raw_written':True,'raw_sha256':hashlib.sha256(payload).hexdigest(),'compressed_bytes':(P/'ORACLE_FIXTURE_RAW_V1.json.gz').stat().st_size,'interpretation':'PENDING_DURABLE_RAW_PERSISTENCE'}),flush=True)

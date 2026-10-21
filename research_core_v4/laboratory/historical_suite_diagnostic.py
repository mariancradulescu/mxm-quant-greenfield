"""Full historic suite diagnostic; no production credentials or market worker."""
import json,os,pathlib,subprocess,time,unittest
from research_core_v4.laboratory.common import bytes_digest
root=pathlib.Path(__file__).resolve().parents[2]
for key in ('SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN'):
    if os.environ.get(key):raise SystemExit('HISTORICAL_SUITE_FORBIDDEN_CREDENTIAL')
out=root/'verification/historical-suite';out.mkdir(parents=True,exist_ok=True)
start=time.monotonic()
with (out/'unittest.log').open('w') as log:
    suite=unittest.defaultTestLoader.discover(str(root/'tests'),top_level_dir=str(root))
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
report={'schema':'mxm.historical-suite-native-diagnostic.v1',
    'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
    'shallow':subprocess.check_output(['git','rev-parse','--is-shallow-repository'],cwd=root,text=True).strip(),
    'run_id':os.environ.get('GITHUB_RUN_ID'),'job':os.environ.get('GITHUB_JOB'),
    'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'skipped':len(result.skipped),'seconds':round(time.monotonic()-start,3),
    'failure_records':[{'test':t.id(),'traceback':detail} for t,detail in result.failures],
    'error_records':[{'test':t.id(),'traceback':detail} for t,detail in result.errors],
    'skip_records':[{'test':t.id(),'reason':reason} for t,reason in result.skipped],
    'log_sha256':bytes_digest((out/'unittest.log').read_bytes()),
    'passed':result.wasSuccessful(),'economic_reception':False,'operational_reception':False,
    'production_credentials_supplied':False,'market_worker_invoked':False}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('failure_records','error_records','skip_records')},sort_keys=True))
raise SystemExit(not result.wasSuccessful())

"""Prevent secret-bearing automatic repetitions of completed fixed-source models."""
import copy,hashlib,json,unittest,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'.github/workflows/mxm-csharp-authentic-cold.yml'
STEPS={'bounded-cold-to-csharp':'9b28c1979b311eda150d204e0fa2593eb5916cc0106647e1ba5e2082373f68b3','weekly-cold-to-csharp':'8f0773e549b9c748d19b5541ae0fad54979f426124d4d6bba93b2ef7ddc5b5e7'}
ALLOWED={'.github/workflows/mxm-csharp-authentic-cold.yml','research_core_v4/laboratory/chronology_csharp_bridge.py','research_core_v4/laboratory/captured_symbol_terms.py','research_core_v4/laboratory/durable_native_chronology.py'}
def need(ok,why):
    if not ok:raise ValueError('RETIRED_REPLAY_'+why)
def validate(config):
    triggers=config.get('on',config.get(True))
    need(isinstance(triggers,dict) and set(triggers)=={'push'},'NO_DISPATCH_SCHEDULE_OR_RESEARCH_EVENT')
    push=triggers['push'];need(push['branches']==['mxm-remediation-p0-p4-20261015-v1'] and set(push['paths'])==ALLOWED,'NO_BROAD_CSHARP_OR_ARCHIVE_TRIGGER')
    need(config['permissions']=={} and set(config['jobs'])==set(STEPS),'NO_NEW_JOB_OR_PRIVILEGE')
    for name,j in config['jobs'].items():
        need(j['if']=='${{ false }}','ALL_JOBS_MUST_STOP_BEFORE_ENVIRONMENT')
        need(j['environment']=='mxm-r3-custody-v1' and j['permissions']==({'contents':'read','actions':'read'} if name=='bounded-cold-to-csharp' else {'contents':'read'}),'ORIGINAL_RESTRICTED_ENVIRONMENT_AND_PERMISSIONS')
        h=hashlib.sha256(json.dumps(j['steps'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        need(h==STEPS[name],'ORIGINAL_AUDITABLE_JOB_BODY_PRESERVED')
    return True
class RetiredReplay(unittest.TestCase):
    def setUp(self):self.config=yaml.safe_load(PATH.read_text())
    def test_current_retirement_and_historical_job_bodies(self):self.assertTrue(validate(self.config))
    def test_resurrected_job_or_secret_access_is_rejected(self):
        for name in STEPS:
            with self.subTest(job=name):
                c=copy.deepcopy(self.config);c['jobs'][name]['if']='true'
                with self.assertRaises(ValueError):validate(c)
    def test_broad_trigger_dispatch_and_changed_body_are_rejected(self):
        for mutate in (lambda c:c[True]['push']['paths'].append('research_core_v4/native_tick_replay_v1/csharp/**'),lambda c:c[True].update(workflow_dispatch={}),lambda c:c['jobs']['weekly-cold-to-csharp']['steps'].append({'run':'changed'})):
            c=copy.deepcopy(self.config);mutate(c)
            with self.assertRaises(ValueError):validate(c)
if __name__=='__main__':unittest.main()

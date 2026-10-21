"""Artificial ACL mutations; native App evidence remains independently required."""
from copy import deepcopy
import unittest
from .common import LabError
from .custody import resolve_control_policy,build_native_workflow,build_certifier_workflow
from .runtime import SOURCE_BRANCH

SOURCE='a'*40

class ControlPolicyWitness(unittest.TestCase):
    def fixture(self):
        source={'id':7,'target':'branch','source_type':'Repository',
            'source':'mariancradulescu/mxm-quant-greenfield','enforcement':'active',
            'conditions':{'ref_name':{'include':['refs/heads/'+SOURCE_BRANCH],'exclude':[]}},
            'rules':[{'type':k} for k in ('creation','update','deletion','non_fast_forward')],
            'updated_at':'2026-10-21T05:00:00.123+02:00','bypass_actors':[]}
        evidence={**deepcopy(source),'id':8,
            'conditions':{'ref_name':{'include':['refs/heads/mxm-o04-integrated-laboratory-evidence'],'exclude':[]}},
            'rules':[{'type':'update'}],
            'bypass_actors':[{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]}
        witness={'schema':'mxm.native-control-policy-witness.v1','source_sha':SOURCE,
            'source_ref':SOURCE_BRANCH,'policies':[source,evidence]}
        observed=deepcopy(source);observed.pop('bypass_actors')
        observed['updated_at']='2026-10-21T03:00:00.123Z'
        return observed,witness

    def test_exact_live_revision_resolves_only_redacted_actor_inventory(self):
        observed,witness=self.fixture();original=deepcopy(observed)
        self.assertEqual(resolve_control_policy(observed,witness,SOURCE)['bypass_actors'],[])
        self.assertEqual(observed,original)
        evidence=deepcopy(witness['policies'][1]);evidence.pop('bypass_actors')
        self.assertEqual(resolve_control_policy(evidence,witness,SOURCE)['bypass_actors'],
            [{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}])

    def test_every_live_security_field_and_revision_is_bound(self):
        for field,value in [('id',99),('target','tag'),('source_type','Organization'),
            ('source','OTHER/OTHER'),('enforcement','disabled'),('conditions',{}),
            ('rules',[]),('updated_at','2026-10-21T03:00:00.124Z'),
            ('bypass_actors',[{'actor_id':1}])]:
            observed,witness=self.fixture();observed[field]=value
            with self.subTest(field=field),self.assertRaises(LabError):
                resolve_control_policy(observed,witness,SOURCE)

    def test_omission_is_not_empty_and_witness_cannot_broaden_authority(self):
        for mode in ('missing_revision','missing_actors','broad_target','wrong_source',
                     'wrong_ref','extra_policy','source_bypass','wrong_evidence_app'):
            observed,witness=self.fixture();policy=witness['policies'][0]
            if mode=='missing_revision':observed.pop('updated_at')
            elif mode=='missing_actors':policy.pop('bypass_actors')
            elif mode=='broad_target':
                policy['conditions']['ref_name']['include']=['refs/heads/*']
                observed['conditions']=deepcopy(policy['conditions'])
            elif mode=='wrong_source':witness['source_sha']='b'*40
            elif mode=='wrong_ref':witness['source_ref']='OTHER'
            elif mode=='extra_policy':witness['policies'].append(deepcopy(policy))
            elif mode=='source_bypass':policy['bypass_actors']=[{'actor_id':5343530}]
            else:
                observed=deepcopy(witness['policies'][1]);observed.pop('bypass_actors')
                witness['policies'][1]['bypass_actors'][0]['actor_id']=1
            with self.subTest(mode=mode),self.assertRaises(LabError):
                resolve_control_policy(observed,witness,SOURCE)

    def test_witness_is_environment_configuration_only_for_issuer_jobs(self):
        import yaml
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        baseline=yaml.safe_load((root/'docs/laboratory-completion/20261020/R3_EXISTING_OPERATIONAL_DAG_BASELINE.yml').read_bytes())
        for workflow in (build_native_workflow(SOURCE,baseline),build_certifier_workflow(SOURCE)):
            for job in workflow['jobs'].values():
                for step in job['steps']:
                    env=step.get('env',{})
                    self.assertEqual('R3_CONTROL_WITNESS' in env,'SUCCESSOR_APP_PRIVATE_KEY' in env)
                    if 'R3_CONTROL_WITNESS' in env:
                        self.assertEqual(env['R3_CONTROL_WITNESS'],'${{ vars.R3_CONTROL_WITNESS }}')
                        self.assertEqual(job['environment'],'mxm-p0-successor-issuer-v1')

if __name__=='__main__':unittest.main()

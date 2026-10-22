"""Synthetic claim/recovery history around the conserved public checkpoint20.

No private archive, GitHub write, task execution or economic exposure here.
"""
import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from .common import digest,encoded,LabError
from .protocol import STATE_PATH,recovered_public_base,verify_checkpoint20_public
from .claim import claim_state
from .checkpoint20_readback import authority
from .test_native_acceptance_v3 import make_fixture,SOURCE,HISTORIC
from . import integrated

ORIGIN='09703adad6433f395a0506fa640f59bf3dba80b5'
CLAIM='3'*40;RECOVERY='4'*40


class RecoveredTransition(unittest.TestCase):
    def fixture(self):
        route,_,_=make_fixture();original_json=route.json
        original=json.loads((Path(__file__).parent/'fixtures/sealed_checkpoint20_public.json').read_bytes())
        auth=authority(original)
        certificate={'run_id':HISTORIC,'source_sha':SOURCE,'trigger_sha':'8'*40,'parent_oid':ORIGIN,
            'admission_ref':'e'*40,'admission_path':'research_programs/admissions/TECHNICAL.json','admission_sha256':'d'*64}
        claimed=claim_state(original,HISTORIC,certificate['admission_sha256'],ORIGIN,SOURCE)
        claimed['pending'].update(phase='PRE_EXPOSURE',preflight_sha256=digest(certificate))
        intent={'base_state':deepcopy(original),'preflight':certificate,'pending':claimed['pending']}
        recovered=recovered_public_base(intent)
        proof={'run_id':HISTORIC,'no_economic_exposure':True,'refunds':0,'base_state_sha256':digest(original)}
        intent_path='typed-successor/intents/'+str(HISTORIC)+'.json';proof_path='typed-successor/recoveries/'+str(HISTORIC)+'.json'
        route.storage[(STATE_PATH,ORIGIN)]=encoded(original)
        route.storage[(STATE_PATH,CLAIM)]=encoded(claimed)
        route.storage[(intent_path,RECOVERY)]=encoded(intent);route.storage[(proof_path,RECOVERY)]=encoded(proof)
        route.commits={RECOVERY:{'parents':[{'sha':CLAIM}],'files':[{'filename':STATE_PATH,'status':'modified'},{'filename':proof_path,'status':'added'}]},
            CLAIM:{'parents':[{'sha':ORIGIN}],'files':[{'filename':STATE_PATH,'status':'modified'},{'filename':intent_path,'status':'added'}]}}
        def query(path):
            if path.startswith('commits/'):return route.commits[path[8:]]
            result=original_json(path)
            if path=='actions/runs/'+str(HISTORIC)+'/attempts/1/jobs?per_page=100':result['total_count']=len(result['jobs'])
            return result
        route.json=query
        return route,original,auth,recovered

    def check(self,route,state,auth):
        with patch.dict(os.environ,{'LAB_SOURCE_SHA':SOURCE}):
            return integrated.transition_predecessor(route,state,RECOVERY,auth)

    def test_exact_recovery_retains_original_migration_authority_without_replay(self):
        route,original,auth,recovered=self.fixture();before=digest(recovered)
        state,origin=self.check(route,recovered,auth)
        self.assertEqual((state,origin),(original,ORIGIN));self.assertEqual(digest(recovered),before)
        verify_checkpoint20_public(state,auth,origin)
        # The old preflight passed current recovery HEAD/state directly; that
        # necessarily rejects even this authentic-shaped safe continuation.
        with self.assertRaises(LabError):verify_checkpoint20_public(recovered,auth,RECOVERY)

    def test_arbitrary_descendant_or_extra_write_cannot_authorize_migration(self):
        for mode in ('wrong_parent','extra_file','changed_status','second_recovery'):
            route,_,auth,recovered=self.fixture()
            if mode=='wrong_parent':route.commits[CLAIM]['parents']=[{'sha':'5'*40}]
            elif mode=='extra_file':route.commits[RECOVERY]['files'].append({'filename':'OTHER','status':'added'})
            elif mode=='changed_status':route.commits[CLAIM]['files'][1]['status']='modified'
            else:route.commits[RECOVERY]['parents'].append({'sha':ORIGIN})
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route,recovered,auth)

    def test_changed_accounting_cipher_continuation_or_claim_is_held(self):
        for mode in ('book','cipher','continuation','claim','proof'):
            route,_,auth,recovered=self.fixture()
            if mode=='book':recovered['accounting']['refunds']=1
            elif mode=='cipher':recovered['ciphertext_sha256']='a'*64
            elif mode=='continuation':recovered['recovery_continuation']['admission_sha256']='a'*64
            else:
                key=(STATE_PATH,CLAIM) if mode=='claim' else ('typed-successor/recoveries/'+str(HISTORIC)+'.json',RECOVERY)
                value=json.loads(route.storage[key])
                if mode=='claim':value['pending']['phase']='EXECUTION_FENCED'
                else:value['no_economic_exposure']=False
                route.storage[key]=encoded(value)
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route,recovered,auth)

    def test_wrong_source_native_checkout_is_not_recovery_evidence(self):
        route,_,auth,recovered=self.fixture();key=('.github/workflows/mxm-integrated-p0.yml','8'*40)
        workflow=json.loads(route.storage[key]);workflow['jobs']['segment-intent']['steps'][0]['with']['ref']='a'*40
        route.storage[key]=encoded(workflow)
        with self.assertRaises(LabError):self.check(route,recovered,auth)


if __name__=='__main__':unittest.main()

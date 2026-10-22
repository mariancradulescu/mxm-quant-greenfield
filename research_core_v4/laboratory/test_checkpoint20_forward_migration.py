"""Zero-key predecessor authorization tests; NOT a live ciphertext migration."""
import json,unittest
from pathlib import Path
from copy import deepcopy
from .common import digest
from .protocol import verify_checkpoint20_public,typed_source_transition

ROOT=Path(__file__).resolve().parent
EVIDENCE='09703adad6433f395a0506fa640f59bf3dba80b5'
PRIVATE_SHA='01227d7a7715a89bc1bfcf6fac183fbaec3b941f8c61281fb3c0e4f01f232fa6'

def source():
    state=json.loads((ROOT/'fixtures/sealed_checkpoint20_public.json').read_text())
    authority={'schema':'mxm.integrated-typed-predecessor.v3',
               'evidence_oid':EVIDENCE,'source_sha':state['source_sha'],
               'sequence':20,'ciphertext_sha256':state['ciphertext_sha256'],
               'private_sha256':PRIVATE_SHA,'public_state_sha256':digest(state)}
    return state,authority

class Checkpoint20ForwardTests(unittest.TestCase):
    def test_exact_public_checkpoint20_is_eligible_for_verified_decryption(self):
        state,a=source()
        self.assertTrue(verify_checkpoint20_public(state,a,EVIDENCE))
        self.assertIsNone(state['pending'])
        self.assertEqual(state['accounting']['lanes']['V2']['reservation_holds'],1)
    def test_no_public_field_or_evidence_ref_can_be_renamed(self):
        state,a=source()
        for field,value in [('evidence_oid','0'*40),('source_sha','0'*40),
                            ('sequence',19),('ciphertext_sha256','0'*64),
                            ('private_sha256','0'*64),('public_state_sha256','0'*64)]:
            bad=deepcopy(a);bad[field]=value
            with self.subTest(field=field),self.assertRaises(Exception):
                verify_checkpoint20_public(state,bad,EVIDENCE)
        for field,value in [('pending',{'run_id':123}),('safe_stop',False),
                            ('orders',1),('last_run_id',0)]:
            bad=deepcopy(state);bad[field]=value
            with self.subTest(field=field),self.assertRaises(Exception):
                verify_checkpoint20_public(bad,a,EVIDENCE)
        bad=deepcopy(state);bad['accounting']['lanes']['V2']['encumbered']=21
        bad_a=deepcopy(a);bad_a['public_state_sha256']=digest(bad)
        with self.assertRaises(Exception):verify_checkpoint20_public(bad,bad_a,EVIDENCE)
    def test_no_synthetic_private_can_masquerade_as_sealed_checkpoint(self):
        state,a=source()
        private={'source_sha':state['source_sha'],'sequence':20,'pending':None,
                 'safe_stop':True,'trial_book':{},'programmes':{},
                 'shared_catalogue':{}}
        before=deepcopy(private)
        with self.assertRaises(Exception):
            typed_source_transition(private,state,a,'f'*40,evidence_oid=EVIDENCE)
        self.assertEqual(private,before)
    def test_prior_closed_checkpoint19_has_distinct_lineage(self):
        _,a=source()
        state={'source_sha':'541bfe0e7d1eea060aa38d9e1e46a6639b7db13b',
               'sequence':19,'ciphertext_sha256':a['ciphertext_sha256'],
               'pending':None,'safe_stop':True}
        with self.assertRaises(Exception):
            typed_source_transition({},state,a,'f'*40,evidence_oid=EVIDENCE)

if __name__=='__main__':unittest.main()

"""Public authorization is exact; it never substitutes for native decryption."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from .common import digest,LabError
from .protocol import verify_checkpoint23_public,typed_source_transition

def predecessor():
    state=json.loads((Path(__file__).parent/'fixtures/sealed_checkpoint23_public.json').read_text())
    authority={'schema':'mxm.integrated-typed-predecessor.v3','evidence_oid':'fc6bc295f326a84134dcc57149afe9bfe393f5af',
        'source_sha':state['source_sha'],'sequence':23,'ciphertext_sha256':state['ciphertext_sha256'],
        'private_sha256':'ee2b40a28bfc0f294dbe0652c4720e6082f7475818919cffb2724686df54e2be',
        'public_state_sha256':digest(state)}
    return state,authority

class Checkpoint23Migration(unittest.TestCase):
    def test_exact_native_closed_state_and_no_public_authority_substitution(self):
        state,a=predecessor();self.assertTrue(verify_checkpoint23_public(state,a,a['evidence_oid']))
        for field,value in [('pending',{'run_id':1}),('safe_stop',False),('sequence',22),('source_sha','a'*40),('last_run_id',0)]:
            bad=deepcopy(state);bad[field]=value;claim=deepcopy(a);claim['public_state_sha256']=digest(bad)
            with self.subTest(field=field),self.assertRaises(LabError):verify_checkpoint23_public(bad,claim,a['evidence_oid'])
        for field in ('evidence_oid','private_sha256','ciphertext_sha256','source_sha','schema','public_state_sha256'):
            bad=deepcopy(a);bad[field]='INVALID'
            with self.subTest(field=field),self.assertRaises(LabError):verify_checkpoint23_public(state,bad,a['evidence_oid'])
    def test_authentic_public_receipt_cannot_authorize_fabricated_private(self):
        state,a=predecessor();private={'source_sha':state['source_sha'],'sequence':23}
        with self.assertRaises(LabError):typed_source_transition(private,state,a,'f'*40,evidence_oid=a['evidence_oid'])

if __name__=='__main__':unittest.main()

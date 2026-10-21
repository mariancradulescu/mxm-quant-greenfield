from copy import deepcopy
import json
from pathlib import Path
import unittest
from .common import digest,LabError
from .protocol import verify_checkpoint24_public,typed_source_transition

def predecessor():
    state=json.loads((Path(__file__).parent/'fixtures/sealed_checkpoint24_public.json').read_text())
    return state,{'schema':'mxm.integrated-typed-predecessor.v3','evidence_oid':'5d5be97cd4f316945aeea4268528b2f4262c8b07',
        'source_sha':state['source_sha'],'sequence':24,'ciphertext_sha256':state['ciphertext_sha256'],
        'private_sha256':'d0728bcd3c8b89b9dacde8466b4acd503cecb0706c8ff15f63f3ccab8910f0be','public_state_sha256':digest(state)}

class Checkpoint24Migration(unittest.TestCase):
    def test_only_exact_closed_native_state_is_eligible(self):
        state,a=predecessor();self.assertTrue(verify_checkpoint24_public(state,a,a['evidence_oid']))
        for field,value in [('sequence',23),('pending',{'run_id':1}),('safe_stop',False),('orders',1)]:
            bad=deepcopy(state);bad[field]=value;claim=deepcopy(a);claim['public_state_sha256']=digest(bad)
            with self.subTest(field=field),self.assertRaises(LabError):verify_checkpoint24_public(bad,claim,a['evidence_oid'])
        for field in ('evidence_oid','source_sha','private_sha256','ciphertext_sha256'):
            bad=deepcopy(a);bad[field]='INVALID'
            with self.subTest(field=field),self.assertRaises(LabError):verify_checkpoint24_public(state,bad,a['evidence_oid'])
    def test_public_authority_cannot_substitute_for_private_decryption(self):
        state,a=predecessor()
        with self.assertRaises(LabError):typed_source_transition({'source_sha':state['source_sha'],'sequence':24},state,a,'f'*40,evidence_oid=a['evidence_oid'])

if __name__=='__main__':unittest.main()

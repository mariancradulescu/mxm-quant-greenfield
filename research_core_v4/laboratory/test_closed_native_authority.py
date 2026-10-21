from copy import deepcopy
import json
from pathlib import Path
import unittest
from .common import digest,LabError
from .protocol import closed_native_authorities,validate_closed_native_authorities,verify_closed_native_predecessor,typed_source_transition

class ClosedNativeAuthority(unittest.TestCase):
    def test_exact_checkpoint25_is_authorized_without_new_code_branch(self):
        state=json.loads((Path(__file__).parent/'fixtures/sealed_checkpoint25_public.json').read_text())
        authority=next(x for x in closed_native_authorities() if x['sequence']==25)
        self.assertTrue(verify_closed_native_predecessor(state,authority,authority['evidence_oid']))
        for key,value in [('pending',{'run_id':1}),('safe_stop',False),('sequence',24),('source_sha','a'*40)]:
            bad=deepcopy(state);bad[key]=value;forged=deepcopy(authority);forged['public_state_sha256']=digest(bad)
            with self.subTest(key=key),self.assertRaises(LabError):verify_closed_native_predecessor(bad,forged,authority['evidence_oid'])
        with self.assertRaises(LabError):typed_source_transition({'source_sha':state['source_sha'],'sequence':25},state,authority,'f'*40,evidence_oid=authority['evidence_oid'])
    def test_malformed_or_duplicate_authority_table_is_refused(self):
        doc={'schema':'mxm.closed-native-predecessor-authority.v1','entries':closed_native_authorities()}
        for mode in ('extra','duplicate','bad_source','boolean_sequence','empty','ambiguous_origin'):
            bad=deepcopy(doc)
            if mode=='extra':bad['extra']=1
            elif mode=='duplicate':bad['entries'].append(deepcopy(bad['entries'][0]))
            elif mode=='bad_source':bad['entries'][0]['source_sha']='invalid'
            elif mode=='boolean_sequence':bad['entries'][0]['sequence']=True
            elif mode=='empty':bad['entries']=[]
            else:bad['entries'][1]['evidence_oid']=bad['entries'][0]['evidence_oid']
            with self.subTest(mode=mode),self.assertRaises(LabError):validate_closed_native_authorities(bad)

if __name__=='__main__':unittest.main()

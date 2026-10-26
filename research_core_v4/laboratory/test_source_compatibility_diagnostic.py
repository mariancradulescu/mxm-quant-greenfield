import base64,json,unittest
from .source_compatibility_diagnostic import original_fault,workflow,PATH,ROOT,SCIENCE
class FiniteDiagnostic(unittest.TestCase):
    def fixture(self):return {'schema':'mxm.intrinsic-account-private.v1','source_sha':'b5b14da063a40f93797b8bc8a15537fe79489215','spec_sha256':SCIENCE,'disposition':'DATA_LIMITED','gates':{'complete_three_week_account':False},'independent_reference':{'segments':[{'fault':'OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE'}]},'original_csharp_json_b64':[base64.b64encode(json.dumps({'fault':'ArgumentException OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE','account':None}).encode()).decode()]}
    def test_original_fault_only_not_arbitrary_private_text(self):
        p=self.fixture();self.assertEqual(original_fault(p),'OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE')
        p['independent_reference']['segments'][0]['fault']='private arbitrary string'
        with self.assertRaises(ValueError):original_fault(p)
        p=self.fixture();p['source_sha']='different'
        with self.assertRaises(ValueError):original_fault(p)
    def test_workflow_least_privilege_no_economics_or_broker(self):
        w=workflow();self.assertEqual(json.loads((ROOT/PATH).read_bytes()),w)
        j=w['jobs']['source-compatibility'];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertNotIn('workflow_dispatch',w['on']);self.assertNotIn('pull_request',w['on'])
        runs='\n'.join(s.get('run','') for s in j['steps'])
        for forbidden in ('intrinsic_development result','intrinsic_recovery result','dotnet run','gh workflow run','SUCCESSOR_APP','R3_CTRADER_'):self.assertNotIn(forbidden,runs)
if __name__=='__main__':unittest.main()

import json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from .eur_book_reception import ROOT,PROJECT,PATH,workflow,reference
class EurBook(unittest.TestCase):
    def test_workflow_is_exact_and_bounded(self):
        w=workflow();self.assertEqual(w,json.loads((ROOT/PATH).read_bytes()));self.assertEqual(set(w['on']),{'push'})
        j=w['jobs']['eur-book-reception'];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertNotIn('env',j);self.assertEqual(j['environment'],'mxm-r3-custody-v1')
        self.assertNotIn('env',j['steps'][-1]);self.assertIn(' context ',j['steps'][-2]['run'])
        runs='\n'.join(s.get('run','') for s in j['steps'])
        for bad in ('intrinsic_development result','intrinsic_recovery result','gh workflow','SUCCESSOR_APP','R3_CTRADER_'):self.assertNotIn(bad,runs)
    @unittest.skipUnless(shutil.which('dotnet'),'local .NET absent')
    def test_actual_typed_adapter_and_independent_arrays(self):
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--','--selftest'],check=True,capture_output=True)
        rows=[(0,'bid',100),(0,'ask',100),(5000,'bid',99),(5001,'bid',99),(6000,'ask',102),(6000,'ask',103),(7000,'ask',101),(8000,'bid',102)]
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'input';o=Path(t)/'output';p.write_text(''.join(json.dumps({'t':a,'side':b,'raw':c})+'\n' for a,b,c in rows))
            for target in (0,1,3,6):
                subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(p),str(target),str(o)],check=True,capture_output=True)
                actual=json.loads(o.read_bytes());expected=reference(p,target)
                for k,v in expected.items():self.assertEqual(actual[k],v)
                self.assertEqual(set(expected['codes']),{'OBSERVED_LOCKED','OBSERVED_POSITIVE_SPREAD','SOURCE_AGE_LIMIT','SOURCE_MISSING_OR_CONFLICT','SOURCE_CROSSED'})
            p.write_text(json.dumps({'t':2,'side':'bid','raw':1})+'\n'+json.dumps({'t':1,'side':'ask','raw':2})+'\n')
            self.assertNotEqual(subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(p),'0',str(o)],capture_output=True).returncode,0)
if __name__=='__main__':unittest.main()

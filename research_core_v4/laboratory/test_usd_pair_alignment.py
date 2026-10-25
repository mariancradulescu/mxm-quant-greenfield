"""Artificial quote times/FX only; actual C# execution mandatory in CI."""
import copy,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from .usd_pair_alignment import reference,verify
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/usd_pair/MxmUsdPairAlignment.csproj'
class PairAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
        self.eur=self.folder/'eur.ndjson';self.gbp=self.folder/'gbp.ndjson'
    def write(self,eur,gbp):
        for path,rows in [(self.eur,eur),(self.gbp,gbp)]:path.write_text(''.join(json.dumps({'t':t,'side':s,'raw':v})+'\n' for t,s,v in rows))
    def base(self):
        self.write([(1000,'bid',110000),(1000,'ask',110020),(1002,'bid',120000),(1002,'ask',120020)],
                   [(1000,'bid',125000),(1000,'ask',125020),(1001,'bid',125001),(1003,'ask',125025)])
    def test_same_ms_cannot_supply_fx_to_routing_and_fx_only_marks_are_separate(self):
        self.base();trace=[];r=reference(self.eur,self.gbp,trace)
        self.assertEqual(r['Routing'],{'FX_MISSING':1,'READY_STRICT_PRIOR_FX':2})
        self.assertEqual(r['FxOnlyMarkGroups'],1)
        self.assertIn('110000,1000',trace[1]);self.assertNotIn('120000',trace[1])
        self.assertTrue(trace[1].endswith('90.89256499,-90.90909091'))
        self.assertTrue(trace[2].endswith('83.31944676,-83.33333333'))
    def test_changed_same_side_invalidates_without_falling_back_to_old_value(self):
        self.write([(0,'bid',110000),(0,'ask',110010),(1,'bid',110001),(1,'bid',110002)],
                   [(2,'bid',125000),(2,'ask',125020)])
        r=reference(self.eur,self.gbp);self.assertEqual(r['Conflicts']['EURUSD'],1);self.assertEqual(r['Routing'],{'FX_CONFLICT':1})
    def test_crossed_stale_and_missing_are_rejected(self):
        cases=[([(0,'bid',110000)],'FX_MISSING'),([(0,'bid',110020),(0,'ask',110000)],'FX_CROSSED'),
               ([(0,'bid',110000),(0,'ask',110010)],'FX_STALE')]
        for rows,code in cases:
            self.write(rows,[(6000,'bid',125000),(6000,'ask',125010)])
            self.assertEqual(reference(self.eur,self.gbp)['Routing'],{code:1})
    def test_prefix_invariance_and_exact_staleness_boundary(self):
        eur=[(0,'bid',110000),(0,'ask',110010)];gbp=[(5000,'bid',125000),(5000,'ask',125010)]
        self.write(eur,gbp);before=[];r=reference(self.eur,self.gbp,before);self.assertEqual(r['Routing'],{'READY_STRICT_PRIOR_FX':1})
        self.write(eur+[(7000,'bid',111000)],gbp+[(5001,'bid',125001)]);after=[];reference(self.eur,self.gbp,after)
        self.assertEqual(before,after[:len(before)]);self.assertIn('FX_STALE',after[1])
    def test_invalid_price_and_source_time_order_refused(self):
        for rows in [[(0,'bid',0)],[(2,'bid',110000),(1,'ask',110010)]]:
            self.write(rows,[])
            with self.assertRaises(ValueError):reference(self.eur,self.gbp)
    def test_actual_compiled_csharp_and_all_mutation_negatives(self):
        if not shutil.which('dotnet'):
            if os.environ.get('MXM_REQUIRE_PAIRED_CSHARP')=='1':self.fail('Actual C# runner is required')
            self.skipTest('C# execution is mandatory in CI; SDK absent locally')
        self.base();report=self.folder/'report.json'
        child={k:v for k,v in os.environ.items() if k in ('PATH','HOME','DOTNET_ROOT','DOTNET_CLI_HOME','TMPDIR','LANG')}
        subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--',str(self.eur),str(self.gbp),str(report)],check=True,capture_output=True,env=child)
        verify(self.eur,self.gbp,report);original=json.loads(report.read_bytes())
        for key in ('StateSha256','RoutingSha256','MarkSha256'):
            v=copy.deepcopy(original);v['result'][key]='0'*64;report.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'EVERY_GROUP'):verify(self.eur,self.gbp,report)
        v=copy.deepcopy(original);v['economic_edge_proven']=True;report.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'FALSE_ECONOMIC'):verify(self.eur,self.gbp,report)
        report.write_text(json.dumps(original));self.eur.write_text(self.eur.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'SOURCE_HASHES'):verify(self.eur,self.gbp,report)
if __name__=='__main__':unittest.main()

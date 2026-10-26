import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from decimal import Decimal as D
from .usd_leadlag_reference import reference,reconcile,read_routes,decide
from .usd_leadlag_development import ROOT,PROJECT,spec,workflow,WORKFLOW
T=1788760800000 # Monday2026-09-07 06:00UTC

def synthetic(sign=1,gap=False):
    eur=[];gbp=[]
    for i in range(181):
        if not(gap and 84<=i<=93):
            f=110000+(sign*100 if i>=60 else 0)
            eur.extend({'t':T+i*1000-1,'side':side,'raw':f+offset} for side,offset in [('bid',0),('ask',2)])
        g=125000+(sign*50 if i>=125 else 0)
        gbp.extend({'t':T+i*1000,'side':side,'raw':g+offset} for side,offset in [('bid',0),('ask',2)])
    return eur,gbp

class LeadLagTests(unittest.TestCase):
    def test_finite_precommit_and_exact_workflow(self):
        s=spec();self.assertEqual(s['model_leaves'],1);self.assertEqual(s['budget']['native_attempts'],1)
        self.assertEqual(json.loads((ROOT/WORKFLOW).read_bytes()),workflow());self.assertFalse(s['capital_replay'])
    def test_compiled_csharp_against_independent_source_and_array_selection(self):
        assembly=ROOT/'research_core_v4/laboratory/csharp/usd_leadlag/bin/Release/net8.0/MxmUsdLeadLag.dll'
        if not assembly.exists():self.skipTest('Compiled fixture mandatory in native workflow and PR CI')
        for sign,gap in [(1,False),(-1,False),(1,True)]:
            with self.subTest(sign=sign,gap=gap),tempfile.TemporaryDirectory() as folder:
                p=Path(folder);eur,gbp=synthetic(sign,gap)
                for name,rows in [('eur',eur),('gbp',gbp)]:
                    (p/(name+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in rows))
                subprocess.run(['dotnet',str(assembly),str(p/'eur.jsonl'),str(p/'gbp.jsonl'),str(p/'result.json')],check=True)
                actual=json.loads((p/'result.json').read_bytes(),parse_float=D)
                source,rows=read_routes(p/'eur.jsonl',p/'gbp.jsonl');self.assertEqual(source,actual['source'])
                expected=reference(rows);reconcile(actual['result'],expected)
                self.assertEqual(expected['Signals'],1)
                self.assertEqual((expected['Complete'],expected['Censored']),(0,1) if gap else (1,0))
                if not gap:self.assertGreater(expected['Episodes'][0]['NetEur'],0)
    def test_reversed_future_does_not_alter_decision_or_entry(self):
        rows=[]
        for i in range(181):
            f=110000+(100 if i>=60 else 0);g=125000+(50 if i>=125 else 0)
            rows.append((T+i*1000,'READY_STRICT_PRIOR_FX',g,g+2,f,f+2))
        a=reference(rows);b=copy.deepcopy(rows)
        b[125:]=[(t,c,120000,120002,fb,fa) for t,c,_,__,fb,fa in b[125:]]
        e=reference(b)
        self.assertEqual(a['DecisionSha256'],e['DecisionSha256'])
        self.assertEqual(a['Episodes'][0]['Entry'],e['Episodes'][0]['Entry'])
        self.assertLess(e['Episodes'][0]['NetUsd'],0)
    def test_timeout_invalid_and_terminal_are_censored_never_free_exit(self):
        rows=[(T+i*1000,'READY_STRICT_PRIOR_FX',125000,125002,110000+(100 if i>=60 else 0),110002+(100 if i>=60 else 0)) for i in range(80)]
        self.assertEqual(reference(rows)['Censored'],1)
        rows[70]=(rows[70][0],'FX_STALE',125000,125002,None,None)
        self.assertEqual(reference(rows)['Censored'],1)
    def test_net_is_not_certification_and_censoring_blocks_promotion(self):
        self.assertEqual(decide({'Complete':0,'Censored':1,'Episodes':[]})[0],'DATA_LIMITED')
        r={'Signals':1,'Complete':1,'Censored':0,'DecisionSha256':'a','Episodes':[]}
        e=copy.deepcopy(r);e['DecisionSha256']='b'
        with self.assertRaises(ValueError):reconcile(r,e)
if __name__=='__main__':unittest.main()

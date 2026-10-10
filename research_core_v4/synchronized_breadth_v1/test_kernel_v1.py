import unittest,math,copy
from research_core_v4.synchronized_breadth_v1 import kernel_v1 as k

def panel():
    return {sid:[{'x':[1.,.02*((j+sid)%7-3),.03],'y':float((j*sid)%11-5),'label':'SUPPORTED','feature':'FEATURE_VALID'} for j in range(672)] for sid in range(1,11)}

class Tests(unittest.TestCase):
    def test_target_excluded(self):
        a=panel();b=copy.deepcopy(a)
        for r in b[1]:r['x'][1]*=-1
        ba,_=k.peer_breadth(a,{'g':list(a)});bb,_=k.peer_breadth(b,{'g':list(b)})
        self.assertEqual(ba[1],bb[1]);self.assertNotEqual(ba[2],bb[2])
    def test_future_cannot_change_forecasts(self):
        a=panel();b=copy.deepcopy(a)
        for rows in b.values():
            for j in range(400,672):rows[j]['x'][1]*=-2;rows[j]['y']+=100
        ba,_=k.peer_breadth(a,{'g':list(a)});bb,_=k.peer_breadth(b,{'g':list(b)})
        ra=k.evaluate(1,a,ba);rb=k.evaluate(1,b,bb)
        keys=('clock','training','breadth','model','baseline')
        self.assertEqual([tuple(r[z] for z in keys) for r in ra['trials'][:400]],[tuple(r[z] for z in keys) for r in rb['trials'][:400]])
        self.assertEqual(ra['trials'][33]['training'],32);self.assertIsNone(ra['trials'][32]['model'])
    def test_missing_peer_and_target_support(self):
        p=panel()
        for sid in (2,3):p[sid][100]['x']=None;p[sid][100]['feature']='FEATURE_GAP'
        b,_=k.peer_breadth(p,{'g':list(p)})
        self.assertIsNone(b[1][100]['b']);self.assertEqual(b[2][100]['reason'],'FEATURE_GAP')
        self.assertEqual(b[1][99]['peers'],9)
    def test_calendar_denominators_and_label_gap(self):
        p=panel();p[1][101]['y']=None;p[1][101]['label']='LABEL_GAP'
        b,_=k.peer_breadth(p,{'g':list(p)});r=k.evaluate(1,p,b)
        self.assertEqual([m['calendar'] for m in r['four_weeks']],[168]*4)
        self.assertEqual(r['trials'][101]['reason'],'LABEL_GAP');self.assertIsNotNone(r['trials'][101]['model'])
        self.assertEqual(sum(m['calendar'] for m in r['iso_utc'].values()),672)
    def test_inactive_and_receipt_rows_are_not_features(self):
        bars={}
        for i in range(8064):
            t=k.n.START+i*300;bars[t]={'timestamp':t,'available_at':t+300,'open':100.,'close':100.01,'high':100.02,'low':99.,'tick_volume':10}
        t=k.n.START+100*3600;bars[t-300]['tick_volume']=0
        self.assertEqual(k.reduce(bars)[100]['feature'],'INACTIVE_FEATURE_ABSTENTION')
        bars[t-300]['tick_volume']=10;bars[t-300]['available_at']=t+901
        self.assertEqual(k.reduce(bars)[100]['feature'],'FEATURE_RECEIPT')
if __name__=='__main__':unittest.main()

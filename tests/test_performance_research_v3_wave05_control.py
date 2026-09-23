import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from m7 import competition_performance_v3_wave05_c029_c030_evaluator as w

UTC=timezone.utc

def bar(t,p=100.0):
    return {"t":t,"o":p,"h":p+0.2,"l":p-0.2,"c":p}

class Wave05ControlPathTests(unittest.TestCase):
    def test_c029_entry_admitted_without_future_target(self):
        st=datetime(2026,6,15,0,0,tzinfo=UTC)
        rows=[bar(st+i*w.M5,100.0) for i in range(151)]
        i=149
        rows[i]={"t":rows[i]["t"],"o":100.0,"h":110.2,"l":99.8,"c":110.0}
        rows[i+1]=bar(rows[i+1]["t"],110.0)
        with patch.object(w.statistics,"median",return_value=0.01):
            trades,diag,bad=w.c029_trades({"X":rows},{"X":0.001})
        self.assertEqual(bad,[])
        self.assertEqual(trades,[])
        self.assertEqual(diag["X"]["admitted_entries"],1)
        self.assertEqual(diag["X"]["right_censored_entries"],1)

    def test_c029_exact_target_settles_only_after_admission(self):
        st=datetime(2026,6,15,0,0,tzinfo=UTC)
        rows=[bar(st+i*w.M5,100.0) for i in range(190)]
        i=149
        rows[i]={"t":rows[i]["t"],"o":100.0,"h":110.2,"l":99.8,"c":110.0}
        rows[i+1]=bar(rows[i+1]["t"],110.0)
        for j in range(i+1,len(rows)):
            rows[j]["h"]=max(rows[j]["h"],111.0)
        with patch.object(w.statistics,"median",return_value=0.01):
            trades,diag,bad=w.c029_trades({"X":rows},{"X":0.001})
        self.assertEqual(bad,[])
        self.assertGreaterEqual(len(trades),1)
        self.assertEqual(trades[0]["e"],rows[i+1]["t"])
        self.assertEqual(trades[0]["x"],rows[i+1]["t"]+timedelta(minutes=180))

    def test_c030_tail_target_is_right_censored_not_prechecked(self):
        st=datetime(2026,6,15,0,0,tzinfo=UTC)
        leader=[bar(st+i*w.M5,100*(1.001**i)) for i in range(360)]
        lag=[bar(st+i*w.M5,100*(1.0002**i)) for i in range(360)]
        with patch.object(w.statistics,"median",return_value=0.001):
            trades,diag,bad=w._pair_shocks(leader,lag,{"LAG":0.0},"LEAD","LAG")
        self.assertEqual(bad,[])
        self.assertGreater(diag["trained_shocks"],0)
        self.assertGreater(diag["admitted_trade_entries"],0)
        self.assertGreater(diag["right_censored_pending_items"],0)

    def test_c030_internal_post_entry_gap_is_data_invalid(self):
        st=datetime(2026,6,15,0,0,tzinfo=UTC)
        lag=[bar(st+i*w.M5,100+i*.01) for i in range(30)]
        idx={r["t"]:i for i,r in enumerate(lag)}
        item={"entry_i":5,"entry_t":lag[5]["t"],"entry_price":lag[5]["o"],"target":lag[17]["t"],"direction":"LONG","sign":1.0}
        status,_=w._settle_lag_example(lag,idx,item,lag[-1]["t"])
        self.assertEqual(status,"SETTLED")
        broken=lag[:12]+lag[13:]
        idx2={r["t"]:i for i,r in enumerate(broken)}
        item2=dict(item); item2["entry_i"]=idx2[item["entry_t"]]
        status,_=w._settle_lag_example(broken,idx2,item2,broken[-1]["t"])
        self.assertEqual(status,"INVALID")

if __name__=="__main__":
    unittest.main(verbosity=2)

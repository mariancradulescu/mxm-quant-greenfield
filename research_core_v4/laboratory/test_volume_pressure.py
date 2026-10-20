"""New research extractor checks, separate from accepted laboratory reception."""
import unittest
from .data import DataCatalogue
from .common import LabError
from .volume_pressure import volume_pressure_intents

class VolumePressure(unittest.TestCase):
    def setup_case(self):
        decision=1736164800000
        rows=[{'t':decision-300000*j,'available_at':decision-300000*j+300000,
          'open':100.,'high':102.,'low':98.,'close':100.,'volume':10.} for j in range(13,0,-1)]
        rows[-1].update(open=100.,high=102.,low=98.,close=101.5,volume=20.)
        spec={'parameters':{'volume_pressure':{'prior_bars':12,'volume_multiple':2,'close_location_threshold':.8,
          'entry_delay_ms':1000,'hold_ms':1800000,'symbols':{'A':9},'decision_times_ms':[decision]}}}
        cache=DataCatalogue(assets={'a':{'partition':'DEVELOPMENT','resolution':'M5','instrument':'A',
          'trust':'AUTHENTICATED_NATIVE_COLLECTION','invalid':0,'conflicts':0}},rows={'a':rows})
        return decision,spec,cache
    def test_exact_known_pressure_and_no_overlap_horizon(self):
        d,s,c=self.setup_case();r=volume_pressure_intents(s,c,{'A':'a'})
        self.assertEqual(r['intents'],[{'decision_ms':d,'feature_available_ms':d,'entry_ms':d+1000,
          'exit_ms':d+1801000,'direction':1,'symbol_id':9}])
        self.assertFalse(r['missing'])
    def test_unknown_clock_or_late_receipt_does_not_compress_history(self):
        for mode in ('gap','late'):
            with self.subTest(mode=mode):
                d,s,c=self.setup_case()
                if mode=='gap':c.rows['a'].pop(5)
                else:c.rows['a'][5]['available_at']=d+1
                r=volume_pressure_intents(s,c,{'A':'a'})
                self.assertEqual(r['intents'],[]);self.assertEqual(len(r['missing']),1)
    def test_no_volume_shock_and_zero_volume_are_not_signals(self):
        for volume in (19.,0.):
            d,s,c=self.setup_case();c.rows['a'][-1]['volume']=volume
            self.assertEqual(volume_pressure_intents(s,c,{'A':'a'})['intents'],[])
    def test_future_and_synthetic_assets_rejected(self):
        d,s,c=self.setup_case();c.assets['a']['trust']='SYNTHETIC'
        with self.assertRaises(LabError):volume_pressure_intents(s,c,{'A':'a'})
        d,s,c=self.setup_case();s['parameters']['volume_pressure']['decision_times_ms']=[1789603200000]
        with self.assertRaises(LabError):volume_pressure_intents(s,c,{'A':'a'})
if __name__=='__main__':unittest.main()

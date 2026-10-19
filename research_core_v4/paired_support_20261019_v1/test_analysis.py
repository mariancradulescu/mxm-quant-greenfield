import copy, unittest
from .analysis import analyze, contrast, check_account, FIELDS

def account(net=2., cash=False):
    a={f:0. for f in FIELDS}; a.update(midpoint_gross_eur=net,net_eur=net)
    if cash:a['cash_tie']=True
    return a

def row(sid=1,t=0,model=2.,baseline=1.):
    return {'sid':sid,'t':t,'exit':t+900,'accounts':{'model':None if model is None else account(model),
        'midpoint':None if baseline is None else account(baseline),'quote_count':account(0.,True)}}

def fixture(rows):
    acc={}
    for a in ('model','midpoint','quote_count'):
        known=[r['accounts'][a] for r in rows if r['accounts'].get(a) is not None]
        acc[a]={'selected':len(rows),'evaluable':len(known),'unknown':len(rows)-len(known),
                'known_subtotal':{f:sum(r[f] for r in known) if known else None for f in FIELDS}}
        if a!='model':
            pairs=[r for r in rows if r['accounts'].get('model') is not None and r['accounts'].get(a) is not None]
            acc[a].update(paired_entries=len(pairs),paired_model_increment_eur=sum(r['accounts']['model']['net_eur']-r['accounts'][a]['net_eur'] for r in pairs) if pairs else None)
    return {'summary':{'portfolio':{'selected':[{'sid':r['sid'],'entry':r['t']} for r in rows]},'accounting':acc},'selected_accounting':rows}

class Tests(unittest.TestCase):
    def test_missing_joint_support_not_complete(self):
        v=analyze(fixture([row(),row(2,model=None)]));self.assertEqual(len(v['exact_unresolved_targets']),1);self.assertFalse(v['contrasts']['midpoint']['full_population_increment_identified'])
    def test_disjoint_support_no_fake_pair(self):
        v=contrast([row(model=None),row(2,baseline=None)],'midpoint');self.assertEqual(v['paired'],0);self.assertIsNone(v['saved_component_increment_eur']['net_eur'])
    def test_cash_tie_is_observed_zero(self):
        self.assertEqual(analyze(fixture([row()]))['contrasts']['quote_count']['cash_tie_baselines'],1)
    def test_cost_differential_identity(self):
        r=row();r['accounts']['model'].update(midpoint_gross_eur=3.,spread_drag_eur=1.);v=analyze(fixture([r]))['contrasts']['midpoint']['saved_component_increment_eur'];self.assertEqual(v['midpoint_gross_eur'],2.);self.assertEqual(v['net_eur'],1.)
    def test_deletion_no_independent_inference(self):
        v=contrast([row(),row(2,7*86400,model=-4.)],'midpoint');self.assertEqual(v['leave_one_identity_out_known_increment_eur'],{'1':-5.,'2':1.});self.assertIsNone(v['p_value'])
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):analyze(fixture([row(),row()]))
    def test_summary_drift_rejected(self):
        f=fixture([row()]);f['summary']['accounting']['model']['known_subtotal']['net_eur']=3.
        with self.assertRaises(ValueError):analyze(f)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):check_account(account(float('nan')))
    def test_cash_falsehood_rejected(self):
        with self.assertRaises(ValueError):check_account(account(2.,True))
    def test_no_row_complete_claim(self):
        v=analyze(fixture([]));self.assertFalse(v['contrasts']['midpoint']['full_population_increment_identified'])

if __name__=='__main__':unittest.main()

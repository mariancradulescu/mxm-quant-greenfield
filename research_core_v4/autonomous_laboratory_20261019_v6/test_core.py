import copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from .core import *
R=json.loads(Path(__file__).with_name('REGISTRY.json').read_text())

class Registry(unittest.TestCase):
    def test_verdict_selects_distinct_next_or_stop(self):
        self.assertEqual(next_task(TASKS[0],'DATA_INSUFFICIENT',[],R),TASKS[1])
        self.assertIsNone(next_task(TASKS[0],'SUPPORTED_REFERENCE_ONLY',[],R))
        self.assertIsNone(next_task(TASKS[1],'COST_UNRESOLVED',[TASKS[0]],R))
    def test_replay_unknown_and_budget_stop(self):
        for args in [(TASKS[0],'DATA_INSUFFICIENT',[TASKS[0]],R),(TASKS[0],'PROFIT',[],R)]:
            with self.assertRaises(ValueError):next_task(*args)
        r=copy.deepcopy(R);r['budgets']['feasibility_investigations']=0
        with self.assertRaisesRegex(ValueError,'BUDGET'):next_task(TASKS[0],'DATA_INSUFFICIENT',[],r)
    def test_directional_trial_cannot_sneak_into_support_program(self):
        r=copy.deepcopy(R);r['tasks'][TASKS[1]]['strategy_trials']=1
        with self.assertRaisesRegex(ValueError,'DIRECTIONAL_BUDGET'):next_task(TASKS[0],'DATA_INSUFFICIENT',[],r)
    def test_carry_unknown_is_not_zero_or_later_snapshot(self):
        data={'summary':{'dated_contract_terms':'CATALOG_CURRENT_REFERENCE'},'catalog':{'full':{'1':{'swapLong':5}}},'all_identity_status':[{'sid':1}],'events':[{'t':1}]}
        x=carry_temporal_authority(data)
        self.assertEqual(x['classification'],'DATA_INSUFFICIENT');self.assertIsNone(x['historical_carry_net_eur'])
        self.assertFalse(x['causal_entry_possible_from_later_terms'])
    def test_missing_cost_blocks_replay_without_consuming_events(self):
        def fail():raise AssertionError('Replay must not run');yield
        self.assertEqual(replay_candidate({}, {}, {'global_reconciled':False}, fail())['state'],'BUDGET_UNRECONCILED')
        self.assertEqual(candidate_gate({}, {'causal':True,'full_dependency_support':True}, {'global_reconciled':True,'remaining':1}),'COST_UNRESOLVED')
    def test_established_account_replay_integrates_without_resets(self):
        from competition.continuous_account_replay_v2 import CapitalEvent
        common={'candidate_id':'SYNTHETIC_ONLY','symbol':'TEST','position_id':'p','quote_to_eur_rate':1}
        events=[CapitalEvent('2026-01-04T23:00:00Z','ENTRY',direction='LONG',direction_feasibility='EUR200_MIN_VOLUME_FEASIBLE',volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=1000,margin_eur=50,price=10,base_units=1,transaction_cost_eur=1,**common),
            CapitalEvent('2026-01-05T01:00:00Z','EXIT',price=13,transaction_cost_eur=1,**common)]
        ev={'causal':True,'full_dependency_support':True,'costs_identified_or_certified_bound':True,'positive_edge':True}
        spec={'starting_equity_eur':200,'deposit_count':1,'account_type':'HEDGED','margin_type':'SUM'}
        r=replay_candidate(spec,ev,{'global_reconciled':True,'remaining':1},events)['result']
        self.assertEqual(r.starting_equity_eur,Decimal('200'));self.assertEqual(r.terminal_strategy_nav_eur,Decimal('201'))
        self.assertEqual(r.accepted_entries,1)
    def test_pending_and_source_mismatch_stop(self):
        from .runtime import check_state
        s={'schema':'mxm.scientific-evidence-state.v6','registry_sha256':sha(enc(R)),'authority':R['authority'],'source_sha':'a'*40,'pending':None,'strategy_trials':0,'completed':[]}
        with patch.dict(os.environ,{'V6_SOURCE_SHA':'a'*40}):
            check_state(s,R);s['pending']='unknown ack'
            with self.assertRaisesRegex(ValueError,'STATE_BINDING'):check_state(s,R)

class Capital(unittest.TestCase):
    def fixture(self):
        class A:
            graph=staticmethod(lambda x:{})
            point=staticmethod(lambda q: {'bid':10.,'ask':10.1,'mid':10.05} if q else None)
            convert=staticmethod(lambda x,*a:x)
            commission=staticmethod(lambda *a:1.)
        c={'all_identity_status':[{'sid':1,'class':'TEST','quote':'EUR','min_units':1.,'margin_eur':100.}],
          'catalog':{'full':{'1':{'minVolume':100,'stepVolume':100,'maxVolume':1000}}},
          'raw_quote_receipts':[{'symbol_id':1,'boundary_ms':100000}], 'events':[{'sid':1,'t':100}]}
        return c,A
    def test_native_ticket_sensitivity_is_not_repeated_deposit(self):
        c,a=self.fixture();r=capital_scale(c,a)
        self.assertEqual(r['state_counts']['80']['REFERENCE_CAPITAL_INFEASIBLE'],1)
        self.assertEqual(r['state_counts']['200']['REFERENCE_ADMISSIBLE'],1)
        self.assertFalse(r['capital_states_are_deposits']);self.assertEqual(r['deposit_count'],1)
        self.assertIsNone(r['realizable_net_pnl'])
    def test_invalid_lattice_and_missing_margin_unknown(self):
        c,a=self.fixture();c['catalog']['full']['1']['stepVolume']=0
        r=capital_scale(c,a);self.assertEqual(r['priced_boundaries'],0);self.assertEqual(r['classification'],'DATA_INSUFFICIENT')
        c,a=self.fixture();c['all_identity_status'][0]['margin_eur']=None
        self.assertEqual(capital_scale(c,a)['unresolved']['CURRENT_MARGIN_UNRESOLVED'],1)
    def test_foreign_or_protected_data_not_admitted(self):
        c,a=self.fixture();c['events'][0]['t']=1789603200
        with self.assertRaisesRegex(ValueError,'PROTECTED_BOUNDARY'):capital_scale(c,a)

if __name__=='__main__':unittest.main()

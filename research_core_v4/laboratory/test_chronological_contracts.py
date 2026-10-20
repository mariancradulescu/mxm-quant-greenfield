"""Adversarial account/adapter contracts; artificial inputs, no market outcomes."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import unittest

from competition.continuous_account_replay_v2 import CapitalEvent, ReplayContractError, replay_continuous_account
from .common import LabError, digest
from .fixtures import economic_fixture, native_path_fixture, candidate


class ChronologicalContracts(unittest.TestCase):
    def entry(self, ident='A', margin=100, direction='LONG'):
        return CapitalEvent('2025-01-06T12:00:00Z', 'ENTRY', 'TEST', ident, ident,
            direction=direction, direction_feasibility='EUR200_MIN_VOLUME_FEASIBLE',
            volume_cents=100, min_volume_cents=100, step_volume_cents=100,
            max_volume_cents=1000, margin_eur=margin, price=100,
            base_units=1, quote_to_eur_rate=1)

    def replay(self, events, **kw):
        return replay_continuous_account(events, starting_equity_eur=200,
            account_type='HEDGED', total_margin_calculation_type='SUM', **kw)

    def test_equivalent_utc_instants_form_one_atomic_mark_batch(self):
        a=self.entry('A', 40); b=self.entry('B', 40, 'SHORT')
        rows=[a,b,
            replace(a,kind='MARK',timestamp_utc='2025-01-06T12:05:00Z',price=20),
            replace(b,kind='MARK',timestamp_utc='2025-01-06T14:05:00+02:00',price=20),
            replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:10:00Z'),
            replace(b,kind='EXIT',timestamp_utc='2025-01-06T12:10:00Z')]
        result=self.replay(rows,unresolved_stop_out_guard_ratio=Decimal('1.8'))
        self.assertEqual(result.status,'COMPLETE')
        self.assertEqual(result.minimum_margin_level_ratio,Decimal('2.5'))

    def test_mark_risk_precedes_same_instant_exit_margin_release(self):
        a=self.entry('A',100); b=self.entry('B',40)
        result=self.replay([a,b,
            replace(a,kind='MARK',timestamp_utc='2025-01-06T12:05:00Z',price=40),
            replace(b,kind='EXIT',timestamp_utc='2025-01-06T12:05:00Z'),
            replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:10:00Z')],
            unresolved_stop_out_guard_ratio=Decimal('1.2'))
        self.assertEqual(result.status,'HALT_UNRESOLVED_BROKER_STOP_OUT')
        self.assertFalse(any(d.kind=='EXIT' and d.accepted for d in result.decisions))

    def test_exit_quote_itself_cannot_escape_stop_out_guard(self):
        a=self.entry('A',100)
        result=self.replay([a,replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:05:00Z',price=40)],
            unresolved_stop_out_guard_ratio=Decimal('1.5'))
        self.assertEqual(result.status,'HALT_UNRESOLVED_BROKER_STOP_OUT')
        self.assertEqual(result.terminal_broker_equity_eur,140)
        self.assertFalse(result.decisions[-1].accepted)

    def test_adjacent_funding_intervals_conserve_cash(self):
        from .economics import replay
        spec,evidence=economic_fixture()
        for stamp,start,end,amount in [('2025-01-06T12:00:30Z',1736164801000,1736164820000,1),
                                     ('2025-01-06T12:00:40Z',1736164820000,1736164830000,-2)]:
            row=deepcopy(evidence['events'][0]);row.update(kind='FINANCING',financing_eur=amount,timestamp_utc=stamp)
            row['metadata'].update(accrual_start_ms=start,accrual_end_ms=end)
            evidence['events'].append(row)
        result=replay(spec,evidence)
        self.assertEqual(Decimal(result['replay']['financing_eur']),-1)
        self.assertEqual(Decimal(result['replay']['terminal_broker_equity_eur']),201)

    def test_mark_must_match_active_candidate_and_symbol(self):
        a=self.entry()
        for field in ('candidate_id','symbol'):
            bad=replace(a,kind='MARK',timestamp_utc='2025-01-06T12:01:00Z',**{field:'OTHER'})
            with self.subTest(field=field),self.assertRaises(ReplayContractError):
                self.replay([a,bad,replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:02:00Z')])

    def test_fractional_or_boolean_volume_is_not_coerced(self):
        for volume in (100.5,True):
            a=replace(self.entry(),volume_cents=volume)
            with self.subTest(volume=volume),self.assertRaises(ReplayContractError):
                self.replay([a,replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:02:00Z')])

    def test_exit_price_and_conversion_must_be_positive(self):
        a=self.entry()
        for field in ('price','quote_to_eur_rate'):
            with self.subTest(field=field),self.assertRaises(ReplayContractError):
                self.replay([a,replace(a,kind='EXIT',timestamp_utc='2025-01-06T12:02:00Z',**{field:-1})])

    def test_laboratory_replay_requires_explicit_stop_out_contract(self):
        from .economics import replay
        spec,evidence=economic_fixture();spec.pop('broker_stop_out_guard',None)
        with self.assertRaisesRegex(LabError,'STOP_OUT'):
            replay(spec,evidence)

    def test_negative_component_cannot_hide_in_positive_total_cost(self):
        from .economics import replay
        spec,evidence=economic_fixture()
        spec['broker_stop_out_guard']=.5
        row=evidence['events'][0];row['transaction_cost_eur']=.1
        row['metadata']['cost_components_eur'].update(commission=-.1,slippage=.2)
        with self.assertRaisesRegex(LabError,'NEGATIVE_COST'):
            replay(spec,evidence)

    def test_financing_intervals_cannot_be_recharged_at_another_timestamp(self):
        from .economics import replay
        spec,evidence=economic_fixture();spec['broker_stop_out_guard']=.5
        base=deepcopy(evidence['events'][0]);base.update(kind='FINANCING',financing_eur=1,
            timestamp_utc='2025-01-06T12:00:30Z')
        base['metadata'].update(accrual_start_ms=1736164801000,accrual_end_ms=1736164820000)
        other=deepcopy(base);other['timestamp_utc']='2025-01-06T12:00:40Z'
        evidence['events'] += [base,other]
        with self.assertRaisesRegex(ReplayContractError,'accrual'):
            replay(spec,evidence)

    def test_native_screen_rejects_future_signal_before_opening(self):
        from discovery.engine import DiscoveryEngine
        from .science import native_quote_screen
        generated,corpus,_,coarse,_=native_path_fixture()
        spec=DiscoveryEngine().freeze_candidate(candidate('V2-C999','TEST'),persist=False)
        generated['intents'][0]['feature_available_ms']=generated['intents'][0]['entry_ms']
        opened=[]
        with self.assertRaises(LabError):
            native_quote_screen(spec,generated,corpus,coarse,lambda:opened.append(True))
        self.assertEqual(opened,[])

    def test_native_screen_rejects_late_quote_before_opening(self):
        from discovery.engine import DiscoveryEngine
        from .science import native_quote_screen
        generated,corpus,_,coarse,_=native_path_fixture()
        spec=DiscoveryEngine().freeze_candidate(candidate('V2-C999','TEST'),persist=False)
        side=corpus['raw_quote_receipts'][0]['sides']['ask']
        side['available_at_ms']=side['timestamp_ms']+1
        opened=[]
        with self.assertRaisesRegex(LabError,'AVAILABILITY'):
            native_quote_screen(spec,generated,corpus,coarse,lambda:opened.append(True))
        self.assertEqual(opened,[])


if __name__=='__main__':unittest.main()

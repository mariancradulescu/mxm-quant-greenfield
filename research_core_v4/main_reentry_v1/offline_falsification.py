"""Finite exact semantic witnesses only. No market reader, fitter or trial bank.

The two diagnostic maps are not experimental candidates. Synthetic receipts
below describe fabricated records only; no archive receipt is reconstructed.
"""
from fractions import Fraction as F
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import socket
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "immutable_compact_reference", ROOT / "compact_baseline_v2.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
T = 10800


def deny_network(*args, **kwargs):
    raise RuntimeError("OFFLINE_ONLY")


def fabricated_hour(order):
    assert len(order) == 12
    return [{"timestamp": 7200 + 300*j, "available_at": 7500 + 300*j,
             "open": 2, "high": 4, "low": 1, "close": c,
             "tick_volume": j+1} for j, c in enumerate(order)]


def diagnostic_maps(bars):
    """Fully elapsed exact hour only. Neither map is a certified predictor."""
    if len(bars) != 12 or [b["timestamp"] for b in bars] != list(range(7200, T, 300)):
        raise ValueError("MISSING_DUPLICATE_OR_OFFGRID")
    for b in bars:
        if not b['low'] <= min(b['open'], b['close']) <= max(b['open'], b['close']) <= b['high']:
            raise ValueError("INVALID_OHLC")
        if type(b['tick_volume']) is not int or b['tick_volume'] < 0:
            raise ValueError("INVALID_ACTIVITY")
    u = [(b['close'] > b['open']) - (b['close'] < b['open']) for b in bars]
    chronology = F(sum(a*b for a, b in zip(u, u[1:])), 11)
    total = sum(b['tick_volume'] for b in bars)
    coupling = F(sum(b['tick_volume']*v for b, v in zip(bars, u)), total) if total else None
    return chronology, coupling


def inherited_own_signature(bars):
    """Exact invariants sufficient for these two finite witnesses only.

    Sorted close counts encode identical squared log variations and locations
    here because every open/high/low is identical. This is not a general
    implementation or substitute for the frozen five source maps.
    """
    b = reference.baseline(T, bars)
    assert b is not None
    loc = F(bars[-1]['close']-1, 3)
    hour_state = (loc > F(1, 2)) - (loc < F(1, 2))
    return b, hour_state, tuple(sorted(x['close'] for x in bars)), tuple(x['tick_volume'] for x in bars)


def information_refinement_witness():
    a = fabricated_hour([1, 3, 1] + [3]*9)
    b = fabricated_hour([1, 1] + [3]*10)
    assert inherited_own_signature(a) == inherited_own_signature(b)
    ma, mb = diagnostic_maps(a), diagnostic_maps(b)
    assert ma[0] != mb[0] and ma[1] != mb[1]
    return {"same_exact_ten_coordinate_B": True,
            "same_V2_hour_state_activity_vector_variation_multiset_location_multiset": True,
            "preceding_hour_and_Q_peer_records_held_fixed": True,
            "chronology_values": [str(ma[0]), str(mb[0])],
            "coupling_values": [str(ma[1]), str(mb[1])],
            "scope": "Structural refinement beyond B and the five V2 maps on this legal domain; no predictive or all-history noncollision certificate"}


def brier_conditional_null_witness():
    """Phi independent Y given B(q), yet a restricted comparator gains."""
    p = {0: F(3, 4), 1: F(1, 4), 2: F(3, 4)}
    atoms = []
    for q, phi, y in itertools.product(range(3), (0, 1), (0, 1)):
        pp = p[q] if phi else 1-p[q]
        py = p[q] if y else 1-p[q]
        atoms.append((q, phi, y, F(1, 3)*pp*py))
    assert sum(a[3] for a in atoms) == 1
    EY = sum(y*w for q, ph, y, w in atoms)
    conditional = {}
    for ph in (0, 1):
        mass = sum(w for q, phi, y, w in atoms if phi == ph)
        conditional[ph] = sum(y*w for q, phi, y, w in atoms if phi == ph)/mass
    gain = sum(w*((y-EY)**2 - (y-conditional[ph])**2) for q, ph, y, w in atoms)
    oracle_gain = sum(w*((y-p[q])**2 - (y-p[q])**2) for q, ph, y, w in atoms)
    assert gain > 0 and oracle_gain == 0
    # The conditioning variable is an actual coordinate of the frozen B.
    for q in range(3):
        bars = fabricated_hour([3]*12)
        for bar in bars:
            bar['tick_volume'] = q
        B = reference.baseline(T, bars)
        assert B[4] == q and B[7] == 12*q
    return {"conditional_independence_by_factorization": True,
            "population_restricted_B_prediction": str(EY),
            "augmented_prediction_by_phi": {str(k): str(v) for k, v in conditional.items()},
            "positive_Brier_gain_under_information_null": str(gain),
            "oracle_B_gain": str(oracle_gain), "finite_atoms": 12,
            "falsified_claim": "A positive proper-score model comparison proves information beyond sigma(B)"}


def receipt_worlds_witness():
    ontime = fabricated_hour([3]*12)
    delayed = [dict(b) for b in ontime]
    delayed[0]['available_at'] = T+1
    archive = lambda rows: [{k: v for k, v in b.items() if k != 'available_at'} for b in rows]
    assert archive(ontime) == archive(delayed)
    assert reference.baseline(T, ontime) is not None
    assert reference.baseline(T, delayed) is None
    assert reference.baseline(T, archive(ontime)) is None
    return {"identical_archived_OHLC_activity_open_times": True,
            "ontime_world_causal": True, "delayed_world_causal": False,
            "archive_receipt_status": "UNKNOWN",
            "structural_completion_passes_in_both_worlds": True,
            "receipt_cannot_be_identified_from_archive_projection": True,
            "conditional_as_if_completion_route_still_possible": True}


def ar050_witness():
    # Stationary +/-1 chain: same sign probability3/4 -> lag-one correlation1/2.
    atoms = [(a, b, F(3, 8) if a == b else F(1, 8))
             for a, b in itertools.product((-1, 1), repeat=2)]
    EX1 = sum(w*a for a, b, w in atoms)
    EX2 = sum(w*b for a, b, w in atoms)
    autocov = sum(w*a*b for a, b, w in atoms)
    naive = sum(w*(1+F(1, 2)*a)*(1+F(1, 2)*b) for a, b, w in atoms)
    assert EX1 == EX2 == 0 and autocov == F(1, 2) and naive == F(9, 8)
    return {"lag_one_correlation": str(autocov), "both_marginal_means": "0",
            "naive_product_expectation": str(naive),
            "next_conditional_mean": "X1/2",
            "falsified_claim": "Marginal mean-zero scores imply product e-process validity under arbitrary serial dependence",
            "not_a_certification_campaign": True, "finite_atoms": 4}


def radius(n, alpha, weight, repeated=True):
    if type(n) is not int or n < 1 or not 0 < alpha < 1 or not 0 < weight <= 1:
        raise ValueError("INVALID_BOUND_INPUT")
    spend = alpha*weight/(n*(n+1)) if repeated else alpha*weight
    return math.sqrt(2*math.log(1/spend)/n)


def authorization_scope(expected_head, observed_head, independent_authorization, scientific_freeze):
    """A decision fixture, not installed on legacy executable entrypoints."""
    return bool(expected_head == observed_head and independent_authorization
                and scientific_freeze and independent_authorization.get('scope') == 'NEW_EXACT_DEVELOPMENT_RESPONSE')


class Checks(unittest.TestCase):
    def test_01_new_maps_are_structural_refinements(self):
        self.assertTrue(information_refinement_witness()['same_exact_ten_coordinate_B'])

    def test_02_missing_and_duplicate_fail(self):
        bars = fabricated_hour([3]*12)
        for corrupted in (bars[:-1], bars[:-1]+[bars[0]]):
            with self.assertRaises(ValueError):
                diagnostic_maps(corrupted)

    def test_03_future_perturbation_does_not_change_reference(self):
        bars = fabricated_hour([3]*12)
        future = {'timestamp': T, 'available_at': T+300, 'open': 999, 'high': 1000,
                  'low': 1, 'close': 500, 'tick_volume': 999}
        self.assertEqual(reference.baseline(T, bars), reference.baseline(T, bars+[future]))

    def test_04_receipt_nonidentification(self):
        self.assertEqual(receipt_worlds_witness()['archive_receipt_status'], 'UNKNOWN')

    def test_05_information_null_can_have_forecast_gain(self):
        self.assertGreater(F(brier_conditional_null_witness()['positive_Brier_gain_under_information_null']), 0)

    def test_06_marginal_null_not_conditional_null(self):
        self.assertEqual(ar050_witness()['naive_product_expectation'], '9/8')

    def test_07_partial_null_repeated_look_spending(self):
        # For any true-null subset, the complete weights still bound the union.
        weights = [F(1, 4)]*4
        for subset in itertools.chain.from_iterable(itertools.combinations(range(4), r) for r in range(5)):
            spent = sum(weights[j]*sum(F(1, n*(n+1)) for n in range(1, 101)) for j in subset)
            self.assertLessEqual(spent, 1)
        self.assertEqual(sum(F(1, n*(n+1)) for n in range(1, 101)), F(100, 101))

    def test_08_common_factor_not_extra_sample_size(self):
        # Duplicating a whole synchronized instrument path leaves daily mean identical.
        path = [F(1, 2), F(-1, 4), F(1, 8)]
        duplicate = [(a+a)/2 for a in path]
        self.assertEqual(path, duplicate)
        self.assertGreater(radius(3, .025, .25), radius(6, .025, .25))

    def test_09_censoring_changes_estimand(self):
        atoms = [(F(-1), F(1, 2), False), (F(1), F(1, 2), True)]
        complete = sum(x*w for x, w, present in atoms)
        observed = sum(x*w for x, w, present in atoms if present)/sum(w for x, w, present in atoms if present)
        self.assertEqual(complete, 0)
        self.assertEqual(observed, 1)

    def test_10_head_bound_missing_authorization_fails(self):
        for expected, observed, auth, freeze in [('a', 'b', {'scope':'NEW_EXACT_DEVELOPMENT_RESPONSE'}, True),
                                                ('a', 'a', None, True),
                                                ('a', 'a', {'scope':'NEW_EXACT_DEVELOPMENT_RESPONSE'}, False)]:
            self.assertFalse(authorization_scope(expected, observed, auth, freeze))

    def test_11_fixed_and_repeated_bound_laws(self):
        self.assertGreater(radius(224, .025, F(1, 261)), radius(224, .025, F(1, 261), False))
        with self.assertRaises(ValueError):
            radius(0, .025, 1)

    def test_12_historical_authority_hashes(self):
        inventory = json.loads((HERE/'INPUT_BINDINGS_V1.json').read_text())
        root = ROOT.parent
        for path, digest in inventory['files_sha256'].items():
            self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(), digest, path)


def main():
    socket.socket = socket.create_connection = socket.getaddrinfo = deny_network
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TestResult()
    suite.run(result)
    report = {
        'schema': 'mxm.main-reentry.offline-falsification.v1',
        'tests_run': result.testsRun, 'passed': result.testsRun-len(result.failures)-len(result.errors),
        'failures': [{'test': str(t), 'traceback': s} for t, s in result.failures],
        'errors': [{'test': str(t), 'traceback': s} for t, s in result.errors],
        'structural_refinement': information_refinement_witness(),
        'forecast_skill_not_information': brier_conditional_null_witness(),
        'receipt_nonidentification': receipt_worlds_witness(),
        'dependent_null': ar050_witness(),
        'semantic_proposals_falsified': ['FORECAST_GAIN_IMPLIES_SIGMA_B_INFORMATION',
                                      'BAR_CLOSE_CERTIFIES_ORIGINAL_RECEIPT',
                                      'MARGINAL_NULL_SUFFICES_FOR_PRODUCT_E_PROCESS',
                                      'RESPONSE_SELECTED_OBSERVATIONS_KEEP_FULL_DOMAIN_ESTIMAND'],
        'diagnostic_bounds_not_a_design_or_power_certificate': {
            'alpha_new_example_only': .025, 'family_example_only': 261,
            'fixed224_fullrange_Hoeffding_radius': radius(224, .025, F(1, 261), False),
            'repeated224_fullrange_Hoeffding_radius': radius(224, .025, F(1, 261)),
            'meaning': 'Maximum-range conservative uncertainty in bounded score units; no market power or bps claim'},
        'ingress': {'market_rows': 0, 'real_responses': 0, 'broker_requests': 0,
                    'encrypted_assets': 0, 'null_monte_carlo_trials': 0, 'power_trials': 0,
                    'orders': 0, 'telemetry_rows': 0, 'legacy_campaign_replays': 0},
        'scientific_experiment_certified': False,
        'result_scope': 'Exact finite witnesses and software/semantic checks; no empirical discovery',
        'python_version': sys.version.split()[0],
    }
    output = HERE/'OFFLINE_RESULT_V1.json'
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'tests_run': report['tests_run'], 'passed': report['passed'],
                      'failures': report['failures'], 'errors': report['errors'],
                      'result_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic mutation probes: corrupted scientific/numeric claims must fail."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_stop_risk_capacity_receipt import RECEIPT, PREREG, validate

class ReceiptIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(RECEIPT.read_text())
        cls.p = json.loads(PREREG.read_text())

    def test_original_readback(self):
        self.assertEqual(validate(self.r, self.p)["validated_cells"], 6)

    def reject(self, mutation):
        r = copy.deepcopy(self.r)
        mutation(r)
        with self.assertRaises(ValueError):
            validate(r, self.p)

    def test_duplicate_cell(self):
        self.reject(lambda r: r["risk_cells"].__setitem__(0, copy.deepcopy(r["risk_cells"][1])))

    def test_omitted_cell(self):
        self.reject(lambda r: r["risk_cells"].pop())

    def test_malformed_positive_pnl(self):
        self.reject(lambda r: r["risk_cells"][2].__setitem__("hypothetical_final_equity_eur", 201))

    def test_negative_nonfinite_and_mutated_count(self):
        for x in (-1, "NaN", "Infinity", 198):
            with self.subTest(x=x):
                self.reject(lambda r: r["risk_cells"][2].__setitem__("hypothetical_final_equity_eur", x))
        self.reject(lambda r: r["risk_cells"][2].__setitem__("modeled_entries", 8))

    def test_fake_hard21(self):
        self.reject(lambda r: r.__setitem__("hard21", True))
        self.reject(lambda r: r.__setitem__("full_iso_utc_weeks", 1))

    def test_fake_scientific_promotion(self):
        self.reject(lambda r: r.__setitem__("research_disposition", "PROMOTE"))
        self.reject(lambda r: r.__setitem__("confirmation_opened", True))
        self.reject(lambda r: r.__setitem__("scientific_classification", "INDEPENDENT_CONFIRMATION"))

    def test_authority_and_custody_mutations(self):
        for key in ("canonical_V2_trial_ledger_modified", "owner_checkpoint_modified",
                    "protected_forward_opened", "bidask_are_broker_fills"):
            with self.subTest(key=key):
                self.reject(lambda r: r.__setitem__(key, True))
        self.reject(lambda r: r.__setitem__("encrypted_private_result_sha256", "0" * 64))

    def test_fake_broker_execution(self):
        self.reject(lambda r: r.__setitem__("broker_requests", 1))
        self.reject(lambda r: r.__setitem__("live_orders", 1))

if __name__ == "__main__":
    unittest.main()

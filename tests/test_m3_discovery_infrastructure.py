import copy
import json
import tempfile
import unittest
from pathlib import Path

from discovery.canonical import compute_spec_hash, freeze_spec, verify_spec_hash
from discovery.engine import DiscoveryEngine
from discovery.ledger import append_entry, read_ledger
from discovery.schema import SchemaError, validate_candidate_spec


def draft():
    return {
        "id":"V2-C001","mechanism":{"family":"TEST_ONLY_STRUCTURAL"},
        "rationale":"M3 schema fixture only; no economic hypothesis is opened.",
        "universe":["SYNTHETIC"],"data":{"resolution":"TEST","manifest_refs":[]},
        "causal_availability":{"rule":"completed_only"},"features":[],"lookbacks":[],
        "normalization_training":{"mode":"none"},"timing":{"decision":"bar_close"},
        "direction":"BOTH","entry":{"rule":"next_valid"},"exit":{"rule":"fixture"},
        "maximum_hold":{"unit":"bars","value":1},
        "execution_assumptions":{"scope":"structural_test_only"},"filters":[],"parameters":{},
        "capital_semantics":{"mode":"continuous"},"cost_state":{"state":"UNRESOLVED"},
        "cloud_portability":{"required":True},
        "no_rescue_rule":{"material_semantic_change_requires_new_identity":True},
        "spec_hash":"","provenance":{"scope":"M3_TEST_ONLY"},
    }


class M3DiscoveryInfrastructure(unittest.TestCase):
    def test_m3_01_candidate_required_fields(self):
        self.assertTrue(validate_candidate_spec(freeze_spec(draft())))

    def test_m3_02_hash_is_order_invariant(self):
        a=draft(); b=dict(reversed(list(a.items())))
        self.assertEqual(compute_spec_hash(a),compute_spec_hash(b))

    def test_m3_03_semantic_change_changes_hash(self):
        a=draft(); b=copy.deepcopy(a); b["maximum_hold"]["value"]=2
        self.assertNotEqual(compute_spec_hash(a),compute_spec_hash(b))

    def test_m3_04_nonsemantic_metadata_does_not_change_hash(self):
        a=draft(); b=copy.deepcopy(a); b["rationale"]="rewritten rationale"; b["provenance"]={"scope":"rewritten metadata"}
        self.assertEqual(compute_spec_hash(a),compute_spec_hash(b))

    def test_m3_05_verify_detects_tamper(self):
        spec=freeze_spec(draft()); spec["entry"]={"rule":"changed"}
        with self.assertRaises(ValueError): verify_spec_hash(spec)

    def test_m3_06_schema_rejects_bad_id(self):
        spec=freeze_spec(draft()); spec["id"]="D001"
        with self.assertRaises(SchemaError): validate_candidate_spec(spec)

    def test_m3_07_ledger_append_and_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            first=append_entry(path,entry_type="CANDIDATE_FROZEN",candidate_id="V2-C001",spec_hash="a"*64,payload={"test":1},timestamp_utc="2026-01-01T00:00:00Z")
            second=append_entry(path,entry_type="RESULT_RECORDED",candidate_id="V2-C001",spec_hash="a"*64,payload={"test":2},timestamp_utc="2026-01-01T01:00:00Z")
            entries=read_ledger(path)
            self.assertEqual([e["sequence"] for e in entries],[1,2])
            self.assertEqual(second["previous_entry_hash"],first["entry_hash"])

    def test_m3_08_ledger_detects_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            append_entry(path,entry_type="CANDIDATE_FROZEN",candidate_id="V2-C001",spec_hash="b"*64,payload={"test":1},timestamp_utc="2026-01-01T00:00:00Z")
            entry=json.loads(path.read_text()); entry["payload"]["test"]=999; path.write_text(json.dumps(entry)+"\n")
            with self.assertRaises(ValueError): read_ledger(path)

    def test_m3_09_engine_freeze_is_structural_only(self):
        spec=DiscoveryEngine().freeze_candidate(draft(),persist=False)
        self.assertTrue(verify_spec_hash(spec)); self.assertEqual(spec["id"],"V2-C001")


if __name__=="__main__": unittest.main(verbosity=2)

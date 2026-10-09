"""Faults target actual numerical adapter, private store and public commit callsite."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as m
from research_core_v4.numeric_development_v1.public_output_guard_v1 import PublicDisclosureDenied

class IntegratedFaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master,cls.entries,cls.digits,cls.manifest=m.verify_science()

    def test_adapter_real_schema_and_wrong_plaintext_sha(self):
        raw,entry=m.fabricated_shard(1,0,self.master,self.digits)
        engine=n.new(self.master)
        with self.assertRaisesRegex(n.NumericalStop,"PLAINTEXT_DIGEST"):
            n.consume_shard(engine,raw+b"CORRUPT",entry,self.master,self.digits)
        self.assertEqual(engine["next_shard"],0)

    def test_wrong_ciphertext_digest(self):
        raw,entry=m.fabricated_shard(1,0,self.master,self.digits)
        entry["ENCRYPTED_ASSET_SHA256"]="0"*64
        with self.assertRaisesRegex(n.NumericalStop,"CIPHERTEXT_DIGEST"):
            n.consume_shard(n.new(self.master),raw,entry,self.master,self.digits,ciphertext=b"fabricated")

    def test_true_consume_shard_and_duplicate_rejected(self):
        raw,entry=m.fabricated_shard(1,0,self.master,self.digits)
        engine=n.new(self.master)
        n.consume_shard(engine,raw,entry,self.master,self.digits)
        self.assertEqual(engine["next_shard"],1)
        with self.assertRaisesRegex(n.NumericalStop,"SHARD_ORDER"):
            n.consume_shard(engine,raw,entry,self.master,self.digits)

    def test_invalid_ohlc_is_rejected_not_imputed(self):
        raw,entry=m.fabricated_shard(1,0,self.master,self.digits)
        obj=json.loads(raw);obj["items"][0]["rows"][0]["high"]="-1.00000"
        altered=n.enc(obj);entry["PLAINTEXT_CANONICAL_SHA256"]=n.sha(altered)
        with self.assertRaises(n.NumericalStop):
            n.consume_shard(n.new(self.master),altered,entry,self.master,self.digits)

    def test_missing_real_independent_approval_blocks_before_archive_opening(self):
        with patch.object(m,"ARM_PATH","research_core_v4/numeric_development_v1/NONEXISTENT_ARM_V1.json"):
            with self.assertRaisesRegex(n.NumericalStop,"MISSING_INDEPENDENT_APPROVAL"):
                m.real_prearm("f"*40,self.master,self.entries)

    def test_public_confidential_output_rejected_before_blob(self):
        store=m.GitHubStore("a"*40,None,None,None,"synthetic")
        called=[]
        def fakeapi(url,*args,**kwargs):
            called.append(url)
            if url.startswith("git/ref/heads/"):return {"object":{"sha":"a"*40}}
            raise AssertionError("UNEXPECTED_API_CALLED")
        base={"schema":"mxm.master1576.public.status.v1","phase":"FINAL",
              "status":"PASS","source_head":"a"*40}
        with patch.object(m,"api",fakeapi):
            with self.assertRaises(PublicDisclosureDenied):
                store.publish({**base,"exact_price_response":[1.,2.]},
                        "research_core_v4/numeric_development_v1/public_status/INTEGRATED_SYNTHETIC_RESULT_V1.json")
        self.assertNotIn("git/blobs",called)

    def test_publication_api_failure_nonzero_error(self):
        store=m.GitHubStore("a"*40,None,None,None,"synthetic")
        calls=[]
        def fakeapi(url,*args,**kwargs):
            calls.append(url)
            if url.startswith("git/ref/heads/"):return {"object":{"sha":"a"*40}}
            if url=="git/blobs":raise n.NumericalStop("PUBLICATION_FAILURE")
            raise AssertionError("UNEXPECTED_GIT_WRITE")
        base={"schema":"mxm.master1576.public.status.v1","phase":"FINAL",
              "status":"PASS","source_head":"a"*40}
        with patch.object(m,"api",fakeapi),self.assertRaisesRegex(n.NumericalStop,"PUBLICATION_FAILURE"):
            store.publish(base,"research_core_v4/numeric_development_v1/public_status/INTEGRATED_SYNTHETIC_RESULT_V1.json")
        self.assertIn("git/blobs",calls)

    def test_remote_readback_failure(self):
        store=m.GitHubStore("a"*40,None,None,None,"synthetic")
        store.release={"id":123}
        meta={"id":1,"name":"private-checkpoint.mxmenc","size":123,
              "ciphertext_sha256":"a"*64}
        with patch.object(m,"api",return_value=[]):
            with self.assertRaisesRegex(n.NumericalStop,"CIPHERTEXT_REMOTE_METADATA_DRIFT"):
                store.restore(meta)

    def test_duplicate_remote_claim_rejected(self):
        store=m.GitHubStore("a"*40,None,None,None,"synthetic")
        def fakeapi(url,*args,**kwargs):
            if url.startswith("git/ref/heads/"):return {"object":{"sha":"a"*40}}
            raise n.NumericalStop("DUPLICATE_INVOCATION")
        with patch.object(m,"api",fakeapi):
            with self.assertRaisesRegex(n.NumericalStop,"DUPLICATE_INVOCATION"):
                store.claim()

    def test_resource_exhaustion_is_nonzero(self):
        with self.assertRaisesRegex(n.NumericalStop,"WALL_BUDGET"):
            m.budget(maxwall=-1)

    def test_missing_censored_labels_preserved(self):
        engine=n.new(self.master)
        s=engine["states"][0];n._advance(engine,s,n.END+n.LAGS[-1]+3600)
        self.assertEqual(s["next_clock"],672)
        self.assertGreater(s["lag"]["900"]["reasons"]["DOMAIN_CENSOR"],0)

if __name__=="__main__":
    unittest.main(verbosity=2)

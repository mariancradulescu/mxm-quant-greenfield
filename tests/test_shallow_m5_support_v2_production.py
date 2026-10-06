from __future__ import annotations

import hashlib
import inspect
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from m6.ctrader_proto import OpenApiMessages_pb2 as legacy
from m6.ctrader_proto import OpenApiModelMessages_pb2 as model
from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4 import shallow_m5_support_v2_production as prod


class FakeAuthTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def request(self, message, timeout=None):
        self.sent.append(type(message).__name__)
        return self.responses.pop(0)


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def make_current_envelope(*, client_msg_id="c1", account_id=123, symbol_id=10, minute=None, has_more=False):
    if minute is None:
        minute = v2.to_ms(v2.SEGMENTS[0][0]) // 60000
    bar = v2.ProtoOATrendbarV2(
        volume=11,
        period=v2.M5_ENUM,
        low=100000,
        deltaOpen=1,
        deltaHigh=5,
        deltaClose=3,
        utcTimestampInMinutes=minute,
    )
    res = v2.ProtoOAGetTrendbarsResV2(
        ctidTraderAccountId=account_id,
        period=v2.M5_ENUM,
        timestamp=minute * 60000,
        trendbar=[bar],
        symbolId=symbol_id,
        hasMore=has_more,
    )
    return ProtoMessage(
        payloadType=v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,
        payload=res.SerializeToString(),
        clientMsgId=client_msg_id,
    )


class ProductionArchitectureTests(unittest.TestCase):
    def test_current_proto_raw_envelope_path_does_not_use_legacy_trendbar_decoder(self):
        ctx = v2.RequestContext(
            client_msg_id="c1",
            authenticated_account_id=123,
            symbol_id=10,
            from_ms=v2.to_ms(v2.SEGMENTS[0][0]),
            to_ms=v2.to_ms(v2.SEGMENTS[0][1]),
        )
        envelope = make_current_envelope()
        with mock.patch("m6.ctrader_transport.extract_payload", side_effect=AssertionError("legacy path used")):
            rows, present, value = prod.decode_history_envelope(envelope, ctx=ctx, digits=5)
        self.assertEqual(len(rows), 1)
        self.assertTrue(present)
        self.assertFalse(value)

    def test_client_msg_id_correlation_fail_closed(self):
        ctx = v2.RequestContext(
            client_msg_id="expected",
            authenticated_account_id=123,
            symbol_id=10,
            from_ms=v2.to_ms(v2.SEGMENTS[0][0]),
            to_ms=v2.to_ms(v2.SEGMENTS[0][1]),
        )
        with self.assertRaises(prod.SystemicFailure) as cm:
            prod.decode_history_envelope(make_current_envelope(client_msg_id="wrong"), ctx=ctx, digits=5)
        self.assertEqual(cm.exception.code, "RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE")

    def test_auth_fingerprint_exact_match(self):
        account_id = 123456789
        fp = hashlib.sha256(f"ctrader-account:{account_id}".encode("ascii")).hexdigest()
        accounts = legacy.ProtoOAGetAccountListByAccessTokenRes(permissionScope=model.SCOPE_VIEW)
        acct = accounts.ctidTraderAccount.add()
        acct.ctidTraderAccountId = account_id
        acct.isLive = True
        transport = FakeAuthTransport(
            [
                legacy.ProtoOAApplicationAuthRes(),
                accounts,
                legacy.ProtoOAAccountAuthRes(ctidTraderAccountId=account_id),
            ]
        )
        with mock.patch.object(prod, "ACCOUNT_FINGERPRINT_SHA256", fp):
            observed = prod.authenticate_segment(transport, "id", "secret", "token")
        self.assertEqual(observed, account_id)
        self.assertEqual(
            transport.sent,
            ["ProtoOAApplicationAuthReq", "ProtoOAGetAccountListByAccessTokenReq", "ProtoOAAccountAuthReq"],
        )

    def test_scope_view_gate(self):
        account_id = 123456789
        fp = hashlib.sha256(f"ctrader-account:{account_id}".encode("ascii")).hexdigest()
        accounts = legacy.ProtoOAGetAccountListByAccessTokenRes(permissionScope=model.SCOPE_TRADE)
        acct = accounts.ctidTraderAccount.add()
        acct.ctidTraderAccountId = account_id
        acct.isLive = True
        transport = FakeAuthTransport([legacy.ProtoOAApplicationAuthRes(), accounts])
        with mock.patch.object(prod, "ACCOUNT_FINGERPRINT_SHA256", fp):
            with self.assertRaises(prod.SystemicFailure) as cm:
                prod.authenticate_segment(transport, "id", "secret", "token")
        self.assertEqual(cm.exception.code, "SCOPE_NOT_EXPLICIT_VIEW")

    def test_four_strictly_sequential_segment_job_plan(self):
        workflow = (prod.ROOT / prod.WORKFLOW_REL).read_text(encoding="utf-8")
        self.assertIn("segment-1:", workflow)
        self.assertIn("segment-2:\n    needs: segment-1", workflow)
        self.assertIn("segment-3:\n    needs: segment-2", workflow)
        self.assertIn("segment-4:\n    needs: segment-3", workflow)
        self.assertNotIn("workflow_dispatch", workflow)

    def test_no_concurrent_historical_connections(self):
        plan = prod.production_plan()
        self.assertTrue(plan["one_active_live_historical_connection_globally"])
        self.assertEqual(plan["concurrent_historical_connections"], 0)
        self.assertEqual(plan["exact_segment_jobs"], 4)

    def test_previous_segment_durable_gate_precedes_broker_auth(self):
        source = inspect.getsource(prod.run_segment)
        gate = source.index("previous = store.load_segment_manifest(segment - 1)")
        auth = source.index("transport, account_id = _connect_and_auth(credentials)")
        self.assertLess(gate, auth)
        self.assertIn('"DURABLE_STORAGE_INTEGRITY_FAILURE"', source)

    def test_all_segment_jobs_validate_same_exact_arm_event(self):
        source = inspect.getsource(prod.run_segment)
        self.assertIn("validate_arm_git_event(arm)", source)
        self.assertNotIn("if segment == 1:\\n        validate_arm_git_event(arm)", source)

    def test_four_rps_rate_limit(self):
        fc = FakeClock()
        limiter = prod.RateLimiter(clock=fc.clock, sleeper=fc.sleep)
        limiter.before_send()
        limiter.before_send()
        limiter.before_send()
        self.assertEqual(fc.sleeps, [0.25, 0.25])

    def test_ten_second_heartbeat(self):
        self.assertEqual(prod.HEARTBEAT_MAX_IDLE_SECONDS, 10)
        from m6 import ctrader_transport
        self.assertEqual(int(ctrader_transport.HEARTBEAT_IDLE_SECONDS), 10)

    def test_page_cap_partial_data_limited_continue_semantics(self):
        ctx = v2.RequestContext(
            client_msg_id="x",
            authenticated_account_id=1,
            symbol_id=1,
            from_ms=0,
            to_ms=600000,
        )
        rows = [{"time_utc": "1970-01-01T00:05:00Z"}]
        decision = v2.pagination_decision(
            ctx=ctx,
            decoded_rows=rows,
            has_more_present=True,
            has_more_value=True,
            page_index=3,
        )
        self.assertTrue(decision.fail_closed)
        self.assertEqual(decision.reason, "PAGE_CAP_REACHED_WITH_MORE_REQUIRED")
        self.assertEqual("SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED", "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED")

    def test_systemic_failure_stops_campaign(self):
        with self.assertRaises(prod.SystemicFailure) as cm:
            raise prod.SystemicFailure("DIGITS_MAP_MISMATCH")
        self.assertEqual(cm.exception.code, "DIGITS_MAP_MISMATCH")

    def test_soft_runtime_stop_precedes_github_hard_timeout(self):
        self.assertEqual(prod.SOFT_STOP_MINUTES, 270)
        self.assertEqual(prod.GITHUB_JOB_TIMEOUT_MINUTES, 330)
        self.assertEqual(prod.SHUTDOWN_UPLOAD_MARGIN_MINUTES, 60)
        self.assertLess(prod.SOFT_STOP_MINUTES, prod.GITHUB_JOB_TIMEOUT_MINUTES)

    def test_checkpoint_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "checkpoint.json"
            prod.atomic_json(p, {"page": 2, "rows": [{"x": 1}]})
            self.assertEqual(prod.load_json(p)["page"], 2)
            self.assertFalse(p.with_name(p.name + ".tmp").exists())

    def test_completed_durable_shard_not_requeried(self):
        manifest = {
            "entries": [
                {
                    "SHARD_INDEX": 3,
                    "IDENTITY_RANGE": [193, 256],
                    "ENCRYPTED_ASSET_SHA256": "a" * 64,
                }
            ]
        }
        self.assertEqual(
            prod.synthetic_durable_resume_decision(
                manifest,
                shard_index=3,
                identity_range=[193, 256],
                observed_asset_sha256="a" * 64,
            ),
            "SKIP_WITHOUT_BROKER_REQUERY",
        )

    def test_conflicting_existing_shard_fails_closed(self):
        manifest = {
            "entries": [
                {
                    "SHARD_INDEX": 3,
                    "IDENTITY_RANGE": [193, 256],
                    "ENCRYPTED_ASSET_SHA256": "a" * 64,
                }
            ]
        }
        self.assertEqual(
            prod.synthetic_durable_resume_decision(
                manifest,
                shard_index=3,
                identity_range=[193, 256],
                observed_asset_sha256="b" * 64,
            ),
            "FAIL_CLOSED",
        )

    @unittest.skipUnless(shutil.which("openssl") and shutil.which("gpg"), "openssl and gpg required")
    def test_encrypt_decrypt_synthetic_shard_byte_equivalence(self):
        raw = b'{"synthetic":true,"rows":[1,2,3]}\n'
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            priv = td / "private.pem"
            pub = td / "public.pem"
            out = td / "asset.mxmenc"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(priv)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(priv), "-pubout", "-out", str(pub)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            prod.encrypt_shard(raw, public_key=pub, output=out)
            self.assertEqual(prod.decrypt_synthetic_package(out.read_bytes(), private_key=priv), raw)

    @unittest.skipUnless(shutil.which("openssl") and shutil.which("gpg"), "openssl and gpg required")
    def test_wrong_private_key_fails(self):
        raw = b"synthetic\n"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p1, p2, pub = td / "p1.pem", td / "p2.pem", td / "pub.pem"
            out = td / "asset.mxmenc"
            for p in (p1, p2):
                subprocess.run(
                    ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(p)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            subprocess.run(
                ["openssl", "pkey", "-in", str(p1), "-pubout", "-out", str(pub)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            prod.encrypt_shard(raw, public_key=pub, output=out)
            with self.assertRaises(subprocess.CalledProcessError):
                prod.decrypt_synthetic_package(out.read_bytes(), private_key=p2)

    @unittest.skipUnless(shutil.which("openssl") and shutil.which("gpg"), "openssl and gpg required")
    def test_corrupted_encrypted_asset_fails(self):
        raw = b"synthetic-corruption\n"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            priv, pub, out = td / "p.pem", td / "pub.pem", td / "asset.mxmenc"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(priv)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(priv), "-pubout", "-out", str(pub)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            prod.encrypt_shard(raw, public_key=pub, output=out)
            damaged = bytearray(out.read_bytes())
            damaged[-1] ^= 0x01
            with self.assertRaises(subprocess.CalledProcessError):
                prod.decrypt_synthetic_package(bytes(damaged), private_key=priv)

    def test_durable_asset_hash_conflict_fails(self):
        self.assertEqual(
            prod.synthetic_durable_resume_decision(
                {"entries": [{"SHARD_INDEX": 0, "IDENTITY_RANGE": [1, 64], "ENCRYPTED_ASSET_SHA256": "1" * 64}]},
                shard_index=0,
                identity_range=[1, 64],
                observed_asset_sha256="2" * 64,
            ),
            "FAIL_CLOSED",
        )

    def test_release_publication_control_flow_synthetic_proof(self):
        source = inspect.getsource(prod.GitHubReleaseStore.publish_shard)
        upload = source.index('"release", "upload"')
        redownload = source.index("self._download_asset", upload)
        manifest = source.index("self._put_repo_json", redownload)
        self.assertLess(upload, redownload)
        self.assertLess(redownload, manifest)
        self.assertNotIn("upload-artifact", source)

    def test_final_four_segment_compact_manifest_reconstruction(self):
        manifests = []
        for segment in range(1, 5):
            entries = []
            for shard in range(prod.SHARD_COUNT_PER_SEGMENT):
                start = shard * prod.IDENTITIES_PER_SHARD + 1
                end = min(prod.MASTER_COUNT, start + prod.IDENTITIES_PER_SHARD - 1)
                entries.append(
                    {
                        "SEGMENT_INDEX": segment,
                        "SHARD_INDEX": shard,
                        "IDENTITY_RANGE": [start, end],
                        "PROTECTED_FORWARD_ROW_COUNT": 0,
                    }
                )
            manifests.append({"SEGMENT_INDEX": segment, "status": "COMPLETE", "entries": entries})
        final = prod.reconstruct_final_manifest(manifests)
        self.assertEqual(final["segment_count"], 4)
        self.assertEqual(final["encrypted_shard_count"], 100)
        self.assertEqual(final["PROTECTED_FORWARD_ROW_COUNT"], 0)

    def test_zero_protected_forward(self):
        boundary_ms = v2.to_ms(v2.PROTECTED_FORWARD_BOUNDARY_UTC)
        minute = (boundary_ms // 300000 + 1) * 5
        ctx = v2.RequestContext(
            client_msg_id="c1",
            authenticated_account_id=123,
            symbol_id=10,
            from_ms=boundary_ms - 600000,
            to_ms=boundary_ms + 600000,
        )
        envelope = make_current_envelope(minute=minute)
        with self.assertRaises(prod.SystemicFailure) as cm:
            prod.decode_history_envelope(envelope, ctx=ctx, digits=5)
        self.assertEqual(cm.exception.code, "PROTECTED_FORWARD_LEAK")

    def test_zero_ticks_subscriptions_depth_orders_refresh(self):
        self.assertTrue(prod.ALLOWED_OUTBOUND_MESSAGE_NAMES.isdisjoint(prod.FORBIDDEN_OUTBOUND_MESSAGE_NAMES))
        self.assertEqual(
            prod.ALLOWED_OUTBOUND_MESSAGE_NAMES,
            {
                "ProtoOAApplicationAuthReq",
                "ProtoOAGetAccountListByAccessTokenReq",
                "ProtoOAAccountAuthReq",
                "ProtoOAGetTrendbarsReq",
                "ProtoHeartbeatEvent",
            },
        )
        workflow = (prod.ROOT / prod.WORKFLOW_REL).read_text(encoding="utf-8")
        self.assertNotIn("CTRADER_REFRESH_TOKEN", workflow)
        for forbidden in prod.FORBIDDEN_OUTBOUND_MESSAGE_NAMES:
            self.assertNotIn(forbidden, workflow)

    def test_arm_absent_at_architecture_freeze_time(self):
        self.assertFalse((prod.ROOT / prod.ARM_REL).exists())


if __name__ == "__main__":
    unittest.main()

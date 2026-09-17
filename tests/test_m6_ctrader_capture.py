import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from m6.ctrader_capture import (
    EXPECTED_PLAN_SHA, PROTECTED_FORWARD_START,
    CaptureContractError, MappingError, OAuthError, RateLimiter, ResponseError,
    assert_no_secret_values, build_authorization_url, deterministic_zip,
    drop_secret_fields, gap_diagnostics, historical_windows, load_resume_state,
    merge_chunk_rows, new_resume_state, next_pagination_to_ms,
    normalize_trendbars, parse_oauth_redirect, raw_csv_bytes,
    record_completed_chunk, require_read_only_request, resolve_symbol_mapping,
    scan_bundle_for_secrets, select_live_pepperstone_account, sha256_file,
    validate_capture_plan, verified_chunk_path,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"
STATUS_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_PREPARATION_STATUS_V1.json"
CHECKPOINT_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V1.json"
LEDGER_PATH = ROOT / "discovery/ledger.jsonl"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class CTraderCaptureCoreTests(unittest.TestCase):
    def test_01_oauth_accounts_only_and_redirect_parse(self):
        url = build_authorization_url("client", "http://127.0.0.1:8765/callback")
        self.assertIn("scope=accounts", url)
        self.assertNotIn("scope=trading", url)
        with self.assertRaises(OAuthError):
            build_authorization_url("client", "http://127.0.0.1:8765/callback", scope="trading")
        self.assertEqual(
            parse_oauth_redirect("http://127.0.0.1:8765/callback?code=abc", "http://127.0.0.1:8765/callback"),
            "abc",
        )
        with self.assertRaises(OAuthError):
            parse_oauth_redirect("http://127.0.0.1:9999/callback?code=x", "http://127.0.0.1:8765/callback")
        with self.assertRaises(OAuthError):
            parse_oauth_redirect("http://127.0.0.1:8765/callback?code=a&code=b", "http://127.0.0.1:8765/callback")

    def test_02_token_credential_redaction(self):
        clean = drop_secret_fields({
            "client_id": "ok", "client_secret": "SECRET", "accessToken": "TOKEN",
            "nested": {"refresh_token": "REFRESH", "safe": 1},
        })
        self.assertEqual(clean, {"client_id": "ok", "nested": {"safe": 1}})
        with self.assertRaises(CaptureContractError):
            assert_no_secret_values(b"x TOKEN y", ["TOKEN"])

    def test_03_no_order_no_account_mutation_contract(self):
        for allowed in ("ProtoOAGetTrendbarsReq", "ProtoOAExpectedMarginReq", "ProtoOASymbolByIdReq"):
            self.assertEqual(require_read_only_request(allowed), allowed)
        for forbidden in (
            "ProtoOANewOrderReq", "ProtoOACancelOrderReq", "ProtoOAClosePositionReq",
            "ProtoOAAccountLogoutReq", "ProtoOASubscribeSpotsReq", "ProtoOAUnknownConvenienceReq",
        ):
            with self.assertRaises(CaptureContractError):
                require_read_only_request(forbidden)

    def test_04_historical_chunking_and_protected_boundary(self):
        windows = historical_windows("2026-01-01T00:00:00Z", "2026-01-20T23:59:59Z", "M15")
        self.assertGreater(len(windows), 1)
        self.assertLess(windows[-1][1], int(datetime(2026, 9, 17, 12, 2, 58, tzinfo=timezone.utc).timestamp() * 1000))
        with self.assertRaises(CaptureContractError):
            historical_windows("2026-09-17T00:00:00Z", PROTECTED_FORWARD_START, "M15")

    def test_05_server_pagination_is_backward_and_malformed_fails(self):
        self.assertEqual(
            next_pagination_to_ms([{"utcTimestampInMinutes": 100}, {"utcTimestampInMinutes": 90}], 0),
            90 * 60000 - 1,
        )
        with self.assertRaises(ResponseError):
            next_pagination_to_ms([{"utcTimestampInMinutes": "bad"}], 0)

    def test_06_historical_rate_limiter_below_five_per_second(self):
        clock = [0.0]
        sleeps = []
        def now(): return clock[0]
        def sleep(delay):
            sleeps.append(delay)
            clock[0] += delay
        limiter = RateLimiter(clock=now, sleeper=sleep)
        for _ in range(5): limiter.wait()
        self.assertEqual(len(sleeps), 4)
        self.assertTrue(all(d >= 0.209 for d in sleeps))
        self.assertGreaterEqual(clock[0], 0.84)

    def test_07_completed_bar_normalization_and_protected_exclusion(self):
        minute = int(datetime(2026, 9, 16, 20, tzinfo=timezone.utc).timestamp() // 60)
        rows = normalize_trendbars(
            [{"utcTimestampInMinutes": minute, "low": 100000, "deltaOpen": 10,
              "deltaHigh": 50, "deltaClose": 20, "volume": 7}],
            resolution="H4", digits=5,
            requested_start_utc="2026-09-16T00:00:00Z", requested_end_utc="2026-09-16T23:59:59Z",
        )
        self.assertEqual(rows[0]["open"], "1.00010")
        cross = int(datetime(2026, 9, 17, 9, tzinfo=timezone.utc).timestamp() // 60)
        self.assertEqual(normalize_trendbars(
            [{"utcTimestampInMinutes": cross, "low": 100000, "deltaOpen": 0,
              "deltaHigh": 1, "deltaClose": 1, "volume": 1}],
            resolution="H4", digits=5,
            requested_start_utc="2026-09-17T00:00:00Z", requested_end_utc="2026-09-17T11:00:00Z",
        ), [])

    def test_08_malformed_trendbar_fails_closed(self):
        with self.assertRaises(ResponseError):
            normalize_trendbars(
                [{"utcTimestampInMinutes": "bad", "low": 1}], resolution="M15", digits=5,
                requested_start_utc="2026-01-01T00:00:00Z", requested_end_utc="2026-01-02T00:00:00Z",
            )

    def test_09_mapping_ambiguity_and_disabled_fail_closed(self):
        symbols = [
            {"symbolId": 1, "symbolName": "US500", "enabled": True},
            {"symbolId": 2, "symbolName": "NAS100", "enabled": True},
        ]
        self.assertEqual(resolve_symbol_mapping("US500", symbols)["symbolId"], 1)
        with self.assertRaises(MappingError):
            resolve_symbol_mapping("US500", symbols + [{"symbolId": 3, "symbolName": "US-500", "enabled": True}])
        with self.assertRaises(MappingError):
            resolve_symbol_mapping("XAUUSD", [{"symbolId": 4, "symbolName": "XAUUSD", "enabled": False}])

    def test_10_live_pepperstone_account_selection_fail_closed(self):
        accounts = [
            {"ctidTraderAccountId": 1, "isLive": True, "brokerTitleShort": "Pepperstone EU"},
            {"ctidTraderAccountId": 2, "isLive": True, "brokerTitleShort": "Pepperstone EU"},
        ]
        with self.assertRaises(MappingError):
            select_live_pepperstone_account(accounts)
        self.assertEqual(select_live_pepperstone_account(accounts, account_override=2)["ctidTraderAccountId"], 2)

    def test_11_resume_reuses_only_hash_verified_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "chunk.csv"
            p.write_bytes(raw_csv_bytes([{
                "time_utc": "2026-01-01T00:00:00Z", "open": "1", "high": "1",
                "low": "1", "close": "1", "tick_volume": "1",
            }]))
            state = new_resume_state(EXPECTED_PLAN_SHA)
            record_completed_chunk(state, chunk_key="k", path=p, raw_capture_id="RAW",
                                   request_from_ms=1, request_to_ms=2, page=0, row_count=1)
            self.assertEqual(verified_chunk_path(state, "k"), p)
            p.write_text("corrupt", encoding="utf-8")
            self.assertIsNone(verified_chunk_path(state, "k"))

    def test_12_resume_plan_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "resume.json"
            path.write_text(json.dumps({"plan_sha256": "wrong", "chunks": {}}), encoding="utf-8")
            from m6.ctrader_capture import ResumeError
            with self.assertRaises(ResumeError): load_resume_state(path, EXPECTED_PLAN_SHA)

    def test_13_merge_dedup_and_gap_diagnostics_never_fill(self):
        r1 = {"time_utc": "2026-01-01T00:00:00Z", "open": "1", "high": "1", "low": "1", "close": "1", "tick_volume": "1"}
        r2 = {"time_utc": "2026-01-01T00:30:00Z", "open": "2", "high": "2", "low": "2", "close": "2", "tick_volume": "1"}
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "a.csv", Path(td) / "b.csv"
            a.write_bytes(raw_csv_bytes([r1, r2])); b.write_bytes(raw_csv_bytes([r1]))
            merged = merge_chunk_rows([a, b])
            self.assertEqual(len(merged), 2)
            self.assertEqual(gap_diagnostics(merged, "M15")["gap_count"], 1)

    def test_14_exact_11_raw_12_bindings_and_shared_us500(self):
        plan = load(PLAN_PATH)
        result = validate_capture_plan(plan)
        self.assertEqual(result["unique_raw_capture_count"], 11)
        self.assertEqual(result["candidate_binding_count"], 12)
        bs = {b["candidate_id"]: b for b in plan["candidate_dataset_bindings"] if b["canonical_instrument"] == "US500"}
        self.assertEqual(bs["V2-C006"]["raw_capture_id"], "PW02-RAW-US500-M15-a7856539f970beef")
        self.assertEqual(bs["V2-C006"]["raw_capture_id"], bs["V2-C012"]["raw_capture_id"])
        self.assertNotEqual(bs["V2-C006"]["semantic_requirements_sha256"], bs["V2-C012"]["semantic_requirements_sha256"])

    def test_15_secret_scan_and_deterministic_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "bundle"; root.mkdir()
            (root / "b.txt").write_text("B\n", encoding="utf-8")
            (root / "a.txt").write_text("A\n", encoding="utf-8")
            scan_bundle_for_secrets(root, ["SECRET"])
            z1, z2 = Path(td) / "one.zip", Path(td) / "two.zip"
            h1, h2 = deterministic_zip(root, z1), deterministic_zip(root, z2)
            self.assertEqual(h1, h2); self.assertEqual(z1.read_bytes(), z2.read_bytes())
            self.assertEqual(h1, sha256_file(z1))

    def test_16_bundle_secret_field_names_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.json").write_text('{"accessToken":"x"}', encoding="utf-8")
            with self.assertRaises(CaptureContractError): scan_bundle_for_secrets(root)

    def test_17_runtime_source_never_imports_order_messages(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        for forbidden in ("ProtoOANewOrderReq", "ProtoOACancelOrderReq", "ProtoOAClosePositionReq", 'scope="trading"'):
            self.assertNotIn(forbidden, source)

    def test_18_local_secret_and_work_paths_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for item in ("m6_capture_local.json", ".m6_secrets/", ".m6_capture_work/", "capture_output/"):
            self.assertIn(item, ignore)

    def test_19_zero_economic_state_protected_closed_m6_pending(self):
        p = load(STATUS_PATH)["pre_economic_integrity"]
        self.assertEqual(p["result_recorded_count"], 0)
        self.assertEqual(p["v2_attempts_used"], 0)
        self.assertEqual(p["v2_evaluated_identities"], 0)
        self.assertEqual(p["economic_outcomes_opened"], 0)
        self.assertFalse(p["protected_evidence_opened"])
        self.assertEqual(p["protected_forward_start"], PROTECTED_FORWARD_START)
        self.assertEqual(p["m6_status"], "PENDING")
        self.assertNotIn('"entry_type":"RESULT_RECORDED"', LEDGER_PATH.read_text(encoding="utf-8"))

    def test_20_capture_checkpoint_tooling_only_accounts_scope(self):
        cp = load(CHECKPOINT_PATH)
        self.assertEqual(cp["status"], "TOOLING_READY_EXTERNAL_PYDROID_EXECUTION_REQUIRED")
        self.assertEqual(cp["oauth"]["scope"], "accounts")
        self.assertFalse(cp["oauth"]["trading_scope_requested"])
        actual = cp["actual_execution"]
        self.assertFalse(actual["broker_capture_run"])
        self.assertFalse(actual["m6_economics_run"])
        self.assertEqual(actual["economic_outcomes_opened"], 0)
        self.assertEqual(actual["v2_attempts_used"], 0)
        self.assertFalse(actual["protected_evidence_opened"])
        self.assertFalse(actual["live_orders"])
        self.assertEqual(actual["m6_status"], "PENDING")


if __name__ == "__main__":
    unittest.main(verbosity=2)

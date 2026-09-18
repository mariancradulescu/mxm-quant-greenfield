import copy
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from m6.ctrader_capture import (
    EXPECTED_PLAN_SHA,
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
    HISTORICAL_TARGET_RPS,
    PROTECTED_FORWARD_START,
    PYDROID_PACKAGE_FILES,
    TRANSFERABLE_REQUIRED_FILES,
    CaptureContractError,
    MappingError,
    OAuthError,
    RateLimiter,
    ResponseError,
    assert_no_secret_values,
    build_authorization_url,
    build_pydroid_package,
    canonical_plan_sha256,
    deterministic_zip,
    drop_secret_fields,
    format_capture_progress,
    gap_diagnostics,
    historical_windows,
    load_resume_state,
    merge_chunk_rows,
    new_resume_state,
    next_pagination_to_ms,
    normalize_trendbars,
    parse_oauth_redirect,
    raw_csv_bytes,
    record_completed_chunk,
    require_read_only_request,
    resolve_symbol_mapping,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
    sha256_file,
    validate_capture_plan,
    validate_transferable_bundle,
    validate_transferable_zip,
    verified_chunk_path,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"
STATUS_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_PREPARATION_STATUS_V1.json"
CHECKPOINT_V1_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V1.json"
CHECKPOINT_V2_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V2.json"
LEDGER_PATH = ROOT / "discovery/ledger.jsonl"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def bar(open_dt, *, low=100000, delta_open=10, delta_high=50, delta_close=20, volume=7):
    return {
        "utcTimestampInMinutes": int(open_dt.timestamp() // 60),
        "low": low,
        "deltaOpen": delta_open,
        "deltaHigh": delta_high,
        "deltaClose": delta_close,
        "volume": volume,
    }


class CTraderCaptureCoreTests(unittest.TestCase):
    def test_01_oauth_accounts_only_and_redirect_parse(self):
        url = build_authorization_url("client", "http://127.0.0.1:8765/callback")
        self.assertIn("scope=accounts", url)
        self.assertNotIn("scope=trading", url)
        with self.assertRaises(OAuthError):
            build_authorization_url("client", "http://127.0.0.1:8765/callback", scope="trading")
        self.assertEqual(
            parse_oauth_redirect(
                "http://127.0.0.1:8765/callback?code=abc",
                "http://127.0.0.1:8765/callback",
            ),
            "abc",
        )
        with self.assertRaises(OAuthError):
            parse_oauth_redirect(
                "http://127.0.0.1:9999/callback?code=x",
                "http://127.0.0.1:8765/callback",
            )
        with self.assertRaises(OAuthError):
            parse_oauth_redirect(
                "http://127.0.0.1:8765/callback?code=a&code=b",
                "http://127.0.0.1:8765/callback",
            )

    def test_02_token_credential_redaction(self):
        clean = drop_secret_fields({
            "client_id": "ok",
            "client_secret": "SECRET",
            "accessToken": "TOKEN",
            "nested": {"refresh_token": "REFRESH", "safe": 1},
        })
        self.assertEqual(clean, {"client_id": "ok", "nested": {"safe": 1}})
        with self.assertRaises(CaptureContractError):
            assert_no_secret_values(b"x TOKEN y", ["TOKEN"])

    def test_03_no_order_no_account_mutation_contract(self):
        for allowed in ("ProtoOAGetTrendbarsReq", "ProtoOAExpectedMarginReq", "ProtoOASymbolByIdReq"):
            self.assertEqual(require_read_only_request(allowed), allowed)
        for forbidden in FORBIDDEN_MUTATION_PROTO_REQUESTS | {"ProtoOAUnknownConvenienceReq"}:
            with self.assertRaises(CaptureContractError):
                require_read_only_request(forbidden)

    def test_04_historical_chunking_and_protected_boundary(self):
        windows = historical_windows("2026-01-01T00:00:00Z", "2026-01-20T23:59:59Z", "M15")
        self.assertGreater(len(windows), 1)
        protected_ms = int(datetime(2026, 9, 17, 12, 2, 58, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertLess(windows[-1][1], protected_ms)
        with self.assertRaises(CaptureContractError):
            historical_windows("2026-09-17T00:00:00Z", PROTECTED_FORWARD_START, "M15")

    def test_05_server_pagination_is_backward_and_malformed_fails(self):
        self.assertEqual(
            next_pagination_to_ms(
                [{"utcTimestampInMinutes": 100}, {"utcTimestampInMinutes": 90}], 0
            ),
            90 * 60000 - 1,
        )
        with self.assertRaises(ResponseError):
            next_pagination_to_ms([{"utcTimestampInMinutes": "bad"}], 0)

    def test_06_historical_rate_limiter_near_but_below_five_per_second(self):
        clock = [0.0]
        sleeps = []
        def now():
            return clock[0]
        def sleep(delay):
            sleeps.append(delay)
            clock[0] += delay
        limiter = RateLimiter(clock=now, sleeper=sleep)
        for _ in range(5):
            limiter.wait()
        self.assertEqual(len(sleeps), 4)
        self.assertTrue(all(delay >= 0.209 for delay in sleeps))
        self.assertGreaterEqual(clock[0], 0.84)
        self.assertGreater(HISTORICAL_TARGET_RPS, 4.7)
        self.assertLess(HISTORICAL_TARGET_RPS, 4.8)
        self.assertLess(HISTORICAL_TARGET_RPS, 5.0)

    def test_07_completed_bar_normalization_normal_case(self):
        opened = datetime(2026, 9, 16, 16, 0, tzinfo=timezone.utc)
        rows = normalize_trendbars(
            [bar(opened)],
            resolution="H4",
            digits=5,
            requested_start_utc="2026-09-16T00:00:00Z",
            requested_end_utc="2026-09-16T23:59:59Z",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], "1.00010")

    def test_08_malformed_trendbar_fails_closed(self):
        with self.assertRaises(ResponseError):
            normalize_trendbars(
                [{"utcTimestampInMinutes": "bad", "low": 1}],
                resolution="M15",
                digits=5,
                requested_start_utc="2026-01-01T00:00:00Z",
                requested_end_utc="2026-01-02T00:00:00Z",
            )

    def test_09_mapping_ambiguity_and_disabled_fail_closed(self):
        symbols = [
            {"symbolId": 1, "symbolName": "US500", "enabled": True},
            {"symbolId": 2, "symbolName": "NAS100", "enabled": True},
        ]
        self.assertEqual(resolve_symbol_mapping("US500", symbols)["symbolId"], 1)
        with self.assertRaises(MappingError):
            resolve_symbol_mapping(
                "US500",
                symbols + [{"symbolId": 3, "symbolName": "US-500", "enabled": True}],
            )
        with self.assertRaises(MappingError):
            resolve_symbol_mapping(
                "XAUUSD", [{"symbolId": 4, "symbolName": "XAUUSD", "enabled": False}]
            )

    def test_10_live_pepperstone_account_selection_fail_closed(self):
        accounts = [
            {"ctidTraderAccountId": 1, "isLive": True, "brokerTitleShort": "Pepperstone EU"},
            {"ctidTraderAccountId": 2, "isLive": True, "brokerTitleShort": "Pepperstone EU"},
        ]
        with self.assertRaises(MappingError):
            select_live_pepperstone_account(accounts)
        self.assertEqual(
            select_live_pepperstone_account(accounts, account_override=2)["ctidTraderAccountId"], 2
        )

    def test_11_resume_reuses_only_hash_verified_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "chunk.csv"
            path.write_bytes(raw_csv_bytes([{
                "time_utc": "2026-01-01T00:00:00Z",
                "open": "1", "high": "1", "low": "1", "close": "1", "tick_volume": "1",
            }]))
            state = new_resume_state(EXPECTED_PLAN_SHA)
            record_completed_chunk(
                state, chunk_key="k", path=path, raw_capture_id="RAW",
                request_from_ms=1, request_to_ms=2, page=0, row_count=1,
            )
            self.assertEqual(verified_chunk_path(state, "k"), path)
            path.write_text("corrupt", encoding="utf-8")
            self.assertIsNone(verified_chunk_path(state, "k"))

    def test_12_resume_plan_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "resume.json"
            path.write_text(json.dumps({"plan_sha256": "wrong", "chunks": {}}), encoding="utf-8")
            from m6.ctrader_capture import ResumeError
            with self.assertRaises(ResumeError):
                load_resume_state(path, EXPECTED_PLAN_SHA)

    def test_13_merge_dedup_and_gap_diagnostics_never_fill(self):
        r1 = {"time_utc": "2026-01-01T00:00:00Z", "open": "1", "high": "1", "low": "1", "close": "1", "tick_volume": "1"}
        r2 = {"time_utc": "2026-01-01T00:30:00Z", "open": "2", "high": "2", "low": "2", "close": "2", "tick_volume": "1"}
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "a.csv", Path(td) / "b.csv"
            a.write_bytes(raw_csv_bytes([r1, r2]))
            b.write_bytes(raw_csv_bytes([r1]))
            merged = merge_chunk_rows([a, b])
            self.assertEqual(len(merged), 2)
            self.assertEqual(gap_diagnostics(merged, "M15")["gap_count"], 1)

    def test_14_exact_11_raw_12_bindings_and_shared_us500(self):
        plan = load(PLAN_PATH)
        result = validate_capture_plan(plan)
        self.assertEqual(result["unique_raw_capture_count"], 11)
        self.assertEqual(result["candidate_binding_count"], 12)
        bindings = {
            b["candidate_id"]: b
            for b in plan["candidate_dataset_bindings"]
            if b["canonical_instrument"] == "US500"
        }
        self.assertEqual(bindings["V2-C006"]["raw_capture_id"], "PW02-RAW-US500-M15-a7856539f970beef")
        self.assertEqual(bindings["V2-C006"]["raw_capture_id"], bindings["V2-C012"]["raw_capture_id"])
        self.assertNotEqual(
            bindings["V2-C006"]["semantic_requirements_sha256"],
            bindings["V2-C012"]["semantic_requirements_sha256"],
        )

    def test_15_secret_scan_and_deterministic_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "bundle"
            root.mkdir()
            (root / "b.txt").write_text("B\n", encoding="utf-8")
            (root / "a.txt").write_text("A\n", encoding="utf-8")
            scan_bundle_for_secrets(root, ["SECRET"])
            z1, z2 = Path(td) / "one.zip", Path(td) / "two.zip"
            h1, h2 = deterministic_zip(root, z1), deterministic_zip(root, z2)
            self.assertEqual(h1, h2)
            self.assertEqual(z1.read_bytes(), z2.read_bytes())
            self.assertEqual(h1, sha256_file(z1))

    def test_16_bundle_secret_field_names_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.json").write_text('{"accessToken":"x"}', encoding="utf-8")
            with self.assertRaises(CaptureContractError):
                scan_bundle_for_secrets(root)

    def test_17_runtime_source_never_imports_order_messages(self):
        for rel in ("m6/ctrader_openapi.py", "m6/_ctrader_openapi_base.py"):
            source = (ROOT / rel).read_text(encoding="utf-8")
            for forbidden in (
                "ProtoOANewOrderReq", "ProtoOACancelOrderReq", "ProtoOAClosePositionReq",
                "ProtoOAAmendOrderReq", 'scope="trading"', "scope='trading'",
            ):
                self.assertNotIn(forbidden, source)

    def test_18_local_secret_and_work_paths_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for item in ("m6_capture_local.json", ".m6_secrets/", ".m6_capture_work/", "capture_output/"):
            self.assertIn(item, ignore)

    def test_19_zero_economic_state_protected_closed_m6_pending(self):
        state = load(STATUS_PATH)["pre_economic_integrity"]
        self.assertEqual(state["result_recorded_count"], 0)
        self.assertEqual(state["v2_attempts_used"], 0)
        self.assertEqual(state["v2_evaluated_identities"], 0)
        self.assertEqual(state["economic_outcomes_opened"], 0)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertEqual(state["protected_forward_start"], PROTECTED_FORWARD_START)
        self.assertEqual(state["m6_status"], "PENDING")
        self.assertNotIn('"entry_type":"RESULT_RECORDED"', LEDGER_PATH.read_text(encoding="utf-8"))

    def test_20_prior_capture_checkpoint_remains_tooling_only(self):
        cp = load(CHECKPOINT_V1_PATH)
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

    def test_21_exact_h4_completion_boundary_regression(self):
        opened = datetime(2026, 9, 16, 20, 0, tzinfo=timezone.utc)
        rows = normalize_trendbars(
            [bar(opened)],
            resolution="H4",
            digits=5,
            requested_start_utc="2026-09-16T00:00:00Z",
            requested_end_utc="2026-09-16T23:59:59Z",
        )
        self.assertEqual(rows, [], "H4 bar completing 2026-09-17T00:00:00Z must be excluded")

    def test_22_completion_boundary_generic_m15_h1_h4_d1(self):
        cases = {
            "M15": datetime(2026, 9, 16, 23, 45, tzinfo=timezone.utc),
            "H1": datetime(2026, 9, 16, 23, 0, tzinfo=timezone.utc),
            "H4": datetime(2026, 9, 16, 20, 0, tzinfo=timezone.utc),
            "D1": datetime(2026, 9, 16, 0, 0, tzinfo=timezone.utc),
        }
        for resolution, opened in cases.items():
            with self.subTest(resolution=resolution):
                completion = {
                    "M15": "2026-09-17T00:00:00Z",
                    "H1": "2026-09-17T00:00:00Z",
                    "H4": "2026-09-17T00:00:00Z",
                    "D1": "2026-09-17T00:00:00Z",
                }[resolution]
                included = normalize_trendbars(
                    [bar(opened)], resolution=resolution, digits=5,
                    requested_start_utc="2026-09-15T00:00:00Z",
                    requested_end_utc=completion,
                )
                self.assertEqual(len(included), 1)
                excluded = normalize_trendbars(
                    [bar(opened)], resolution=resolution, digits=5,
                    requested_start_utc="2026-09-15T00:00:00Z",
                    requested_end_utc="2026-09-16T23:59:59Z",
                )
                self.assertEqual(excluded, [])

    def test_23_plan_canonical_hash_tamper_fails_closed(self):
        plan = load(PLAN_PATH)
        self.assertEqual(canonical_plan_sha256(plan), EXPECTED_PLAN_SHA)
        tampered = copy.deepcopy(plan)
        tampered["status"] = "TAMPERED"
        with self.assertRaises(CaptureContractError):
            validate_capture_plan(tampered)

    def test_24_progress_line_has_user_visible_metrics(self):
        line = format_capture_progress(
            overall_percent=37.4,
            stage="PRIMARY",
            instrument="US500",
            resolution="M15",
            series_percent=62.0,
            completed_windows=153,
            total_windows=247,
            completed_chunks=153,
            historical_requests_completed=211,
            rows_captured=104822,
            elapsed_seconds=48,
            effective_rps=4.72,
            reused_chunks=9,
        )
        for token in ("37.4%", "US500 M15", "series  62.0%", "windows 153/247", "chunks 153", "rows 104,822", "hist req 211", "4.72 req/s", "elapsed 00:48", "resume 9"):
            self.assertIn(token, line)

    def test_25_deployment_package_is_exact_deterministic_and_secret_free(self):
        with tempfile.TemporaryDirectory() as td:
            z1 = Path(td) / "one.zip"
            z2 = Path(td) / "two.zip"
            h1 = build_pydroid_package(ROOT, z1)
            h2 = build_pydroid_package(ROOT, z2)
            self.assertEqual(h1, h2)
            self.assertEqual(z1.read_bytes(), z2.read_bytes())
            with zipfile.ZipFile(z1, "r") as zf:
                names = set(zf.namelist())
            self.assertEqual(names, set(PYDROID_PACKAGE_FILES))
            for forbidden in ("m6_capture_local.json", ".m6_secrets", ".m6_capture_work"):
                self.assertFalse(any(forbidden in name for name in names))

    def test_26_final_transferable_bundle_contract_complete_and_local_paths_forbidden(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "bundle"
            for rel in TRANSFERABLE_REQUIRED_FILES:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            for index in range(11):
                path = root / "raw" / f"r{index:02d}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("time_utc,open,high,low,close,tick_volume\n", encoding="utf-8")
            aux = root / "auxiliary" / "conversion_raw" / "fx.csv"
            aux.parent.mkdir(parents=True, exist_ok=True)
            aux.write_text("time_utc,open,high,low,close,tick_volume\n", encoding="utf-8")
            report = validate_transferable_bundle(root)
            self.assertEqual(report["primary_raw_files"], 11)
            z = Path(td) / "bundle.zip"
            deterministic_zip(root, z)
            self.assertEqual(validate_transferable_zip(z)["primary_raw_files"], 11)
            local = root / ".m6_secrets" / "token_cache.json"
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text("{}", encoding="utf-8")
            with self.assertRaises(CaptureContractError):
                validate_transferable_bundle(root)

    def test_27_actual_runtime_adapter_import_and_sdk_heartbeat_smoke(self):
        import m6.ctrader_openapi as runtime
        report = runtime.runtime_sdk_preflight()
        self.assertEqual(report["ctrader_open_api_version"], "0.9.2")
        self.assertTrue(report["tcp_protocol_heartbeat_available"])
        self.assertTrue(report["sdk_idle_heartbeat_path_verified"])
        self.assertFalse(report["network_connection_attempted"])
        self.assertFalse(report["credentials_used"])

    def test_28_launcher_preflight_precedes_oauth_token_acquisition(self):
        source = (ROOT / "m6/pydroid_launcher.py").read_text(encoding="utf-8")
        main = source[source.index("def main()") :]
        self.assertLess(main.index("local_preflight()"), main.index("ensure_v2_authorization()"))
        self.assertIn("STOPPED before OAuth and before broker capture", source)
        entry = (ROOT / "M6_CAPTURE_RUN.py").read_text(encoding="utf-8")
        self.assertNotIn("input(", entry)
        self.assertNotIn("getpass", entry)

    def test_29_workflow_installs_runtime_imports_preflights_and_builds_package(self):
        workflow = (ROOT / ".github/workflows/m6_preparation.yml").read_text(encoding="utf-8")
        self.assertIn("pip install -r tools/requirements-m6-capture.txt", workflow)
        self.assertIn("python -m py_compile", workflow)
        self.assertIn("runtime_sdk_preflight", workflow)
        self.assertIn("RUNTIME_PREFLIGHT_PASS", workflow)
        self.assertIn("build_m6_pydroid_package.py", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)

    def test_30_final_hardening_checkpoint_preserves_frozen_state(self):
        cp = load(CHECKPOINT_V2_PATH)
        self.assertEqual(cp["status"], "FINAL_PRE_RUN_HARDENING_COMPLETE_EXTERNAL_PYDROID_EXECUTION_REQUIRED")
        self.assertEqual(cp["staging_parent_head"], "45fa613ce811510b4b3f43615f796342ce94c1fe")
        self.assertEqual(cp["active_plan_sha256"], EXPECTED_PLAN_SHA)
        self.assertEqual(cp["protected_forward_start"], PROTECTED_FORWARD_START)
        self.assertEqual(cp["oauth"]["scope"], "accounts")
        self.assertFalse(cp["oauth"]["trading_scope_requested"])
        self.assertEqual(cp["capture_contract"]["unique_primary_raw_series"], 11)
        self.assertEqual(cp["capture_contract"]["candidate_bindings"], 12)
        self.assertTrue(cp["capture_contract"]["exact_development_completion_boundary_enforced"])
        self.assertAlmostEqual(cp["runtime_hardening"]["normal_historical_target_requests_per_second"], HISTORICAL_TARGET_RPS, places=5)
        self.assertEqual(cp["deployment_package"]["name"], "MXM_M6_CAPTURE_PYDROID_PACKAGE.zip")
        self.assertEqual(cp["expected_final_capture_zip"], "MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip")
        actual = cp["actual_execution"]
        self.assertFalse(actual["broker_capture_run"])
        self.assertFalse(actual["m6_economics_run"])
        self.assertEqual(actual["economic_outcomes_opened"], 0)
        self.assertEqual(actual["v2_attempts_used"], 0)
        self.assertEqual(actual["result_recorded"], 0)
        self.assertFalse(actual["protected_evidence_opened"])
        self.assertFalse(actual["live_orders"])
        self.assertFalse(actual["competition_start"])
        self.assertEqual(actual["m6_status"], "PENDING")


if __name__ == "__main__":
    unittest.main(verbosity=2)

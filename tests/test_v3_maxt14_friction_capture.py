import hashlib
import json
import unittest
from pathlib import Path

from m6.pydroid_oauth import (
    PYDROID_MAIN_COMPONENT,
    PYDROID_PACKAGE,
    _pydroid_foreground_commands,
)
from research_core_v3.v3_friction_capture import (
    V3MaxT14FrictionRunner,
    account_identity_recovery_decision,
    build_account_rebind_proposal_document,
    classify_ctrader_api_error,
    coalesce_exact_windows,
    decode_delta_windows,
    history_coverage_for_window,
    local_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json"


class V3MaxT14FrictionCaptureTests(unittest.TestCase):
    def test_plan_binding_and_hard_boundaries(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        binding = plan.pop("binding_sha256")
        raw = json.dumps(
            plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding)
        self.assertEqual(plan["selection"]["selected_regions"], 14)
        self.assertEqual(
            plan["selection"]["other_gross_regions_remaining_COST_UNRESOLVED"], 74
        )
        self.assertFalse(plan["broker_identity"]["orders"])
        self.assertFalse(plan["broker_identity"]["account_mutation"])
        self.assertFalse(plan["acquisition"]["protected_forward_opened"])
        self.assertFalse(plan["acquisition"]["fill_authority"])
        self.assertFalse(
            plan["freeze_gate"]["candidate_freeze_allowed_by_this_capture"]
        )

    def test_delta_decode_is_exact(self):
        self.assertEqual(
            decode_delta_windows([[1000, 32], [300, 40], [0, 10]]),
            [(1000, 1032), (1300, 1340), (1300, 1310)],
        )

    def test_transport_grouping_never_changes_exact_windows(self):
        source = [(1000, 1032), (1200, 1232), (700000, 700032)]
        blocks = coalesce_exact_windows(
            source, max_gap_ms=300000, max_block_span_ms=3600000
        )
        self.assertEqual(len(blocks), 2)
        recovered = [
            (w.start_ms, w.end_ms) for block in blocks for w in block.windows
        ]
        self.assertEqual(recovered, source)
        self.assertEqual(blocks[0].start_ms, 1000)
        self.assertEqual(blocks[0].end_ms, 1232)

    def test_error_policy_is_conservative(self):
        self.assertEqual(
            classify_ctrader_api_error(
                "INVALID_REQUEST",
                "Historical tick data is not available outside the retention period",
                historical=True,
            ),
            "EXPLICIT_BROKER_HISTORY_UNAVAILABLE",
        )
        self.assertEqual(
            classify_ctrader_api_error(
                "INVALID_REQUEST",
                "Tick data request interval must not exceed one week",
                historical=True,
            ),
            "FAIL_CLOSED",
        )
        self.assertEqual(
            classify_ctrader_api_error(
                "BLOCKED_PAYLOAD_TYPE", "Rate limit reached", historical=True
            ),
            "TRANSIENT_RETRY",
        )
        self.assertEqual(
            classify_ctrader_api_error(
                "INVALID_REQUEST",
                "Historical tick data is not available",
                historical=False,
            ),
            "FAIL_CLOSED",
        )

    def test_window_history_coverage_is_exact_and_deterministic(self):
        record = {
            "broker_history_unavailable_ranges": [
                {"from_ms": 1200, "to_ms": 1800},
            ]
        }
        self.assertEqual(
            history_coverage_for_window(record, 1000, 2000),
            "PARTIAL_BROKER_HISTORY_UNAVAILABLE",
        )
        self.assertEqual(
            history_coverage_for_window(record, 1200, 1800),
            "BROKER_HISTORY_UNAVAILABLE",
        )
        self.assertEqual(
            history_coverage_for_window(record, 2000, 3000),
            "REQUEST_COMPLETED",
        )

    def test_account_identity_recovery_requires_fresh_oauth_before_rebind(self):
        frozen = "a" * 64
        self.assertEqual(
            account_identity_recovery_decision(
                frozen, ["b" * 64], "REUSED_SAVED_ACCESS_TOKEN"
            ),
            "FORCE_FRESH_OAUTH",
        )
        self.assertEqual(
            account_identity_recovery_decision(
                frozen, [frozen], "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION_FORCED"
            ),
            "MATCH_FROZEN_ACCOUNT",
        )
        self.assertEqual(
            account_identity_recovery_decision(
                frozen, ["b" * 64], "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION_FORCED"
            ),
            "REBIND_REVIEW_REQUIRED",
        )

    def test_rebind_proposal_is_sanitized_and_does_not_change_authority(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        symbols = {}
        for target in plan["targets"]:
            symbols[target["symbol"]] = {
                "symbol": target["symbol"],
                "symbol_id": target["symbol_id"],
                "identity": "EXACT_ACCEPTED_SYMBOL_ID_NAME_CURRENT_ENABLED",
                "current_metadata_only_not_historical_cost_truth": {
                    "symbolId": target["symbol_id"]
                },
            }
        proposal = build_account_rebind_proposal_document(
            plan,
            {
                "account_fingerprint_sha256": "c" * 64,
                "environment": "Pepperstone - Europe LIVE",
                "broker_name": "Pepperstone",
            },
            symbols,
        )
        self.assertTrue(proposal["rebind_scientifically_eligible"])
        self.assertFalse(proposal["authority_change_performed"])
        self.assertFalse(proposal["historical_bid_ask_capture_started"])
        self.assertEqual(proposal["verified_symbol_count"], 14)
        encoded = json.dumps(proposal, sort_keys=True)
        self.assertNotIn("ctidTraderAccountId", encoded)
        self.assertNotIn("ctid_trader_account_id", encoded)

    def test_application_auth_is_once_per_session_and_replayed_after_reconnect(self):
        class Response:
            pass

        class FakeTransport:
            def __init__(self):
                self.connected = False
                self.requests = []
                self.cached_endpoints = ()

            def connect(self):
                self.connected = True

            def close(self):
                self.connected = False

            def request(self, request, timeout=60):
                self.requests.append(type(request).__name__)
                return Response()

        runner = object.__new__(V3MaxT14FrictionRunner)
        runner.client_id = "client"
        runner.client_secret = "secret"
        runner.access_token = "token"
        runner.transport = FakeTransport()
        runner._logical_app_authorized = False
        runner._logical_account_id = None
        runner._session_app_authorized = False
        runner._session_account_authorized_id = None
        runner._persist_network_endpoint_cache = lambda: None
        runner._historical_requests = 0
        runner._historical_unavailable_responses = 0
        runner._last_historical_send = None
        runner._stage = lambda message: None

        runner._restore_session()
        runner._ensure_application_authenticated()
        runner._ensure_application_authenticated()
        self.assertEqual(
            runner.transport.requests.count("ProtoOAApplicationAuthReq"), 1
        )

        runner.transport.close()
        runner._restore_session()
        runner._ensure_application_authenticated()
        self.assertEqual(
            runner.transport.requests.count("ProtoOAApplicationAuthReq"), 2
        )

    def test_pydroid_foreground_uses_explicit_component_before_launcher_fallback(self):
        commands = _pydroid_foreground_commands()
        self.assertGreaterEqual(len(commands), 2)
        self.assertEqual(
            commands[0],
            ("am", "start", "-n", PYDROID_MAIN_COMPONENT),
        )
        self.assertEqual(PYDROID_PACKAGE, "ru.iiec.pydroid3")
        self.assertIn(PYDROID_PACKAGE, commands[1])

    def test_real_frozen_scope_geometry_preflight(self):
        geometry = local_geometry_preflight(ROOT)
        self.assertEqual(geometry["symbols"], 14)
        self.assertEqual(geometry["exact_windows"], 691919)
        self.assertGreater(geometry["transport_blocks"], 0)
        self.assertLessEqual(
            geometry["transport_blocks"], geometry["exact_windows"]
        )
        self.assertEqual(
            geometry["base_bid_ask_requests_before_pagination"],
            2 * geometry["transport_blocks"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

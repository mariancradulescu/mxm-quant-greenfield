import unittest
from types import SimpleNamespace

from research_v3.copilot_sdk_observability import (
    SDK_PIN, build_session_record, normalize_context_event,
    normalize_session_metrics, normalize_usage_event, sdk_session_kwargs,
    sdk_transport_is_opt_in,
)

class CopilotSdkObservabilityV1Tests(unittest.TestCase):
    def test_usage_event_normalization_captures_requested_fields_without_provider_call(self):
        data=SimpleNamespace(
            model="gpt-test",input_tokens=10,output_tokens=4,reasoning_tokens=2,
            cache_read_tokens=3,cache_write_tokens=1,cost=0.5,
            api_call_id="api-1",provider_call_id="gh-1",
        )
        event=SimpleNamespace(type="assistant.usage",data=data)
        row=normalize_usage_event(event)
        self.assertEqual(row["model"],"gpt-test")
        self.assertEqual(row["input_tokens"],10)
        self.assertEqual(row["output_tokens"],4)
        self.assertEqual(row["cache_read_tokens"],3)
        self.assertEqual(row["cost_multiplier"],0.5)

    def test_context_and_session_metrics_preserve_nulls(self):
        c=normalize_context_event(SimpleNamespace(type="session.usage_info",data=SimpleNamespace(current_tokens=100,token_limit=1000,messages_length=7)))
        self.assertEqual(c["current_tokens"],100)
        metrics=normalize_session_metrics({"totalNanoAiu":123,"totalPremiumRequestCost":None,"modelMetrics":{"m":{"usage":{"inputTokens":9,"outputTokens":2},"totalNanoAiu":123}}})
        self.assertEqual(metrics["total_nano_aiu"],123)
        self.assertIsNone(metrics["total_premium_request_cost"])
        self.assertEqual(metrics["model_metrics"]["m"]["input_tokens"],9)

    def test_session_limit_is_circuit_breaker_only_and_sdk_is_opt_in(self):
        kwargs=sdk_session_kwargs(model="auto",session_id="s1",max_ai_credits=12)
        self.assertEqual(kwargs["session_limits"]["max_ai_credits"],12)
        self.assertFalse(sdk_transport_is_opt_in({}))
        self.assertTrue(sdk_transport_is_opt_in({"MXM_COPILOT_TRANSPORT":"sdk"}))
        record=build_session_record(session_id="s1",semantic_fingerprint="f"*64,evidence_epoch=21,material_state_advanced=False,usage_events=[],context_events=[],metrics=None,max_ai_credits=12)
        self.assertEqual(record["sdk_pin"],SDK_PIN)
        self.assertEqual(record["session_limit"]["role"],"CIRCUIT_BREAKER_ONLY")
        self.assertTrue(record["unsupported_values_remain_null"])

if __name__=="__main__":
    unittest.main()

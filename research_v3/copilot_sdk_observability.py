"""Copilot SDK observability adapter with zero-call deterministic test surface.

The proven CLI transport remains the active fallback.  This module prepares the next
genuine semantic call to use a pinned SDK-managed session when explicitly enabled,
while preserving nulls for unavailable billing/account fields.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

SDK_PIN="github-copilot-sdk==1.0.14"
SCHEMA="mxm.greenfield.copilot-sdk-session-observability.v1"

def _get(obj:Any,name:str,default=None):
    if isinstance(obj,Mapping):
        return obj.get(name,default)
    return getattr(obj,name,default)

def _data(event:Any)->Any:
    return _get(event,"data",{})

def normalize_usage_event(event:Any)->dict[str,Any] | None:
    et=str(_get(event,"type",""))
    if "ASSISTANT_USAGE" not in et.upper() and et!="assistant.usage":
        return None
    d=_data(event)
    return {
        "model":_get(d,"model"),
        "input_tokens":_get(d,"input_tokens",_get(d,"inputTokens")),
        "output_tokens":_get(d,"output_tokens",_get(d,"outputTokens")),
        "reasoning_tokens":_get(d,"reasoning_tokens",_get(d,"reasoningTokens")),
        "cache_read_tokens":_get(d,"cache_read_tokens",_get(d,"cacheReadTokens")),
        "cache_write_tokens":_get(d,"cache_write_tokens",_get(d,"cacheWriteTokens")),
        "cost_multiplier":_get(d,"cost"),
        "api_call_id":_get(d,"api_call_id",_get(d,"apiCallId")),
        "provider_call_id":_get(d,"provider_call_id",_get(d,"providerCallId")),
    }

def normalize_context_event(event:Any)->dict[str,Any] | None:
    et=str(_get(event,"type",""))
    if "USAGE_INFO" not in et.upper() and et!="session.usage_info":
        return None
    d=_data(event)
    return {
        "current_tokens":_get(d,"current_tokens",_get(d,"currentTokens")),
        "token_limit":_get(d,"token_limit",_get(d,"tokenLimit")),
        "messages_length":_get(d,"messages_length",_get(d,"messagesLength")),
    }

def normalize_session_metrics(metrics:Any)->dict[str,Any]:
    models=_get(metrics,"model_metrics",_get(metrics,"modelMetrics",{})) or {}
    out_models={}
    if isinstance(models,Mapping):
        for model,m in models.items():
            usage=_get(m,"usage",{}) or {}
            out_models[str(model)]={
                "input_tokens":_get(usage,"input_tokens",_get(usage,"inputTokens")),
                "output_tokens":_get(usage,"output_tokens",_get(usage,"outputTokens")),
                "total_nano_aiu":_get(m,"total_nano_aiu",_get(m,"totalNanoAiu")),
            }
    return {
        "total_nano_aiu":_get(metrics,"total_nano_aiu",_get(metrics,"totalNanoAiu")),
        "total_premium_request_cost":_get(metrics,"total_premium_request_cost",_get(metrics,"totalPremiumRequestCost")),
        "model_metrics":out_models,
    }

def build_session_record(*,session_id:str|None,semantic_fingerprint:str,evidence_epoch:int,
                         material_state_advanced:bool,usage_events:list[dict[str,Any]],
                         context_events:list[dict[str,Any]],metrics:dict[str,Any]|None,
                         max_ai_credits:float|None)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "sdk_pin":SDK_PIN,
        "session_id":session_id,
        "semantic_fingerprint":semantic_fingerprint,
        "evidence_epoch":evidence_epoch,
        "whether_material_state_advanced":material_state_advanced,
        "per_model_calls":usage_events,
        "context_window_utilization":context_events[-1] if context_events else None,
        "session_metrics":metrics,
        "session_limit":{"max_ai_credits":max_ai_credits,"role":"CIRCUIT_BREAKER_ONLY"} if max_ai_credits is not None else None,
        "unsupported_values_remain_null":True,
    }

def sdk_session_kwargs(*,model:str,session_id:str,max_ai_credits:float|None=None)->dict[str,Any]:
    kwargs={"model":model,"session_id":session_id,"streaming":True}
    if max_ai_credits is not None:
        kwargs["session_limits"]={"max_ai_credits":max_ai_credits}
    return kwargs

def sdk_transport_is_opt_in(environment:Mapping[str,str])->bool:
    return str(environment.get("MXM_COPILOT_TRANSPORT") or "cli").strip().lower()=="sdk"

from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any

def _load(root:Path,rel:str)->dict[str,Any]: return json.loads((root/rel).read_text(encoding='utf-8'))
def _sha(root:Path,rel:str)->str: return hashlib.sha256((root/rel).read_bytes()).hexdigest()

def salvage_legacy_v2(root:Path)->dict[str,Any]:
    refs={
      'epoch46_acceptance':'evidence/EPOCH46_OUTCOME_BLIND_M5_WAVE_01_CAPTURE_ACCEPTANCE_V1.json',
      'epoch46_sufficiency':'evidence/EPOCH46_OUTCOME_BLIND_M5_WAVE_01_DATA_SUFFICIENCY_V1.json',
      'epoch47_result':'evidence/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_SCAN_V1.json',
      'epoch48_result':'evidence/EPOCH48_MEAN_REVERSION_STAGE2_ROBUST_NEIGHBORHOOD_RESULT_V1.json',
      'v2_state':'research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json',
      'provider_usage':'research_v3/ai_director/PROVIDER_USAGE_V1.json',
    }
    docs={k:_load(root,v) for k,v in refs.items()}
    e46=docs['epoch46_acceptance']; integ=e46.get('integrity_validation',{})
    e48=docs['epoch48_result']; state=docs['v2_state']; usage=docs['provider_usage']
    return {
      "schema":"mxm.research-core-v3.legacy-v2-salvage.v1","legacy_v2_read_only":True,"pending_v2_epoch49_execution_authorized":False,
      "source_refs":{k:{"path":v,"sha256":_sha(root,v)} for k,v in refs.items()},
      "epoch46":{"status":e46.get('status'),"requested_identities":(e46.get('frozen_scope') or {}).get('requested_identity_count'),"valid_nonempty_identities":integ.get('nonempty_series'),"zero_history_identity":(e46.get('zero_history_identity') or {}).get('broker_symbol'),"authentic_pepperstone_m5_rows":integ.get('total_m5_rows'),"duplicate_timestamps":integ.get('duplicate_timestamps'),"ohlc_failures":integ.get('ohlc_invariant_failures'),"protected_forward_rows":integ.get('protected_forward_rows'),"strategy_returns_opened":integ.get('strategy_returns_computed'),"pnl_opened":integ.get('pnl_computed')},
      "epoch47":{"status":docs['epoch47_result'].get('status'),"scope":docs['epoch47_result'].get('scope'),"grid":docs['epoch47_result'].get('grid')},
      "epoch48":{"status":e48.get('status'),"summary":e48.get('summary'),"scope":e48.get('scope'),"grid":e48.get('grid')},
      "v2_terminal_snapshot":{"status":state.get('status'),"current_research_evidence_epoch":state.get('current_research_evidence_epoch'),"next_action_preserved_but_not_executed":state.get('next_action'),"source_ai_proposal_id":state.get('source_ai_proposal_id'),"accounting":state.get('accounting')},
      "provider_accounting_preserved":{"provider_attempts":usage.get('provider_attempts'),"provider_invocations":usage.get('provider_invocations'),"failed_or_timeout_invocations":usage.get('failed_or_timeout_invocations'),"successful_reasoning_invocations":usage.get('successful_reasoning_invocations'),"successful_implementation_invocations":usage.get('successful_implementation_invocations')},
    }

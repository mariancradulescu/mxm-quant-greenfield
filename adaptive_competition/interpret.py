"""Predeclared interpretation only; never retunes or reruns the policy."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .data import STATE,sha,save

def interpret():
 p=STATE/'ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json';r=json.loads(p.read_text())
 entries=r['opportunity_counts'].get('executed_entry_count',0);net=r['conservative_net_pnl_eur'];gross=r['gross_pnl_eur'];ics=r['forecasting']['return_information_coefficient_by_horizon']
 # Classification is exact V1 development only, never a family closure or
 # proof of absent information. Statistical significance is not invented.
 if entries==0:classification='ECONOMIC_SCOPE_COST_LIMITED' if any(abs(v)>.01 for v in ics) else 'NO_PREDICTIVE_INFORMATION'
 elif net<=0:classification='PREDICTIVE_BUT_FRICTION_NEGATIVE' if gross>0 else 'POSITIVE_PRIMITIVES_CAPITAL_POLICY_WEAK' if max(ics)>.01 else 'NO_PREDICTIVE_INFORMATION'
 elif r['open_tranche_count'] or r['opportunity_counts'].get('financing_unresolved_positions',0) or r['opportunity_counts'].get('unresolved_position_marks',0):classification='POSITIVE_BUT_RISK_INFEASIBLE'
 elif r['top_contributor_shares']['top1']>.5:classification='POSITIVE_BUT_CONCENTRATED'
 elif not all(w['pass_floor21'] for w in r['entries_by_utc_iso_week'].values()):classification='POSITIVE_BUT_HARD21_INSUFFICIENT'
 else:classification='PROMISING_ADAPTIVE_ECONOMIC_RESULT'
 notes=['All results are development and conditional on explicit cost/margin/execution proxy scenarios.','Current metadata is not exact historical metadata; margin scenario and financing gaps prevent certification.','Prefix friction sample maximum x2 is a conservative scenario, not a mathematically guaranteed bound on every unseen quote.','Every 145 primary series participates; unmeasured costs lock execution but do not blacklist prediction.','No protected forward or confirmation evidence was opened.','Exact V1 failure closes only exact V1. No V1_1 is authorized here.','Raw overlapping labels and correlated trades are not independent replications.']
 interpretation={'classification':classification,'scope':'EXACT_ADAPTIVE_COMPETITION_POLICY_V1_PREQUENTIAL_DEVELOPMENT_ONLY','raw_result_sha256':sha(p.read_bytes()),'policy_hash':r['exact_policy_spec_hash'],'gross_pnl_eur':gross,'conservative_net_pnl_eur':net,'notes':notes,'statistical_significance_claimed':False,'realizable_edge_certified':False,'next_state':'PENDING_INDEPENDENT_AUDIT_OF_ADAPTIVE_COMPETITION_POLICY_V1_ECONOMIC_RESULT','machine_side_research_auth':'DEFERRED_NONBLOCKING_FOLLOWUP;NOT_PROVEN','next_identity_authorized':False}
 # Attribution is accounting telemetry, never a claim of counterfactual
 # causal contribution without actually executing a diagnostic ablation.
 decomposition={'layers':{'GROSS_INFORMATION_SURFACE':r['forecasting'],'CONSERVATIVE_EXECUTABLE_SURFACE':{'gross_pnl_eur':gross,'net_pnl_eur':net,'total_cost_eur':r['total_cost_eur'],'terminal_equity_eur':r['terminal_equity_eur']}},'spread_or_friction_cost_eur':r['spread_cost_eur'],'commission_eur':r['commission_cost_eur'],'slippage_or_delay_bound_cost_eur':r['slippage_delay_bound_cost_eur'],'financing_state':r['financing_state'],'currency_conversion_state':r['currency_conversion_state'],'margin_state':r['margin_state'],'churn_closed_trades':r['closed_trade_count'],'turnover_eur':r['turnover_eur'],'capital_allocation_contribution':{'account_net_pnl_eur':net,'capital_utilization':r['capital_utilization_mean_margin_fraction'],'counterfactual_causal_increment':'NOT_ESTIMATED;NO_POSTOUTCOME_POLICY_RESCUE'},'scale_in_contribution':{'add_actions':r['action_counts'].get('ADD',0),'counterfactual_causal_increment':'NOT_ESTIMATED'},'scale_out_contribution':{'reduce_actions':r['action_counts'].get('REDUCE',0),'exit_actions':r['action_counts'].get('EXIT',0),'counterfactual_causal_increment':'NOT_ESTIMATED'},'capital_rotation_contribution':{'decisions':r['capital_rotation_decisions'],'counterfactual_causal_increment':'NOT_ESTIMATED'},'final_net_result_eur':net,'classification':classification}
 save('ADAPTIVE_COMPETITION_POLICY_V1_INTERPRETATION.json',interpretation);save('ECONOMIC_DECOMPOSITION_V1.json',decomposition)
 return interpretation
if __name__=='__main__':print(json.dumps(interpret(),indent=2))

"""Integration of the canonical Discovery schema and continuous account evaluator.

No price/fill generator. Inputs must carry immutable source/availability receipts.
A certified conservative cost is a bound, never an authentic fill assertion.
"""
from dataclasses import asdict
from decimal import Decimal
from datetime import datetime,timedelta,timezone
from collections import Counter,defaultdict
from pathlib import Path
from .common import *
from discovery.engine import DiscoveryEngine
from discovery.schema import STAGE_A_METRIC_KEYS
from competition.continuous_account_replay_v2 import CapitalEvent,replay_continuous_account
COSTS=('spread','commission','slippage','funding','fx_conversion')

def unavailable(reason):return {'state':'UNAVAILABLE','reason':reason}
def serial(v):
    if isinstance(v,Decimal):return str(v)
    if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [serial(x) for x in v]
    return v

def screen(spec,evidence):
    """Cheap net screening on bound causal cashflows, not an execution simulator."""
    def evaluator(s,e):
        records=e.get('trades',[]);valid=e.get('implementation_valid') is True
        complete=e.get('complete') is True and bool(records)
        cost_state=e.get('cost_state','UNRESOLVED');need(cost_state in ('VERIFIED','CONSERVATIVE_BOUND','UNRESOLVED'),'COST_STATE')
        known=cost_state!='UNRESOLVED';gross=[];net=[];weeks=Counter()
        for r in records:
            entry=utc_ms(r['entry_ms']);exit=utc_ms(r['exit_ms']);decision=utc_ms(r['decision_ms'])
            need(entry>decision and exit>entry and r['feature_available_ms']<=decision,'FUTURE_INFORMATION')
            need(exit<1789603200000 and r['partition']=='DEVELOPMENT','PROTECTED_OUTCOME')
            need(all(len(r[k])==64 for k in ('source_sha256','execution_evidence_sha256')),'EXECUTION_PROVENANCE')
            need(r['execution_basis'] in ('AUTHENTIC_EXECUTION','CAUSAL_QUOTE_SIMULATION','SYNTHETIC_RECEPTION'),'EXECUTION_BASIS')
            need(number(r['gross_eur']),'GROSS_UNKNOWN');gross.append(r['gross_eur'])
            c=r.get('costs',{});this_known=all(number(c.get(k)) for k in COSTS)
            # Funding may be a credit; all other costs must be nonnegative.
            need(all(not number(c.get(k)) or c[k]>=0 for k in COSTS if k!='funding'),'NEGATIVE_COST')
            known=known and this_known
            if this_known:net.append(r['gross_eur']-sum(c[k] for k in COSTS))
            d=datetime.fromtimestamp(entry/1000,timezone.utc).isocalendar();weeks[f'{d.year}-W{d.week:02d}']+=1
        if not known:cost_state='UNRESOLVED'
        metrics={k:unavailable('NOT_MEASURED_AT_SCREENING') for k in STAGE_A_METRIC_KEYS}
        metrics.update(event_count=len(records),gross_pnl=sum(gross) if complete else unavailable('MISSING_SUPPORT'),coarse_net_pnl=sum(net) if complete and known else unavailable('MISSING_COST_OR_SUPPORT'))
        if complete:
            metrics.update(gross_per_event=sum(gross)/len(records),weekly_events=dict(weeks),active_weeks=len(weeks))
            if known:metrics.update(net_per_event=sum(net)/len(records),cost_burden=sum(gross)-sum(net))
        status='IMPLEMENTATION_INVALID' if not valid else 'DATA_INSUFFICIENT' if not complete else 'COST_UNRESOLVED' if not known else 'GROSS_EDGE_FAIL' if sum(gross)<=0 else 'COARSE_NET_FAIL' if sum(net)<=0 else 'DISCOVERY_SURVIVOR'
        result={'candidate_id':s['id'],'spec_hash':s['spec_hash'],'stage':'A','status':status,
          'implementation_validity':{'state':'VALID' if valid else 'INVALID'},'data_completeness':{'state':'SUFFICIENT' if complete else 'INSUFFICIENT'},
          'eur200_feasibility':{'state':'NOT_EVALUATED'},'cost_confidence':{'state':cost_state},'metrics':metrics,
          'provenance':{'data_evidence':{'identity':e['identity'],'binding':{'type':'DATASET_SHA256','sha256':digest(records)}},
            'cost_evidence':{'identity':e['identity']+':costs','state':cost_state,'sha256':digest([r.get('costs') for r in records])},
            'evaluator':{'version':'CANONICAL_DISCOVERY_WITH_BOUND_CASHFLOW_SCREEN_1','sha256':bytes_digest(Path(__file__).read_bytes())}}}
        return result
    return DiscoveryEngine().evaluate(spec,evidence,evaluator,persist=False)

def replay(spec,evidence):
    """Reuse account replay. All primitive costs must be explicit, even if zero.

    Price convention is prospectively recorded so spread is not charged twice.
    No external deposits after the one initial EUR200 endowment are permitted.
    """
    need(spec['starting_equity_eur']==200 and spec['deposit_count']==1,'CAPITAL_CONTRACT')
    need(evidence['screen_status']=='DISCOVERY_SURVIVOR','DEEP_WITHOUT_SCREEN_SURVIVOR')
    need(evidence['cost_state'] in ('VERIFIED','CONSERVATIVE_BOUND'),'UNKNOWN_DEEP_COST')
    need(evidence['full_mark_path'] is True and evidence['dated_broker_terms'] is True,'DEEP_SUPPORT')
    need(spec['sizing_rule_frozen'] is True and spec['allocator_frozen'] is True,'POST_OUTCOME_RESCUE')
    need(spec['price_cost_convention'] in ('MID_PLUS_ALL_FRICTIONS','BID_ASK_PLUS_NONSPREAD_COSTS'),'COST_CONVENTION')
    events=[]
    for row in evidence['events']:
        row=dict(row);need(row['kind'] in ('ENTRY','EXIT','MARK','FINANCING'),'CASH_RESET')
        need(row.get('causal_state') is True and utc_ms(row['timestamp_utc'])<1789603200000,'CAUSAL_REPLAY')
        meta=row.get('metadata',{});need(len(meta.get('source_sha256',''))==64,'REPLAY_PROVENANCE')
        need(meta.get('available_at_ms',utc_ms(row['timestamp_utc'])+1)<=utc_ms(row['timestamp_utc']),'REPLAY_AVAILABILITY')
        if row['kind'] in ('ENTRY','EXIT'):
            c=meta.get('cost_components_eur',{});need(all(number(c.get(k)) for k in COSTS),'REPLAY_MISSING_COST')
            need(c['funding']==0,'FUNDING_REQUIRES_SEPARATE_CASHFLOW')
            charged=sum(c[k] for k in COSTS if k!='funding')
            need(abs(float(row['transaction_cost_eur'])-charged)<1e-9,'COST_AGGREGATION')
            if spec['price_cost_convention']=='BID_ASK_PLUS_NONSPREAD_COSTS':need(c['spread']==0,'DOUBLE_SPREAD')
        if row['kind']=='ENTRY':
            need(all(type(row.get(k)) is int for k in ('volume_cents','min_volume_cents','step_volume_cents','max_volume_cents')),'INTEGER_VOLUME')
            need(abs(float(row['base_units'])-row['volume_cents']/100)<1e-9,'VOLUME_UNITS')
        events.append(CapitalEvent(**row))
    transform=None
    if spec.get('sizing_policy') is not None:
        from .sizing import policy
        transform=policy(spec['sizing_policy'])
    result=replay_continuous_account(events,starting_equity_eur=200,account_type=spec['account_type'],
      total_margin_calculation_type=spec['margin_type'],same_symbol_overlap_allowed=spec['same_symbol_overlap_allowed'],
      entry_margin_level_floor_ratio=spec.get('broker_entry_margin_floor'),unresolved_stop_out_guard_ratio=spec.get('broker_stop_out_guard'),entry_transform=transform)
    # Include idle weeks/months rather than drop them from the certificate.
    start=utc_ms(spec['evaluation_start']);end=utc_ms(spec['evaluation_end']);need(start<end,'EVALUATION_INTERVAL')
    need(all(start<=utc_ms(e.timestamp_utc)<end for e in events),'EVENT_OUTSIDE_EVALUATION')
    weeks={};months={};t=datetime.fromtimestamp(start/1000,timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    while int(t.timestamp()*1000)<end:
        i=t.isocalendar();weeks[f'{i.year}-W{i.week:02d}']=0;months[f'{t.year:04d}-{t.month:02d}']=None;t+=timedelta(days=1)
    for k in weeks:weeks[k]=result.entries_by_iso_week.get(k,0)
    def carry(keys,values):
        equity='200';out={}
        for k in sorted(keys):equity=str(values[k]) if k in values else equity;out[k]=equity
        return out
    weekly=carry(weeks,result.weekly_final_equity_eur);monthly=carry(months,result.monthly_final_equity_eur)
    def growth(values):
        prev=Decimal(200);out={}
        for k,v in values.items():current=Decimal(v);out[k]=str(current/prev-1) if prev>0 else None;prev=current
        return out
    return {'classification':'SUPPORTED_FOR_ROBUSTNESS' if result.status=='COMPLETE' else result.status,
      'replay':serial(asdict(result)),'weekly_equity':weekly,'monthly_equity':monthly,
      'weekly_growth':growth(weekly),'monthly_growth':growth(monthly),'entries_per_week':weeks,
      'HARD21':bool(weeks) and all(n>=21 for n in weeks.values()),'certification_scope':'EXACT_DECLARED_INTERVAL_INCLUDES_PARTIAL_WEEKS',
      'risk_of_ruin_probability':None,'ruin_probability_reason':'NO_INDEPENDENT_STOCHASTIC_MODEL_SUPPLIED',
      'survived_observed_path':result.status=='COMPLETE' and result.terminal_broker_equity_eur>0,'cbot_qualified':False}

def robustness(evidence):
    """Prospective cost stresses, cash baseline and chronological attribution.

    Uses bound cashflows; folds attribute the same path without capital resets.
    These diagnostics never constitute independent confirmation.
    """
    records=evidence['cashflows'];scenarios=evidence['cost_multipliers'];folds=evidence['chronological_folds']
    need(bool(records) and scenarios and folds,'ROBUSTNESS_POPULATION')
    need(all(number(v) and v>=1 for v in scenarios.values()),'ROBUSTNESS_COST_STRESS')
    need(all(all(number(r['costs'].get(k)) for k in COSTS) for r in records),'ROBUSTNESS_UNKNOWN_COST')
    ordered=sorted(folds,key=lambda f:f['start_ms']);need(all(f['start_ms']<f['end_ms'] for f in ordered),'ROBUSTNESS_FOLD')
    need(all(a['end_ms']==b['start_ms'] for a,b in zip(ordered,ordered[1:])),'ROBUSTNESS_FOLD_CONTINUITY')
    need(all(sum(f['start_ms']<=r['entry_ms']<f['end_ms'] for f in ordered)==1 for r in records),'ROBUSTNESS_POPULATION_COVERAGE')
    outputs={}
    for name,mult in scenarios.items():
        net=[r['gross_eur']-sum(r['costs'][k]*mult for k in COSTS) for r in records]
        outputs[name]={'net_eur':sum(net),'events':len(net),'incremental_over_cash_eur':sum(net)}
    attribution=[]
    for fold in ordered:
        subset=[r for r in records if fold['start_ms']<=r['entry_ms']<fold['end_ms']]
        attribution.append({'id':fold['id'],'events':len(subset),'net_eur':sum(r['gross_eur']-sum(r['costs'].values()) for r in subset) if subset else None})
    adequate=all(x['events']>0 for x in attribution)
    positive=all(x['net_eur']>0 for x in outputs.values()) and adequate and all(x['net_eur']>0 for x in attribution)
    return {'classification':'READY_FOR_SEPARATE_CONFIRMATION_REVIEW' if positive else 'INSUFFICIENT_ROBUSTNESS' if not adequate else 'ROBUSTNESS_REJECTED',
      'population_sha256':digest(records),'scenarios':outputs,'chronological_attribution':attribution,'cash_baseline_net_eur':0,
      'capital_resets':0,'independent_confirmation':False,'risk_of_ruin_probability':None,'cbot_qualified':False}

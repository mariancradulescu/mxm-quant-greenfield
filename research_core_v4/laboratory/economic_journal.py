"""Audit completeness for a first prospective result inside existing encrypted custody.

This is a result contract, not an evaluator, controller, account or new journal service.
Unknown costs/conversions remain explicit. Original source bytes stay in their cipher.
"""
from .common import need,digest
from decimal import Decimal
def canonical_values(value):
    if isinstance(value,Decimal):
        need(value.is_finite(),'AUDIT_FINITE_DECIMAL');return str(value)
    if isinstance(value,dict):return {k:canonical_values(v) for k,v in value.items()}
    if isinstance(value,list):return [canonical_values(v) for v in value]
    return value
STATES={'ABSTAIN','PROPOSAL','OVERLAP_REJECTED','ENTRY','EXIT','CENSORED','MARK_UNAVAILABLE'}
FIELDS={'ordinal','source_sequence','received_ms','arrival_ns','state','reason','direction','opportunity_id','context','modeled_fill'}
def validate(rows,*,target_events,source_sha256,policy_sha256):
    need(isinstance(rows,list) and len(rows)<=300000 and all(isinstance(s,str) and len(s)==64 for s in (source_sha256,policy_sha256)),'AUDIT_CONTEXT')
    own=set();opened={};closed=set();prior_ns=-1;prior_seq=0
    for i,r in enumerate(rows):
        need(set(r)==FIELDS and r['ordinal']==i+1 and r['state'] in STATES and r['reason'],'AUDIT_ROW_SCHEMA')
        need(type(r['arrival_ns']) is int and r['arrival_ns']>=prior_ns and type(r['received_ms']) is int and
             type(r['source_sequence']) is int and r['source_sequence']>=prior_seq and type(r['direction']) is int and r['direction'] in (-1,0,1),'AUDIT_CLOCK')
        prior_ns=r['arrival_ns'];prior_seq=r['source_sequence']
        if r['context'].get('source_symbol')==2:own.add(r['source_sequence'])
        c=r['context'];need(isinstance(c,dict) and {'target','fx','synthetic','cost_state','margin_state','risk_state'}<=set(c),'AUDIT_COST_FX_SOURCE_CONTEXT')
        fill=r['modeled_fill'];ident=r['opportunity_id'];state=r['state']
        if state=='PROPOSAL':need(type(ident) is int and ident>0 and ident not in opened,'AUDIT_DUPLICATE_OPPORTUNITY');opened[ident]=dict(state='PENDING',direction=r['direction'],at=r['arrival_ns'],units=None)
        if state=='ENTRY':
            need(ident in opened and opened[ident]['state']=='PENDING' and fill is not None and
                 r['direction']==opened[ident]['direction'] and r['arrival_ns']>opened[ident]['at'],'AUDIT_ENTRY_LIFECYCLE')
            opened[ident]=dict(state='OPEN',direction=r['direction'],at=r['arrival_ns'],units=fill['units'])
        if state in ('EXIT','CENSORED'):
            need(ident in opened and ident not in closed and r['direction']==opened[ident]['direction'],'AUDIT_CLOSED_LIFECYCLE')
            if state=='EXIT':need(opened[ident]['state']=='OPEN' and fill is not None and fill['units']==opened[ident]['units'] and
                                  r['arrival_ns']>opened[ident]['at'],'AUDIT_EXIT_WITHOUT_SAME_OPEN_POSITION')
            closed.add(ident)
        if state in ('ENTRY','EXIT'):
            need({'price','units','commission_eur','fx_profit','fx_loss','spread_embedded','slippage_quote','funding_state','source_sequence'}<=set(fill),'AUDIT_FILL_BREAKDOWN')
            need(all(fill[k] is not None and Decimal(str(fill[k])).is_finite() and Decimal(str(fill[k]))>0 for k in ('price','units','fx_profit','fx_loss')) and
                 all(fill[k] is not None and Decimal(str(fill[k])).is_finite() and Decimal(str(fill[k]))>=0 for k in ('commission_eur','slippage_quote')) and
                 fill['source_sequence']==r['source_sequence'],'AUDIT_FILL_ARITHMETIC_FIELDS')
            need(fill['spread_embedded'] is True and fill['funding_state']=='UNRESOLVED_NOT_ZERO_ACTUAL_CHARGE','AUDIT_NO_FREE_COST_PROMOTION')
    need(set(opened)==closed,'AUDIT_UNRESOLVED_OPPORTUNITY_NOT_RETAINED')
    need(len(own)==target_events,'AUDIT_EVERY_TARGET_EVENT_RECORDED')
    return dict(schema='mxm.first-execution-economic-journal.v1',rows=len(rows),target_events=target_events,
      opportunities=len(opened),source_sha256=source_sha256,policy_sha256=policy_sha256,ledger_sha256=digest(canonical_values(rows)),
      every_target_event_retained=True,complete_individual_ledger=True,independent_confirmation=False)

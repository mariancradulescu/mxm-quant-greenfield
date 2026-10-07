"""Symbolic readset QA only. No row adapter, market parser, decryptor or runner."""
SOURCES=('MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','CROSS_SECTIONAL_RELATIVE_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE')
def required_windows(source,t,horizon):
 if source not in SOURCES:raise ValueError('SOURCE')
 if type(t) is not int or t%300:raise ValueError('M5_GRID')
 if horizon not in ([12] if source=='REGIME_AND_STRUCTURAL_BREAK_STATE' else [1,12]):raise ValueError('HORIZON')
 if source=='REGIME_AND_STRUCTURAL_BREAK_STATE' and t%3600:raise ValueError('REGIME_UTC_HOUR_SCHEDULE')
 hour=(t//3600)*3600;B=set(range(hour-3600,hour,300))|{t-300}
 start=hour-4500 if source=='MULTISCALE_PRICE_STATE' else hour-7200 if source=='REGIME_AND_STRUCTURAL_BREAK_STATE' else hour-3600
 feature=set(range(start,hour,300));future=set(range(t,t+horizon*300,300))
 return {'baseline':sorted(B),'feature':sorted(feature),'future':sorted(future),'entry':t,'horizon':horizon,'peer_role':'All potential peer B queries then frozen fresh-set future-mask queries' if source=='CROSS_SECTIONAL_RELATIVE_STATE' else None}
def causal_conjunction(states):
 if any(x not in (True,False,None) for x in states):raise ValueError('TRISTATE')
 return False if False in states else None if None in states else True
def frozen_synthetic_peers(own,context_ids,causal_B_states):
 # Synthetic boolean QA interface; never accepts OHLC, actual source rows or files.
 if set(causal_B_states)!=set(context_ids):raise ValueError('CONTEXT_MASK_DOMAIN')
 if own not in context_ids:raise ValueError('OWN_NOT_IN_CONTEXT')
 return tuple(j for j in sorted(context_ids) if j!=own and causal_B_states[j] is True)
def response_synthetic_subset(frozen_peers,response_validity):
 if set(response_validity)!=set(frozen_peers):raise ValueError('NO_NEW_RESPONSE_PEERS')
 return tuple(j for j in frozen_peers if response_validity[j] is True)
def shared_dates(key_opens):
 # Attach to every day touched by queried M5 intervals, including close boundary.
 return sorted({d for s in key_opens for d in (s//86400,(s+299)//86400)})
def symbolic_overlap(query_a,query_b):return bool(set(query_a)&set(query_b))

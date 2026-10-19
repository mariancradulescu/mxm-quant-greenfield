"""Prospective account-state sizing over broker-certified volume options.

No linear-margin/linear-commission assumption or below-minimum rounding. This is
an evaluation interface, not a claimed profitable production allocator.
"""
from dataclasses import replace
from .common import *

def policy(spec):
    need(spec['frozen'] is True and spec['increase_after_loss'] is False,'SIZING_POLICY')
    need(number(spec['maximum_equity_risk_fraction']) and 0<spec['maximum_equity_risk_fraction']<1,'SIZING_RISK')
    need(number(spec['free_margin_reserve_fraction']) and 0<=spec['free_margin_reserve_fraction']<1,'SIZING_RESERVE')
    need(spec['common_factor_limits_fraction'] and all(number(x) and x>0 for x in spec['common_factor_limits_fraction'].values()),'FACTOR_RISK_LIMITS')
    def transform(event,snapshot,positions):
        equity=float(snapshot.broker_equity_eur);free=float(snapshot.free_margin_eur)
        options=event.metadata['certified_volume_options'];need(options,'VOLUME_OPTIONS')
        current={}
        for p in positions:
            for factor,risk in p.risk_exposures.items():current[factor]=current.get(factor,0)+abs(float(risk))
        available=[]
        for o in options:
            need(o['causally_available_at_ms']<=utc_ms(event.timestamp_utc) and len(o['source_sha256'])==64,'VOLUME_OPTION_PROVENANCE')
            v=o['volume_cents'];need(type(v) is int and v>=event.min_volume_cents and v<=event.max_volume_cents and (v-event.min_volume_cents)%event.step_volume_cents==0,'VOLUME_OPTION_LATTICE')
            need(all(number(o.get(k)) and o[k]>=0 for k in ('margin_eur','entry_cost_eur','worst_case_loss_eur')),'VOLUME_OPTION_TERMS')
            need(number(o['expected_net_eur']) and o['expected_net_eur']>0,'NONPOSITIVE_OPPORTUNITY')
            factors=o['risk_exposures_eur'];need(factors and set(factors)<=set(spec['common_factor_limits_fraction']) and all(number(x) for x in factors.values()),'FACTOR_EXPOSURE')
            if o['worst_case_loss_eur']>equity*spec['maximum_equity_risk_fraction']:continue
            if o['margin_eur']+o['entry_cost_eur']+equity*spec['free_margin_reserve_fraction']>free:continue
            if any(current.get(f,0)+abs(r)>equity*spec['common_factor_limits_fraction'][f] for f,r in factors.items()):continue
            available.append(o)
        if not available:return None,'REJECT_NO_SAFE_EXECUTABLE_VOLUME'
        chosen=max(available,key=lambda o:o['volume_cents'])
        return replace(event,volume_cents=chosen['volume_cents'],base_units=chosen['volume_cents']/100,
          margin_eur=chosen['margin_eur'],transaction_cost_eur=chosen['entry_cost_eur'],
          metadata={**event.metadata,'risk_exposures_eur':chosen['risk_exposures_eur']}),'ACCEPTED_FROZEN_ACCOUNT_STATE_POLICY'
    return transform

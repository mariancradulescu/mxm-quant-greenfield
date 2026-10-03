"""Fictional Gaussian breadth/power planning, not market calibration.

Uses conservative Bonferroni-24 + Holm structural contexts, not a simulation of
all proposed maxT/support/stability gates. This planning comparison bounds neither the proposed full lead power nor
observed-market exclusion power. It is not the proposed maxT test.
"""
import math
from statistics import NormalDist
import numpy as np


def holm(p, alpha=.05):
    p=np.asarray(p); order=np.argsort(p,kind='stable'); reject=np.zeros(len(p),dtype=bool)
    for rank,i in enumerate(order):
        if p[i] > alpha/(len(p)-rank): break
        reject[i]=True
    return reject


def information(n,weeks,rho,loss):
    k=max(1,int(math.floor(n*(1-loss))))
    w=max(1,int(math.floor(weeks*(1-loss))))
    return {'retained_identities':k,'retained_weeks':w,
            'effective_independent_identity_equivalents':1/(rho+(1-rho)/k),
            'context_mean_standard_error_weekly_noise_units':math.sqrt((rho+(1-rho)/k)/w)}


def run(counts,replicates=1000,seed=20261004):
    nd=NormalDist(); rows=[]
    def pvalues(z):
        # 24 fixed-cell union bound; no cell-dependent tuning.
        return np.minimum(1.,24*np.array([nd.cdf(-float(x)) for x in z]))
    scopes=[('PILOT_V1_SYMBOL_HOLM', [1]*5,17),
            ('FULL_FRONTIER_CONTEXTS_17_WEEKS', list(counts),17),
            ('FULL_FRONTIER_CONTEXTS_52_WEEKS', list(counts),52)]
    for label,ns,weeks in scopes:
        for rho in [0.,.2,.8]:
            for loss in [0.,.2,.5]:
                info=[information(n,weeks,rho,loss) for n in ns]
                for prevalence in [.1,.3,1.]:
                    rng=np.random.default_rng(seed) # common random numbers for comparisons
                    hit=0; broad_hit=0; null_hit=0
                    for _ in range(replicates):
                        common=rng.normal()
                        v=np.array([rho+(1-rho)/i['retained_identities'] for i in info])
                        zs=np.sqrt(rho/v)*common+np.sqrt((v-rho)/v)*rng.normal(size=len(ns))
                        null_hit+=bool(holm(pvalues(zs)).any())
                        # A predesignated context, not the best sampled one.
                        j=0 if label=='PILOT_V1_SYMBOL_HOLM' else int(np.argmax(ns))
                        n=info[j]['retained_identities']; active=max(1,int(math.ceil(prevalence*n)))
                        realized=active/n
                        delta=.5*realized/info[j]['context_mean_standard_error_weekly_noise_units']
                        effect=zs.copy();effect[j]+=delta
                        rejected=bool(holm(pvalues(effect))[j]);hit+=rejected
                        # 60% positive identity breadth under the same Gaussian
                        # common-week regime; simulate actual identity means.
                        n=info[j]['retained_identities'];w=info[j]['retained_weeks']
                        active=max(1,int(math.ceil(prevalence*n)));mu=np.zeros(n);mu[:active]=.5
                        vals=mu+math.sqrt(rho/w)*common+math.sqrt((1-rho)/w)*rng.normal(size=n)
                        broad_hit+=rejected and n>=2 and (vals>0).mean()>=.6
                    rows.append({'scope':label,'weeks':weeks,'contexts_or_symbols':len(ns),
                      'rho':rho,'support_loss':loss,'active_prevalence':prevalence,
                      'realized_active_prevalence_in_target_context':realized, 'target_context_identity_count':n,
                      'injected_active_identity_weekly_noise_sd':.5,'replicates':replicates,
                      'inference_rejection_fraction':hit/replicates,
                      'separate_synthetic_breadth_screen_overlap_fraction_not_full_gate_power':broad_hit/replicates,
                      'null_any_reject_fraction':null_hit/replicates,
                      'full_lead_power_certified':False})
    return {'schema':'mxm.v4.quote-scope-synthetic-power-planning.v1','seed':seed,
      'method':'GAUSSIAN_ANALYTICAL_STANDARD_ERRORS_AND_CONSERVATIVE_BONFERRONI24_HOLM;NOT_MAXT_CALIBRATION',
      'limitations':['support and complete temporal/window/concentration gates not modeled',
        'rho and support loss are hypothetical, not estimated from quotes',
        'conditional Gaussian null; not real geometry, sparse non-Gaussian or missing-not-at-random certification',
        'synthetic identity breadth uses separate idiosyncratic draws sharing regime; overlap is not full joint-gate power or independent confirmation','comparison uses conservative one-cell Bonferroni24 bound, not distribution of max over24; not V1 exact maxT power', 'no market effect-size exclusion guarantee'],
      'scenarios':rows,'market_inputs_read':0,'broker_calls':0}

if __name__=='__main__':
    import json,pathlib
    p=pathlib.Path('research_core_v4/state/NEXT_QUOTE_SEQUENCE_FULL_FRONTIER_ELIGIBILITY_V1.json')
    d=json.loads(p.read_bytes());counts=list(d['asset_class_counts'].values())
    print(json.dumps(run(counts),sort_keys=True,indent=2))

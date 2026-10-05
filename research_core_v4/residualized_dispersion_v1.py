"""Dense synchronized peer residual energy; own-leg response, no acquisition."""
import math
from collections import defaultdict
import numpy as np
from research_core_v4.online_change_v1 import canonical,sha,require,read_series

def panel_hours(panel,d):
    ids=list(panel);valid={sid:{t for t in p if d['training_start']+3600<=t<d['evaluation_end_exclusive'] and all(t-300*k in p for k in range(13))} for sid,p in panel.items()}
    times=sorted(set.intersection(*(valid[sid] for sid in ids)))
    r=np.array([[math.log(panel[sid][t]/panel[sid][t-3600]) for sid in ids] for t in times])
    require(r.ndim==2 and r.shape[1]==6,'complete six-member panel')
    return np.array(times,dtype=np.int64),r,valid

def factor_returns(r):return (r.sum(axis=1,keepdims=True)-r)/5

def fit_panel_normalization(times,r,d):
    ii=(times<d['normalization_end']);a=r[ii];require(len(a)>=d['support']['normalization_clocks_min'],'normalization panel support')
    f=factor_returns(a);mx=f.mean(axis=0);my=a.mean(axis=0);vx=np.sum((f-mx)**2,axis=0)
    require(np.all(vx>1e-30),'singular factor prefix')
    beta=np.sum((f-mx)*(a-my),axis=0)/vx;alpha=my-beta*mx
    sigma=np.sqrt(np.mean((a-alpha-beta*f)**2,axis=0));own=np.sqrt(np.mean(a*a,axis=0));fs=np.sqrt(np.mean(f*f,axis=0))
    require(np.all(sigma>1e-15) and np.all(own>1e-15) and np.all(fs>1e-15),'singular normalization')
    g=np.clip((a-alpha-beta*f)/sigma,-4,4);disp=np.sqrt(np.maximum((np.sum(g*g,axis=1,keepdims=True)-g*g)/5,0))
    return {'alpha':alpha.tolist(),'beta':beta.tolist(),'sigma':sigma.tolist(),'own_sigma':own.tolist(),'factor_sigma':fs.tolist(),'dispersion_center':disp.mean(axis=0).tolist(),'normalization_clocks':len(a)}

def features(times,r,m):
    f=factor_returns(r);g=np.clip((r-m['alpha']-np.array(m['beta'])*f)/m['sigma'],-4,4)
    energy=np.maximum((np.sum(g*g,axis=1,keepdims=True)-g*g)/5,0);disp=np.sqrt(energy)
    interaction=g*(disp-m['dispersion_center']);phase=2*np.pi*(times%86400)/86400
    z=np.stack([np.ones_like(g),g,np.clip(f/m['factor_sigma'],-4,4),np.abs(g),disp,np.broadcast_to(np.sin(phase)[:,None],g.shape),np.broadcast_to(np.cos(phase)[:,None],g.shape)],axis=2)
    return interaction,z,disp

def fit_prefix(panel,d):
    ids=list(panel);times,r,valid=panel_hours(panel,d);m=fit_panel_normalization(times,r,d);interaction,z,disp=features(times,r,m)
    prefix=(times>=d['normalization_end']+3600)&(times<=d['training_end']-3600)
    bx=[];by=[];sx=[];counts=[];ranks=[]
    for i,sid in enumerate(ids):
        ii=[j for j,t in enumerate(times) if prefix[j] and all(int(t)+300*k in panel[sid] for k in range(1,13))]
        require(len(ii)>=d['support']['prefix_clocks_min'],'second prefix support')
        zz=z[ii,i,:];xx=interaction[ii,i];yy=np.array([math.log(panel[sid][int(times[j])+3600]/panel[sid][int(times[j])])/m['own_sigma'][i] for j in ii])
        rank=int(np.linalg.matrix_rank(zz));require(rank==7,'prefix seven-control rank')
        b=np.linalg.lstsq(zz,xx,rcond=None)[0];c=np.linalg.lstsq(zz,yy,rcond=None)[0];scale=float(np.sqrt(np.mean((xx-zz@b)**2)))
        require(scale>1e-10,'singular dispersion interaction')
        bx.append(b.tolist());by.append(c.tolist());sx.append(scale);counts.append(len(ii));ranks.append(rank)
    m.update(x_beta=bx,y_beta=by,x_scale=sx,prefix_clocks=counts,control_ranks=ranks)
    x=(interaction-np.einsum('tik,ik->ti',z,np.array(bx)))/sx;baseline=np.einsum('tik,ik->ti',z,np.array(by))
    return ids,times,x,baseline,m,valid

def prepare(series,d):
    require(d['training_end']+3600<d['evaluation_start'],'prefix purge')
    require(set(series)==set(d['memberships']),'exact contexts')
    population={};models={};contexts={};all_ok=True
    for c,ids_expected in sorted(d['memberships'].items()):
        require(set(series[c])==set(ids_expected) and len(ids_expected)==6,'exact panel')
        # Identity order is frozen, never dictionary-dependent.
        panel={sid:series[c][sid] for sid in ids_expected}
        try:ids,times,x,baseline,m,valid=fit_prefix(panel,d)
        except ValueError as e:
            return {'schema':'mxm.v4.dispersion-support.v1','pass':False,'blocker':str(e),'failed_context':c,'real_response_opened':False},{}
        models[c]=m;counts={};block_sets=[];evalii=np.where((times>=d['evaluation_start'])&(times<d['evaluation_end_exclusive']))[0]
        for i,sid in enumerate(ids):
            p=panel[sid];own_possible=sum(d['evaluation_start']<=t<d['evaluation_end_exclusive'] for t in valid[sid]);rows=[];weekly=defaultdict(int)
            for j in evalii:
                t=int(times[j])
                # Timestamp membership only, no future-price accessor.
                if not all(t+300*k in p for k in range(1,13)):continue
                week=(t-d['evaluation_start'])//604800
                rows.append({'t':t,'x':float(x[j,i]),'baseline_y':float(baseline[j,i]),'week':week});weekly[week]+=1
            blocks=[b for b in range(21) if weekly[2*b]>=d['support']['per_week_clocks_min'] and weekly[2*b+1]>=d['support']['per_week_clocks_min']]
            panel_ret=len(evalii)/max(1,own_possible);ret=len(rows)/max(1,len(evalii))
            ok=len(rows)>=d['support']['per_symbol_clocks_min'] and ret>=d['support']['retention_min'] and panel_ret>=d['support']['panel_retention_min']
            population[str(sid)]=rows;counts[str(sid)]={'own_eligible_current_clocks':own_possible,'panel_clocks':len(evalii),'panel_retention':panel_ret,'retained_clocks':len(rows),'future_timestamp_retention':ret,'blocks':blocks,'prefix_clocks':m['prefix_clocks'][i],'normalization_clocks':m['normalization_clocks'],'control_rank':m['control_ranks'][i],'pass':bool(ok)}
            block_sets.append(set(blocks));all_ok=all_ok and ok
        contexts[c]={'symbols':counts,'blocks':sorted(set.intersection(*block_sets))}
    joint=sorted(set.intersection(*(set(v['blocks']) for v in contexts.values())))
    geometry=len(joint)>=d['support']['joint_blocks_min'] and joint==list(range(joint[0],joint[-1]+1)) and all(sum(b//7==q for b in joint)>=d['support']['blocks_per_third_min'] for q in range(3))
    return {'schema':'mxm.v4.dispersion-support.v1','pass':bool(all_ok and geometry),'contexts':contexts,'joint_blocks':joint,'population_sha256':sha(canonical(population)),'models_sha256':sha(canonical(models)),'models':models,'causal_panel_integrity_pass':True,'real_response_opened':False,'broker_contacts':0,'historical_requests':0},population

def response(row,p,scale):
    t=row['t'];return row['x']*(math.log(p[t+3600]/p[t])/scale-row['baseline_y'])

def raw_result(series,d,support,population,authorized=False):
    require(authorized is True or d.get('synthetic_only') is True,'REAL_RESPONSE_NOT_AUTHORIZED');require(support['pass'],'support denied')
    blocks=support['joint_blocks'];values={};assets={}
    for c,ids in sorted(d['memberships'].items()):
        symbols={}
        for i,sid in enumerate(ids):
            byweek=defaultdict(list)
            for row in population[str(sid)]:
                if row['week']//2 in blocks:byweek[row['week']].append(response(row,series[c][sid],support['models'][c]['own_sigma'][i]))
            symbols[str(sid)]=[float(np.mean([np.mean(byweek[2*b]),np.mean(byweek[2*b+1])])) for b in blocks]
        assets[c]=symbols;values[c]=np.mean(list(symbols.values()),axis=0).tolist()
    return {'schema':'mxm.v4.dispersion-raw.v1','blocks':blocks,'context_block_scores':values,'symbol_block_scores':assets,'design_sha256':sha(canonical(d)),'population_sha256':support['population_sha256'],'response_opened':True,'profit_claimed':False,'broker_contacts':0,'historical_requests':0}

def critical_count(n,alpha):
    for k in range(n+1):
        if sum(math.comb(n,j) for j in range(k,n+1))/2**n<=alpha/4:return k
    return n+1

def family_rejections(x,d):
    x=np.asarray(x);n=x.shape[-1];k=critical_count(n,d['inference']['family_alpha'])
    return np.any((np.sum(x>0,axis=-1)>=k)|(np.sum(x<0,axis=-1)>=k),axis=-1)

def complete_lead(x,assets,blocks,d):
    x=np.asarray(x);n=x.shape[-1];k=critical_count(n,d['inference']['family_alpha']);direction=np.sign(x.mean(axis=-1)[...,0]);s=direction[...,None,None]
    ok=(direction!=0)&np.all(np.sum(s*x>0,axis=-1)>=k,axis=-1)
    for q in range(3):
        ii=np.array([b//7==q for b in blocks]);require(ii.sum()>=d['support']['blocks_per_third_min'],'temporal geometry');ok&=np.all(direction[...,None]*x[...,ii].mean(axis=-1)>0,axis=-1)
    ok&=np.all(np.sum(direction[...,None,None]*np.asarray(assets).mean(axis=-1)>0,axis=-1)>=4,axis=-1)
    return ok

def interpret(raw,d):
    contexts=sorted(d['memberships']);x=np.array([raw['context_block_scores'][c] for c in contexts]);assets=np.array([list(raw['symbol_block_scores'][c].values()) for c in contexts]);lead=bool(complete_lead(x,assets,raw['blocks'],d));n=len(raw['blocks']);k=critical_count(n,d['inference']['family_alpha']);direction=int(np.sign(x[0].mean())) if lead else None
    return {'schema':'mxm.v4.dispersion-interpretation.v1','classification':'REPLICATED_INFORMATION_LEAD_COST_UNRESOLVED_DISJOINT_CONFIRMATION_REQUIRED' if lead else 'NO_REPLICATED_INFORMATION_LEAD_SMALL_EFFECTS_LOW_POWER_INCONCLUSIVE','lead':lead,'direction':direction,'context_order':contexts,'block_counts_positive':np.sum(x>0,axis=1).tolist(),'block_counts_negative':np.sum(x<0,axis=1).tolist(),'critical_count':k,'context_means':x.mean(axis=1).tolist(),'temporal_thirds':{c:[float(np.mean([v for b,v in zip(raw['blocks'],raw['context_block_scores'][c]) if b//7==q])) for q in range(3)] for c in contexts},'economic_status':'COST_UNRESOLVED','economic_null_claimed':False,'profit_claimed':False,'candidate_frozen_count':0,'confirmation_opened':False,'protected_forward_opened':False,'broader_family_closed':False}

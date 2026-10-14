"""Prospectively fixed price-level comparisons. No future price response."""
from collections import Counter
from datetime import datetime
from research_core_v4.dom_live_probe_20261013_v1.live_adapter_v1 import DepthBook

class InformationBook(DepthBook):
    def __init__(self,sid,digits,*,start_utc,rules):
        super().__init__(sid,digits);self.start_utc=start_utc;self.rules=rules
        self.previous=None;self.origin_ns=None;self.previous_ns=None;self.previous_valid=False
        self.valid_seconds=0.;self.longest_complete_seconds=0.;self.run_seconds=0.
        self.bins={};self.rank_stats={};self.records=[];self.unchanged_bbo_run=0
        self.complete_intervals=[];self.processing_ns=[]

    def depth_event(self,event,stamp):
        import time
        begin=time.monotonic_ns();before=self.previous
        super().depth_event(event,stamp)
        now=stamp['receive_monotonic_ns'];self.origin_ns=self.origin_ns or now
        warm=(now-self.origin_ns)/1e9>=self.rules['warmup_seconds']
        bid,ask=self.levels('bid'),self.levels('ask')
        valid=warm and not self.invalid_epoch and len(bid)>=3 and len(ask)>=3 and bid[0][0]<ask[0][0]
        bin_id=int((datetime.fromisoformat(stamp['receive_utc'])-self.start_utc).total_seconds()//self.rules['bin_seconds'])
        stats=self.bins.setdefault(bin_id,Counter());stats['dom_events']+=1
        if self.previous_ns is not None and self.previous_valid:
            dt=(now-self.previous_ns)/1e9;fresh=min(dt,self.rules['maximum_state_age_seconds'])
            self.valid_seconds+=fresh;stats['fresh_complete_seconds']+=fresh
            self.run_seconds+=fresh;self.longest_complete_seconds=max(self.longest_complete_seconds,self.run_seconds)
            self.complete_intervals.append([self.previous_ns,self.previous_ns+int(fresh*1e9)])
            if dt>self.rules['maximum_state_age_seconds']:self.run_seconds=0.
        if not valid:self.run_seconds=0.
        current={'bid':bid,'ask':ask}
        paired=valid and self.previous_valid and before is not None and (now-self.previous_ns)/1e9<=self.rules['maximum_state_age_seconds']
        if paired:
            stats['valid_adjacent_pairs']+=1
            bbo_same=all(current[s][0][0]==before[s][0][0] for s in ('bid','ask'))
            self.unchanged_bbo_run=self.unchanged_bbo_run+1 if bbo_same else 0
            changed_sides=[];record={'sequence':stamp['sequence'],'monotonic_ns':now,'bin':bin_id,'bbo_unchanged':bbo_same,'side_changes':{}}
            rank_sizes_equal=True;prices_changed=False;all_changes=[]
            for side in ('bid','ask'):
                old=dict(before[side]);new=dict(current[side]);old_rank={p:i+1 for i,(p,v) in enumerate(before[side])}
                common=set(old)&set(new);changed=[p for p in common if old[p]!=new[p]]
                stats[side+'_shared_price_pairs']+=len(common)
                stats[side+'_same_price_quantity_changes']+=len(changed)
                top_changed=[p for p in changed if old_rank[p]<=3 and next(i+1 for i,(q,v) in enumerate(current[side]) if q==p)<=3]
                stats[side+'_top3_same_price_quantity_changes']+=len(top_changed)
                if changed:
                    changed_sides.append(side);stats[side+'_quantity_change_events']+=1
                    if bbo_same:stats[side+'_bbo_fixed_quantity_events']+=1
                    if bbo_same and self.unchanged_bbo_run>=2:stats[side+'_quantity_events_after_two_fixed_bbo_updates']+=1
                stats[side+'_refill_levels']+=sum(new[p]>old[p] for p in changed)
                stats[side+'_depletion_levels']+=sum(new[p]<old[p] for p in changed)
                stats[side+'_refill_size_cents']+=sum(new[p]-old[p] for p in changed if new[p]>old[p])
                stats[side+'_depletion_size_cents']+=sum(old[p]-new[p] for p in changed if new[p]<old[p])
                stats[side+'_entered_price_levels']+=len(set(new)-set(old));stats[side+'_exited_price_levels']+=len(set(old)-set(new))
                for rank,(price,size) in enumerate(current[side],1):
                    if rank>3:break
                    rs=self.rank_stats.setdefault((bin_id,side,rank),{'n':0,'sum':0,'sumsq':0,'min':None,'max':None,'fixed_price_rank_pairs':0,'fixed_price_rank_changes':0,'rank_migration_pairs':0})
                    rs['n']+=1;rs['sum']+=size;rs['sumsq']+=size*size
                    rs['min']=size if rs['min'] is None else min(rs['min'],size);rs['max']=size if rs['max'] is None else max(rs['max'],size)
                    if price in old:
                        if old_rank[price]==rank:
                            rs['fixed_price_rank_pairs']+=1;rs['fixed_price_rank_changes']+=int(old[price]!=size)
                        else:rs['rank_migration_pairs']+=1
                rank_sizes_equal &= [v for p,v in before[side]]==[v for p,v in current[side]]
                prices_changed |= [p for p,v in before[side]]!=[p for p,v in current[side]]
                record['side_changes'][side]=[{'price':p,'before_size_cents':old[p],'after_size_cents':new[p]} for p in sorted(changed)]
                all_changes.extend(changed)
            # Operational price-only comparator, not proof of broker generation mechanism.
            if rank_sizes_equal and prices_changed:stats['price_ladder_only_compatible_events']+=1
            if all_changes and not rank_sizes_equal:stats['quantity_distinct_from_rank_size_preserving_ladder_events']+=1
            if changed_sides==['bid']:stats['bid_only_quantity_events']+=1
            elif changed_sides==['ask']:stats['ask_only_quantity_events']+=1
            elif len(changed_sides)==2:stats['both_side_quantity_events']+=1
            if bbo_same:stats['fixed_bbo_adjacent_pairs']+=1
            self.records.append(record)
        else:self.unchanged_bbo_run=0
        self.previous=current;self.previous_ns=now;self.previous_valid=valid
        self.processing_ns.append(time.monotonic_ns()-begin)

    def finish(self,end_ns):
        if self.previous_valid and self.previous_ns is not None:
            fresh=max(0,min((end_ns-self.previous_ns)/1e9,self.rules['maximum_state_age_seconds']))
            self.valid_seconds+=fresh;self.longest_complete_seconds=max(self.longest_complete_seconds,self.run_seconds+fresh)
            self.complete_intervals.append([self.previous_ns,self.previous_ns+int(fresh*1e9)])

    def summary(self):
        result=super().summary();rank=[]
        for (bin_id,side,k),rs in sorted(self.rank_stats.items()):
            n=rs['n'];rank.append({'bin':bin_id,'side':side,'rank':k,**rs,'mean_size_cents':rs['sum']/n,'variance_size_cents':max(0,rs['sumsq']/n-(rs['sum']/n)**2)})
        totals=Counter()
        for stats in self.bins.values():totals.update(stats)
        supported_bins=[k for k,stats in self.bins.items() if all(stats[s+'_bbo_fixed_quantity_events']>=self.rules['minimum_fixed_bbo_quantity_events_per_side_bin'] for s in ('bid','ask'))]
        supported=self.valid_seconds>=self.rules['minimum_fresh_complete_seconds'] and len(supported_bins)>=self.rules['minimum_supported_bins'] and not self.invalid_epoch
        distinct=totals['quantity_distinct_from_rank_size_preserving_ladder_events']>0
        verdict='DISTINCT_QUOTED_QUANTITY_OBSERVED_SUPPORTED_FOR_SEPARATE_STUDY_DESIGN' if supported and distinct else ('DISTINCT_QUOTED_QUANTITY_OBSERVED_SUPPORT_INSUFFICIENT' if distinct else 'NO_DISTINCT_QUANTITY_DEMONSTRATED_IN_THIS_CAPTURE')
        result['information']={'verdict':verdict,'fresh_complete_seconds':self.valid_seconds,'longest_fresh_complete_seconds':self.longest_complete_seconds,'supported_bins':supported_bins,'bins':{str(k):dict(v) for k,v in sorted(self.bins.items())},'totals':dict(totals),'rank_conditioned_quantity':rank,'processing_latency_p95_seconds':sorted(self.processing_ns)[min(len(self.processing_ns)-1,int(.95*len(self.processing_ns)))]/1e9 if self.processing_ns else None,'completeness':'OBSERVED_COHERENT_TOP3_NOT_SERVER_CERTIFIED_FULL_BOOK','price_only_comparator':'UNCHANGED_SIZE_VECTOR_BY_RANK_WITH_CHANGED_PRICES;COMPATIBILITY_NOT_GENERATIVE_CAUSAL_PROOF','economic_response_tested':False}
        return result

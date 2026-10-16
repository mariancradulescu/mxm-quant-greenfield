"""Read preserved checkpoint objects only; no outcome re-evaluation or broker IO."""
import gzip
import json
import math
import re
import pathlib
from collections import Counter,defaultdict
from .safety import canonical,sha,require

def inspect(journal,read,key,tmp,root):
    from .resolution import EvidenceIndex, unique_metadata
    indexer=EvidenceIndex(journal)
    # This is the exact current-checkpoint reachable set, not every historical
    # import attempt or deleted log. Missing source manifests remain explicit.
    metas=[]
    for field in ('shards','record_shards','snapshots_v2','increments_v2'):
        value=journal.get(field,[]);metas.extend(value.values() if isinstance(value,dict) else value)
    unique=unique_metadata(journal);receipts=[];wire={};collisions=[];spans=defaultdict(list);totals=Counter();source_binds=Counter()
    for index,meta in enumerate(unique.values()):
        record={'asset_id':meta['id'],'release_id':meta.get('release_id'),'ciphertext_sha256':meta.get('ciphertext_sha256'),'gzip_sha256':meta.get('gzip_sha256'),'canonical_sha256':meta.get('canonical_sha256')}
        try:
            value=read(meta,key,tmp);local=Counter()
            for row in value.get('bars',[]):
                if not isinstance(row,list) or len(row)!=7:local['bar_schema_unknown']+=1;continue
                sid,t,*v=row;local['bars_inspected']+=1
                if not all(isinstance(x,(float,int)) and math.isfinite(x) for x in v) or v[-1]<0:local['invalid_finite_or_volume']+=1
                if type(t) is not int or t%300:local['invalid_bar_clock']+=1
            for row in value.get('ticks',[]):
                if not isinstance(row,list) or len(row)!=4:local['tick_schema_unknown']+=1;continue
                sid,side,t,price=row;local['ticks_inspected']+=1
                if not 1787097600000<=t<1789344000000:local['out_of_domain_tick']+=1
            for row in value.get('wire',[]):
                local['wire_inspected']+=1;k=tuple(row[:4]);v=tuple(row[4:]);old=wire.get(k)
                if old is not None and old!=v:collisions.append({'key_sha256':sha(canonical(k)),'before_sha256':sha(canonical(old)),'after_sha256':sha(canonical(v)),'asset_id':meta['id']})
                else:wire[k]=v
            for sid,k,a,b,z in value.get('spans',[]):spans[sid,k].append((a,b,z));local['spans_inspected']+=1
            for raw in value.get('raw',[]):
                local['raw_receipts_inspected']+=1
                evidence=raw.get('preserved_failure_evidence')
                if evidence is not None:
                    # Legacy global receipts lack exact account/server/request-id.
                    from .safety import bind_failure
                    state=bind_failure(raw,evidence).get('state');local['failure_'+state]+=1
            source_binds['objects_without_complete_row_account_server_receipt']+=int('source_receipt' not in value)
            indexer.consume(meta,value)
            record.update(state='OWNER_VERIFIED',counts=dict(local));totals.update(local)
        except Exception as ex:
            code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else 'OWNER_SOURCE_'+type(ex).__name__
            record.update(state='UNKNOWN_ASSET_NOT_VERIFIED',exception_class=type(ex).__name__,safe_code=code);totals['unverified_assets']+=1
            indexer.unavailable(meta,code)
        receipts.append(record)
        if index%20==0:print(json.dumps({'phase':'PRESERVED_CHECKPOINT_INTEGRITY_READBACK','objects_inspected':index+1,'objects_total':len(unique)}),flush=True)
    # Compare overlap categories, without rewriting original interval ledger.
    conflict_ranges=[]
    for (sid,k),rows in spans.items():
        good=lambda z:z in ('CONFIRMED_COMPLETE','EMPTY_AUTHENTIC_RESPONSE','SESSION_CLOSED_SUPPORTED')
        events=sorted([(a,1,good(z),b,z) for a,b,z in rows]);active=[]
        for a,_,g,b,z in events:
            active=[x for x in active if x[0]>=a]
            for end,old_g,old_z in active:
                if g!=old_g:conflict_ranges.append({'key_sha256':sha(canonical((sid,k,a,min(end,b)))),'states':[z,old_z]})
            active.append((b,g,z))
    result={'schema':'mxm.owner.current.checkpoint.impact.inventory.v1','generation':1807,'journal_sha256':journal.get('last_checkpoint',{}).get('canonical_sha256'),'scope':'ALL_DIRECT_CURRENT_CHECKPOINT_DATA_RECORD_SNAPSHOT_INCREMENT_REFERENCES','expected_assets':len(unique),'asset_receipts':receipts,'counts':dict(totals),'wire_conflicts':collisions,'span_conflicts':conflict_ranges,'source_binding_limits':dict(source_binds),'historical_failed_import_inputs':'NOT_EXHAUSTIVELY_ENUMERATED_BY_CURRENT_MANIFEST','raw_response_identity':'LEGACY_MISSING_REQUEST_BINDINGS_REMAIN_UNKNOWN','original_artifacts_changed':False,'broker_requests':0,'new_outcomes':0,'alpha_certified':False}
    # Detailed key locators and counts are OWNER-only, never stdout plaintext.
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
    out=root/'verification';out.mkdir(exist_ok=True)
    private=out/'owner-impact.mxmenc';encrypt_shard(gzip.compress(canonical(result),mtime=0),public_key=root/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',output=private)
    public={'scope':result['scope'],'expected_assets':len(unique),'verified_assets':sum(r['state']=='OWNER_VERIFIED' for r in receipts),'unverified_assets':sum(r['state']!='OWNER_VERIFIED' for r in receipts),'private_inventory_ciphertext_sha256':sha(private.read_bytes()),'observed_integrity_counts':{'wire_conflicts':len(collisions),'overlapping_span_conflict_candidates':len(conflict_ranges),'invalid_finite_or_volume':totals.get('invalid_finite_or_volume',0),'invalid_bar_clock':totals.get('invalid_bar_clock',0),'out_of_domain_tick':totals.get('out_of_domain_tick',0),'failure_evidence_unbound':totals.get('failure_EVIDENCE_UNBOUND',0)},'failure_categories':dict(Counter(r.get('safe_code','UNCLASSIFIED') for r in receipts if r['state']!='OWNER_VERIFIED')),'historical_impact_closed':False,'no_global_clean_claim':True,'broker_requests':0,'new_outcomes':0}
    (out/'owner-impact-summary.json').write_text(json.dumps(public,sort_keys=True)+'\n')
    from .resolution import write_private,public_summary
    from .owner import bounded_decrypt
    detailed=indexer.finish()
    private_proof=write_private(detailed,root,key,tmp,bounded_decrypt)
    resolution=public_summary(detailed,private_proof)
    (out/'resolution-summary.json').write_text(json.dumps(resolution,sort_keys=True)+'\n')
    public['resolution']=resolution
    return public

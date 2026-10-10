"""Distinct owner-authorized RV joint moment comparison; no broker acquisition."""
import json,os,pathlib,tempfile
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.variance_kernel_v1 import evaluate,merge
from research_core_v4.owner_recovery_v1.runtime_v1 import gate
e=rt.e
PHASE='GATE'

def main():
    global PHASE
    os.umask(0o077);head,auth=gate('variance');master,entries,digits,manifest=e.w.old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-variance-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'KEY_BINDING')
        PHASE='SOURCE_READ'
        rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);assets={x['name']:x for x in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')}
        result=[];provenance=[];rowcount=0
        # Group-first keeps complete four-week history for at most 64 identities.
        for group in range(25):
            buffers={ordinal:{} for ordinal in range(group*64+1,min(1576,group*64+64)+1)}
            for segment in range(1,5):
                entry=entries[(segment-1)*25+group];asset=assets[entry['ENCRYPTED_ASSET_NAME']]
                e.w.old.need(asset['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'SOURCE_ASSET_BINDING')
                blob=e.w.old.download(asset['browser_download_url'],asset['size']);e.w.old.need(e.a.sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'SOURCE_CIPHER_BYTES')
                raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp);e.w.old.need(e.a.sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'SOURCE_PLAIN_BYTES')
                obj=e.w.n.canonical.strict_json(raw);e.w.old.need(e.w.n.canonical.canonical(obj)==raw and set(obj)==e.w.n.canonical.PACKAGE_KEYS and obj['segment_index']==segment and obj['shard_index']==group and obj['identity_range']==entry['IDENTITY_RANGE'],'SOURCE_PACKAGE')
                lo,hi=entry['IDENTITY_RANGE'];e.w.old.need(len(obj['items'])==hi-lo+1,'SOURCE_ITEMS');count=0
                for ordinal,item in zip(range(lo,hi+1),obj['items']):
                    e.w.old.need(item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'] and item['failure'] is None,'SOURCE_IDENTITY')
                    previous=-1
                    for row in item['rows']:
                        ts,bar=e.w.n._bar(row,digits[item['symbol_id']]);e.w.old.need(ts>previous and ts not in buffers[ordinal] and (ts-e.w.n.START)//604800==segment-1,'SOURCE_ROW_ORDER');previous=ts;buffers[ordinal][ts]=bar;count+=1
                e.w.old.need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'SOURCE_COUNTS');rowcount+=count
                provenance.append({'segment':segment,'shard':group,'ciphertext_sha256':entry['ENCRYPTED_ASSET_SHA256'],'canonical_sha256':entry['PLAINTEXT_CANONICAL_SHA256'],'rows':count})
            PHASE='PREQUENTIAL_EVALUATION'
            for ordinal,bars in buffers.items():result.append({'ordinal':ordinal,'symbol_id':master[ordinal-1]['symbol_id'],'symbol':master[ordinal-1]['symbol'],'asset_class':master[ordinal-1]['asset_class'],'rows':len(bars),'result':evaluate(bars)})
            del buffers;PHASE='SOURCE_READ';e.w.old.budget(maxwall=1500,maxcpu=1200,maxkib=2097152)
        e.w.old.need(rowcount==3355389 and len(provenance)==100 and len(result)==1576,'COMPLETE_FRONTIER_COUNTS')
        allweeks=merge(result);byclass={c:merge([x for x in result if x['asset_class']==c]) for c in sorted({x['asset_class'] for x in result})}
        design=json.loads((e.a.ROOT/('research_core_v4/owner_recovery_v1/VARIANCE_DESIGN_V1.json')).read_text())
        summary={'schema':'mxm.private.rv.joint.moment.frontier.summary.v1','identities':1576,'shards':100,'rows':rowcount,'new_information_comparisons':1,'four_weeks':allweeks,'by_asset_class':byclass,'all_identity_week_counts':[{'ordinal':x['ordinal'],'symbol_id':x['symbol_id'],'four_weeks':x['result']['four_weeks']} for x in result],'design':design,'status':'EXPLORATORY_DEVELOPMENT_ONLY','costs':'UNRESOLVED','scientific_significance_claimed':False,'independent_confirmation':False,'protected_forward':False,'broker_requests':0,'orders':0,'gross_directional_references_are_fills':False,'selection_history':'ADDITIONAL_DEVELOPMENT_SELECTION;ALL_PREVIOUS_CLOSURES_PRESERVED'}
        PHASE='DELIVERY';rt.output(head,auth,tmp,key,'variance',{'summary':summary,'identities':result,'input_provenance':provenance},summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None

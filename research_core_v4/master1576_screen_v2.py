"""Deterministic structural worker; real route requires a separate hash-bound ARM.

No broker API, prices in outputs, predictive response or ranking. Input OHLC exists
only transiently for canonical integrity. One encrypted shard is processed at a time.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import urllib.request
import zlib
from research_core_v4.quote_scope_metadata_v1 import classify as accepted_metadata_classifier

BASE = '227409d11a96c7365d17c9d3bbdeb9ce0b7c53f2'
S = 'research_core_v4/state/'
ACCEPTANCE = S+'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json'
PROTOCOL = S+'MASTER1576_POST_SHALLOW_OUTCOME_BLIND_DEEP_HISTORICAL_M5_QUALIFICATION_PROTOCOL_V2.json'
WORKER = 'research_core_v4/master1576_screen_v2.py'
PREFLIGHT = S+'MASTER1576_QUALIFICATION_V2_SYNTHETIC_PREFLIGHT_RESULT_V1.json'
MAGIC = b'MXM_SHALLOW_M5_V2_ENC1\x00'
ROW_KEYS = {'time_utc','open','high','low','close','tick_volume'}
ITEM_KEYS = {'ordinal','symbol_id','classification','request_count','retry_count','page_cap_hits','failure','transport_geometry_pages','rows'}
PACKAGE_KEYS = {'schema','segment_index','shard_index','identity_range','items'}
SEGMENTS = [('2026-08-20T00:00:00Z','2026-08-26T23:55:00Z'),('2026-08-27T00:00:00Z','2026-09-02T23:55:00Z'),('2026-09-03T00:00:00Z','2026-09-09T23:55:00Z'),('2026-09-10T00:00:00Z','2026-09-16T23:55:00Z')]
PROTECTED = '2026-09-17T12:02:58Z'
RESULT_FIELDS = {'schema','protocol_sha256','campaign_acceptance_sha256','final_manifest_sha256','master_sha256','release_identity','processed_asset_count','processed_canonical_row_count','identity_count','classification_counts','eligible_count','identities','execution_scope'}
IDENTITY_FIELDS = {'MASTER_ORDINAL','SYMBOL_ID','BROKER_NATIVE_CONTEXT','TOTAL_ROW_COUNT','ROW_COUNT_BY_SEGMENT','FIRST_TIMESTAMP','LAST_TIMESTAMP','ACTIVE_CALENDAR_DAY_COUNT','OBSERVED_GAP_GEOMETRY','SEGMENT_PRESENCE','TICK_VOLUME_PRESENT','NONZERO_TICK_VOLUME_COUNT','NONZERO_TICK_VOLUME_FRACTION','DATA_INTEGRITY_STATUS','CURRENT_METADATA_GATE_STATUS','EUR200_STRUCTURAL_GATE_STATUS','V2_CLASSIFICATION','COMPLETE_REASON_LEDGER'}
GAP_FIELDS = {'histogram_minutes','maximum_minutes','interval_count'}
REASON_FIELDS = {'hard_gates_pass','cost_status','descriptive_non_gating','late_start_proven','codes'}

class ScreenError(ValueError):
    """Only fixed, price-free error codes may leave the worker."""
    def __init__(self, code): self.code=code; super().__init__(code)
def require(ok, code):
    if not ok: raise ScreenError(code)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
def integer(v): return type(v) is int

def strict_json(raw):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'DUPLICATE_JSON_KEY'); result[k]=v
        return result
    try: return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ScreenError('NONFINITE_JSON')))
    except ScreenError: raise
    except Exception: raise ScreenError('MALFORMED_PACKAGE') from None

def timestamp(s):
    require(isinstance(s,str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',s) is not None,'MALFORMED_TIMESTAMP')
    try: return int(datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())
    except Exception: raise ScreenError('MALFORMED_TIMESTAMP') from None

def command(args, *, input=None):
    try:
        r=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,check=False)
        require(r.returncode==0,'CRYPTO_FAILURE');return r.stdout
    except ScreenError: raise
    except Exception: raise ScreenError('CRYPTO_FAILURE') from None

def decrypt_package(package, *, private_key, expected_public_spki_sha256, temp_parent=None):
    """Existing RSA-OAEP-SHA256/OpenPGP AES256 route; cleanup on every exit."""
    require(package.startswith(MAGIC) and len(package)>len(MAGIC)+4,'MALFORMED_ENCRYPTED_PACKAGE')
    pos=len(MAGIC); n=struct.unpack('>I',package[pos:pos+4])[0];pos+=4
    require(n>0 and pos+n<len(package),'MALFORMED_ENCRYPTED_PACKAGE')
    pub=command(['openssl','pkey','-in',str(private_key),'-pubout','-outform','DER'])
    require(sha(pub)==expected_public_spki_sha256,'PRIVATE_ROUTE_KEY_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='mxm-screen-v2-',dir=temp_parent) as td:
        td=Path(td);os.chmod(td,0o700);home=td/'gnupg';home.mkdir(mode=0o700)
        try:
            wrapped=td/'wrapped';cipher=td/'cipher';passfile=td/'pass';plain=td/'plain'
            wrapped.write_bytes(package[pos:pos+n]);cipher.write_bytes(package[pos+n:])
            command(['openssl','pkeyutl','-decrypt','-inkey',str(private_key),'-in',str(wrapped),'-out',str(passfile),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'])
            os.chmod(passfile,0o600)
            command(['gpg','--homedir',str(home),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(passfile),'--output',str(plain),'--decrypt',str(cipher)])
            os.chmod(plain,0o600);return plain.read_bytes()
        finally:
            try: subprocess.run(['gpgconf','--homedir',str(home),'--kill','gpg-agent'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)
            except Exception: pass

class BoundScreen:
    """Same reducer for full synthetic 1576 campaign and future authorized real input."""
    def __init__(self, *, master, entries, metadata, digits, bindings, late_start_evidence=None):
        require(len(master)==1576 and len({x['symbol_id'] for x in master})==1576,'MASTER_INTEGRITY_FAILURE')
        require([x['symbol_id'] for x in master]==sorted(x['symbol_id'] for x in master),'MASTER_ORDER_FAILURE')
        require(len(entries)==100,'ASSET_INVENTORY_FAILURE')
        require([(e['SEGMENT_INDEX'],e['SHARD_INDEX']) for e in entries]==[(s,k) for s in range(1,5) for k in range(25)],'ASSET_ORDER_FAILURE')
        require(len({e['ENCRYPTED_ASSET_NAME'] for e in entries})==100,'ASSET_INVENTORY_FAILURE')
        require(set(metadata)=={x['symbol_id'] for x in master} and set(digits)==set(metadata),'METADATA_IDENTITY_FAILURE')
        self.master=master;self.entries=entries;self.metadata=metadata;self.digits=digits;self.bindings=bindings
        self.late=late_start_evidence or {};self.next_index=0;self.total=0
        self.summaries=[None]*1576;self.day_sets=[set() for _ in master]
        self.session_counts=[Counter() for _ in master];self.segment_active_days=[[] for _ in master]
        self.late_start={}
        # Evidence may only be supplied from a hash-bound authority in the real loader.
        for sid,e in self.late.items():
            require(sid in metadata and set(e)=={'start_utc','authority_ref','authority_sha256'} and e['authority_ref'] and re.fullmatch('[0-9a-f]{64}',e['authority_sha256']) is not None,'LATE_START_EVIDENCE_FAILURE')
            self.late_start[sid]=timestamp(e['start_utc'])
    def consume(self, package, *, decrypt):
        require(self.next_index<100,'EXTRA_ASSET');entry=self.entries[self.next_index]
        require(isinstance(package,bytes) and sha(package)==entry['ENCRYPTED_ASSET_SHA256'],'ENCRYPTED_HASH_FAILURE')
        raw=None;obj=None
        try:
            raw=decrypt(package)
            require(isinstance(raw,bytes) and sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'PLAINTEXT_HASH_FAILURE')
            obj=strict_json(raw);require(canonical(obj)==raw,'NONCANONICAL_PACKAGE')
            self._consume_object(obj,entry)
        finally:
            # No plaintext file is created by this reducer; crypto adapter owns cleanup.
            if isinstance(obj,dict):obj.clear()
            raw=None;obj=None
        self.next_index+=1
    def _consume_object(self,obj,e):
        require(isinstance(obj,dict) and set(obj)==PACKAGE_KEYS and obj['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1','PACKAGE_SCHEMA_FAILURE')
        s=e['SEGMENT_INDEX'];k=e['SHARD_INDEX'];lo=k*64+1;hi=min(1576,lo+63)
        require(integer(obj['segment_index']) and integer(obj['shard_index']) and obj['segment_index']==s and obj['shard_index']==k and obj['identity_range']==[lo,hi] and e['IDENTITY_RANGE']==[lo,hi],'SEGMENT_BINDING_FAILURE')
        items=obj['items'];require(isinstance(items,list) and len(items)==hi-lo+1,'IDENTITY_BINDING_FAILURE')
        n=0;first=None;last=None;requests=0
        pending=[]
        for ordinal,item in zip(range(lo,hi+1),items):
            identity=self.master[ordinal-1]
            require(isinstance(item,dict) and set(item)==ITEM_KEYS,'ITEM_SCHEMA_FAILURE')
            require(integer(item['ordinal']) and integer(item['symbol_id']) and item['ordinal']==ordinal and item['symbol_id']==identity['symbol_id'],'IDENTITY_BINDING_FAILURE')
            require(item['failure'] is None and item['retry_count']==0 and item['page_cap_hits']==0 and integer(item['request_count']) and item['request_count']>=1,'ACQUISITION_COMPLETION_FAILURE')
            require(isinstance(item['transport_geometry_pages'],list),'ITEM_SCHEMA_FAILURE')
            rows=item['rows'];require(isinstance(rows,list),'ROW_SCHEMA_FAILURE')
            require(item['classification']==('SHALLOW_SUPPORT_COMPLETE' if rows else 'NO_HISTORICAL_SUPPORT'),'ACQUISITION_COMPLETION_FAILURE')
            summary,days,hours=self._rows(rows,s,self.digits[identity['symbol_id']])
            n+=summary['count'];requests+=item['request_count']
            if summary['first'] is not None:
                first=min(first or summary['first'],summary['first']);last=max(last or summary['last'],summary['last'])
            pending.append((ordinal,summary,days,hours))
        require(n==e['ROW_COUNT'] and first==e['FIRST_TIMESTAMP'] and last==e['LAST_TIMESTAMP'] and requests==e['REQUEST_COUNT'] and e['RETRY_COUNT']==0 and e['PAGE_CAP_HITS']==0 and e['FAILURE_LEDGER']=={} and e['PROTECTED_FORWARD_ROW_COUNT']==0,'MANIFEST_RECONCILIATION_FAILURE')
        # Commit summary state only after the entire shard verifies.
        for ordinal,summary,days,hours in pending:
            ix=ordinal-1
            if self.summaries[ix] is None:self.summaries[ix]=[]
            require(len(self.summaries[ix])==s-1,'SEGMENT_ORDER_FAILURE')
            self.summaries[ix].append(summary);self.day_sets[ix].update(days);self.session_counts[ix].update(hours);self.segment_active_days[ix].append(len(days))
        self.total+=n
    def _rows(self,rows,s,digits):
        start,end=map(timestamp,SEGMENTS[s-1]);protected=timestamp(PROTECTED)
        require(integer(digits) and 0<=digits<=15,'DIGITS_BINDING_FAILURE')
        previous=None;seen=set();days=set();hours=Counter();gaps=Counter();positive=0
        for r in rows:
            require(isinstance(r,dict) and set(r)==ROW_KEYS,'ROW_SCHEMA_FAILURE');t=timestamp(r['time_utc'])
            require(t<protected,'PROTECTED_FORWARD_FAILURE')
            require(start<=t<=end,'OUT_OF_INTERVAL_FAILURE');require(t%300==0,'M5_ALIGNMENT_FAILURE')
            require(t not in seen,'DUPLICATE_TIMESTAMP_FAILURE');require(previous is None or t>previous,'TIMESTAMP_ORDER_FAILURE');seen.add(t)
            vals={}
            for key in ['open','high','low','close']:
                value=r[key];require(isinstance(value,str) and re.fullmatch(r'-?\d+(?:\.\d+)?',value) is not None,'MALFORMED_CANONICAL_ROW')
                try: dec=Decimal(value)
                except InvalidOperation: raise ScreenError('MALFORMED_CANONICAL_ROW') from None
                require(dec.is_finite() and format(abs(dec) if dec==0 else dec,f'.{digits}f')==value,'MALFORMED_CANONICAL_ROW');vals[key]=dec
            require(vals['low']<=vals['open']<=vals['high'] and vals['low']<=vals['close']<=vals['high'],'OHLC_INVARIANT_FAILURE')
            v=r['tick_volume'];require(isinstance(v,str) and re.fullmatch(r'0|[1-9]\d*',v) is not None,'MALFORMED_CANONICAL_ROW');positive+=int(int(v)>0)
            days.add(r['time_utc'][:10]);dt=datetime.fromtimestamp(t,timezone.utc);hours[f'{dt.weekday()}:{dt.hour:02d}']+=1
            if previous is not None:gaps[(t-previous)//60]+=1
            previous=t
        return {'count':len(rows),'first':rows[0]['time_utc'] if rows else None,'last':rows[-1]['time_utc'] if rows else None,'positive':positive,'gaps':{'histogram_minutes':{str(k):v for k,v in sorted(gaps.items())},'maximum_minutes':max(gaps,default=None),'interval_count':sum(gaps.values())}},days,hours
    def finish(self):
        require(self.next_index==100,'INCOMPLETE_CAMPAIGN');out=[];counts=Counter();eligible=0
        for ordinal,identity in enumerate(self.master,1):
            ix=ordinal-1;parts=self.summaries[ix];require(parts is not None and len(parts)==4,'INCOMPLETE_IDENTITY')
            m=self.metadata[identity['symbol_id']]
            try:
                gate=accepted_metadata_classifier(identity,m.get('current_light_metadata'),m.get('current_full_metadata'),m.get('expected_margin'),'EUR')
            except Exception: gate={'status':'METADATA_INSUFFICIENT'}
            status=gate['status'];n=sum(x['count'] for x in parts);positive=sum(x['positive'] for x in parts)
            late=identity['symbol_id'] in self.late_start and self.late_start[identity['symbol_id']]>timestamp(SEGMENTS[0][0])
            if late and n:
                require(timestamp(min(x['first'] for x in parts if x['first']))>=self.late_start[identity['symbol_id']],'LATE_START_EVIDENCE_CONTRADICTION')
            hard_pass=status=='STRUCTURALLY_ELIGIBLE' and n>=1
            if status in ('STRUCTURALLY_INELIGIBLE','ECONOMICALLY_UNEXECUTABLE_FOR_EUR200'):cls='STRUCTURALLY_INFEASIBLE_FOR_CURRENT_EUR200_CONSTRAINT'
            elif status!='STRUCTURALLY_ELIGIBLE':cls='EXECUTION_OR_FRICTION_METADATA_LIMITED'
            elif late:cls='COLD_START_OR_LATE_JOIN_NOT_REJECTED'
            elif n==0:cls='SUPPORT_LIMITED_NOT_REJECTED'
            else:cls='QUALIFIED_FOR_DEEP_HISTORICAL_M5'
            eligible+=int(hard_pass);counts[cls]+=1
            out.append({'MASTER_ORDINAL':ordinal,'SYMBOL_ID':identity['symbol_id'],'BROKER_NATIVE_CONTEXT':identity['asset_class'],'TOTAL_ROW_COUNT':n,'ROW_COUNT_BY_SEGMENT':[x['count'] for x in parts],'FIRST_TIMESTAMP':min((x['first'] for x in parts if x['first']),default=None),'LAST_TIMESTAMP':max((x['last'] for x in parts if x['last']),default=None),'ACTIVE_CALENDAR_DAY_COUNT':len(self.day_sets[ix]),'OBSERVED_GAP_GEOMETRY':[x['gaps'] for x in parts],'SEGMENT_PRESENCE':[x['count']>0 for x in parts],'TICK_VOLUME_PRESENT':n>0,'NONZERO_TICK_VOLUME_COUNT':positive,'NONZERO_TICK_VOLUME_FRACTION':positive/n if n else None,'DATA_INTEGRITY_STATUS':'PASS','CURRENT_METADATA_GATE_STATUS':status,'EUR200_STRUCTURAL_GATE_STATUS':'PASS' if status=='STRUCTURALLY_ELIGIBLE' else ('FAIL' if status in ('STRUCTURALLY_INELIGIBLE','ECONOMICALLY_UNEXECUTABLE_FOR_EUR200') else 'UNRESOLVED'),'V2_CLASSIFICATION':cls,'COMPLETE_REASON_LEDGER':{'hard_gates_pass':hard_pass,'cost_status':'COST_UNRESOLVED','descriptive_non_gating':{'active_days_by_segment':self.segment_active_days[ix],'session_timestamp_distribution_utc_weekday_hour':dict(sorted(self.session_counts[ix].items())),'activity_distribution':{'zero_tick_volume_bars':n-positive,'nonzero_tick_volume_bars':positive}},'late_start_proven':late,'codes':[status,'AUTHENTIC_SUPPORT_PRESENT' if n else 'ZERO_AUTHENTIC_ROWS', 'AUTHORITATIVE_LATE_START' if late else 'NO_AUTHORITATIVE_LATE_START','COST_UNRESOLVED_DEFERRED_NOT_ACQUISITION_BLOCKER']}})
        result={'schema':'mxm.v4.master1576.structural-screen-result.v2',**self.bindings,'processed_asset_count':100,'processed_canonical_row_count':self.total,'identity_count':1576,'classification_counts':dict(sorted(counts.items())),'eligible_count':eligible,'identities':out,'execution_scope':'STRUCTURAL_ACQUISITION_ELIGIBILITY_ONLY_NOT_INFORMATION_OR_ECONOMIC_CERTIFICATION'}
        validate_output(result);return result

def validate_output(result):
    require(set(result)==RESULT_FIELDS and len(result['identities'])==1576,'OUTPUT_SCHEMA_FAILURE')
    for r in result['identities']:
        require(set(r)==IDENTITY_FIELDS and set(r['COMPLETE_REASON_LEDGER'])==REASON_FIELDS,'OUTPUT_SCHEMA_FAILURE')
        require(set(r['COMPLETE_REASON_LEDGER']['descriptive_non_gating'])=={'active_days_by_segment','session_timestamp_distribution_utc_weekday_hour','activity_distribution'},'OUTPUT_SCHEMA_FAILURE')
        require(set(r['COMPLETE_REASON_LEDGER']['descriptive_non_gating']['activity_distribution'])=={'zero_tick_volume_bars','nonzero_tick_volume_bars'},'OUTPUT_SCHEMA_FAILURE')
        for g in r['OBSERVED_GAP_GEOMETRY']:require(set(g)==GAP_FIELDS,'OUTPUT_SCHEMA_FAILURE')

# Real configuration is loaded only after explicit separate ARM verification.
def load_real_context(root):
    root=Path(root);praw=(root/PROTOCOL).read_bytes();p=strict_json(praw)
    require(p['status']=='FROZEN_PREOUTCOME_EXECUTABLE_NOT_EXECUTED_PENDING_INDEPENDENT_AUDIT','PROTOCOL_BINDING_FAILURE')
    for b in p['bindings'].values():require(sha((root/b['ref']).read_bytes())==b['sha256'],'AUTHORITY_HASH_FAILURE')
    a=strict_json((root/ACCEPTANCE).read_bytes());f=strict_json((root/a['final_manifest']['ref']).read_bytes())
    require(len(f['entries'])==100 and f['status']=='COMPLETE','MANIFEST_RECONCILIATION_FAILURE')
    allentries=[]
    for b in a['segment_manifests']:
        raw=(root/b['ref']).read_bytes();require(sha(raw)==b['sha256'],'AUTHORITY_HASH_FAILURE');d=strict_json(raw);require(d['status']=='COMPLETE','MANIFEST_RECONCILIATION_FAILURE');allentries+=d['entries']
    require(allentries==f['entries'],'MANIFEST_RECONCILIATION_FAILURE')
    master=strict_json((root/p['bindings']['master']['ref']).read_bytes())
    require(sha(canonical(master).rstrip(b'\n'))==f['MASTER_SHA256'],'MASTER_INTEGRITY_FAILURE')
    inv={x['name']:x for x in a['exact_release_inventory']['assets']}
    for e in f['entries']:
        require(e['ENCRYPTED_ASSET_NAME'] in inv and inv[e['ENCRYPTED_ASSET_NAME']]['digest']=='sha256:'+e['ENCRYPTED_ASSET_SHA256'],'ASSET_INVENTORY_FAILURE')
    loc=strict_json(zlib.decompress(base64.b64decode((root/p['bindings']['metadata']['ref']).read_bytes())))
    require(loc['deposit_asset']=='EUR' and loc['frontier_identity_sha256']==f['MASTER_SHA256'] and len(loc['rows'])==1576 and len({x['symbol_id'] for x in loc['rows']})==1576,'METADATA_IDENTITY_FAILURE')
    dm=strict_json((root/p['bindings']['digits']['ref']).read_bytes())
    metadata={x['symbol_id']:x for x in loc['rows']};digits={x['symbol_id']:x['digits'] for x in dm['entries']}
    bindings={'protocol_sha256':sha(praw),'campaign_acceptance_sha256':sha((root/ACCEPTANCE).read_bytes()),'final_manifest_sha256':a['final_manifest']['sha256'],'master_sha256':f['MASTER_SHA256'],'release_identity':f['DURABLE_RELEASE_IDENTITY']}
    return BoundScreen(master=master,entries=f['entries'],metadata=metadata,digits=digits,bindings=bindings),p,a

def verify_arm(root,arm_path):
    root=Path(root);require(Path(arm_path).is_file(),'SEPARATE_REAL_AUTHORIZATION_REQUIRED');arm=strict_json(Path(arm_path).read_bytes())
    keys={'schema','status','execution_head','protocol_sha256','worker_sha256','preflight_sha256','campaign_acceptance_sha256','output_path'}
    require(set(arm)==keys and arm['schema']=='mxm.v4.master1576.structural-screen-real-arm.v1' and arm['status']=='AUTHORIZED_ONCE_STRUCTURAL_SCREEN_ONLY','SEPARATE_REAL_AUTHORIZATION_REQUIRED')
    for field,path in [('protocol_sha256',PROTOCOL),('worker_sha256',WORKER),('preflight_sha256',PREFLIGHT),('campaign_acceptance_sha256',ACCEPTANCE)]:require(arm[field]==sha((root/path).read_bytes()),'ARM_HASH_FAILURE')
    pre=strict_json((root/PREFLIGHT).read_bytes());require(pre['tests_failed']==0 and pre['status']=='PASS_SYNTHETIC_ONLY_NO_REAL_DECRYPTION','PREFLIGHT_NOT_PASS')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();require(head==arm['execution_head'],'ARM_HEAD_FAILURE')
    live=subprocess.check_output(['git','ls-remote','https://github.com/mariancradulescu/mxm-quant-greenfield.git','refs/heads/performance-research-v3-20260922'],text=True).split()[0];require(live==head,'BRANCH_DRIFT')
    output=Path(arm['output_path']);require(not output.exists(),'RESULT_ALREADY_EXISTS');return arm,output

def download_asset(name,release):
    require(re.fullmatch(r'shallow-m5-v2-seg[1-4]-shard\d{2}\.mxmenc',name) is not None,'ASSET_INVENTORY_FAILURE')
    url=f'https://github.com/mariancradulescu/mxm-quant-greenfield/releases/download/{release}/{name}'
    try:
        with urllib.request.urlopen(url,timeout=60) as response:return response.read()
    except Exception:raise ScreenError('GITHUB_ASSET_DOWNLOAD_FAILURE') from None

def run_authorized(root,arm_path):
    """No real ARM is created or consumed by synthetic preflight."""
    root=Path(root);arm,output=verify_arm(root,arm_path);screen,p,a=load_real_context(root)
    require(screen.bindings['release_identity']==p['release_identity'],'RELEASE_BINDING_FAILURE')
    lock=output.with_name(output.name+'.attempt-lock');lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ScreenError('ATTEMPT_ALREADY_STARTED') from None
    os.close(fd)
    # Existing private-route name; never use any cTrader credential.
    require(bool(os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','')),'PRIVATE_ROUTE_UNAVAILABLE')
    with tempfile.TemporaryDirectory(prefix='mxm-screen-v2-key-') as td:
        from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
        try:key,fingerprint=_private_key_from_secret(Path(td))
        except Exception:raise ScreenError('PRIVATE_ROUTE_KEY_MISMATCH') from None
        require(fingerprint==p['public_spki_sha256'],'PRIVATE_ROUTE_KEY_MISMATCH')
        for e in screen.entries:
            raw=download_asset(e['ENCRYPTED_ASSET_NAME'],screen.bindings['release_identity'])
            inventory={v['name']:v for v in a['exact_release_inventory']['assets']}
            require(len(raw)==inventory[e['ENCRYPTED_ASSET_NAME']]['size'],'ENCRYPTED_ASSET_SIZE_FAILURE')
            screen.consume(raw,decrypt=lambda b:decrypt_package(b,private_key=key,expected_public_spki_sha256=p['public_spki_sha256']));raw=None
        result=screen.finish()
        require(result['processed_canonical_row_count']==a['totals']['canonical_M5_rows'],'MANIFEST_RECONCILIATION_FAILURE')
    tmp=output.with_name(output.name+'.tmp')
    try:
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as file:file.write(canonical(result));file.flush();os.fsync(file.fileno())
        os.replace(tmp,output)
    finally:tmp.unlink(missing_ok=True)
    return {'status':'COMPLETE_STRUCTURAL_SCREEN','result_sha256':sha(output.read_bytes())}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));parser.add_argument('--arm',required=True);args=parser.parse_args()
    try:print(json.dumps(run_authorized(args.root,args.arm),sort_keys=True))
    except ScreenError as e:print(json.dumps({'status':'FAILED_CLOSED','code':e.code}));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())

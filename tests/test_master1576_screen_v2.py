"""Synthetic-only encrypted format and full MASTER1576 screen preflight."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib
from research_core_v4 import master1576_screen_v2 as w
ROOT=Path(__file__).resolve().parents[1]

def read(path):return json.loads((ROOT/path).read_text())
def digest(path):return w.sha((ROOT/path).read_bytes())
def denied(*a,**kw):raise AssertionError('Network is prohibited in synthetic preflight')

def fixture(changes=None):
    """Use accepted roster/current metadata only; market rows are fabricated constants."""
    p=read(w.PROTOCOL);master=read(p['bindings']['master']['ref'])
    loc=json.loads(zlib.decompress(base64.b64decode((ROOT/p['bindings']['metadata']['ref']).read_bytes())))
    metadata={x['symbol_id']:copy.deepcopy(x) for x in loc['rows']}
    digits={x['symbol_id']:x['digits'] for x in read(p['bindings']['digits']['ref'])['entries']}
    entries=[];payloads=[]
    for segment in range(1,5):
        for shard in range(25):
            lo=shard*64+1;hi=min(1576,lo+63);items=[]
            for ordinal in range(lo,hi+1):
                sid=master[ordinal-1]['symbol_id'];digits_n=digits[sid];price=format(1,f'.{digits_n}f')
                rows=[{'time_utc':w.SEGMENTS[segment-1][0],'open':price,'high':price,'low':price,'close':price,'tick_volume':'0'}]
                item={'ordinal':ordinal,'symbol_id':sid,'classification':'SHALLOW_SUPPORT_COMPLETE','request_count':1,'retry_count':0,'page_cap_hits':0,'failure':None,'transport_geometry_pages':[],'rows':rows}
                if changes:changes(ordinal,segment,item,metadata[sid])
                item['classification']='SHALLOW_SUPPORT_COMPLETE' if item['rows'] else 'NO_HISTORICAL_SUPPORT'
                items.append(item)
            obj={'schema':'mxm.v4.shallow-m5-v2.raw-shard.v1','segment_index':segment,'shard_index':shard,'identity_range':[lo,hi],'items':items};raw=w.canonical(obj);cipher=b'SYNTHETIC_ONLY:'+raw
            rows=[r for item in items for r in item['rows']]
            entries.append({'SEGMENT_INDEX':segment,'SHARD_INDEX':shard,'IDENTITY_RANGE':[lo,hi],'ENCRYPTED_ASSET_NAME':f'shallow-m5-v2-seg{segment}-shard{shard:02d}.mxmenc','ENCRYPTED_ASSET_SHA256':w.sha(cipher),'PLAINTEXT_CANONICAL_SHA256':w.sha(raw),'ROW_COUNT':len(rows),'FIRST_TIMESTAMP':min((r['time_utc'] for r in rows),default=None),'LAST_TIMESTAMP':max((r['time_utc'] for r in rows),default=None),'REQUEST_COUNT':hi-lo+1,'RETRY_COUNT':0,'PAGE_CAP_HITS':0,'FAILURE_LEDGER':{},'PROTECTED_FORWARD_ROW_COUNT':0})
            payloads.append(cipher)
    bindings={'protocol_sha256':digest(w.PROTOCOL),'campaign_acceptance_sha256':digest(w.ACCEPTANCE),'final_manifest_sha256':p['bindings']['final_manifest']['sha256'],'master_sha256':read(w.ACCEPTANCE)['master1576_sha256'],'release_identity':'SYNTHETIC_ONLY_NOT_REAL_RELEASE'}
    return dict(master=master,entries=entries,metadata=metadata,digits=digits,bindings=bindings),payloads

def reduce_campaign(f,payloads,late=None):
    reducer=w.BoundScreen(**copy.deepcopy(f),late_start_evidence=late)
    for data in payloads:reducer.consume(data,decrypt=lambda b:b.removeprefix(b'SYNTHETIC_ONLY:'))
    return reducer.finish()

def mutate_first(f,payloads,mutator):
    f=copy.deepcopy(f);payloads=list(payloads);obj=json.loads(payloads[0].removeprefix(b'SYNTHETIC_ONLY:'));mutator(obj)
    raw=w.canonical(obj);payloads[0]=b'SYNTHETIC_ONLY:'+raw;f['entries'][0]['ENCRYPTED_ASSET_SHA256']=w.sha(payloads[0]);f['entries'][0]['PLAINTEXT_CANONICAL_SHA256']=w.sha(raw)
    return f,payloads

class SyntheticScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,cls.payloads=fixture()
    def setUp(self):
        self.socket_patch=patch('socket.socket',denied);self.url_patch=patch('urllib.request.urlopen',denied)
        self.socket_patch.start();self.url_patch.start()
    def tearDown(self):self.url_patch.stop();self.socket_patch.stop()
    def failure(self,code,f=None,data=None):
        reducer=w.BoundScreen(**copy.deepcopy(f or self.f));payload=data or self.payloads[0]
        with self.assertRaises(w.ScreenError) as ctx:reducer.consume(payload,decrypt=lambda b:b.removeprefix(b'SYNTHETIC_ONLY:'))
        self.assertEqual(ctx.exception.code,code);self.assertEqual(reducer.next_index,0)
    def test_01_qualified_all1576_zero_activity_zero_price_change(self):
        r=reduce_campaign(self.f,self.payloads)
        self.assertEqual(r['eligible_count'],1576);self.assertEqual(r['classification_counts'],{'QUALIFIED_FOR_DEEP_HISTORICAL_M5':1576});self.assertEqual(r['processed_asset_count'],100)
        self.assertTrue(all(x['NONZERO_TICK_VOLUME_FRACTION']==0 for x in r['identities']))
    def test_02_zero_row_support_limited(self):
        def changes(o,s,item,m):
            if o==1:item['rows']=[]
        f,p=fixture(changes);r=reduce_campaign(f,p);x=r['identities'][0]
        self.assertEqual(x['V2_CLASSIFICATION'],'SUPPORT_LIMITED_NOT_REJECTED');self.assertFalse(x['COMPLETE_REASON_LEDGER']['hard_gates_pass']);self.assertEqual(r['eligible_count'],1575)
    def test_03_authoritative_cold_start_zero_rows(self):
        def changes(o,s,item,m):
            if o==1:item['rows']=[]
        f,p=fixture(changes);sid=f['master'][0]['symbol_id'];r=reduce_campaign(f,p,{sid:{'start_utc':'2026-09-15T00:00:00Z','authority_ref':'synthetic-authoritative-listing-proof','authority_sha256':'a'*64}})
        self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'COLD_START_OR_LATE_JOIN_NOT_REJECTED');self.assertFalse(r['identities'][0]['COMPLETE_REASON_LEDGER']['hard_gates_pass'])
    def test_04_metadata_limited(self):
        f=copy.deepcopy(self.f);sid=f['master'][0]['symbol_id'];f['metadata'][sid]['current_full_metadata'].pop('minVolume');r=reduce_campaign(f,self.payloads)
        self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'EXECUTION_OR_FRICTION_METADATA_LIMITED');self.assertEqual(r['eligible_count'],1575)
    def test_05_margin_exact200_infeasible(self):
        f=copy.deepcopy(self.f);sid=f['master'][0]['symbol_id'];m=f['metadata'][sid]['expected_margin'];m['buyMargin']=str(200*10**int(m['moneyDigits']));r=reduce_campaign(f,self.payloads)
        self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'STRUCTURALLY_INFEASIBLE_FOR_CURRENT_EUR200_CONSTRAINT')
    def test_06_encrypted_hash_failure_before_decrypt(self):
        reducer=w.BoundScreen(**copy.deepcopy(self.f))
        with self.assertRaisesRegex(w.ScreenError,'ENCRYPTED_HASH_FAILURE'):reducer.consume(b'wrong',decrypt=denied)
    def test_07_plaintext_hash_failure(self):
        reducer=w.BoundScreen(**copy.deepcopy(self.f))
        with self.assertRaisesRegex(w.ScreenError,'PLAINTEXT_HASH_FAILURE'):reducer.consume(self.payloads[0],decrypt=lambda _:b'wrong')
    def test_08_duplicate_timestamp(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0]['rows'].append(copy.deepcopy(obj['items'][0]['rows'][0])));self.failure('DUPLICATE_TIMESTAMP_FAILURE',f,p[0])
    def test_09_out_of_interval(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0]['rows'][0].update(time_utc='2026-08-19T23:55:00Z'));self.failure('OUT_OF_INTERVAL_FAILURE',f,p[0])
    def test_10_protected_forward(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0]['rows'][0].update(time_utc='2026-09-17T12:05:00Z'));self.failure('PROTECTED_FORWARD_FAILURE',f,p[0])
    def test_11_wrong_identity(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0].update(symbol_id=999999));self.failure('IDENTITY_BINDING_FAILURE',f,p[0])
    def test_12_wrong_segment(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj.update(segment_index=2));self.failure('SEGMENT_BINDING_FAILURE',f,p[0])
    def test_13_malformed_price_fails_without_price_exception(self):
        for bad in ['NaN','Infinity','PRICE_SECRET','1.123456789123456789']:
            f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0]['rows'][0].update(open=bad));self.failure('MALFORMED_CANONICAL_ROW',f,p[0])
    def test_14_outputs_exclude_ohlc_returns_pnl(self):
        r=reduce_campaign(self.f,self.payloads);w.validate_output(r)
        for key in ['open','high','low','close','rows','forward_returns','pnl','sharpe','profit_factor','best_symbol_score']:
            self.assertNotIn('"'+key+'":',w.canonical(r).decode())
        bad=copy.deepcopy(r);bad['identities'][0]['open']='1.000';self.assertRaises(w.ScreenError,w.validate_output,bad)
    def test_15_repeatability_and_all_passers_order(self):
        r1=reduce_campaign(self.f,self.payloads);r2=reduce_campaign(self.f,self.payloads);self.assertEqual(w.canonical(r1),w.canonical(r2))
        self.assertEqual([x['SYMBOL_ID'] for x in r1['identities']],[x['symbol_id'] for x in self.f['master']])
    def test_16_single_segment_support_still_qualifies(self):
        def changes(o,s,item,m):
            if o==1 and s>1:item['rows']=[]
        f,p=fixture(changes);r=reduce_campaign(f,p);x=r['identities'][0]
        self.assertEqual(x['ROW_COUNT_BY_SEGMENT'],[1,0,0,0]);self.assertEqual(x['V2_CLASSIFICATION'],'QUALIFIED_FOR_DEEP_HISTORICAL_M5');self.assertEqual(r['eligible_count'],1576)
    def test_17_incomplete_campaign_no_partial_result(self):
        reducer=w.BoundScreen(**copy.deepcopy(self.f));reducer.consume(self.payloads[0],decrypt=lambda b:b.removeprefix(b'SYNTHETIC_ONLY:'));self.assertRaisesRegex(w.ScreenError,'INCOMPLETE_CAMPAIGN',reducer.finish)
    def test_18_exact_minimum_volume_alignment(self):
        f=copy.deepcopy(self.f);sid=f['master'][0]['symbol_id'];m=f['metadata'][sid]['current_full_metadata'];m['minVolume']=str(int(m['minVolume'])+1);r=reduce_campaign(f,self.payloads)
        self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'EXECUTION_OR_FRICTION_METADATA_LIMITED')
    def test_19_min_margin_below200_passes_existing_gate(self):
        f=copy.deepcopy(self.f);sid=f['master'][0]['symbol_id'];m=f['metadata'][sid]['expected_margin'];d=int(m['moneyDigits']);m['buyMargin']=str(200*10**d-1);m['sellMargin']=m['buyMargin'];r=reduce_campaign(f,self.payloads)
        self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'QUALIFIED_FOR_DEEP_HISTORICAL_M5')
    def test_20_first_observed_timestamp_never_implies_late_start(self):
        def changes(o,s,item,m):
            if o==1 and s<4:item['rows']=[]
        f,p=fixture(changes);r=reduce_campaign(f,p);self.assertFalse(r['identities'][0]['COMPLETE_REASON_LEDGER']['late_start_proven']);self.assertEqual(r['identities'][0]['V2_CLASSIFICATION'],'QUALIFIED_FOR_DEEP_HISTORICAL_M5')
    def test_21_real_route_requires_absent_separate_arm(self):
        with patch.dict('os.environ',{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'DO_NOT_READ'}):
            self.assertRaisesRegex(w.ScreenError,'SEPARATE_REAL_AUTHORIZATION_REQUIRED',w.run_authorized,ROOT,ROOT/'no-real-screen-arm.json')
    def test_22_manifest_row_count_failure(self):
        f=copy.deepcopy(self.f);f['entries'][0]['ROW_COUNT']+=1;self.failure('MANIFEST_RECONCILIATION_FAILURE',f)
    def test_23_timestamp_order_and_m5_alignment(self):
        f,p=mutate_first(self.f,self.payloads,lambda obj:obj['items'][0]['rows'][0].update(time_utc='2026-08-20T00:01:00Z'));self.failure('M5_ALIGNMENT_FAILURE',f,p[0])
    def test_24_unknown_cost_is_deferred_not_zero(self):
        r=reduce_campaign(self.f,self.payloads);self.assertEqual(r['eligible_count'],1576);self.assertTrue(all(x['COMPLETE_REASON_LEDGER']['cost_status']=='COST_UNRESOLVED' for x in r['identities']))
    def test_25_signed_canonical_prices_follow_decoder_contract(self):
        def changes(o,s,item,m):
            if o==1:
                for key in ['open','high','low','close']:item['rows'][0][key]='-'+item['rows'][0][key]
        f,p=fixture(changes);r=reduce_campaign(f,p);self.assertEqual(r['eligible_count'],1576)

class SyntheticCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='mxm-synthetic-v2-');cls.root=Path(cls.tmp.name);cls.key=cls.root/'synthetic-private.pem'
        w.command(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(cls.key)]);cls.key.chmod(0o600)
        cls.public=cls.root/'synthetic-public.pem';cls.public.write_bytes(w.command(['openssl','pkey','-in',str(cls.key),'-pubout']))
        cls.fp=w.sha(w.command(['openssl','pkey','-in',str(cls.key),'-pubout','-outform','DER']))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def encrypt(self,plain):
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            p=Path(td);home=p/'gnupg';home.mkdir(mode=0o700);(p/'plain').write_bytes(plain);(p/'pass').write_bytes(base64.urlsafe_b64encode(b'X'*32)+b'\n')
            try:
                w.command(['gpg','--homedir',str(home),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(p/'pass'),'--symmetric','--cipher-algo','AES256','--force-mdc','--output',str(p/'cipher'),str(p/'plain')])
                w.command(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(self.public),'-in',str(p/'pass'),'-out',str(p/'wrapped'),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'])
                wrapped=(p/'wrapped').read_bytes();return w.MAGIC+struct.pack('>I',len(wrapped))+wrapped+(p/'cipher').read_bytes()
            finally:subprocess.run(['gpgconf','--homedir',str(home),'--kill','gpg-agent'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    def test_26_existing_encryption_format_roundtrip_and_cleanup(self):
        before=set(self.root.iterdir());plain=b'SYNTHETIC ONLY NO MARKET DATA';pack=self.encrypt(plain)
        self.assertEqual(w.decrypt_package(pack,private_key=self.key,expected_public_spki_sha256=self.fp,temp_parent=self.root),plain);self.assertEqual(set(self.root.iterdir()),before)
    def test_27_crypto_failure_cleanup(self):
        pack=self.encrypt(b'SYNTHETIC ONLY');pack=pack[:-12]+b'BAD-CIPHER!!';before=set(self.root.iterdir())
        self.assertRaisesRegex(w.ScreenError,'CRYPTO_FAILURE',w.decrypt_package,pack,private_key=self.key,expected_public_spki_sha256=self.fp,temp_parent=self.root);self.assertEqual(set(self.root.iterdir()),before)
    def test_28_key_fingerprint_rejects_before_plaintext(self):
        pack=self.encrypt(b'SYNTHETIC ONLY');self.assertRaisesRegex(w.ScreenError,'PRIVATE_ROUTE_KEY_MISMATCH',w.decrypt_package,pack,private_key=self.key,expected_public_spki_sha256='0'*64,temp_parent=self.root)

    def test_33_crypto_to_structural_reducer_integration(self):
        f,p=fixture();raw=p[0].removeprefix(b'SYNTHETIC_ONLY:');cipher=self.encrypt(raw)
        f['entries'][0]['ENCRYPTED_ASSET_SHA256']=w.sha(cipher)
        reducer=w.BoundScreen(**f);before=set(self.root.iterdir())
        reducer.consume(cipher,decrypt=lambda b:w.decrypt_package(b,private_key=self.key,expected_public_spki_sha256=self.fp,temp_parent=self.root))
        self.assertEqual(reducer.next_index,1);self.assertEqual(reducer.total,64);self.assertEqual(set(self.root.iterdir()),before)
    def test_34_malformed_encrypted_header(self):
        self.assertRaisesRegex(w.ScreenError,'MALFORMED_ENCRYPTED_PACKAGE',w.decrypt_package,b'INVALID',private_key=self.key,expected_public_spki_sha256=self.fp,temp_parent=self.root)

class GovernanceBindingTests(unittest.TestCase):
    def test_29_preserved_v1_acceptance_and_manifests(self):
        self.assertEqual(digest(read(w.PROTOCOL)['supersession']['V1']['ref']),'031444998d2d99d1e4d35c8bec2e52dee1faf3aa7ab371d506194cf9728eb351');self.assertEqual(digest(w.ACCEPTANCE),'73a7714757488bcffbc2ac48a34653e9deed50491d72e72cffc7a402f83ae38e')
        for b in read(w.PROTOCOL)['bindings'].values():self.assertEqual(digest(b['ref']),b['sha256'])
    def test_30_no_new_cutoffs_or_duration(self):
        p=read(w.PROTOCOL);self.assertTrue(p['no_activity_or_friction_thresholds']);self.assertFalse(p['classification']['fixed_top_k']);self.assertFalse(p['classification']['rank_and_truncate']);self.assertTrue(p['classification']['all_passers_retained']);self.assertFalse(p['deep_history_duration']['selected']);self.assertIsNone(p['deep_history_duration']['value'])
    def test_31_real_context_metadata_only_preflight(self):
        # Loads manifest/roster/current metadata only. No downloader or decrypt invocation.
        with patch('urllib.request.urlopen',denied),patch.object(w,'decrypt_package',denied):screen,p,a=w.load_real_context(ROOT)
        self.assertEqual(screen.next_index,0);self.assertEqual(screen.total,0);self.assertEqual(len(screen.entries),100)
    def test_32_primary_governance_budget_preserved(self):
        p=read(w.PROTOCOL);self.assertEqual(p['bindings']['discovery']['sha256'],'ce80c4a71fe2f49c3f9b6eba7797f47de6e2f49827bd97384e54b81e63f28be5');self.assertEqual(p['bindings']['selection']['sha256'],'f1a2ce55407351686588b7ef9f1af45f08c83d4340dd03df0ed24eddbceff449')
        m=read(p['bindings']['PRIMARY145']['ref']);self.assertEqual(m['primary_count'],145);self.assertEqual(sum(x['row_count'] for x in m['primary_series']),11406418)
        b=p['preservation']['search_budget'];self.assertEqual((b['total'],b['used'],b['remaining'],b['economic_outcomes_opened']),(84,21,63,29));self.assertFalse(p['preservation']['protected_forward_opened']);self.assertFalse(p['preservation']['confirmation_opened'])
    def test_35_final_rebind_when_preflight_materialized(self):
        # Initial synthetic freeze stage intentionally preserves V1 operation.
        if not (ROOT/w.PREFLIGHT).exists():
            self.assertEqual(read(w.S+'V4_STATE.json')['qualification_protocol_ref'],read(w.PROTOCOL)['supersession']['V1']['ref']);return
        report=read(w.PREFLIGHT);self.assertEqual(report['status'],'PASS_SYNTHETIC_ONLY_NO_REAL_DECRYPTION');self.assertEqual(report['tests_failed'],0);self.assertEqual(report['tests_skipped'],0)
        for b in report['bindings'].values():self.assertEqual(digest(b['ref']),b['sha256'])
        for path in [w.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']:
            state=read(path);self.assertEqual(state['current_authority'],w.ACCEPTANCE);self.assertEqual(state['qualification_protocol_ref'],w.PROTOCOL);self.assertEqual(state['qualification_protocol_sha256'],digest(w.PROTOCOL));self.assertEqual(state['screen_preflight_sha256'],digest(w.PREFLIGHT));self.assertEqual(state['next_action'],read(w.PROTOCOL)['next_action'])
    def test_36_exact_diff_preserves_historical_bytes(self):
        allowed={w.PROTOCOL,w.WORKER,w.PREFLIGHT,'research_core_v4/master1576_screen_v2_preflight.py','tests/test_master1576_screen_v2.py','.github/workflows/master1576-screen-v2-synthetic-offline.yml',w.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json'}
        changed=set(subprocess.check_output(['git','diff','--name-only',w.BASE],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        self.assertLessEqual(changed,allowed)
if __name__=='__main__':unittest.main()

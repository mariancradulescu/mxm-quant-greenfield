import copy
import json
import pathlib
import subprocess
import urllib.error
from unittest.mock import patch
from .test_acceptance import Base,contracts,ROOT
from . import control as c,safety as s,provenance as p,science as sci
from research_core_v4.critical_frontier_repair_20261014_v2 import archive_v2 as ar

class P0More(Base):
    @contracts('MXM-ACT-O04.3')
    def test_stale_epoch_reader_isolation(self):
        one=s.Fence(self.path/'f');two=s.Fence(self.path/'f');one.initialize(1807,'H');epoch=one.claim(1807,'H','W1');one.commit(1807,'H',epoch,'W1','N');higher=two.claim(1808,'N','W2')
        self.assertGreater(higher,epoch);self.reject('FENCE_CAS',one.commit,1807,'H',epoch,'W1','BAD')
        calls=[];reader=s.ReadOnlyAPI(lambda *a:calls.append(a) or {},[1]);reader('releases/1');self.reject('READER_MUTATION',reader,'releases/1','PATCH',{});self.assertEqual([x[1] for x in calls],['GET'])
    @contracts('MXM-EXISTING-N25.1')
    def test_source_absent_malformed_timeout_no_create(self):
        calls=[]
        for error,state in [(urllib.error.HTTPError('u',404,'absent',{},None),'SOURCE_ABSENT'),(ValueError('bad'),'SOURCE_MALFORMED'),(TimeoutError(),'NETWORK_UNKNOWN')]:
            def api(path):calls.append(('GET',path));raise error
            self.assertEqual(c.read_source(api,'releases/1')['state'],state)
        self.assertEqual(c.read_source(lambda _: {},'releases/1')['state'],'AVAILABLE');self.assertTrue(all(x[0]=='GET' for x in calls))
    @contracts('MXM-ACT-N02.2','MXM-ACT-N02.3')
    def test_deep_dependency_and_dirty_source(self):
        root=self.path/'source';root.mkdir();(root/'a.py').write_text('import importlib\nimportlib.import_module("dynamic")\n');(root/'dynamic.py').write_text('X=1\n');(root/'x.proto').write_text('syntax = "proto3";');(root/'x.dll').write_bytes(b'SYNTHETIC')
        manifest=c.source_inventory(root);self.assertEqual(c.compare_inventory(root,manifest),manifest)
        for path in ['dynamic.py','x.proto','x.dll']:
            old=(root/path).read_bytes();(root/path).write_bytes(old+b'X');self.reject('DIGEST_DRIFT',c.compare_inventory,root,manifest);(root/path).write_bytes(old)
        with patch.object(s.subprocess,'check_output',return_value=' M dynamic.py\n'):
            self.reject('DIRTY_SOURCE_BEFORE_SECRET',s.clean_tree,root)
        with patch.object(s.subprocess,'check_output',return_value=''):s.clean_tree(root)
    @contracts('MXM-SEM-G01.2','MXM-SEM-G01.3','MXM-SEM-G03.1')
    def test_distinct_trust_predicates_and_incident_classes(self):
        for kind in ['market_data','personal_info','credentials','synthetic_private_key_header']:
            z=c.exposure(kind);self.assertFalse(z['confirmed_compromise']);self.assertFalse(z['rotate_authorized'])
        z=c.exposure('credentials',True);self.assertEqual(z['action'],'STOP_REPORT_NO_ROTATION');self.assertTrue(z['confirmed_compromise']);self.assertFalse(z['rotate_authorized'])
        for args in [{'cipher':True},{'owner':True},{'producer':True}]:
            z=c.provenance_predicates(**args);self.assertFalse(z['broker_semantics']);self.assertFalse(z['NET_true']);self.assertFalse(z['alpha_certified'])
    @contracts('MXM-EXISTING-N32.3')
    def test_durable_request_crash_boundaries(self):
        identity={'account':'A','server':'LIVE','s':9,'k':'bid','a':1,'b':2,'sequence':1}
        for phase in ['prepare','send','receipt','delta','manifest','anchor','restore']:
            path=self.path/phase;ledger=c.RequestLedger(path);h=ledger.prepare(identity)
            if phase!='prepare':ledger.send_boundary(h)
            if phase in ('receipt','delta','manifest','anchor','restore'):ledger.accept(h,'a'*64)
            resumed=c.RequestLedger(path);row=resumed.db.execute('SELECT state FROM request WHERE h=?',(h,)).fetchone()[0]
            self.assertEqual(row,'NOT_SENT' if phase=='prepare' else 'SENT_UNKNOWN' if phase=='send' else 'RESPONSE_ACCEPTED')
            if phase!='prepare':self.reject('REQUEST_REPLAY_DENIED',resumed.send_boundary,h)
            self.assertEqual(resumed.counters()['attempted'],1)

class P1More(Base):
    @contracts('MXM-SEM-D06.1','MXM-SEM-D06.3','MXM-REM-N12.1')
    def test_uncertainty_monotonic_cold(self):
        identity={'account':'A','server':'LIVE','s':9,'k':'bid','a':1,'b':2,'sequence':1};ledger=c.RequestLedger(self.path/'q');h=ledger.prepare(identity)
        self.assertEqual(ledger.counters(),{'attempted':1,'sent_or_uncertain':0,'acknowledged':0,'uncertain':0,'definitely_sent':None})
        ledger.send_boundary(h);cold=c.RequestLedger(self.path/'q');self.assertEqual(cold.counters()['uncertain'],1);self.assertEqual(cold.counters()['acknowledged'],0);self.reject('REQUEST_REPLAY',cold.send_boundary,h)
        cold.accept(h,'a'*64);self.assertEqual(cold.counters()['acknowledged'],1);self.assertEqual(cold.counters()['sent_or_uncertain'],1)
    @contracts('MXM-EXISTING-N22.1','MXM-EXISTING-N22.4')
    def test_asset_all_pages_and_ambiguous_rejection(self):
        inventory=[{'id':i,'name':str(i),'digest':'sha256:'+'a'*64} for i in range(750)]
        calls=[]
        def api(path):
            calls.append(path);page=int(path.split('page=')[-1]);return inventory[(page-1)*100:page*100]
        for id in [99,100,749]:self.assertEqual(c.lookup(api,1,id,'a'*64)['id'],id)
        self.assertTrue(any('page=8' in x for x in calls));self.reject('DIGEST_MISMATCH',c.lookup,api,1,99,'b'*64)
        inventory.append({'id':1000,'name':'99','digest':'sha256:'+'a'*64});self.reject('AMBIGUOUS_ASSET',c.lookup,api,1,99,'a'*64)
        def failed(path):
            if 'page=2' in path:raise TimeoutError()
            return inventory[:100]
        with self.assertRaises(TimeoutError):c.lookup(failed,1,100,'a'*64)
    @contracts('MXM-EXISTING-N18.4')
    def test_end_exclusive_domain_censor(self):
        self.assertEqual(c.domain_event(ar.END-900,900,ar.LOW,ar.END),'DOMAIN_CENSORED');self.assertEqual(c.domain_event(ar.END-901,900,ar.LOW,ar.END),'IN_DOMAIN');self.reject('ENTRY_OUTSIDE_DOMAIN',c.domain_event,ar.END,1,ar.LOW,ar.END)
        db=ar.dbopen(':memory:');ar.putbar(db,9,ar.END,[1,2,.5,1,1]);self.assertEqual(db.execute('SELECT count(*) FROM bar').fetchone()[0],0)
    @contracts('MXM-EXISTING-N31.1','MXM-EXISTING-N31.2','MXM-EXISTING-N31.3')
    def test_empty_is_not_observed_quote(self):
        t=ar.START*1000;db=ar.dbopen(':memory:')
        for side in ('bid','ask'):ar.span(db,9,side,t-600000,t+600000,'EMPTY_AUTHENTIC_RESPONSE')
        self.assertEqual(c.quote_observed(db,9,t),{'state':'EMPTY','observed':False})
        db.executemany('INSERT INTO tick VALUES(?,?,?,?)',[(9,'bid',t,100),(9,'ask',t,101)]);self.assertTrue(c.quote_observed(db,9,t)['observed'])
        self.assertEqual(c.quote_observed(db,9,t+300001),{'state':'STALE','observed':False})
        db.execute('INSERT INTO tick VALUES(?,?,?,?)',(9,'bid',t,102));self.assertEqual(c.quote_observed(db,9,t)['state'],'CONFLICTED')
        db.execute('DELETE FROM tick WHERE k="bid"');db.execute('INSERT INTO tick VALUES(?,?,?,?)',(9,'bid',t,102));self.assertEqual(c.quote_observed(db,9,t)['state'],'INVALID_CROSSED')
        ar.span(db,9,'bid',t,t+1,'UNKNOWN_TRANSPORT');self.assertEqual(c.quote_observed(db,9,t)['state'],'UNKNOWN_COVERAGE')

class P2More(Base):
    @contracts('MXM-SEM-S02.1','MXM-SEM-S02.2','MXM-SEM-S02.3','MXM-SEM-S02.4','MXM-ACT-O05.1')
    def test_authority_precedence_no_execution(self):
        old={'head':'OLD','scope':'Stage8','state':'ALLOW','digest':'old','current':False};new={'head':'H','scope':'Stage8','state':'STOP','digest':'new','current':True}
        for stage in ('discovery','confirmation','economic','execution','Cloud','Stage8','protected_forward'):
            a={**new,'scope':stage};z=c.resolve([old,a],stage,'H');self.assertEqual(z['state'],'STOP');self.assertFalse(z['alpha_certified']);self.assertFalse(z['Cloud_deployed']);self.assertEqual(z['refs'],['old','new'])
        good={**new,'scope':'readiness','state':'REMEDIATION_ONLY'};self.assertEqual(c.resolve([old,good],'readiness','H')['state'],'READINESS_ONLY')
        for bad in [{**good,'consumed':True},{**good,'expired':True}]:self.assertEqual(c.resolve([bad],'readiness','H')['state'],'STOP')
        self.assertEqual(c.resolve([good,good],'readiness','H')['state'],'DENY_CONFLICT_OR_MISSING');self.assertEqual(c.resolve([],'execution','H')['state'],'DENY_CONFLICT_OR_MISSING')
    @contracts('MXM-SEM-S04.2','MXM-REM-S13.1','MXM-REM-S13.2')
    def test_dependence_and_support_not_power(self):
        rec={'id':'A','first_seen':1,'design_sha256':'a'*64,'baseline_sha256':'b'*64,'split':{'development':[(1,10)],'confirmation':[(10,20)]},'feature_max_time':4,'decision_time':5,'outcome_time':6,'dependence':{'calendar':'SAME_WEEK','symbols':['A','B'],'FX':'COMMON_EUR','trials':None}}
        ledger=sci.CandidateLedger(self.path/'d');ledger.append(rec);payload=json.loads(ledger.db.execute('SELECT payload FROM proposal').fetchone()[0]);self.assertEqual(payload['dependence'],rec['dependence']);self.assertIsNone(payload['dependence']['trials'])
        self.assertIn('SUPPORT_NOT_POWER',sci.qualifying([])['gate']);self.assertFalse(sci.qualifying([])['alpha_certified']);self.reject('DEPENDENCE_UNKNOWN',sci.lineage,{**rec,'dependence':{}})

class P3More(Base):
    @contracts('MXM-SEM-E06.1')
    def test_denominators_by_horizon_and_slippage(self):
        rows=[{'id':i,'h':900,'slip':2,'cost_known':True,'entry':i<3,'exit':i<2,'path':i<1} for i in range(4)]
        rows.append({'id':99,'h':14400,'slip':2,'cost_known':True,'entry':True,'exit':True,'path':True})
        z=c.cohorts(rows,900,2);self.assertEqual([z[k]['n'] for k in ('all_cost_observable','entry_feasible','exit_observed','path_complete')],[4,3,2,1]);self.assertIsNone(z['NET'])
        self.assertEqual(c.cohorts(rows,14400,2)['all_cost_observable']['n'],1);self.assertEqual(c.cohorts(rows,900,3)['all_cost_observable']['n'],0)
        self.assertNotEqual(z['all_cost_observable']['row_set_sha256'],z['entry_feasible']['row_set_sha256'])

class P4More(Base):
    @contracts('MXM-ACT-O02.1','MXM-ACT-O02.2','MXM-ACT-O02.3')
    def test_finite_segments_and_cold_budget(self):
        sent=0;anchor=s.JOURNAL;pending=['UNCERTAIN']
        for seq in range(1,27):self.assertEqual(c.segment_budget(seq,sent,100,1),256);sent+=256
        self.assertEqual(sent,6656);self.reject('STOP_FINITE_SEGMENT',c.segment_budget,27,sent,100,1);self.reject('STOP_GLOBAL_BUDGET',c.segment_budget,26,sent,100,1);self.reject('AUTHORITY_EXPIRED',c.segment_budget,1,0,0,1);self.assertEqual(anchor,s.JOURNAL);self.assertEqual(pending,['UNCERTAIN'])
    @contracts('MXM-ACT-O11.1','MXM-ACT-O11.2')
    def test_terminal_report_binding(self):
        x={'observed_at_utc':'2026-10-15T01:00:00Z','run_id':1,'attempt':1,'HEAD':'H','generation':1807,'anchor_sha':'A','state':'STOP_FAIL_CLOSED','run_status':'in_progress','pending':1,'matched_get':True,'anchor_after':'A'}
        self.assertEqual(c.job_milestone(x),'IN_FLIGHT');x.update(run_status='completed',pending=0);self.assertEqual(c.job_milestone(x),'TERMINAL');self.reject('UNSTABLE_ANCHOR',c.job_milestone,{**x,'anchor_after':'B'})
        for key in ['generation','run_id','HEAD']:self.reject('REPORT_BINDING_MISSING',c.job_milestone,{k:v for k,v in x.items() if k!=key})
    @contracts('MXM-SEM-O06.4')
    def test_recount_timeout_gaps(self):
        catalog=json.loads((pathlib.Path(__file__).parent/'workflow_catalog.json').read_text());gaps=[r['path'] for r in catalog['workflows'] if any(t is None for t in r['original_timeouts'].values())]
        self.assertEqual(len(gaps),12) # Recomputed at authorized autonomous HEAD, not copied from earlier nine.
        for path in gaps:self.assertIn('timeout-minutes: 1',(ROOT/path).read_text())
        self.assertFalse(any(r['successor_state']=='ACTIVE' for r in catalog['workflows']))

class P0Final(Base):
    @contracts('MXM-SEM-G01.1','MXM-SEM-G01.5')
    def test_digest_only_exposure_scope(self):
        from .inventory import public_packs,validate_surface_claim
        actual=public_packs(ROOT);expected=json.loads((pathlib.Path(__file__).parent/'public_pack_inventory.json').read_text());self.assertEqual(actual,expected);self.assertEqual((actual['pack_count'],actual['gzip_json_members']),(6,84))
        scope={'global_no_leak_claim':False,'surfaces':{'checkout':'SCANNED_DIGESTS','git_history':'METADATA_AVAILABLE_CONTENT_NOT_EXHAUSTIVE','actions_logs':'REMEDIATION_JOBS_ONLY_REST_UNKNOWN','releases':'ANCHOR_AND_REFERENCED_OWNER_OBJECTS_ONLY','attachments':'APPROVED_PACKAGE_DIGESTS_ONLY'}}
        self.assertEqual(validate_surface_claim(scope),scope);self.reject('GLOBAL_EXPOSURE_CLAIM',validate_surface_claim,{**scope,'global_no_leak_claim':True})
    @contracts('MXM-ACT-N07.2')
    def test_transitive_hash_lock_rejects_tampering(self):
        import zipfile,sys
        wheels=self.path/'w';wheels.mkdir();lines=[]
        for name,dep in [('fixture_root','Requires-Dist: fixture-transitive==1.0\n'),('fixture_transitive','')]:
            path=wheels/f'{name}-1.0-py3-none-any.whl'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr(name+'-1.0.dist-info/METADATA',f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n'+dep)
                z.writestr(name+'-1.0.dist-info/WHEEL','Wheel-Version: 1.0\nGenerator: synthetic-remediation\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                z.writestr(name+'-1.0.dist-info/RECORD','')
            lines.append(f'{name}==1.0 --hash=sha256:{s.sha(path.read_bytes())}')
        lock=self.path/'lock';lock.write_text('\n'.join(lines)+'\n')
        command=[sys.executable,'-m','pip','download','--disable-pip-version-check','--no-index','--require-hashes','--find-links',str(wheels),'-r',str(lock),'--dest',str(self.path/'ok')]
        good=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);self.assertEqual(good.returncode,0,good.stdout.decode())
        target=wheels/'fixture_transitive-1.0-py3-none-any.whl';target.write_bytes(target.read_bytes()+b'TAMPER')
        command[-1]=str(self.path/'bad');bad=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);self.assertNotEqual(bad.returncode,0);self.assertIn(b'HASHES',bad.stdout.upper())

class P1Final(Base):
    @contracts('MXM-SEM-D08.1','MXM-SEM-D08.2','MXM-SEM-D08.3')
    def test_population_partition_no_survivorship(self):
        for name,n in [('CATALOG5326',5326),('PREFILTER1576',1576),('ELIGIBLE1562',1562),('PRIMARY145',145),('LEGACY349',349)]:
            z=sci.population(name,list(range(n)),'SYNTHETIC_MEMBERSHIP;ACCOUNT_A_SERVER_LIVE;COHORT_V1');self.assertEqual(z['n'],n);self.assertEqual(z['population'],name)
        self.reject('POPULATION_UNKNOWN',sci.population,'ALL_EQUIVALENT',[1],'bad')
        parts={'eligible':[1,2],'excluded':[3],'absent':[4],'request_cap':[5],'N_A':[6]};z=c.partition_population(range(1,7),parts);self.assertEqual(sum(v['n'] for v in z.values()),6)
        self.reject('POPULATION_DISAPPEARED',c.partition_population,range(1,8),parts)
        self.reject('POPULATION_OVERLAP',c.partition_population,range(1,7),{**parts,'N_A':[1,6]})
        before=sci.population('PRIMARY145',[1,2],'EXANTE_NO_OUTCOME_ACCESS');outcomes={1:1,2:None};after=sci.population('PRIMARY145',list(outcomes),'EXANTE_NO_OUTCOME_ACCESS');self.assertEqual(before,after);self.assertIsNone(outcomes[2])

class P2Final(Base):
    @contracts('MXM-SEM-S06.1','MXM-SEM-S06.3','MXM-REM-S13.3')
    def test_execution_lineage_and_closed_exact(self):
        base={'spec_id':'EXACT_A','family_id':'BROAD_FAMILY','outcome':None}
        self.assertEqual(c.exact_state(base),'PLANNED_NOT_TESTED')
        self.reject('EXECUTION_LINEAGE_MISSING',c.exact_state,{**base,'outcome':-1})
        valid={**base,'outcome':-1,'design_sha256':'a'*64,'run_id':1,'job_id':2,'artifact_sha256':'b'*64,'freeze_time':1,'outcome_time':2};self.assertEqual(c.exact_state(valid),'EXECUTED_NOT_INDEPENDENTLY_AUDITED')
        self.reject('OUTCOME_BEFORE_FREEZE',c.exact_state,{**valid,'freeze_time':3})
        self.assertEqual(c.exact_state({**valid,'closed_exact':True}),'CLOSED_EXACT_BROADER_UNTESTED');self.assertEqual(c.exact_state({**base,'spec_id':'BROAD_B'}),'PLANNED_NOT_TESTED')
    @contracts('MXM-SEM-S12.1','MXM-SEM-S12.3')
    def test_calendar_regimes_never_confirmation(self):
        ranges=[]
        for regime in ('ALTERNATE_40_WEEKS','THU_TO_THU_4_BLOCKS','ISO_W35_W37_DEVELOPMENT'):
            z=c.calendar_range('2026-08-24T00:00:00Z','2026-09-14T00:00:00Z',regime,0);self.assertFalse(z['confirmation_eligible']);ranges.append(z['regime'])
        self.assertEqual(len(set(ranges)),3)
        self.reject('CALENDAR_REGIME_UNKNOWN',c.calendar_range,'2026-08-24T00:00:00Z','2026-09-14T00:00:00Z','FUTURE_CONFIRMATION',0)
        self.reject('TIMEZONE_REQUIRED',c.calendar_range,'2026-08-24T00:00:00','2026-09-14T00:00:00Z','ALTERNATE_40_WEEKS',0)
        self.assertEqual(sci.consecutive(['2026-W53','2027-W01']),2)

class P3Final(Base):pass
class P4Final(Base):
    @contracts('MXM-REM-N12.2','MXM-REM-N12.3')
    def test_named_legacy_metadata_tests_only(self):
        import unittest
        from tests import test_frontier_information_gain_v1,test_epoch21_frontier_governance
        suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in (test_frontier_information_gain_v1,test_epoch21_frontier_governance)])
        result=unittest.TestResult();suite.run(result);self.assertEqual(result.testsRun,17);self.assertEqual(result.errors,[]);self.assertEqual(result.failures,[])
        # Actual eligibility guard negative controls remain in these tests.
        text=(ROOT/'tests/test_epoch21_frontier_governance.py').read_text();self.assertIn('with self.assertRaises(EnvelopeIneligible)',text);self.assertIn('with self.assertRaisesRegex(EvidenceIneligible',text)

# Actual acquisition functions are exercised with synthetic provider messages;
# connect is never called and persist is intercepted before any remote method.
def _test_systemic_provider_no_second_send(self):
    import time
    from research_core_v4.critical_frontier_repair_20261014_v2 import runner_v2 as runner,storage_v2 as storage
    for code in ('CH_ACCESS_TOKEN_INVALID','OA_AUTH_TOKEN_EXPIRED','ACCOUNT_NOT_AUTHORIZED','TOO_MANY_REQUESTS','PROTOCOL_UNSUPPORTED'):
        for kind in ('M5','bid'):
            db=ar.dbopen(':memory:');storage.track(db);calls=[]
            class Col:
                aid=1
                def send(self,req,historical=False):calls.append(type(req).__name__);return runner.v1.m.ProtoOAErrorRes(errorCode=code)
            state={'requests':{'M5':0,'BID_ASK':0},'campaign_m5_cap':100,'campaign_tick_cap':100,'op_counter':0}
            with patch.object(runner.storage,'persist'),patch.object(runner,'quote_ops',return_value=[{'s':9,'k':'bid','a':ar.START*1000,'b':ar.START*1000+10}]):
                if kind=='M5':self.reject('BROKER_'+code,runner.acquire_m5,db,9,{},Col(),state,None,time.monotonic()+10)
                else:self.reject('BROKER_'+code,runner.acquire_quotes,db,[],Col(),state,None,time.monotonic()+10)
            self.assertEqual(len(calls),1);self.assertEqual(state['requests'][kind if kind=='M5' else 'BID_ASK'],1)
P1Final.test_systemic_provider_no_second_send=contracts('MXM-EXISTING-N23.1')(_test_systemic_provider_no_second_send)
# unittest stores the attribute name as its witness identity.
from .test_acceptance import MAPPING
MAPPING['MXM-EXISTING-N23.1']='test_systemic_provider_no_second_send'

def _test_historical_gate_annotation(self):
    op=json.loads((pathlib.Path(__file__).parent/'operational_successor.json').read_text())
    for path,row in op['original_sources'].items():self.assertEqual(row['original_sha256'],s.sha((ROOT/path).read_bytes()));self.assertFalse(row['original_bytes_changed'])
    self.assertEqual(op['campaign_1807'],'STOP_FAIL_CLOSED_DO_NOT_RESTART');self.assertEqual(op['research'],'SEPARATE_OWNER_AUTHORIZATION_REQUIRED')
P2Final.test_historical_gate_annotation=contracts('MXM-REM-N04.2')(_test_historical_gate_annotation)
MAPPING['MXM-REM-N04.2']='test_historical_gate_annotation'

def _test_real_yaml_failure_lineage(self):
    import yaml
    path='.github/workflows/mxm-remediation-p0-p4-20261015-v1.yml'
    old=subprocess.check_output(['git','show','269702d55cb68b211cd4868663fa5c1b543101cc:'+path],cwd=ROOT,text=True)
    with self.assertRaises(yaml.YAMLError):yaml.safe_load(old)
    current=yaml.safe_load((ROOT/path).read_text());self.assertIn('jobs',current);self.assertIn('offline_acceptance',current['jobs'])
    self.assertNotEqual(s.sha(old.encode()),s.sha((ROOT/path).read_bytes()))
P4Final.test_real_yaml_failure_lineage=contracts('MXM-REM-N13.3')(_test_real_yaml_failure_lineage)
MAPPING['MXM-REM-N13.3']='test_real_yaml_failure_lineage'

def _test_crypto_upload_ack_and_original_manifest(self):
    import os,json,io,copy,gzip,urllib.parse
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
    from research_core_v4.final_recovery_20261014_v1 import storage as storemod
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);private=self.path/'private.pem';public=self.path/'public.pem';private.write_bytes(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()));public.write_bytes(key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo));fingerprint=s.sha(key.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo))
    assets=[];blobs={};anchor={'id':1,'body':'{}'};posts=[];patches=[];mode={'upload':'after','anchor':'normal'}
    def api(path,method='GET',data=None):
        if path.startswith('releases/2/assets'):return copy.deepcopy(assets)
        if path.startswith('releases/assets/'):
            return copy.deepcopy(next(a for a in assets if a['id']==int(path.split('/')[-1])))
        if path=='releases/1':
            if method=='PATCH':
                patches.append(copy.deepcopy(data))
                if mode['anchor']=='before':raise TimeoutError()
                anchor.update(data)
                if mode['anchor']=='after':raise TimeoutError()
            return copy.deepcopy(anchor)
        raise ValueError('UNEXPECTED_FAKE_ENDPOINT')
    def upload(request,timeout):
        posts.append(request.full_url)
        if mode['upload']=='before':raise TimeoutError()
        name=urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)['name'][0];blob=request.data
        asset={'id':len(assets)+10,'name':name,'size':len(blob),'digest':'sha256:'+s.sha(blob),'browser_download_url':'https://github.com/mariancradulescu/mxm-quant-greenfield/releases/download/synthetic/'+name,'state':'uploaded'}
        assets.append(asset);blobs[asset['browser_download_url']]=blob
        return io.BytesIO(json.dumps(asset).encode())
    st=storemod.Store.__new__(storemod.Store)
    st.head='H';st.key=private;st.public=public;st.tmp=self.path;st.tag='synthetic-isolated';st.limit=750;st.index=0;st.inventory=[];st.release={'id':2};st.anchor=copy.deepcopy(anchor);st.uploaded=[];st.upload_posts=0;st.fault_after_upload=True
    with patch.dict(os.environ,{'RUNNER_TEMP':str(self.path),'GH_TOKEN':'SYNTHETIC'}),patch.object(storemod,'api',side_effect=api),patch.object(storemod,'assets',side_effect=lambda rid:copy.deepcopy(assets)),patch.object(storemod,'download',side_effect=lambda url,maxbytes:blobs[url]),patch.object(storemod.urllib.request,'urlopen',side_effect=upload),patch.object(storemod.E.w.old,'FP',fingerprint),patch.object(storemod.time,'sleep'):
        value={'schema':'SYNTHETIC_ONLY','state':'UNKNOWN_TRANSPORT','generation':1807};meta=st.encrypted(value,'synthetic-checkpoint.mxmenc');self.assertEqual(st.upload_posts,1);self.assertEqual(st.restore(meta),value)
        self.assertEqual(st.encrypted(value,'synthetic-checkpoint.mxmenc'),meta);self.assertEqual(st.upload_posts,1)
        # Cold reuse without the original packed manifest must stop, never recompress.
        saved=st.uploaded;st.uploaded=[];self.reject('EXISTING_PACKED_MANIFEST_REQUIRED',st.encrypted,value,'synthetic-checkpoint.mxmenc');st.uploaded=saved
        self.reject('PACKED_DIGEST_MISMATCH',st.restore,{**meta,'gzip_sha256':'0'*64})
        self.reject('REMOTE_ASSET_METADATA',st.restore,{**meta,'ciphertext_sha256':'0'*64})
        wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048);badkey=self.path/'wrong.pem';badkey.write_bytes(wrong.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()));st.key=badkey
        with self.assertRaises(Exception):st.restore(meta)
        st.key=private
        duplicate={**assets[0],'id':99};st.inventory=copy.deepcopy(assets)+[duplicate];self.reject('AMBIGUOUS_OR_INCOMPLETE',st.encrypted,value,'synthetic-checkpoint.mxmenc');st.inventory=copy.deepcopy(assets)
        # Lost ACK after anchor mutation is reconciled by GET, no second PATCH.
        mode['anchor']='after';st.commit({'generation':1808,'journal':meta});self.assertEqual(len(patches),1)
        mode['anchor']='before';self.reject('ANCHOR_MUTATION_UNRESOLVED_NO_RETRY',st.commit,{'generation':1809,'journal':meta});self.assertEqual(len(patches),2)
        for _ in range(2):self.assertEqual(st.restore(meta),value)
        mode['upload']='before';self.reject('UPLOAD_UNCOMMITTED_OUTBOX_PRESERVED_NO_BLIND_RETRY',st.encrypted,{'generation':1809},'synthetic-before.mxmenc');self.assertEqual(st.upload_posts,2)
        self.assertEqual(len(posts),2);self.assertEqual(json.loads(anchor['body'])['generation'],1808)
P0Final.test_crypto_upload_ack_and_original_manifest=contracts('MXM-SEM-G03.3','MXM-EXISTING-N34.2','MXM-EXISTING-N17.4')(_test_crypto_upload_ack_and_original_manifest)
MAPPING.update({i:'test_crypto_upload_ack_and_original_manifest' for i in ('MXM-SEM-G03.3','MXM-EXISTING-N34.2','MXM-EXISTING-N17.4')})

def _test_full_executable_inventory_flags_unknown(self):
    result=c.executable_inventory(ROOT);self.assertIn('research_core_v4/remediation_p0_p4_20261015/owner.py',result['source_sha256']);self.assertTrue(result['static_import_edges']);self.assertTrue(any(x['state'].startswith('DYNAMIC_EDGE') for x in result['unresolved']))
    self.assertTrue(any(p.endswith('.proto') for p in result['source_sha256']))
    self.assertTrue(any(p.endswith('.csproj') for p in result['source_sha256']))
    tampered=dict(result['source_sha256']);tampered.pop('research_core_v4/remediation_p0_p4_20261015/owner.py');self.assertNotEqual(tampered,result['source_sha256'])
P0Final.test_full_executable_inventory_flags_unknown=contracts('MXM-ACT-N02.1')(_test_full_executable_inventory_flags_unknown)
MAPPING['MXM-ACT-N02.1']='test_full_executable_inventory_flags_unknown'

def _test_systemic_public_enum_safe(self):
    from research_core_v4.root_cause_economic_20261014_v1.continuation_1307 import exception_category
    for raw,expected in [('BROKER_OA_AUTH_TOKEN_EXPIRED','AUTH_EXPIRED'),('BROKER_ACCOUNT_NOT_AUTHORIZED','ACCOUNT_UNAUTHORIZED'),('BROKER_TOO_MANY_REQUESTS','RATE_LIMIT'),('BROKER_PROTOCOL_UNSUPPORTED','PROTOCOL_UNSUPPORTED')]:
        category=exception_category(RuntimeError(raw));self.assertEqual(category,expected);z=s.terminal({'category':category},{'M5':1,'BID_ASK':1});self.assertFalse(z['ready']);self.assertEqual(z['state'],'STOP_FAIL_CLOSED')
    self.assertEqual(exception_category(RuntimeError('BROKER_OA_AUTH_TOKEN_EXPIRED SYNTHETIC_SECRET')),'UNCLASSIFIED_EXCEPTION')
P1Final.test_systemic_public_enum_safe=contracts('MXM-EXISTING-N23.3')(_test_systemic_public_enum_safe)
MAPPING['MXM-EXISTING-N23.3']='test_systemic_public_enum_safe'

def _test_collector_fault_evidence_request_scope(self):
    from types import SimpleNamespace
    from research_core_v4.autonomous_native_20261015_v1 import runtime as runtime
    for phase in ('guard','TLS_send','decode','after_response','cold_restart'):
        guard=(lambda:(_ for _ in ()).throw(RuntimeError('SYNTHETIC_GUARD'))) if phase=='guard' else lambda:None
        col=runtime.EvidenceCollector({'M5':1,'BID_ASK':1},guard);col.tr=SimpleNamespace(host='AUTHENTICATED_SYNTHETIC_LIVE_HOST',last_history_envelope=None)
        col.last_evidence={'response_b64':'SYNTHETIC_PRIOR_A'};request={'s':9,'k':'bid','a':10,'b':20};col.operation_request=request
        if phase=='TLS_send':effect=ConnectionError('send failed')
        else:
            class Response:
                def SerializeToString(self):
                    if phase=='decode':raise ValueError('SYNTHETIC_DECODE')
                    return b'SYNTHETIC_CURRENT_B'
            effect=None
        with patch.object(runtime.Collector,'send',side_effect=effect,return_value=Response() if phase!='TLS_send' else None):
            if phase in ('guard','TLS_send','decode'):
                with self.assertRaises(Exception):col.send(SimpleNamespace(ctidTraderAccountId=1),True)
            else:col.send(SimpleNamespace(ctidTraderAccountId=1),True)
        proof=s.bind_failure({'request':request},col.last_evidence);self.assertEqual(proof['state'],'REQUEST_BOUND');self.assertNotIn('SYNTHETIC_PRIOR_A',json.dumps(proof));self.assertIsNone(col.operation_request)
        self.assertEqual(col.last_evidence['request_hash'],s.request_identity(request))
P0Final.test_collector_fault_evidence_request_scope=contracts('MXM-EXISTING-N35.3')(_test_collector_fault_evidence_request_scope)
MAPPING['MXM-EXISTING-N35.3']='test_collector_fault_evidence_request_scope'

def _test_artifact_chain_and_absent_segment(self):
    a={'head':'A','run_id':1,'job_id':10,'artifact_sha256':'a'*64,'artifact_size':100,'artifact_name':'X_v9R1.algo'};b={**a,'head':'B','job_id':11}
    self.assertEqual(c.artifact_chain(a,b,lambda x,y:(x,y)==('A','B'))['state'],'PACKAGE_READY_ONLY')
    self.reject('ARTIFACT_CHAIN_DIGEST',c.artifact_chain,a,{**b,'artifact_name':'X_v9.algo'},lambda *a:True)
    self.reject('ARTIFACT_CHAIN_ANCESTRY',c.artifact_chain,a,b,lambda *a:False)
    entries=[{'sequence':i,'run_id':i,'journal_sha256':str(i),'postsegment_sha256':'r'+str(i)} for i in range(1,27) if i!=19]
    chain=c.segment_chain(entries);self.assertEqual(chain[18],{'sequence':19,'state':'ABSENT'});self.assertEqual(sum(r['state']=='OBSERVED_RECEIPT_NOT_ALPHA' for r in chain),25)
    self.reject('SEGMENT_EVIDENCE_MISSING',c.segment_chain,entries+[{'sequence':19,'run_id':19}])
P4Final.test_artifact_chain_and_absent_segment=contracts('MXM-EXISTING-N20.3','MXM-EXISTING-N30.4')(_test_artifact_chain_and_absent_segment)
MAPPING.update({i:'test_artifact_chain_and_absent_segment' for i in ('MXM-EXISTING-N20.3','MXM-EXISTING-N30.4')})

def _test_every_successor_entrypoint_denies_old_grants(self):
    from research_core_v4.autonomous_native_20261015_v1 import runtime
    from research_core_v4.diverse_mechanism_wave_v2.authority_v2 import real_gate
    from .policy import workflow_guard
    self.assertEqual(workflow_guard(ROOT)['legacy_inert'],193)
    for mode in ('bootstrap','worker','handoff','economic','Stage8','Cloud'):
        with patch.dict(__import__('os').environ,{'MODE':mode}),patch.object(runtime.io,'api') as api,patch.object(runtime.EvidenceCollector,'connect') as connect:
            self.reject('EXPECTED_POLICY_STOP_REMEDIATION_NO_CAMPAIGN',runtime.main)
            api.assert_not_called();connect.assert_not_called()
    self.reject('EXPECTED_POLICY_STOP_NO_INDEPENDENT_TRUST_ROOT',real_gate,'H')
P4Final.test_every_successor_entrypoint_denies_old_grants=contracts('MXM-ACT-O05.3','MXM-SEM-G06.1')(_test_every_successor_entrypoint_denies_old_grants)
MAPPING.update({i:'test_every_successor_entrypoint_denies_old_grants' for i in ('MXM-ACT-O05.3','MXM-SEM-G06.1')})

def _test_request_phases_no_replay_after_cold(self):
    from research_core_v4.critical_frontier_repair_20261014_v2 import runner_v2 as runner,storage_v2 as storage
    identity={'account':'A','server':'LIVE','s':9,'k':'bid','a':ar.START*1000,'b':ar.START*1000+10,'sequence':1}
    for phase in ('pre_request','just_after_send','before_delta','post_manifest','provider_error_ACK'):
        ledger=c.RequestLedger(self.path/phase);h=ledger.prepare(identity)
        if phase!='pre_request':ledger.send_boundary(h)
        if phase in ('post_manifest','provider_error_ACK'):ledger.accept(h,s.sha(('SYNTHETIC_'+phase).encode()))
        cold=c.RequestLedger(self.path/phase);state=cold.db.execute('SELECT state FROM request').fetchone()[0]
        self.assertEqual(state,'NOT_SENT' if phase=='pre_request' else 'RESPONSE_ACCEPTED' if phase in ('post_manifest','provider_error_ACK') else 'SENT_UNKNOWN')
        if phase!='pre_request':self.reject('REQUEST_REPLAY',cold.send_boundary,h)
        db=ar.dbopen(':memory:');storage.track(db)
        runner.wire_record(db,identity,'CONFIRMED_COMPLETE' if state=='RESPONSE_ACCEPTED' else 'UNCERTAIN_WIRE','a'*64)
        before=list(db.iterdump());self.assertFalse(runner.check_new_request(db,identity));self.assertEqual(before,list(db.iterdump()))
P1Final.test_request_phases_no_replay_after_cold=contracts('MXM-EXISTING-N23.2')(_test_request_phases_no_replay_after_cold)
MAPPING['MXM-EXISTING-N23.2']='test_request_phases_no_replay_after_cold'

def _test_fault_restore_conflict_mask_twice(self):
    from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as storage
    from research_core_v4.final_recovery_20261014_v1 import storage as io
    import os
    t=ar.START*1000
    original={'generation':1807,'identity_records':{},'shards':{},'record_shards':{},'snapshots_v2':[{'id':'D'}],'increments_v2':[],'resume_proofs':[],'pending_requests':[],'uncertain_wire':[],'_raw':[{'request':{'s':9},'state':'SYNTHETIC_PRESERVED'}]}
    data={'spans':[(9,'bid',t,t+10,'CONFIRMED_COMPLETE'),(9,'bid',t+5,t+15,'UNKNOWN_TRANSPORT')]}
    class Store:
        anchor={'body':json.dumps({'current_journal':{'id':'J','canonical_sha256':'a'*64}})}
        def restore(self,meta):return copy.deepcopy(original if meta['id']=='J' else data)
    for phase in ('before_SQL_commit','after_SQL_commit','before_manifest','after_manifest'):
        state=copy.deepcopy(original);before=copy.deepcopy(state);db=ar.dbopen(':memory:');storage.track(db)
        def fail(db,store,st,label,groups):
            st['generation']+=1;st['_raw']=[]
            if phase!='before_SQL_commit':db.commit()
            raise RuntimeError('SYNTHETIC_CHECKPOINT_FAULT')
        with patch.object(io,'ORIGINAL_PERSIST',side_effect=fail):self.reject('SYNTHETIC_CHECKPOINT_FAULT',io.persist,db,Store(),state,'fixture')
        self.assertEqual(state,before)
        masks=[]
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'1','GITHUB_JOB':'offline'}):
            for _ in range(2):
                fresh=ar.dbopen(':memory:');storage.track(fresh);loaded=storage.restore(fresh,Store());self.assertEqual(loaded['generation'],1807);masks.append(ar.missing(fresh,9,'bid',t,t+15))
        self.assertEqual(masks,[[(t+5,t+15)],[(t+5,t+15)]])
        # Negative: a forged full confirmed mask is incompatible with the source.
        self.assertNotEqual(masks[0],[])
P1Final.test_fault_restore_conflict_mask_twice=contracts('MXM-EXISTING-N26.4')(_test_fault_restore_conflict_mask_twice)
MAPPING['MXM-EXISTING-N26.4']='test_fault_restore_conflict_mask_twice'

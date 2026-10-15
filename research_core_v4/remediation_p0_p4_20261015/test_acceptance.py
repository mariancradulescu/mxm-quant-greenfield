"""Bounded, synthetic acceptance witnesses. Each mapped contract has assertions.

Unmapped native/historical requirements remain OPEN, never inferred from tests.
"""
import copy
import datetime
import gzip
import itertools
import json
import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from . import safety as s,provenance as p,science as sci,economics as ec,policy
from research_core_v4.autonomous_native_20261015_v1 import runtime as r
from research_core_v4.critical_frontier_repair_20261014_v2 import archive_v2 as ar,runner_v2 as runner,storage_v2 as storage
ROOT=pathlib.Path(__file__).resolve().parents[2]
MAPPING={}
def contracts(*ids):
    def deco(f):
        for i in ids:
            if i in MAPPING:raise ValueError('DUPLICATE_WITNESS')
            MAPPING[i]=f.__name__
        return f
    return deco

class Base(unittest.TestCase):
    def reject(self,code,fn,*a,**kw):
        with self.assertRaisesRegex(Exception,code):fn(*a,**kw)
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=pathlib.Path(self.tmp.name)

class P0(Base):
    @contracts('MXM-REM-N37.1','MXM-REM-N37.2','MXM-REM-N37.3','MXM-REM-N37.4')
    def test_terminal_all_causes(self):
        for failure,budget,extra,state in [(True,5,[],'STOP_FAIL_CLOSED'),(True,0,[],'STOP_FAIL_CLOSED'),(False,0,[],'STOP_GLOBAL_BUDGET'),(True,0,['AUTHORITY_EXPIRED'],'STOP_FAIL_CLOSED')]:
            z=s.terminal({'category':'TLS_SEND_FAILURE'} if failure else None,{'M5':budget,'BID_ASK':2},other=extra)
            self.assertEqual(z['state'],state);self.assertFalse(z['ready'])
            self.assertEqual('STOP_GLOBAL_BUDGET' in z['causes'],budget==0)
            if failure:self.assertEqual(z['failure']['category'],'TLS_SEND_FAILURE')
            if extra:self.assertIn('AUTHORITY_EXPIRED',z['causes'])
    @contracts('MXM-ACT-O03.1','MXM-ACT-O03.2','MXM-ACT-O03.3')
    @patch.dict(os.environ,{'GITHUB_SHA':'H','GITHUB_RUN_ID':'1'})
    def test_lost_ack_reconciliation_pagination(self):
        calls=[]
        def api(path,method='GET',data=None):
            calls.append((path,method))
            if method=='POST' and 'dispatches' in path:raise TimeoutError()
            if path.startswith('actions/runs?'):
                if 'page=2' in path:return {'workflow_runs':[{'head_sha':'H','display_title':'MXM autonomous g1807 s2','id':2}]}
                return {'workflow_runs':[{'head_sha':'other','display_title':'other','id':i+3} for i in range(100)]}
            return {'object':{'sha':'H'}}
        with patch.object(r.io,'api',side_effect=api),patch.object(r.time,'sleep'):
            z=r.dispatch({'branch':'b'},1807,2)
        self.assertEqual(z['successor_run'],2);self.assertEqual(z['ack'],'DISPATCH_UNKNOWN');self.assertEqual(sum(m=='POST' and 'dispatches' in x for x,m in calls),1)
        calls.clear()
        def absent(path,method='GET',data=None):
            calls.append((path,method))
            if path.startswith('actions/runs?'):return {'workflow_runs':[]}
            if method=='POST' and 'dispatches' in path:raise TimeoutError()
            return {'object':{'sha':'H'}}
        with patch.object(r.io,'api',side_effect=absent),patch.object(r.time,'sleep'):
            self.reject('STALLED_INTENT_STOP_DISPATCH_UNKNOWN',r.dispatch,{'branch':'b'},1807,2)
        self.assertEqual(sum(m=='POST' and 'dispatches' in x for x,m in calls),1)
        def exists(path,method='GET',data=None):
            if method=='POST':raise TimeoutError()
            return {'object':{'sha':'H'}}
        with patch.object(r.io,'api',side_effect=exists) as mocked:
            self.reject('STALLED_INTENT_STOP',r.dispatch,{'branch':'b'},1807,2)
        self.assertFalse(any('dispatches' in c.args[0] for c in mocked.call_args_list))
    @contracts('MXM-ACT-O04.2')
    def test_local_cas_two_writers(self):
        f=s.Fence(self.path/'cas');g=s.Fence(self.path/'cas');f.initialize(1807,'H')
        token=f.claim(1807,'H','writer1');self.reject('STALE_OR_CLAIMED',g.claim,1807,'H','writer2')
        self.reject('FENCE_CAS',g.commit,1807,'H',token-1,'writer1','NEW')
        f.commit(1807,'H',token,'writer1','NEW');self.reject('FENCE_CAS',f.commit,1807,'H',token,'writer1','OTHER')
        self.assertEqual(f.db.execute('SELECT generation,hash FROM fence').fetchone(),(1808,'NEW'))
    @contracts('MXM-EXISTING-N25.2')
    def test_reader_method_namespace(self):
        calls=[];reader=s.ReadOnlyAPI(lambda *a:calls.append(a) or {},[412686323,642889915])
        reader('releases/412686323');self.assertEqual(len(calls),1)
        for m in ['POST','PATCH','PUT','DELETE']:self.reject('READER_MUTATION',reader,'releases/412686323',m,{})
        for path in ['git/refs','releases/99','actions/workflows/x/dispatches']:self.reject('READER_NAMESPACE',reader,path)
        self.assertEqual(len(calls),1)
    @contracts('MXM-SEM-G01.4','MXM-EXISTING-N21.4')
    def test_secret_canary_redaction(self):
        canary='SYNTHETIC_ACCESS_TOKEN_NEVER_EMIT_123';raw=s.canonical(s.safe_error(ValueError(canary+' response_b64 SECRET')))
        self.assertNotIn(canary.encode(),raw);self.assertNotIn(b'response_b64',raw);self.assertEqual(json.loads(raw)['category'],'VALIDATION_REJECTED')
        self.assertEqual(s.safe_error(Exception(canary)),{'category':'UNCLASSIFIED_EXCEPTION'})
    @contracts('MXM-REM-N08.1','MXM-REM-N08.2')
    def test_bounded_decode_and_json(self):
        valid=gzip.compress(b'{"x":1}');self.assertEqual(s.strict_json(s.unpack(valid)),{'x':1})
        self.reject('DECOMPRESSION_LIMIT',s.unpack,gzip.compress(b'0'*1000000),1000)
        for bad in [valid[:-5],valid[:-1]+b'X']:
            with self.assertRaises(Exception):s.unpack(bad)
        self.reject('NONFINITE_JSON',s.strict_json,b'{"n":1e999}')
        self.reject('NONFINITE_JSON',s.strict_json,b'{"n":NaN}')
        self.reject('DUPLICATE_JSON_KEY',s.strict_json,b'{"n":1,"n":2}')
        self.reject('JSON_STRUCTURE_LIMIT',s.strict_json,b'[[[[0]]]]',max_depth=2)
    @contracts('MXM-EXISTING-N34.1')
    def test_original_gzip_never_recompressed(self):
        from research_core_v4.final_recovery_20261014_v1 import storage as io
        raw=io.encode({'fixture':'synthetic'});a=gzip.compress(raw,mtime=0);b=gzip.compress(raw,mtime=123)
        self.assertNotEqual(s.sha(a),s.sha(b));self.assertEqual(s.unpack(a),s.unpack(b))
        from research_core_v4.final_recovery_20261014_v1 import storage as io
        st=io.Store.__new__(io.Store);st.key=self.path/'key';st.tmp=self.path
        meta={'id':1,'name':'x','size':3,'ciphertext_sha256':s.sha(b'ENC'),'gzip_sha256':s.sha(a),'canonical_sha256':s.sha(raw)}
        asset={'name':'x','size':3,'digest':'sha256:'+s.sha(b'ENC'),'browser_download_url':'url'}
        with patch.object(io,'api',return_value=asset),patch.object(io,'download',return_value=b'ENC'),patch.object(io.E.w.old.crypto,'decrypt_package',return_value=a):
            self.assertEqual(st.restore(meta),{'fixture':'synthetic'})
            self.reject('PACKED_DIGEST_MISMATCH',st.restore,{**meta,'gzip_sha256':s.sha(b)})
            self.reject('PACKED_DIGEST_MISMATCH',st.restore,{k:v for k,v in meta.items() if k!='gzip_sha256'})
    @contracts('MXM-EXISTING-N35.1','MXM-EXISTING-N35.2')
    def test_exact_request_failure_binding(self):
        a={'account':'A','server':'LIVE','s':9,'k':'bid','a':1,'b':2,'sequence':1};b={**a,'a':2,'b':3}
        e={'request':a,'request_hash':s.request_identity(a),'raw':'SYNTHETIC_A'}
        self.assertEqual(s.bind_failure({'request':a},e)['state'],'REQUEST_BOUND')
        self.assertEqual(s.bind_failure({'request':b},e),{'state':'EVIDENCE_UNBOUND'})
        self.assertEqual(s.bind_failure({'request':b},{}),{'state':'EVIDENCE_UNBOUND'})
    @contracts('MXM-EXISTING-N32.1','MXM-EXISTING-N32.2')
    def test_duplicate_guard_no_mutation(self):
        db=ar.dbopen(':memory:');storage.track(db);req={'s':9,'k':'bid','a':ar.LOW*1000,'b':ar.LOW*1000+10}
        runner.wire_record(db,req,'UNCERTAIN_WIRE','H');ar.span(db,9,'bid',req['a'],req['b'],'UNCERTAIN_WIRE');db.commit()
        before=list(db.iterdump());self.assertFalse(runner.check_new_request(db,req));self.assertEqual(before,list(db.iterdump()))
        self.reject('WIRE_CONFLICT',runner.wire_record,db,req,'CONFIRMED_COMPLETE','OTHER');self.assertEqual(before,list(db.iterdump()))
    @contracts('MXM-SEM-G06.2','MXM-SEM-G06.3')
    def test_scope_expiry_no_inherited_grant(self):
        a={'role':'REMEDIATION_ONLY','head':'H','expires':'2099-01-01T00:00:00+00:00'};c={'branch':s.BRANCH,'head':'H','attempt':1}
        self.assertTrue(s.authorize('offline_tests',a,c))
        for act in ['alpha_research','collection','orders','Cloud','Stage8','protected_forward','safe_stop']:
            self.reject('ACTION_DENIED',s.authorize,act,a,c)
        self.reject('SCOPE_DENIED',s.authorize,'owner_readback',a,{**c,'attempt':2})
        self.reject('SCOPE_DENIED',s.authorize,'owner_readback',a,{**c,'branch':'other'})
        self.reject('HEAD_DENIED',s.authorize,'owner_readback',a,{**c,'head':'B'})
        self.reject('AUTHORITY_EXPIRED',s.authorize,'owner_readback',{**a,'expires':'2000-01-01T00:00:00+00:00'},c)

class P1(Base):
    @contracts('MXM-ACT-N36.1','MXM-ACT-N36.2','MXM-ACT-N36.3')
    def test_unproven_m5_never_complete(self):
        db=ar.dbopen(':memory:')
        for obj in [{'segment_index':1,'shard_index':1,'items':[{'symbol_id':9,'rows':[]}]},{'sid':9,'start':ar.START,'bars':{},'status':'COMPLETE_EXACT_WINDOW'}]:
            ar.extract(db,obj);self.assertEqual(db.execute('SELECT count(*) FROM span').fetchone()[0],0)
        ar.span(db,9,'M5',ar.START*1000,ar.START*1000+10,'ACCEPTED_EXACT_M5_INTERVAL')
        self.assertEqual(ar.missing(db,9,'M5',ar.START*1000,ar.START*1000+10),[(ar.START*1000,ar.START*1000+10)])
    @contracts('MXM-REM-N03.1','MXM-REM-N03.2')
    def test_bars_nonfinite_volume(self):
        db=ar.dbopen(':memory:');ar.putbar(db,9,ar.START,[1,2,.5,1,0]);self.assertEqual(db.execute('SELECT count(*) FROM bar').fetchone()[0],1)
        for values in [[1,float('inf'),.5,1,0],[1,2,.5,1,-1],[1,2,.5,float('nan'),1]]:
            self.reject('BAR_INTEGRITY',ar.putbar,db,9,ar.START+300,values)
        for raw in [b'{"high":1e999}',b'{"high":Infinity}',b'{"fee":NaN}']:self.reject('NONFINITE_JSON',s.strict_json,raw)
    @contracts('MXM-EXISTING-N03.5','MXM-EXISTING-N27.1','MXM-EXISTING-N27.2')
    def test_utc_units(self):
        self.assertEqual(p.timestamp('2026-09-01T00:00:00Z'),1788220800)
        self.assertEqual(p.timestamp('2026-10-15T01:00:00+00:00'),p.timestamp('2026-10-15T04:00:00+03:00'))
        self.assertEqual(p.timestamp(1788220800000,'milliseconds'),p.timestamp(1788220800)*1000)
        for v in [1788220800000,1788220800.7,float('nan'),float('inf'),-1,'2026-09-01T00:00:00']:
            with self.assertRaises(Exception):p.timestamp(v)
    @contracts('MXM-REM-N14.1','MXM-REM-N14.2')
    def test_pagination_true_bool_required(self):
        self.assertEqual(p.coverage(False,[1],True),'CONFIRMED_COMPLETE');self.assertEqual(p.coverage(False,[],True),'EMPTY_AUTHENTIC_RESPONSE');self.assertEqual(p.coverage(True,[1],True),'PARTIAL_HASMORE')
        for v in [None,'false',1,0]:self.assertIn('UNKNOWN',p.coverage(v,[],True))
        self.assertIn('UNKNOWN',p.coverage(False,[],False))
    @contracts('MXM-EXISTING-N16.1','MXM-EXISTING-N16.4')
    def test_import_failure_rolls_back(self):
        db=ar.dbopen(self.path/'db');ar.putbar(db,1,ar.START,[1,2,.5,1,0]);db.commit();before=list(db.iterdump())
        bad={'bars':{'9':{str(ar.START):[1,2,.5,1,1],str(ar.START+300):[1,2,.5,1,-1]}}}
        self.reject('BAR_INTEGRITY',ar.extract,db,bad);self.assertEqual(before,list(db.iterdump()));db.close()
        for i in range(2):
            db=ar.dbopen(self.path/'db');self.assertEqual(before,list(db.iterdump()));db.close()
    @contracts('MXM-EXISTING-N16.2')
    def test_source_receipt_transaction(self):
        db=ar.dbopen(':memory:');raw=b'SYNTHETIC_AUTHENTICATED_FIXTURE';env=p.Envelope('A','LIVE-S','LIVE',9,'M5','price','UTC','native',s.sha(raw),'a'*64,'ProtoOAGetTrendbarsRes')
        state=p.atomic_ingest(db,env,('A','LIVE-S',9),raw,[(ar.START,[1,2,.5,1,1])],False,ar.START,ar.START+300)
        self.assertEqual(state,'CONFIRMED_COMPLETE');self.assertEqual(db.execute('SELECT count(*) FROM row_source JOIN source_receipt USING(h)').fetchone()[0],1)
        before=list(db.iterdump());self.reject('SOURCE_IDENTITY',p.atomic_ingest,db,env,('B','LIVE-S',9),raw,[],False,ar.START,ar.START+300);self.assertEqual(before,list(db.iterdump()))
    @contracts('MXM-SEM-D01.1','MXM-SEM-D01.2','MXM-SEM-D01.3','MXM-SEM-N05.1','MXM-SEM-N05.2','MXM-SEM-N05.4')
    def test_semantic_and_account_namespaces(self):
        for family,protocol_name in p.FAMILIES.items():
            env=p.Envelope('A','LIVE-S','LIVE',9,family,'NATIVE_UNIT','UTC','IDENTITY','a'*64,'b'*64,protocol_name)
            self.assertIs(env.validate(('A','LIVE-S',9)),env);self.assertIs(env.as_type(family),env)
            for other in p.FAMILIES:
                if other!=family:self.reject('SEMANTIC_SUBSTITUTION',env.as_type,other)
            self.reject('SOURCE_IDENTITY',env.validate,('A','OTHER-S',9));self.reject('SOURCE_IDENTITY',env.validate,('B','LIVE-S',9))
        self.reject('WRONG_ENVIRONMENT',p.Envelope('A','S','DEMO',9,'BID','price','UTC','ID','a'*64,'b'*64,p.FAMILIES['BID']).validate,('A','S',9))
        self.reject('PROVENANCE_MISSING',p.Envelope('','S','LIVE',9,'BID','price','UTC','ID','a'*64,'b'*64,p.FAMILIES['BID']).validate,('','S',9))
    @contracts('MXM-EXISTING-N17.1','MXM-EXISTING-N17.2')
    def test_wire_immutable_replay(self):
        db=ar.dbopen(':memory:');storage.track(db);req={'s':9,'k':'bid','a':ar.START*1000,'b':ar.START*1000+10}
        runner.wire_record(db,req,'CONFIRMED_COMPLETE','H');db.commit();before=list(db.iterdump())
        runner.wire_record(db,req,'CONFIRMED_COMPLETE','H');self.assertEqual(before,list(db.iterdump()))
        self.reject('WIRE_CONFLICT',runner.wire_record,db,req,'PARTIAL_HASMORE','OTHER');self.assertEqual(before,list(db.iterdump()))
        data={'wire':[(9,'bid',req['a'],req['b'],'CONFIRMED_COMPLETE','H')]};storage.apply(db,data,{});self.assertEqual(before,list(db.iterdump()))
        self.reject('WIRE_REPLAY_CONFLICT',storage.apply,db,{'wire':[(9,'bid',req['a'],req['b'],'UNKNOWN_TRANSPORT','Q')]},{});self.assertEqual(before,list(db.iterdump()))
    @contracts('MXM-EXISTING-N18.1','MXM-EXISTING-N18.2')
    def test_crop_rows_and_spans_same_domain(self):
        db=ar.dbopen(':memory:');times=[ar.LOW*1000-1,ar.LOW*1000,ar.END*1000-1,ar.END*1000]
        class Tick:
            def __init__(self,t):self.timestamp_ms=t;self.raw_tick=100
        with patch.object(ar,'decode_ctrader_tick_page',return_value=[Tick(t) for t in times]):
            self.assertEqual(ar.tickrows(db,9,'bid',[],times[0]-1,times[-1]+1),2)
        self.assertEqual([x[0] for x in db.execute('SELECT t FROM tick ORDER BY t')],times[1:3])
        ar.span(db,9,'bid',times[0]-1,times[-1]+1,'UNKNOWN_TRANSPORT');a,b=db.execute('SELECT a,b FROM span').fetchone();self.assertEqual((a,b),(ar.LOW*1000,ar.END*1000-1))
    @contracts('MXM-EXISTING-N21.1','MXM-EXISTING-N21.2')
    def test_response_join_by_identity(self):
        m={'account':'A','clientMsgId':'m','payloadType':100,'request_hash':'M'};q={'account':'A','clientMsgId':'q','payloadType':101,'request_hash':'Q'}
        for req,res in [(q,q),(m,m)]:self.assertEqual(p.reconcile_response(req,res),'BOUND')
        for req,res in [(m,q),(q,m),(q,{}),(q,{**q,'account':'B'}),(q,{**q,'clientMsgId':'stale'}),(q,{**q,'payloadType':100})]:self.assertEqual(p.reconcile_response(req,res),'EVIDENCE_UNBOUND')
    @contracts('MXM-EXISTING-N26.1','MXM-EXISTING-N26.2')
    def test_conflicting_intervals_permutation(self):
        t=ar.START*1000;expected=[(t+5,t+15)]
        for rows in itertools.permutations([(t,t+10,'CONFIRMED_COMPLETE'),(t+5,t+15,'UNKNOWN_TRANSPORT')]):
            db=ar.dbopen(':memory:')
            for a,b,z in rows:ar.span(db,9,'bid',a,b,z)
            self.assertEqual(ar.missing(db,9,'bid',t,t+15),expected)
            for a,b,z in rows:ar.span(db,9,'bid',a,b,z)
            self.assertEqual(db.execute('SELECT count(*) FROM span').fetchone()[0],2)

class P2(Base):
    @contracts('MXM-REM-N04.1','MXM-REM-N04.3','MXM-REM-N06.1','MXM-REM-N06.2')
    def test_exante_censoring_and_consecutive_weeks(self):
        def events(weeks):
            return [{'kind':'REOPEN','entry':{'eligible':True},'feature':{'model_side':1},'date':str(i%12),'iso':weeks[i%3],'class':['FX','INDEX'][i%2],'_native_accounting_context':{'paired_reference':False}} for i in range(48)]
        a=events(['2026-W01','2026-W02','2026-W03']);z=sci.qualifying(a);self.assertTrue(z['gate_pass']);self.assertEqual((z['model_entry_support'],z['paired_endpoints'],z['censored']),(48,0,48))
        b=copy.deepcopy(a)
        for e in b:e['_native_accounting_context']['paired_reference']=True
        self.assertEqual(sci.qualifying(b)['model_entry_support'],48)
        self.assertFalse(sci.qualifying(events(['2026-W01','2026-W03','2026-W05']))['gate_pass'])
        self.assertEqual(sci.consecutive(['2026-W53','2027-W01','2027-W02']),3)
        self.assertEqual(sci.consecutive(['2026-W35','2026-W36','2026-W37']),3)
    @contracts('MXM-REM-S14.1','MXM-REM-S14.2','MXM-REM-S14.3')
    def test_additive_closure_51_preserved(self):
        source=ROOT/'research_core_v4/state/POST_QUOTE_V4_CLOSURE_LEDGER_V2.json';old=json.loads(source.read_text());new=json.loads((pathlib.Path(__file__).parent/'closure_index.json').read_text())
        self.assertEqual((old['node_count'],len(old['nodes'])),(50,51));self.assertEqual(new['actual_node_count'],51);self.assertEqual(new['node_semantic_sha256'],[s.sha(json.dumps(n,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()) for n in old['nodes']]);self.assertEqual(new['source_sha256'],s.sha(source.read_bytes()));self.assertFalse(new['original_verdicts_changed']);self.assertEqual(sum(new['classification_counts'].values()),51)
    @contracts('MXM-SEM-S04.1','MXM-SEM-S04.3','MXM-SEM-S12.2')
    def test_immutable_chronology_and_holdout(self):
        rec={'id':'A','first_seen':1,'design_sha256':'a'*64,'baseline_sha256':'b'*64,'split':{'development':[(1,10)],'confirmation':[(10,20)]},'feature_max_time':4,'decision_time':5,'outcome_time':6,'dependence':{'cluster':'common-FX','trials':'UNKNOWN'}}
        ledger=sci.CandidateLedger(self.path/'ledger');h=ledger.append(rec);self.assertEqual(ledger.append(rec),h)
        self.reject('IMMUTABLE_FIRST_SEEN',ledger.append,{**rec,'first_seen':2})
        self.reject('FUTURE_LEAKAGE',sci.lineage,{**rec,'feature_max_time':6})
        self.reject('CONTAMINATED_HOLDOUT',sci.lineage,{**rec,'split':{'development':[(1,11)],'confirmation':[(10,20)]}})
        self.reject('FIRST_SEEN_AFTER_OUTCOME',sci.lineage,{**rec,'first_seen':7})
    @contracts('MXM-EXISTING-N24.1','MXM-EXISTING-N24.2','MXM-EXISTING-N24.3')
    def test_parity_bijection_nonempty(self):
        a=[{'id':i,'value':float(i)} for i in range(4)];self.assertEqual(sci.bijection(a,a[::-1]),{'state':'PASS','n':4})
        for b in [a[:3],a+[{'id':9,'value':9}],a[:3]+[a[2]]]:
            with self.assertRaises(ValueError):sci.bijection(a,b)
        self.assertEqual(sci.bijection([],[])['state'],'UNSUPPORTED_EMPTY')
        self.assertEqual(sci.bijection([{'id':i,'valid':False} for i in range(4)],[{'id':i,'abstain':True} for i in range(4)])['state'],'UNSUPPORTED_ALL_ABSTAIN')

class P3(Base):
    def event(self,**extra):
        return dict(t=1,id='A',kind='OPEN',fx=1,commission=0,spread=0,slippage=0,funding=0,stop_gap=0,risk=1,margin=30,side=1,units=1,step=1,**extra)
    @contracts('MXM-SEM-E02.1','MXM-SEM-E02.2','MXM-SEM-E02.3','MXM-SEM-E02.4')
    def test_continuous_equity_hedges_pending_failclosed(self):
        ledger=ec.EquityLedger(self.path/'equity');ledger.apply(self.event())
        b=self.event();b.update(id='B',kind='PENDING',risk=1,margin=50,side=-1);ledger.apply(b)
        c=self.event();c.update(id='C',risk=.01,margin=0)
        self.reject('AGGREGATE_CAPITAL',ledger.apply,c)
        self.assertEqual(ledger.db.execute('SELECT count(*) FROM position').fetchone()[0],2)
        for field,value in [('risk',float('nan')),('margin',float('inf')),('side',0),('units',1.5),('fx',None),('funding',None)]:
            bad=self.event();bad.update(id='C');bad[field]=value
            with self.assertRaises(Exception):ledger.apply(bad)
        close=self.event();close.update(kind='CLOSE',t=2,gross=-1,fill_confirmed=True,commission=.1,stop_gap=.1);z=ledger.apply(close);self.assertAlmostEqual(z['equity'],198.8)
        # Cold restart cannot reset balance or admit deposit as strategy profit.
        again=ec.EquityLedger(self.path/'equity');self.assertAlmostEqual(again.db.execute('SELECT equity FROM account').fetchone()[0],198.8)
        dep=self.event();dep['kind']='DEPOSIT';dep['t']=3;self.reject('DEPOSITS',again.apply,dep)
        close.update(id='B',gross=None,t=3);self.reject('EXIT_UNKNOWN',again.apply,close)
        mark=self.event();mark.update(t=3,kind='MARK',unrealized=float('nan'),fresh=True);self.reject('MARK_UNKNOWN',again.apply,mark)
    @contracts('MXM-SEM-E06.2','MXM-ACT-O07.1','MXM-ACT-O07.3','MXM-EXISTING-N30.3')
    def test_support_cannot_become_net(self):
        z=ec.classify({});self.assertEqual(z['status'],'SUPPORT_ONLY');self.assertIsNone(z['NET_reference']);self.assertIsNone(z['new_NET']);self.assertFalse(z['alpha_certified']);self.assertFalse(z['HARD21'])
        self.reject('OUTCOME_NOT_READ',ec.classify,{'outcome':1.0})
        self.reject('UNACCEPTED_OUTCOME',ec.classify,{'outcomes_read':True,'outcome':1.0})
        neg=ec.classify({'outcomes_read':True,'outcome':-3.4,'authenticated':True,'previously_accepted':True});self.assertEqual(neg['status'],'NEGATIVE_ACCEPTED');self.assertEqual(neg['NET_reference'],-3.4);self.assertIsNone(neg['NET_certified_executable'])
    @contracts('MXM-ACT-O07.2','MXM-EXISTING-N29.1','MXM-EXISTING-N29.2','MXM-EXISTING-N30.1','MXM-EXISTING-N30.2')
    def test_checkpoint_barrier_all_sequences(self):
        reader=ec.EconomicReader(self.path/'read');cp={'generation':1808,'journal_sha256':'H'};receipt={**cp,'state':'COMMITTED','owner_readback':True,'writer_active':False,'sequence':1}
        for seq in range(1,27):
            c={**cp,'generation':1807+seq};v={**receipt,**c,'sequence':seq};z=reader.evaluate(c,v);self.assertEqual(z['generation'],c['generation']);self.assertEqual(z['sequence'],seq)
            self.assertEqual(z,reader.evaluate(c,v))
        self.assertEqual(reader.db.execute('SELECT count(*) FROM evaluation').fetchone()[0],26)
        for changes in [{'state':'PREPARED'},{'state':'FAILED'},{'owner_readback':False},{'writer_active':True}]:self.reject('CHECKPOINT_NOT_OWNER_COMMITTED',reader.evaluate,cp,{**receipt,**changes})
        for changes in [{'generation':1},{'journal_sha256':'OTHER'}]:self.reject('STALE_CHECKPOINT',reader.evaluate,cp,{**receipt,**changes})
        second=ec.EconomicReader(self.path/'read');self.assertEqual(second.evaluate(cp,receipt),reader.evaluate(cp,receipt))
    @contracts('MXM-EXISTING-N19.1','MXM-EXISTING-N19.2','MXM-EXISTING-N19.4')
    def test_greedy_is_not_optimal_bound(self):
        # Two-resource counterexample: cost-ranked A blocks feasible B+C.
        tickets=[{'cost':0,'risk':2,'margin':80},{'cost':1,'risk':1,'margin':40},{'cost':1,'risk':1,'margin':40}]
        greedy=[]
        for t in tickets:
            if sum(x['risk'] for x in greedy)+t['risk']<=2 and sum(x['margin'] for x in greedy)+t['margin']<=80:greedy.append(t)
        self.assertEqual(len(greedy),1)
        for n in range(3,8):
            arr=(tickets*3)[:n];exact=max(sum(bits) for bits in itertools.product((0,1),repeat=n) if sum(t['risk']*b for t,b in zip(arr,bits))<=2 and sum(t['margin']*b for t,b in zip(arr,bits))<=80)
            self.assertGreaterEqual(ec.optimal_count_bound(arr),exact)
        self.assertEqual(ec.optimal_count_bound(tickets),3)
        self.assertFalse(ec.classify({})['HARD21']);self.assertIsNone(ec.classify({})['NET_certified_executable'])

class P4(Base):
    @contracts('MXM-SEM-O10.1','MXM-SEM-O10.2','MXM-SEM-O10.3','MXM-SEM-O10.4','MXM-ACT-N07.1','MXM-ACT-N07.3','MXM-REM-N13.1','MXM-REM-N13.2')
    def test_all_workflows_inert_and_pinned(self):
        z=policy.workflow_guard(ROOT);self.assertEqual(z['legacy_inert'],193);self.assertEqual(z['active_remediation_only'],1)
        import shutil
        root=self.path/'repo';shutil.copytree(ROOT/'.github',root/'.github');(root/'research_core_v4/remediation_p0_p4_20261015').mkdir(parents=True)
        shutil.copy(pathlib.Path(__file__).parent/'workflow_catalog.json',root/'research_core_v4/remediation_p0_p4_20261015/workflow_catalog.json')
        target=next((root/'.github/workflows').glob('*'));target.write_text(target.read_text().replace('if: ${{ false }}','if: ${{ true }}'))
        with self.assertRaises(ValueError):policy.workflow_guard(root)
    @contracts('MXM-SEM-O06.2')
    def test_expected_stop_not_defect_or_broker(self):
        self.assertEqual(policy.classify_job({'log_sha256':'H','exact_policy_code':'EXPECTED_POLICY_STOP','source_binding_valid':True}),'EXPECTED_POLICY_STOP')
        self.assertEqual(policy.classify_job({'log_sha256':'H','build_error':True}),'DEFECT')
        self.assertEqual(policy.classify_job({'conclusion':'failure'}),'UNKNOWN_LOG_UNAVAILABLE')
        self.assertNotEqual(policy.classify_job({'log_sha256':'H','exact_policy_code':'EXPECTED_POLICY_STOP'}),'EXPECTED_POLICY_STOP')
    @contracts('MXM-ACT-N11.1','MXM-ACT-N11.2','MXM-ACT-N11.3')
    def test_independent_principal_scope(self):
        good={'signature_verified':True,'principal':'AUDITOR','scope':'P0-P4@H','expires':20}
        self.assertTrue(policy.independent_acceptance(good,'DIRECTOR','P0-P4@H',10))
        for bad in [{**good,'signature_verified':False},{**good,'principal':'DIRECTOR'},{**good,'scope':'OTHER'},{**good,'expires':9},{'role':'INDEPENDENT_AUDITOR'}]:
            with self.assertRaises(ValueError):policy.independent_acceptance(bad,'DIRECTOR','P0-P4@H',10)
    @contracts('MXM-EXISTING-N20.1','MXM-EXISTING-N20.2','MXM-EXISTING-N20.4')
    def test_exact_package_no_glob_or_cloud(self):
        directory=self.path/'publish';directory.mkdir();(directory/'X_v9R1.dll').write_bytes(b'SYNTHETIC_DLL');(directory/'X_v9R1.algo').write_bytes(b'SYNTHETIC_ALGO')
        expected={p.name:s.sha(p.read_bytes()) for p in directory.iterdir()};z=policy.packaging(directory,expected);self.assertEqual(z['state'],'PACKAGE_READY_ONLY');self.assertFalse(z['cloud_executed']);self.assertIsNone(z['NET'])
        (directory/'X_v9.algo').write_bytes(b'WRONG_VERSION');self.reject('PACKAGE_EXACT_PATHS',policy.packaging,directory,expected)
        (directory/'X_v9.algo').unlink();(directory/'X_v9R1.algo').write_bytes(b'');self.reject('PACKAGE_DIGEST_OR_EMPTY',policy.packaging,directory,expected)

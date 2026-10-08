"""Isolated end-to-end tests. Only fabricated ZIPs and ephemeral test keys.

Only infrastructure observations (GitHub metadata and durable-host metadata)
are supplied by synthetic providers. Signature, payload, git cleanliness,
SHA256 scope, Linux limits, reader, parsing, fitting and output are actual.
No production CLI fixture bypass or installation of a real key exists.
"""
import base64
import copy
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from cryptography.exceptions import InvalidSignature
from . import gate,reader,entrypoint
from research_core_v4.exploratory_dev_v1 import worker as science

SOURCE_ROOT=gate.ROOT
SOURCE_HERE=gate.HERE
REL='research_core_v4/exploratory_dev_v2'
M='research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json'
OLD='research_core_v4/exploratory_dev_v1'
RESULTS=[]

def write_json(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def fabricated_csv(group,days=84):
    # Sparse but complete feature/label neighborhoods; frozen full366-day
    # calendar remains unchanged and all later missing units abstain.
    timestamps={science.START,science.END-600}
    for t0 in np.arange(science.START,science.START+days*science.DAY,21600):
        t=int(t0)
        for lag in science.LAGS:
            cutoff=t-lag;hour=cutoff//3600*3600-3600
            timestamps.update(range(hour,hour+3600,300));timestamps.add(cutoff-300)
        timestamps.update(range(t-300,t+3600,300))
    timestamps=sorted(t for t in timestamps if science.START<=t<science.END)
    f=io.StringIO();w=csv.writer(f,lineterminator='\n')
    w.writerow(['time_utc','open','high','low','close','tick_volume'])
    for t in timestamps:
        k=(t-science.START)//300;o=20+group+.002*(k%113)
        sign=(-1,0,1)[(k*7+k//12+group)%3];c=o+.001*sign
        dt=science.datetime.fromtimestamp(t,science.timezone.utc).isoformat().replace('+00:00','Z')
        w.writerow([dt,o,max(o,c)+.01,min(o,c)-.01,c,1+(k+group)%17])
    return f.getvalue().encode(),timestamps

class Environment:
    def __init__(self,base,kind='normal',full=False):
        self.base=Path(base);self.repo=self.base/'repo';self.repo.mkdir()
        self.archives=self.base/'archives';self.archives.mkdir()
        self.run=self.base/'run';self.run.mkdir();self.checkpoint=self.run/'checkpoint'
        self.output=self.run/'report.json';self.keypath=self.base/'test-public.pem';self.envelope=self.base/'test-envelope.json'
        original=json.loads((SOURCE_HERE/'CODE_BINDINGS_V2.json').read_bytes())
        for path in original['files_sha256']:
            p=self.repo/path;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE_ROOT/path,p)
        (self.repo/REL).mkdir(parents=True,exist_ok=True)
        self.records=copy.deepcopy(json.loads((self.repo/M).read_bytes())['primary_series'])
        if kind=='incomplete':self.records=self.records[:-1]
        prototypes=[fabricated_csv(g,84 if full else 2) for g in range(3)]
        if kind=='corrupt_records':
            raw,ts=prototypes[0];lines=raw.splitlines(keepends=True);lines.insert(2,lines[1]);prototypes[0]=(b''.join(lines),ts)
        expected_original=json.loads((SOURCE_ROOT/M).read_bytes())['original_capture_sha256']
        original_ids={r['symbol_id'] for r in self.records if r['source_archive_sha256']==expected_original}
        archive_evidence=[]
        for is_original,name in [(True,'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip'),(False,'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip')]:
            chosen=[r for r in self.records if (r['symbol_id'] in original_ids)==is_original]
            with zipfile.ZipFile(self.archives/name,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
                for n,r in enumerate(chosen):
                    raw,ts=prototypes[(r['symbol_id']%3)]
                    if kind=='corrupt_records' and n==0:raw,ts=prototypes[0]
                    info=zipfile.ZipInfo(r['file'],date_time=(2025,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,raw)
                    r['series_sha256']=science.digest(raw);r['row_count']=len(raw.splitlines())-1
                    r['first_timestamp_utc']=science.datetime.fromtimestamp(ts[0],science.timezone.utc).isoformat().replace('+00:00','Z')
                    r['last_timestamp_utc']=science.datetime.fromtimestamp(ts[-1],science.timezone.utc).isoformat().replace('+00:00','Z')
            h=science.digest((self.archives/name).read_bytes())
            for r in chosen:r['source_archive_sha256']=h
            archive_evidence.append({'filename':name,'sha256':h,'size_bytes':(self.archives/name).stat().st_size})
        manifest=json.loads((self.repo/M).read_bytes());manifest['primary_series']=self.records
        manifest['primary_count']=len(self.records);manifest['original_capture_sha256']=archive_evidence[0]['sha256'];manifest['delta_capture_sha256']=archive_evidence[1]['sha256']
        write_json(self.repo/M,manifest)
        recon_path=self.repo/OLD/'RECONCILIATION_AND_CORPUS_V1.json';recon=json.loads(recon_path.read_bytes())
        recon['archives']=archive_evidence;recon['frozen_authorities_verified_sha256'][M]=science.digest((self.repo/M).read_bytes())
        write_json(recon_path,recon)
        # Artificial copied provenance binds artificial corpus bytes. The real
        # V1 source/evidence in SOURCE_ROOT are never changed.
        old_delivery_path=self.repo/OLD/'DELIVERY_MANIFEST_V1.json';old_delivery=json.loads(old_delivery_path.read_bytes())
        old_delivery['files_sha256'][OLD+'/RECONCILIATION_AND_CORPUS_V1.json']=science.digest(recon_path.read_bytes())
        write_json(old_delivery_path,old_delivery)
        layout_path=self.repo/REL/'HOST_LAYOUT_V2.json';layout=json.loads(layout_path.read_bytes())
        layout['paths']={'archive_directory':str(self.archives),'checkpoint_directory':str(self.checkpoint),'output_file':str(self.output)}
        write_json(layout_path,layout)
        bindings=copy.deepcopy(original)
        bindings['files_sha256']={p:science.digest((self.repo/p).read_bytes()) for p in original['files_sha256']}
        if kind=='missing_dependency':del bindings['files_sha256']['research_core_v4/operational_v1/prequential_score.py']
        if kind=='inherited_binding':bindings['files_sha256']['research_core_v4/operational_v1/prequential_score.py']='0'*64
        write_json(self.repo/REL/'CODE_BINDINGS_V2.json',bindings)
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        subprocess.run(['git','add','.'],cwd=self.repo,check=True)
        env=dict(os.environ,GIT_AUTHOR_DATE='2026-01-01T00:00:00+0000',GIT_COMMITTER_DATE='2026-01-01T00:00:00+0000')
        subprocess.run(['git','-c','user.name=SyntheticFixture','-c','user.email=fixture@example.invalid','commit','-qm','Fabricated-only isolated execution scope'],cwd=self.repo,env=env,check=True)
        self.head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo,text=True).strip()
        scope=dict(bindings['files_sha256']);scope[REL+'/CODE_BINDINGS_V2.json']=science.digest((self.repo/REL/'CODE_BINDINGS_V2.json').read_bytes())
        self.key=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.keypath.write_bytes(self.key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo));self.keypath.chmod(0o600)
        self.host={'hostname':'isolated-synthetic-provider','devices':{k:1 for k in layout['paths']},'filesystems':{k:'ext4' for k in layout['paths']}}
        self.payload={'schema':'mxm.primary145.single-exploratory-arm.v2','campaign':'PRIMARY145_EXPLORATORY_V1_OPERATIONAL_V2_SINGLE_PASS',
          'repository':gate.v1.REPO,'branch':gate.v1.BRANCH,'execution_head':self.head,'independent_preexecution_audit':'APPROVED',
          'inference_class':'EXPLORATORY_ONLY_NO_FORMAL_REJECTION','limits':dict(gate.v1.LIMITS),'files_sha256':scope,
          **layout['paths'],'host_binding':{**self.host,'independent_durability_approved':True,'durability_evidence_sha256':science.digest(b'ISOLATED_SYNTHETIC_PROVIDER_NOT_REAL_DURABILITY')}}
        self.sign()

    def sign(self):
        envelope={'payload':self.payload,'signature_base64':base64.b64encode(self.key.sign(gate.canonical(self.payload))).decode()}
        write_json(self.envelope,envelope)

    def execute(self,remote_head=None,host=None,runtime=None,interrupt=False):
        original_socket=socket.socket;original_connection=socket.create_connection
        try:
            with patch.object(gate,'ROOT',self.repo),patch.object(gate,'HERE',self.repo/REL),patch.object(gate,'KEY',self.keypath),patch.object(reader,'ROOT',self.repo),patch.object(gate.v1,'live_head',return_value=remote_head or self.head),patch.object(gate,'observable_host',return_value=host or self.host):
                if runtime:
                    with patch.object(gate.platform,'python_version',return_value=runtime):return entrypoint.execute(self.envelope)
                if interrupt:
                    real=science.derive;calls=[0]
                    def stop(bars):
                        calls[0]+=1
                        if calls[0]==2:raise KeyboardInterrupt('FABRICATED_INTERRUPTION_AFTER_ONE_SERIES')
                        return real(bars)
                    with patch.object(science,'derive',side_effect=stop):return entrypoint.execute(self.envelope)
                return entrypoint.execute(self.envelope)
        finally:
            socket.socket=original_socket;socket.create_connection=original_connection

def model_digest(report):
    excluded={'authorization_payload_sha256','execution_head','CPU_seconds','max_RSS_KiB','parsed_corpus_passes','broker_requests','protected_forward_rows','orders','operational_version'}
    return science.digest(gate.canonical({k:v for k,v in report.items() if k not in excluded}))

class Integrated(unittest.TestCase):
    def negative(self,kind,mutate=None,expected=ValueError,pattern=None,**options):
        with tempfile.TemporaryDirectory(prefix='mxm-synthetic-') as td:
            env=Environment(td,kind)
            if mutate:mutate(env)
            if pattern:
                with self.assertRaisesRegex(expected,pattern):env.execute(**options)
            else:
                with self.assertRaises(expected):env.execute(**options)
            self.assertFalse(env.output.exists())
            return env.checkpoint.exists()

    def test_01_signed_payload_tampering(self):
        def mutate(e):
            x=json.loads(e.envelope.read_bytes());x['payload']['execution_head']='0'*40;write_json(e.envelope,x)
        self.assertFalse(self.negative('normal',mutate,InvalidSignature))

    def test_02_wrong_live_head(self):
        self.assertFalse(self.negative('normal',pattern='LIVE_HEAD_DRIFT',remote_head='0'*40))

    def test_03_wrong_signed_hashes(self):
        def mutate(e):e.payload['files_sha256'][M]='0'*64;e.sign()
        self.assertFalse(self.negative('normal',mutate,pattern='ARM_HASH_SCOPE'))

    def test_04_wrong_absolute_paths(self):
        def mutate(e):e.payload['archive_directory']='/wrong/absolute/path';e.sign()
        self.assertFalse(self.negative('normal',mutate,pattern='EXACT_PATH_SCOPE'))

    def test_05_runtime_drift(self):
        self.assertFalse(self.negative('normal',pattern='PYTHON_RUNTIME_DRIFT',runtime='0.0.0'))

    def test_06_missing_frozen_dependency(self):
        self.assertFalse(self.negative('missing_dependency',pattern='DEPENDENCY_SCOPE_INCOMPLETE'))

    def test_07_inherited_binding_override(self):
        self.assertFalse(self.negative('inherited_binding',pattern='INHERITED_HASH_BINDING_DRIFT'))

    def test_08_host_drift(self):
        self.assertFalse(self.negative('normal',pattern='EXECUTION_HOST_DRIFT',host={'hostname':'wrong','devices':{},'filesystems':{}}))

    def test_09_volatile_filesystem_denied(self):
        def mutate(e):
            e.host['filesystems']={k:'overlay' for k in e.host['filesystems']};e.payload['host_binding'].update(e.host);e.sign()
        self.assertFalse(self.negative('normal',mutate,pattern='EPHEMERAL_FILESYSTEM_DENIED'))

    def test_10_incomplete145_corpus(self):
        self.assertTrue(self.negative('incomplete',pattern='PRIMARY145_INCOMPLETE'))

    def test_11_corrupted_records_fail_in_actual_parser(self):
        self.assertTrue(self.negative('corrupt_records',pattern='SOURCE_CHRONOLOGY'))

    def test_12_corrupted_zip_digest(self):
        def mutate(e):
            p=next(e.archives.glob('*.zip'));p.write_bytes(p.read_bytes()+b'corruption')
        self.assertTrue(self.negative('normal',mutate,pattern='ARCHIVE_DIGEST'))

    def test_13_interrupted_invocation_and_no_replay(self):
        with tempfile.TemporaryDirectory(prefix='mxm-interrupted-') as td:
            env=Environment(td)
            with self.assertRaises(KeyboardInterrupt):env.execute(interrupt=True)
            state=json.loads((env.checkpoint/'CONSUMED.json').read_bytes())
            self.assertEqual(state['parsed_series'],1);self.assertFalse(state['complete'])
            cache_sha=dict(state['caches'])
            with self.assertRaises(FileExistsError):env.execute()
            self.assertEqual(json.loads((env.checkpoint/'CONSUMED.json').read_bytes())['caches'],cache_sha)
            self.assertFalse(env.output.exists())
            RESULTS.append({'interrupted_series':1,'durable_cache_count':1,'replay_denied':True,'error':'FileExistsError invocation reservation'})

    def test_14_complete_signed_reader_checkpoint_report145(self):
        with tempfile.TemporaryDirectory(prefix='mxm-integrated-full-') as td:
            env=Environment(td,full=True);started=time.process_time();report=env.execute()
            state=json.loads((env.checkpoint/'CONSUMED.json').read_bytes())
            self.assertTrue(state['complete']);self.assertEqual(state['parsed_series'],145);self.assertEqual(len(state['caches']),145)
            self.assertEqual(len(report['comparisons']),18);self.assertEqual(len(report['score_clock_utc_epoch']),1240)
            self.assertTrue(all(x['identities']==145 and x['fixed_opportunities']==179800 for x in report['comparisons']))
            self.assertEqual(json.loads(env.output.read_bytes()),report)
            caches=[]
            for sid in report['identity_order']:
                p=env.checkpoint/(str(sid)+'.npz');self.assertEqual(science.digest(p.read_bytes()),state['caches'][str(sid)])
                with np.load(p,allow_pickle=False) as z:caches.append({k:z[k] for k in z.files})
            # Repeat scoring only on FABRICATED cached data, not raw real data.
            repeated=science.evaluate(caches,report['identity_order'])
            self.assertEqual(model_digest(report),model_digest(repeated))
            self.check_across_refits(caches,report['identity_order'])
            with self.assertRaises(ValueError):env.execute()  # output already exists, no second pass
            report['data_kind']='ISOLATED_FABRICATED_END_TO_END_NOT_MARKET_EVIDENCE'
            report['deterministic_scientific_output_sha256']=model_digest(repeated)
            SOURCE_HERE.joinpath('INTEGRATED_SYNTHETIC_REPORT_V2.json.gz').write_bytes(gzip.compress(gate.canonical(report),mtime=0))
            RESULTS.append({'route':'actual signature->scope/runtime/paths/host->reservation->two ZIPs->145 parsers->derive->evaluate18->checkpoint->report',
              'signed_artifact_kind':'EPHEMERAL_TEST_KEY_AND_FABRICATED_CORPUS_ONLY','parsed_series':145,'parsed_rows':state['parsed_rows'],
              'archive_sources':2,'comparisons':18,'calendar_units':1240,'actual_CPU_seconds':time.process_time()-started,
              'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'model_sha256':model_digest(repeated),
              'actual_Linux_resource_limits':{'CPU':list(resource.getrlimit(resource.RLIMIT_CPU)),'AS':list(resource.getrlimit(resource.RLIMIT_AS))},
              'checkpoint_sha256':science.digest((env.checkpoint/'CONSUMED.json').read_bytes()),'no_replay':True,
              'infrastructure_providers':'GitHub HEAD and durable-host observation simulated; no signature/payload/reader/science bypass'})

    def check_across_refits(self,caches,ids):
        n=len(ids);clocks=science.CLOCK;times=np.repeat(clocks,n);identity=np.tile(ids,len(clocks));checks=[]
        for li,lag in enumerate(science.LAGS):
            for hi,h in enumerate(science.HORIZONS):
                b=np.stack([x['b'][li] for x in caches],axis=1).reshape(-1,10)
                phi=np.stack([x['phi'][li] for x in caches],axis=1).reshape(-1,2)
                y=np.stack([x['y'][li,hi] for x in caches],axis=1).reshape(-1)
                valid=np.stack([x['feature_ok'][li]&x['label_ok'][li,hi] for x in caches],axis=1).reshape(-1)
                maturity=times+300*h+lag
                for day in (56,63,70,77,84):
                    refit=science.START+day*science.DAY
                    fit=science.fit_family(times,maturity,identity,b,phi,y,valid,refit,science.START)
                    self.assertIsNotNone(fit)
                    changed=y.copy();changed[maturity>=refit]+=9
                    perturbed=science.fit_family(times,maturity,identity,b,phi,changed,valid,refit,science.START)
                    for a,bb in zip([fit[0].beta_b]+fit[1],[perturbed[0].beta_b]+perturbed[1]):np.testing.assert_array_equal(a,bb)
                    self.assertEqual(fit[0].ymean,perturbed[0].ymean);self.assertEqual(fit[0].ysd,perturbed[0].ysd)
                    ix=fit[0].train_indices;self.assertTrue(np.all(maturity[ix]<refit));self.assertTrue(np.all(times[ix]+245*60<refit))
                    j=int(ix[-1]);self.assertEqual(science.forecasts(fit,b[j],phi[j])[0],science.forecasts(perturbed,b[j],phi[j])[0])
                    # Mature prefix perturbation must affect fit: test is not vacuous.
                    changed2=y.copy();changed2[ix[0]]+=9
                    known=science.fit_family(times,maturity,identity,b,phi,changed2,valid,refit,science.START)
                    self.assertNotEqual(known[0].ymean,fit[0].ymean)
                    checks.append({'lag':lag,'horizon':h,'refit_day':day,'prefix_rows':len(ix),'future_contamination_forecast_invariant':True,'mature_prefix_sensitivity':True})
        self.assertEqual(len(checks),30);RESULTS.append({'no_lookahead_across_refits':checks,'check_count':30})

if __name__=='__main__':
    started=time.process_time();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Integrated)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    out={'schema':'mxm.primary145.integrated-offline.v2','tests_run':result.testsRun,'success':result.wasSuccessful(),
         'failures':len(result.failures),'errors':len(result.errors),'CPU_seconds':time.process_time()-started,
         'evidence':RESULTS,'real_market_numeric_parsing':0,'real_keys_installed':0,'real_ARM_created':False}
    write_json(SOURCE_HERE/'INTEGRATED_RESULT_V2.json',out)
    print(json.dumps({'tests_run':result.testsRun,'success':result.wasSuccessful(),'CPU_seconds':out['CPU_seconds'],'evidence_blocks':len(RESULTS)}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

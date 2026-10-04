"""Final-head offline source/package verifier. All broker connections prohibited."""
import argparse,hashlib,json,socket,subprocess,tempfile,unittest,urllib.request,urllib.parse,zipfile
from pathlib import Path
from unittest.mock import patch
MODULES=['tests.test_v4_signed_tick_decoder_fix','tests.test_v4_android_private_lock_fix','tests.test_v4_quote_support_probe','tests.test_v4_android_current_metadata','tests.test_v4_quote_scope_metadata_protocol','tests.test_m6_browser_oauth','tests.test_v4_quote_probe_decision_law','tests.test_v4_quote_probe_hardening']
STATE='research_core_v4/state/'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def suite():return unittest.TestLoader().loadTestsFromNames(MODULES)
def test_ids(s):
    out=[]
    for t in s:
        out.extend(test_ids(t) if isinstance(t,unittest.TestSuite) else [t.id()])
    return out

def offline_tests():
    # The existing local OAuth callback-server test needs loopback. No broker,
    # public HTTP, DNS-target connection or secret-bearing live auth is allowed.
    original_connect=socket.socket.connect;original_ex=socket.socket.connect_ex
    original_create=socket.create_connection;original_urlopen=urllib.request.urlopen
    def permitted(address):
        if not isinstance(address,tuple) or address[0] not in ['127.0.0.1','::1']:raise AssertionError('EXTERNAL_NETWORK_DENIED_OFFLINE_PROOF')
    def connect(s,a):permitted(a);return original_connect(s,a)
    def connect_ex(s,a):permitted(a);return original_ex(s,a)
    def create(a,*args,**kw):permitted(a);return original_create(a,*args,**kw)
    def urlopen(url,*args,**kw):
        u=url.full_url if hasattr(url,'full_url') else url
        if urllib.parse.urlparse(u).hostname not in ['127.0.0.1','::1']:raise AssertionError('EXTERNAL_HTTP_DENIED_OFFLINE_PROOF')
        return original_urlopen(url,*args,**kw)
    tests=suite();ids=test_ids(tests)
    with patch.object(socket.socket,'connect',connect),patch.object(socket.socket,'connect_ex',connect_ex),patch.object(socket,'create_connection',create),patch.object(urllib.request,'urlopen',urlopen):
        result=unittest.TextTestRunner(verbosity=1).run(tests)
    if not result.wasSuccessful():raise RuntimeError('offline validation failed')
    return dict(tests_run=result.testsRun,test_ids=ids,external_network_denied=True,real_broker_contacts=0,real_historical_requests=0,loopback_only_for_existing_OAuth_callback_test=True)

def verify_package(root,archive,require_durable=False):
    from research_core_v4.pydroid_quote_probe_v1 import verify
    from research_core_v4.quote_probe_decision_law_v1 import load_bound
    from tools.build_v4_quote_probe_package import build
    root=Path(root);archive=Path(archive);law,plan=load_bound(root)
    expected={'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json':'77462da0329b21dd981896c3ab31f3383ef8f092948ac1c6c61a6c148e630208','FIRST_V4_DEVELOPMENT_RESPONSE_INTERPRETATION_V1.json':'715e0d100fddda9b525fedc6f1dbf852973419d14634fa0c347fdb445d31cad2','NEXT_QUOTE_SEQUENCE_DESIGN_V2.json':'f1c986e8588d721babf07eaa34fbf838077508cb96b8a6f35ef04812c379d5c8','NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V1.json':'9c03409cab9c5d5623aa2bd5a694afcc3bb8a6915572a6ae27876aa0bc62a6d2','NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json':'e60b2dcb6cac33fd0f419daf0263d0003beaf1a0d77e7842a5ae690ff855bb16','NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64':'cdbfe0478771277fd6f258c269e324d5cc65308c9831ebcae26a4a8bdb503335'}
    for p,h in expected.items():
        if digest((root/(STATE+p)).read_bytes())!=h:raise AssertionError('preserved bytes changed: '+p)
    old=json.loads((root/(STATE+'NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V1.json')).read_bytes())
    for k in ['thresholds','definitions','support_stop','support_continue','singleton_contexts','full_capture_boundary','transport_fail_closed','limits']:
        if law[k]!=old[k]:raise AssertionError('scientific decision law changed: '+k)
    authority=json.loads((root/(STATE+'USER_DEVICE_PROBE_EXECUTION_AUTHORITY_V1.json')).read_bytes())
    if digest(archive.read_bytes())!=authority['android_package']['sha256']:raise AssertionError('outer package binding')
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None or len(z.namelist())!=len(set(z.namelist())):raise AssertionError('ZIP integrity')
            for n in z.namelist():
                if Path(n).is_absolute() or '..' in Path(n).parts:raise AssertionError('ZIP path')
            z.extractall(d)
        deploy=d/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1';manifest,p=verify(deploy)
        if p!=plan:raise AssertionError('plan altered in deployment')
        for path,h in manifest['file_sha256'].items():
            if (root/path).is_file() and digest((root/path).read_bytes())!=h:raise AssertionError('source/package mismatch: '+path)
        rebuilt=d/'rebuilt.zip';build(root,rebuilt,root.parent/'probe-wheels')
        if rebuilt.read_bytes()!=archive.read_bytes():raise AssertionError('nondeterministic package')
    for path,h in authority['source_file_sha256'].items():
        if digest((root/path).read_bytes())!=h:raise AssertionError('authority source binding')
    head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    if require_durable:
        rel=STATE+'USER_DEVICE_PROBE_EXECUTION_AUTHORITY_V1.json'
        intro=subprocess.check_output(['git','-C',str(root),'log','-1','--format=%H','--',rel]).decode().splitlines()
        if intro!=[head]:raise AssertionError('HEAD must be exact latest authority-updating commit')
        if subprocess.check_output(['git','-C',str(root),'status','--porcelain']).strip():raise AssertionError('dirty final checkout')
        if subprocess.check_output(['git','-C',str(root),'show',head+':'+rel])!=(root/rel).read_bytes():raise AssertionError('durable authority bytes')
    return dict(exact_final_head=head,authority_sha256=digest((root/(STATE+'USER_DEVICE_PROBE_EXECUTION_AUTHORITY_V1.json')).read_bytes()),package_sha256=digest(archive.read_bytes()),source_package_parity=True,deterministic_zip=True,plan_unchanged=True,science_decision_semantic_identity=True,preserved_first_result_and_interpretation=True,real_historical_requests=0,real_scientific_responses=0)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package');p.add_argument('--require-durable',action='store_true');a=p.parse_args()
    result=offline_tests()
    if a.package:result.update(verify_package(Path(__file__).resolve().parents[1],a.package,a.require_durable))
    print(json.dumps(result,sort_keys=True))

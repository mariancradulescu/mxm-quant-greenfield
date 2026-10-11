"""Verified accepted CSV -> frozen sufficient features/labels; no result comparison."""
import pathlib,zipfile,json,hashlib,csv,io,math,gzip,base64
from datetime import datetime
from research_core_v4.integrated_alpha_campaign_v1 import kernel_v1 as k
from research_core_v4.aidr_cost_coverage_v1.agentless_transport_v1 import encrypt
ROOT=pathlib.Path(__file__).resolve().parents[2];P=pathlib.Path(__file__).resolve().parent
FP='b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636'
def sha(b):return hashlib.sha256(b).hexdigest()
def parse(raw):
    out={};previous=-1
    for r in csv.DictReader(io.StringIO(raw.decode())):
        t=int(datetime.fromisoformat(r['time_utc'].replace('Z','+00:00')).timestamp());v=[float(r[n]) for n in ('open','high','low','close','tick_volume')]
        assert t%300==0 and previous<t<k.END and all(math.isfinite(x) for x in v) and min(v[:4])>0 and v[2]<=min(v[0],v[3])<=max(v[0],v[3])<=v[1] and v[4]>=0 and v[4].is_integer()
        out[t]=v;previous=t
    return out

def main(directory):
    m=json.loads((ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());sources={};archives=[]
    for name,want in [('MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip',m['original_capture_sha256']),('MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip',m['delta_capture_sha256'])]:
        path=pathlib.Path(directory)/name;assert sha(path.read_bytes())==want;z=zipfile.ZipFile(path);assert len(z.namelist())==len(set(z.namelist()));cm=json.loads(z.read('CAPTURE_MANIFEST.json'));assert cm['account_fingerprint']==FP and cm['source_environment']=='Pepperstone - Europe LIVE' and cm['read_only_assertion'] and not cm['orders_placed'] and not cm['protected_evidence_opened'];sources[want]=z;archives.append({'name':name,'sha256':want,'size':path.stat().st_size,'capture_manifest_sha256':sha(z.read('CAPTURE_MANIFEST.json'))})
    output=[];rowcount=0
    for x in m['primary_series']:
        raw=sources[x['source_archive_sha256']].read(x['file']);assert sha(raw)==x['series_sha256'];bars=parse(raw);assert len(bars)==x['row_count'];rowcount+=len(bars)
        output.append({'source':x,'records':k.extract(bars)})
    assert len(output)==145 and rowcount==m['total_primary_M5_rows']==11406418
    value={'schema':'mxm.private.verified.primary145.campaign.features.v1','archive_provenance':archives,'source_rows':rowcount,'local_preprocessing':'ALL_ACCEPTED_CSV_BYTES_AND_MEMBER_SHA_VERIFIED;FROZEN_EXTRACTOR;NOT_RUNNER_RAW_CSV_REDECODE;NO_DIRECTION_COMPARISON_OR_OUTCOME_SELECTION','extractor_sha256':sha((P/'stage_v1.py').read_bytes()),'kernel_sha256':sha((P/'kernel_v1.py').read_bytes()),'items':output}
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n';dest=P/'input.mxmenc';meta=encrypt(gzip.compress(raw,mtime=0),ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',dest);blob=dest.read_bytes();encoded=base64.b64encode(blob).decode();parts=[]
    for j in range(0,len(encoded),180000):
        path=P/f'input-{j//180000:03}.b64';path.write_text(encoded[j:j+180000]+'\n');parts.append(str(path.relative_to(ROOT)))
    dest.unlink();manifest={'schema':'mxm.campaign.accepted.encrypted.input.v1','ciphertext_sha256':sha(blob),'canonical_sha256':sha(raw),'parts':parts,'source_rows':rowcount,'source_identities':145,'extractor_sha256':value['extractor_sha256'],'kernel_sha256':value['kernel_sha256'],'archive_provenance':archives,'authentic_source_status':'LOCAL_BYTES_VERIFIED;RUNNER_AUTHENTICATED_FEATURE_PACKAGE_NOT_RAW_CSV_REDECODE','independent_holdout':False,'authenticated_local_roundtrip':meta['authenticated_local_roundtrip']}
    (P/'INPUT_MANIFEST_V1.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');print(json.dumps({'parts':len(parts),'encrypted_bytes':len(blob),'source_rows':rowcount,'canonical_sha256':sha(raw),'ciphertext_sha256':sha(blob)}))
if __name__=='__main__':
    import sys;main(sys.argv[1])

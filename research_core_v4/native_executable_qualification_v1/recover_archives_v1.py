"""Recover accepted archive member bytes; no strategy or outcome evaluation."""
import base64,gzip,hashlib,json,pathlib,zipfile
from research_core_v4.aidr_cost_coverage_v1.agentless_transport_v1 import encrypt
P=pathlib.Path(__file__).resolve().parent
ROOT=P.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def recover(directory):
    files={p.name:p for p in pathlib.Path(directory).rglob('*.zip')}
    bindings=[('EURUSD',1,'MXM_C031_STRUCTURAL_EXTENSION_WAVE_01_M5_8W_CAPTURE_CANONICAL_V1.zip','83df470fb760ec15ae05e5843686e8e4a4dcde84badcd0d4d27740042964afb0','raw/1_EURUSD_M5.csv',None,'evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json'),
      ('GBPUSD',2,'MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6.zip','dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d','stage_a_m5/GBPUSD_M5.csv','3053153b404412600756ada4200a7db2289181d804f9ef9a9feddebe517fd519','data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json'),
      ('SpotCrude',250,'MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6.zip','dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d','stage_a_m5/SpotCrude_M5.csv','b76cf6090b9e5f88b35a77f57d40dbd6e18b69f25927733d7a48cc80b78cf661','data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json')]
    sources=[]
    for name,sid,archive,expected,suffix,member_sha,acceptance in bindings:
        path=files[archive];assert sha(path.read_bytes())==expected
        with zipfile.ZipFile(path) as z:
            matches=[n for n in z.namelist() if n.endswith('/'+suffix) or n==suffix];assert len(matches)==1
            b=z.read(matches[0]);assert member_sha is None or sha(b)==member_sha
        sources.append({'symbol':name,'sid':sid,'archive':archive,'archive_sha256':expected,'member':matches[0],'member_sha256':sha(b),'member_bytes_b64':base64.b64encode(b).decode(),'acceptance_path':acceptance,'acceptance_sha256':sha((ROOT/acceptance).read_bytes()),'same_account_fingerprint_sha256':'b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636'})
    catalog=[]
    for name,path in sorted(files.items()):
        with zipfile.ZipFile(path) as z:
            # Central directory only; never opens earlier economic results.
            target=[n for n in z.namelist() if any(s.lower() in n.lower() for s in ['EURUSD','GBPUSD','SpotCrude','WTIUSD']) and n.lower().endswith(('.csv','.csv.gz'))]
            catalog.append({'archive':name,'size':path.stat().st_size,'sha256':sha(path.read_bytes()),'target_members':target,'selected_m5_source':name in {b[2] for b in bindings}})
    payload={'schema':'mxm.private.native.archive.recovery.v1','sources':sources,'catalog':catalog,'demo_tick_archives':{'EURUSD.zip':'c015aae1df786a0041da0db94ab074686c8e16771a01402e09a300cba2ddc104','SpotCrude.zip':'463aa01070b3c2a22c2cb0083e058160916363811e4a07e6596c149d0773d8b2','manifest_archive':'MXM_A118_C02_OPENAPI_V1.zip','accountMode':'DEMO','reused_as_live_execution':False},'legacy_cbot_archives':'OLDER_A007_AND_A014_NATIVE_M5_IDENTIFIED_BUT_ACCOUNT_IDENTITY_UNCERTIFIED_AND_ENDING_BEFORE_SELECTED_ACCEPTED_SOURCES;RETAINED_UNMODIFIED_NOT_EXECUTABLE_LIVE_SUBSTITUTES','closed_results_read':False}
    raw=canonical(payload);dst=P/'archive-input.mxmenc'
    meta=encrypt(gzip.compress(raw,mtime=0),ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',dst)
    b64=base64.b64encode(dst.read_bytes()).decode();parts=[]
    for i in range(0,len(b64),180000):
        path=P/f'archive-input-part-{i//180000:02d}.b64';path.write_text(b64[i:i+180000]+'\n');parts.append(str(path.relative_to(ROOT)))
    dst.unlink();manifest={'schema':'mxm.owner.encrypted.native.archive.input.v1','ciphertext_sha256':meta['ciphertext_sha256'],'canonical_sha256':sha(raw),'parts':parts,'members':[{k:v for k,v in s.items() if k!='member_bytes_b64'} for s in sources],'catalog':catalog,'envelope':'EXISTING_RSA_OAEP_OPENPGP_AES256_MDC_UNCHANGED','authenticated_local_roundtrip':meta['authenticated_local_roundtrip']}
    (P/'ARCHIVE_INPUT_MANIFEST_V1.json').write_bytes(json.dumps(manifest,indent=2,sort_keys=True).encode()+b'\n')
    print(json.dumps({'parts':len(parts),'ciphertext_sha256':meta['ciphertext_sha256'],'catalogued_archives':len(catalog),'reused_csv_members':len(sources)}))
if __name__=='__main__':
    import sys
    recover(sys.argv[1])

"""Deterministic verifier-only overlay; leaves accepted probe sources intact."""
import argparse,hashlib,json,zipfile
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def build(root,output):
    root=Path(root);output=Path(output);intake=json.loads((root/'research_core_v4/state/QUOTE_SUPPORT_PROBE_RETURN_INTAKE_V1.json').read_bytes())
    original=root.parent/intake['accepted_android_package']['filename']
    accepted_manifest_sha='0bed405b41604d8fbe83068e7ccd69c8fc79bfbfee4fe228371d8211be49e2df'
    if original.exists():
        if sha(original.read_bytes())!=intake['accepted_android_package']['sha256']:raise ValueError('accepted original package SHA')
        with zipfile.ZipFile(original) as z:manifest=z.read('MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/PACKAGE_MANIFEST.json')
        if sha(manifest)!=accepted_manifest_sha:raise ValueError('accepted original manifest SHA')
    authority={'schema':'mxm.v4.private-proof-device-authority.v1','accepted_probe_manifest_sha256':accepted_manifest_sha,'compact_file_sha256':{n:h for n,h in intake['input_zip']['file_sha256'].items() if n!='CHECKSUMS.sha256'},'compact_zip_sha256':intake['input_zip']['sha256'],'minimum_completion_active_seconds':intake['observed_transport']['active_seconds'],'plan_sha256':'e60b2dcb6cac33fd0f419daf0263d0003beaf1a0d77e7842a5ae690ff855bb16','private_proof_only':True,'network_authorized':False,'broker_acquisition_authorized':False,'raw_quote_export_authorized':False,'scientific_response_authorized':False,'device_proof_not_yet_executed':True}
    files={n:(root/n).read_bytes() for n in ['V4_QUOTE_SUPPORT_PRIVATE_PROOF_RUN.py','V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY.py']}
    files['PRIVATE_PROOF_AUTHORITY_V1.json']=json.dumps(authority,sort_keys=True,indent=2).encode()+b'\n'
    files['PRIVATE_PROOF_README.txt']='Extrage peste ACELAȘI folder MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1, păstrând toate fișierele și datele existente. Rulează o singură dată V4_QUOTE_SUPPORT_PRIVATE_PROOF_RUN.py în Pydroid. Proba nu se relansează. Verificarea este offline; trimite numai MXM_V4_QUOTE_SUPPORT_PRIVATE_PROOF_V1.zip din RETURN_PRIVATE_PROOF. Nu trimite raw sau OAuth.\n'.encode()
    files['PRIVATE_PROOF_PACKAGE_MANIFEST.json']=json.dumps({'schema':'mxm.v4.private-proof-verifier-overlay.v1','source_head_binding':'GIT_COMMIT_PREPARING_COMPLETED_PROBE_PRIVATE_OFFLINE_PROOF_V1','file_sha256':{n:sha(b) for n,b in sorted(files.items())},'existing_probe_files_overwritten':False},sort_keys=True,indent=2).encode()+b'\n'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(files.items()):
            info=zipfile.ZipInfo('MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/'+n,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,b)
    return {'filename':output.name,'sha256':sha(output.read_bytes()),'size_bytes':output.stat().st_size,'members':len(files)}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',required=True);v=a.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],v.output)))

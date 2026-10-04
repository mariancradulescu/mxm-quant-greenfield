"""Bounded probe deployment builder. No broker or historical request occurs here."""
from pathlib import Path
import argparse,json,subprocess,zipfile
from tools.build_v4_current_metadata_android_package import build as dependencies,digest
PROBE_FILES=['research_core_v4/state/NEXT_QUOTE_SEQUENCE_V2_ORDERED_EVENT_IMPLEMENTATION_AMENDMENT_V1.json','research_core_v4/state/NEXT_QUOTE_SEQUENCE_DEVICE_AUTHORITY_SCOPE_V1.json','research_core_v4/quote_probe_schedule_preflight_v1.py','research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_PROBE_CONTRACT_V2.json','research_core_v4/state/NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V2.json','V4_QUOTE_SUPPORT_PROBE_RUN.py','research_core_v4/quote_probe_plan_v1.py',
 'research_core_v4/quote_probe_transport_v1.py','research_core_v4/quote_probe_support_v1.py',
 'research_core_v4/pydroid_quote_probe_v1.py','research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json',
 'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_PROBE_CONTRACT_V1.json',
 'research_core_v4/state/NEXT_QUOTE_SEQUENCE_METHOD_SUPPORT_AUDIT_V1.json']
def build(root,output,wheel_dir=None,source_head=None):
    root=Path(root);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    bootstrap=output.parent/'_dependency_only.zip'
    dependencies(root,bootstrap,wheel_dir=wheel_dir)
    with zipfile.ZipFile(bootstrap) as z:
        prefix='MXM_V4_CURRENT_METADATA_ANDROID_V1/'
        files={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix) and n[len(prefix):] not in ['V4_CURRENT_METADATA_RUN.py','research_core_v4/pydroid_quote_metadata_launcher_v1.py','PACKAGE_MANIFEST.json','README.txt']}
    bootstrap.unlink()
    for p in PROBE_FILES:files[p]=(root/p).read_bytes()
    # No evaluator, old collector, outcome files, or full historical manifest.
    head=source_head or 'GIT_COMMIT_APPLYING_ANDROID_PRIVATE_POSIX_LOCK_FIX_V1'
    p={'schema':'mxm.v4.quote-support-probe-source-package.v1','source_head':head,'device_authority_scope_sha256':digest(files['research_core_v4/state/NEXT_QUOTE_SEQUENCE_DEVICE_AUTHORITY_SCOPE_V1.json']),'file_sha256':{n:digest(b) for n,b in sorted(files.items())},'full_capture_authorized':False,'scientific_response_authorized':False,'broker_called_by_builder':False}
    files['PACKAGE_MANIFEST.json']=json.dumps(p,sort_keys=True,indent=2).encode()+b'\n'
    files['README.txt']='Autoritate strictă pentru un singur probe logic, reluabil; verificarea calendarului curent precede orice cerere istorică: actualizează fișierele din același folder existent fără a șterge checkpoint-ul sau datele locale, deschide V4_QUOTE_SUPPORT_PROBE_RUN.py în Pydroid, RUN o singură dată. OAuth privat se reutilizează. La întrerupere păstrează folderul și rulează același fișier pentru resume. Nu se continuă automat la captura integrală. Trimite numai MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1.zip indicat la final; nu trimite DEVICE_LOCAL_PROBE_RAW sau cache-ul OAuth.\n'.encode()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(files.items()):
            info=zipfile.ZipInfo('MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/'+n,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,b)
    return {'file':str(output),'size_bytes':output.stat().st_size,'sha256':digest(output.read_bytes()),'source_head':head,'members':len(files)}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--wheel-dir');v=a.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],v.output,v.wheel_dir)))

"""Deterministic Android deployment package. Build only; never runs OAuth/broker."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import urllib.request
import zipfile

BASE_FILES=['V4_CURRENT_METADATA_RUN.py','research_core_v4/__init__.py',
 'research_core_v4/quote_scope_metadata_v1.py','research_core_v4/quote_metadata_android_v1.py',
 'research_core_v4/pydroid_quote_metadata_launcher_v1.py',
 'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json',
 'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_CONTRACT_V1.json',
 'm6/__init__.py','m6/ctrader_capture.py','m6/_ctrader_capture_base.py',
 'm6/ctrader_transport.py','m6/pydroid_oauth.py','m6/ctrader_proto/__init__.py',
 'm6/ctrader_proto/OpenApiCommonModelMessages_pb2.py','m6/ctrader_proto/OpenApiCommonMessages_pb2.py',
 'm6/ctrader_proto/OpenApiModelMessages_pb2.py','m6/ctrader_proto/OpenApiMessages_pb2.py',
 'm6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt']


def digest(raw):return hashlib.sha256(raw).hexdigest()


def build(root,output,*,wheel_dir=None,source_head=None):
    root=Path(root);output=Path(output)
    lock=json.loads((root/'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_DEPENDENCIES_V1.json').read_bytes())
    files={rel:(root/rel).read_bytes() for rel in BASE_FILES}
    files['research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_DEPENDENCIES_V1.json']=json.dumps(lock,sort_keys=True,indent=2).encode()+b'\n'
    for dep in lock['wheels']:
        path=Path(wheel_dir or output.parent/'wheel_cache')/dep['filename']
        if not path.is_file():
            path.parent.mkdir(parents=True,exist_ok=True)
            # Official PyPI metadata gives immutable wheel URL; expected SHA256
            # remains authoritative. This is a build operation, never on phone.
            with urllib.request.urlopen(f'https://pypi.org/pypi/{dep["name"]}/{dep["version"]}/json',timeout=30) as r:metadata=json.load(r)
            item=next(x for x in metadata['urls'] if x['filename']==dep['filename'])
            if item['digests']['sha256']!=dep['sha256']:raise ValueError('dependency metadata digest')
            with urllib.request.urlopen(item['url'],timeout=30) as r:raw=r.read()
            if digest(raw)!=dep['sha256']:raise ValueError('dependency bytes digest')
            path.write_bytes(raw)
        if digest(path.read_bytes())!=dep['sha256']:raise ValueError('wheel checksum')
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith('/') or name.endswith(('.pyc','.pyo')):continue
                if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('wheel path')
                if name.startswith(('google/','tzdata/')) or '.dist-info/' in name and any(name.endswith(x) for x in ['METADATA','LICENSE','LICENSE.txt','LICENSE.md']):
                    target='vendor/'+name
                    if target in files:raise ValueError('duplicate vendor file')
                    files[target]=z.read(name)
    head=source_head or subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    manifest={'schema':'mxm.v4.android-current-metadata-source-package.v1','source_head':head,
      'file_sha256':{rel:digest(raw) for rel,raw in sorted(files.items())},'wheel_sha256':{d['filename']:d['sha256'] for d in lock['wheels']},
      'metadata_only':True,'broker_called_by_builder':False}
    files['PACKAGE_MANIFEST.json']=json.dumps(manifest,sort_keys=True,indent=2).encode()+b'\n'
    files['README.txt']='Extrage pachetul într-un folder separat. Deschide V4_CURRENT_METADATA_RUN.py în Pydroid și apasă RUN o singură dată. Dacă se deschide cTrader, autorizează contul Pepperstone LIVE cu acces view/accounts. Revino la aceeași rulare; nu apăsa RUN din nou. Trimite doar ZIP-ul indicat la final. Nu trimite cache-ul OAuth sau credențiale.\n'.encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel,raw in sorted(files.items()):
            info=zipfile.ZipInfo('MXM_V4_CURRENT_METADATA_ANDROID_V1/'+rel,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,raw)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('source ZIP CRC')
    return {'filename':output.name,'size_bytes':output.stat().st_size,'sha256':digest(output.read_bytes()),'members':len(files),'source_head':head}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--wheel-dir');args=parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],args.output,wheel_dir=args.wheel_dir),sort_keys=True))

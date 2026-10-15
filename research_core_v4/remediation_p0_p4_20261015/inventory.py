"""Digest-only surface scope and compressed-container inventory; never emit data."""
import gzip
import json
import pathlib
import zipfile
from .safety import sha,unpack,require

def public_packs(root):
    packs=[];members=0
    for index in range(6):
        p=root/f'research_core_v3/state/CORRECTED_FRICTION_SCOPE_V2_PACK_{index:02}.zip'
        row={'path':p.relative_to(root).as_posix(),'sha256':sha(p.read_bytes()),'members':[]}
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if not name.endswith('.gz'):continue
                raw=unpack(z.read(name));obj=json.loads(raw)
                keys=set()
                def visit(v):
                    if isinstance(v,dict):
                        keys.update(str(k).lower() for k in v)
                        for x in v.values():visit(x)
                    elif isinstance(v,list):
                        for x in v:visit(x)
                visit(obj)
                row['members'].append({'name_sha256':sha(name.encode()),'packed_sha256':sha(z.read(name)),'raw_sha256':sha(raw),'structured':True,'market_field_markers':bool(keys & {'open','high','low','close','bid','ask','price','prices','returns','pnl','net_eur'}),'credential_field_markers':bool(keys & {'access_token','client_secret','private_key','password'}),'retention':'PRESERVE_HISTORICAL_BYTES;NO_REPUBLICATION_OR_DELETION_IN_THIS_MANDATE'})
                members+=1
        packs.append(row)
    return {'packs':packs,'pack_count':len(packs),'gzip_json_members':members,'global_no_leak_claim':False,'credential_markers_are_not_authentic_compromise_proof':True}

def validate_surface_claim(scope):
    require(scope.get('global_no_leak_claim') is False,'GLOBAL_EXPOSURE_CLAIM_DENIED')
    require(set(scope['surfaces'])=={'checkout','git_history','actions_logs','releases','attachments'},'SURFACE_SCOPE_MISSING')
    return scope

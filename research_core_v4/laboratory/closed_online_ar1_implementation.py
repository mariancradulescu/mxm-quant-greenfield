"""Immutable code evidence for the CLOSED W35 study, never executable replacement code."""
import base64,gzip,json,hashlib,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACK=ROOT/'docs/economic-development/20261023/week35-online-ar1-reproduction-39973081180/frozen-implementation.json.gz.b64'
PACK_SHA='1bc90c64370a831ff80af79f87e47f9146deee189e5c125d4a8671124d086a42'
def verify_closed_implementation(expected):
    packed=base64.b64decode(PACK.read_text().strip(),validate=True)
    if hashlib.sha256(packed).hexdigest()!=PACK_SHA:raise ValueError('CLOSED_ONLINE_IMPLEMENTATION_ARCHIVE')
    d=zlib.decompressobj(31);raw=d.decompress(packed,200001)
    if len(raw)>200000 or not d.eof or d.unused_data:raise ValueError('CLOSED_ONLINE_IMPLEMENTATION_BOUND')
    files=json.loads(raw)
    if set(files)!=set(expected) or any(hashlib.sha256(files[p].encode()).hexdigest()!=h for p,h in expected.items()):
        raise ValueError('CLOSED_ONLINE_IMPLEMENTATION_DIGESTS')
    return True

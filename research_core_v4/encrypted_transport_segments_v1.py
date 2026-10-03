"""Reassemble only the hash-bound encrypted ZIP; never decrypt market inputs."""
from pathlib import Path
import hashlib,json,os
INDEX='research_core_v4/runtime_inputs/V4_ENCRYPTED_TRANSPORT_SEGMENTS_V1.json'
PAYLOAD='research_core_v4/runtime_inputs/MXM_V4_ASYMMETRIC_STAGING_PAYLOAD_V1.zip'
SHA='6ae52d1123d747fdf976031cd5684fbe9255f35ff865840df86277a3ae7eee10'
SIZE=17964006

def reconstruct(root, index):
    assert index['schema']=='mxm.v4.exact-encrypted-payload-segments.v1'
    assert index['payload_sha256']==SHA and index['payload_size_bytes']==SIZE
    assert len(index['parts'])==69
    target=root/PAYLOAD
    assert not target.exists(), 'payload already exists; reconcile instead of replay'
    temporary=target.with_suffix('.assembling')
    h=hashlib.sha256();total=0
    try:
        with temporary.open('xb') as out:
            for i,p in enumerate(index['parts']):
                assert p['path']==f'research_core_v4/runtime_inputs/transport_segments/chunk-{i:03d}.bin'
                assert p['size_bytes']==(262144 if i<68 else SIZE-68*262144)
                source=root/p['path'];assert source.is_file() and not source.is_symlink()
                b=source.read_bytes();assert len(b)==p['size_bytes']
                assert hashlib.sha256(b).hexdigest()==p['sha256']
                assert hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()==p['git_blob_sha']
                out.write(b);h.update(b);total+=len(b)
        assert total==SIZE and h.hexdigest()==SHA
        os.replace(temporary,target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'payload_size_bytes':total,'payload_sha256':h.hexdigest(),'segment_count':69}

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(reconstruct(root,json.loads((root/INDEX).read_text())),sort_keys=True))

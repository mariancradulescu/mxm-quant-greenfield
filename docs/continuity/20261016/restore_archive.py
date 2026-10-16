"""Offline restoration of the documentation envelope; never accesses network or secrets."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RECIPIENT = '464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'

def restore(envelope, private_key_pem):
    meta = envelope['metadata']
    if meta['schema'] != 'mxm.documentation.encrypted-archive.v1':
        raise ValueError('UNSUPPORTED_ARCHIVE_SCHEMA')
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    fp = hashlib.sha256(der).hexdigest()
    if fp != RECIPIENT or meta['recipient_spki_sha256'] != RECIPIENT:
        raise ValueError('RECIPIENT_MISMATCH')
    if meta['bulk_cipher'] != 'AES-256-GCM' or meta['key_wrap'] != 'RSA-OAEP-SHA256-MGF1-SHA256':
        raise ValueError('UNSUPPORTED_ALGORITHM')
    decode = lambda name: base64.b64decode(envelope[name], validate=True)
    wrapped = decode('wrapped_key_b64')
    session = key.decrypt(wrapped, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    aad = json.dumps(meta, sort_keys=True, separators=(',', ':')).encode()
    raw = AESGCM(session).decrypt(decode('nonce_b64'), decode('ciphertext_b64'), aad)
    if len(raw) != meta['plaintext_size'] or hashlib.sha256(raw).hexdigest() != meta['plaintext_sha256']:
        raise ValueError('PLAINTEXT_DIGEST_MISMATCH')
    return raw

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('owner_private_key', type=Path)
    p.add_argument('output_zip', type=Path)
    a = p.parse_args()
    if a.archive.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('ARCHIVE_SIZE_LIMIT')
    raw = restore(json.loads(a.archive.read_bytes()), a.owner_private_key.read_bytes())
    # Explicit caller-selected output only; never overwrite an existing file.
    fd = os.open(a.output_zip, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
    print(json.dumps({'restored_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}))

if __name__ == '__main__':
    main()

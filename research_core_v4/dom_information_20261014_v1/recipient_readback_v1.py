"""Local recipient recovery of unchanged MXM envelope; OWNER route unchanged.

Requires PGPy==0.6.0. No broker or HTTP calls. Rejects missing MDC or bad hash.
"""
import hashlib,struct
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from research_core_v4.shallow_m5_support_v2_production import _unpackage_cipher,_package_cipher

def decrypt(package,private_pem,expected_fp):
    import pgpy
    key=serialization.load_pem_private_key(private_pem,password=None)
    pub=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(pub).hexdigest()!=expected_fp:raise ValueError('RECIPIENT_KEY_MISMATCH')
    wrapped,cipher=_unpackage_cipher(package)
    secret=key.decrypt(wrapped,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None)).decode().strip()
    message=pgpy.PGPMessage.from_blob(cipher)
    # Tag 18 requires integrity protected encrypted packet (MDC verified by PGPy).
    if type(message._message).__name__!='IntegrityProtectedSKEDataV1':raise ValueError('OPENPGP_INTEGRITY_PACKET_REQUIRED')
    plain=message.decrypt(secret).message
    return plain.encode() if isinstance(plain,str) else bytes(plain)

def synthetic_roundtrip(private_pem,expected_fp):
    import os,base64,pgpy
    from pgpy.constants import SymmetricKeyAlgorithm
    key=serialization.load_pem_private_key(private_pem,password=None)
    secret=base64.urlsafe_b64encode(os.urandom(32)).decode()
    raw=b'MXM synthetic recipient route; no broker data'
    cipher=bytes(pgpy.PGPMessage.new(raw,file=False).encrypt(secret,cipher=SymmetricKeyAlgorithm.AES256))
    wrapped=key.public_key().encrypt((secret+'\n').encode(),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    package=_package_cipher(wrapped,cipher)
    if decrypt(package,private_pem,expected_fp)!=raw:raise ValueError('RECIPIENT_SYNTHETIC_READBACK_FAILED')
    return True

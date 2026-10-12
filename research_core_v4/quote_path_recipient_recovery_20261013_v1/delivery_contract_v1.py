"""Recipient custody/readback contract for future additive runners.

This supplements existing RSA/OpenPGP encryption; it changes no envelope.
No private key loading, network access, data collection or trade execution.
"""
import base64,hashlib,json
from datetime import datetime,timezone
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def fingerprint(public_pem):
    public=serialization.load_pem_public_key(public_pem)
    der=public.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()

def verified_document(envelope,public_pem):
    public=serialization.load_pem_public_key(public_pem)
    public.verify(base64.b64decode(envelope['signature_b64'],validate=True),canonical(envelope['document']),
                  padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
    if envelope['document']['recipient_spki_sha256']!=fingerprint(public_pem):
        raise ValueError('RECIPIENT_FINGERPRINT_MISMATCH')
    return envelope['document']

def require_ready(envelope,public_pem,invocation,required_until_utc,now=None):
    document=verified_document(envelope,public_pem)
    clock=datetime.now(timezone.utc) if now is None else now
    if document['schema']!='mxm.recipient.ready.same-session.v1' or document['invocation_id']!=invocation:
        raise ValueError('RECIPIENT_INVOCATION_MISMATCH')
    if document['custody_mode']!='ACTIVE_SAME_SESSION_UNTIL_ACK_OWNER_DURABLE_FALLBACK':
        raise ValueError('RECIPIENT_CUSTODY_UNVERIFIED')
    if document['cross_session_private_persistence_guaranteed'] is not False:
        raise ValueError('UNPROVEN_PERSISTENCE_CLAIM')
    issued=datetime.fromisoformat(document['issued_utc']);expires=datetime.fromisoformat(document['expires_utc'])
    if issued>clock or (clock-issued).total_seconds()>120 or expires<required_until_utc or clock>=expires:
        raise ValueError('RECIPIENT_LEASE_EXPIRED_OR_INSUFFICIENT')
    if document['unattended_or_cross_session_execution_allowed'] is not False:
        raise ValueError('CROSS_SESSION_CUSTODY_NOT_AVAILABLE')
    return 'RECIPIENT_VERIFIED_FOR_SAME_SESSION_ONLY'

def require_delivered(envelope,public_pem,source_run,cipher_sha,summary_sha):
    document=verified_document(envelope,public_pem)
    if document['schema']!='mxm.recipient.verified.delivery.ack.v1' or document['source_run']!=source_run:
        raise ValueError('DELIVERY_SOURCE_MISMATCH')
    if document['delivered_ciphertext_sha256']!=cipher_sha or document['summary_canonical_sha256']!=summary_sha:
        raise ValueError('DELIVERY_HASH_MISMATCH')
    if document['NUMERIC_SUCCESS'] is not True or document['OWNER_READBACK_SUCCESS'] is not True or document['DELIVERY_SUCCESS'] is not True:
        raise ValueError('DELIVERY_NOT_COMPLETE')
    return 'DELIVERY_SUCCESS'

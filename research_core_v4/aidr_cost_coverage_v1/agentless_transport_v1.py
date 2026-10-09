"""Existing RSA-OAEP/OpenPGP envelope with verified agentless GPG recovery.

No cryptographic format change. A GPG agent-start diagnostic is recoverable
only when the complete ciphertext passes authenticated roundtrip readback.
"""
import base64, hashlib, os, pathlib, struct, subprocess, tempfile
from research_core_v4.master1576_screen_v2 import MAGIC

def encrypt(plaintext, public_key, output):
    with tempfile.TemporaryDirectory(prefix='mxm-verified-transport-') as td:
        p=pathlib.Path(td);p.chmod(0o700);home=p/'gnupg';home.mkdir(mode=0o700)
        plain=p/'plain';cipher=p/'cipher';password=p/'password';wrapped=p/'wrapped'
        plain.write_bytes(plaintext);password.write_bytes(base64.urlsafe_b64encode(os.urandom(32))+b'\n');password.chmod(0o600)
        common=['gpg','--homedir',str(home),'--batch','--yes','--no-autostart','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(password)]
        r=subprocess.run(common+['--symmetric','--cipher-algo','AES256','--force-mdc','--output',str(cipher),str(plain)],capture_output=True,timeout=60)
        if r.returncode:
            allowed=(b"can't connect to the gpg-agent",b'no gpg-agent running in this session',b'problem with the agent: No agent running',b'keybox ')
            lines=r.stderr.splitlines()
            if r.returncode!=2 or not lines or not all(any(v in line for v in allowed) for line in lines):
                raise RuntimeError('TRANSPORT_ENCRYPTION_FAILED')
        check=subprocess.run(common+['--decrypt',str(cipher)],capture_output=True,timeout=60)
        if check.returncode!=0 or check.stdout!=plaintext:raise RuntimeError('TRANSPORT_AUTHENTICATED_READBACK_FAILED')
        subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(public_key),'-in',str(password),'-out',str(wrapped),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        key_bytes=wrapped.read_bytes()
        result=MAGIC+struct.pack('>I',len(key_bytes))+key_bytes+cipher.read_bytes()
        pathlib.Path(output).write_bytes(result);pathlib.Path(output).chmod(0o600)
        return {'canonical_input_sha256':hashlib.sha256(plaintext).hexdigest(),'ciphertext_sha256':hashlib.sha256(result).hexdigest(),'agent_diagnostic_recovered':r.returncode==2,'authenticated_local_roundtrip':True,'existing_envelope_unchanged':True}

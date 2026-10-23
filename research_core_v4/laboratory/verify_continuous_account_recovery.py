"""Offline ciphertext/provenance preservation; no decryption, new trial or native broker claim."""
import base64,hashlib,json
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/continuous-account-recovery-39986696091')
CIPHER='5f27f3de8a071cc5087bf7355fa1b5e4c1e25ccc4433923ca164ea827470f4f5'
SOURCE='e8b0dbe0f81ca41f0f94db7a052f5bce8834bf3f0399a4a2450b61daf791b641'
def need(ok,reason):
    if not ok:raise ValueError('MXM_CONTINUOUS_ACCOUNT_RECOVERY_'+reason)
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes())
    need(m['schema']=='mxm.csharp.continuous-account-recovery-preservation.v1' and
         m['run_id']==39986696091 and m['job_id']==120527605266 and m['artifact_id']==12515403390 and
         m['source_commit']=='adf474883e00138fd7fa7bdd574ea0c34c7744ed' and
         m['pr_head']=='9798b6ba11643fbb0de8028f54fa1a1cb4d1bcbd' and m['required_pr_checks']==6,
         'EXACT_NATIVE_PROVENANCE')
    need(m['original_artifact_archive_sha256']=='4a34dacb8f5e911c138bf0366f02db0c958a9441f22922a3d48137dac5fab732' and
         m['original_artifact_archive_bytes']==30648 and
         m['original_receipt_sha256']=='99f8bb7b57e6ee520b632900ed50756291a42d3509aafcc8897c9f87dd7eb62b' and
         m['preserved']=='EXACT_ORIGINAL_MODEL_CIPHERTEXT_AND_DERIVED_PUBLIC_RECOVERY_PROOF;NOT_ORIGINAL_ZIP_OR_ORIGINAL_RECEIPT_COPY',
         'PRECISE_PRESERVATION_SCOPE')
    need(m['ciphertext_part']=='ciphertext-00.b64','BOUNDED_PART_PATH')
    path=root/'ciphertext-00.b64';need(not path.is_symlink() and path.stat().st_size<40000,'BOUNDED_PART')
    cipher=base64.b64decode(path.read_text().strip(),validate=True)
    need(len(cipher)==28825==m['ciphertext_bytes'] and hashlib.sha256(cipher).hexdigest()==CIPHER==m['ciphertext_sha256'],
         'PINNED_ORIGINAL_ENCRYPTED_RESULT')
    p=json.loads((root/'recovery-proof.json').read_bytes())
    need(p==m['recovery']=={'schema':'mxm.csharp.single-account.cold-process-recovery.v1',
         'source_sha256':SOURCE,'cold_processes':4,'cut_ordinals':[1,136484,204726,409452],
         'all_reports_identical':True,'initial_capital_eur':200,'native_ctrader_recovery':False,
         'new_strategy_trials':0,'orders':0},'EXACT_SOURCE_AND_FOUR_COLD_CONTINUATIONS')
    need(m['original_source_run']==39917922508 and m['partition']=='DEVELOPMENT_ALREADY_EXPOSED' and
         m['orders']==m['new_strategy_trials']==0 and m['original_economic_rejections_preserved'] and
         not m['native_ctrader_recovery'] and not m['independent_confirmation'] and not m['cloud_activated'],
         'NO_ECONOMIC_OR_OPERATIONAL_PROMOTION')
    return {'ciphertext_sha256':CIPHER,'native_run':39986696091,'cold_processes':4,'decrypted':False,
            'native_ctrader_recovery':False,'new_strategy_trials':0,'orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))

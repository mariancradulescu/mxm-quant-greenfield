"""Tracked authentic data/custody inventory; no strategy or archive rerun."""
import re,subprocess
from pathlib import Path
from .common import *

def inventory(root):
    root=Path(root);raw=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=root)
    items=[]
    for record in raw.decode().split('\0'):
        if not record:continue
        header,path=record.split('\t',1);mode,blob,stage=header.split()
        if re.search(r'(manifest|checkpoint|archive|corpus|dataset|receipt|recovery|DATA_|/data/)',path,re.I):
            items.append({'path':path,'git_blob_oid':blob,'size_bytes':(root/path).stat().st_size,
              'classification':'ENCRYPTED_OR_ENCODED_CUSTODY_REFERENCE' if re.search(r'(mxmenc|zip|parts/|\.b64$)',path) else 'REQUIRES_TYPED_SOURCE_MANIFEST_BEFORE_USE'})
    return {'schema':'mxm.existing-data-inventory.v1','root_manifest':'data/DATA_MANIFEST.json','tracked_assets':items,
      'index_sha256':digest(items),'index_is_market_data_validation':False,'new_provider':False,'original_manifests_remain_authoritative':True}

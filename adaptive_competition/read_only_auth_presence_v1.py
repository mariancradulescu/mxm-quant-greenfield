"""Presence probe only. No secret values, token fingerprints, or broker contact."""
import os,json,argparse
from pathlib import Path
NAMES=['CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_REFRESH_TOKEN','CTRADER_EXPECTED_ACCOUNT_ID']
def main(out):
 missing=[n for n in NAMES if not os.environ.get(n,'').strip()]
 result={'status':'USER_SECURITY_ACTION_REQUIRED' if missing else 'SECRETS_PRESENT_PRIVATE_ROTATION_CHECKPOINT_REQUIRED','exact_missing_secret_names':missing,'secret_names_checked':NAMES,'secret_values_inspected':False,'probe':'ENVIRONMENT_NONEMPTY_BOOLEAN_ONLY','source_head':os.environ.get('GITHUB_SHA'),'broker_contact':False,'token_refresh_attempted':False,'orders_placed':False,'market_history_acquired':False,'auth_proven':False,'accounts_only_scope_required':True,'oauth_reauthorization_required':'REQUIRED_TO_CREATE_ACCOUNTS_ONLY_REFRESH_TOKEN_IF_NO_EXISTING_VALID_ACCOUNTS_ONLY_TOKEN' if 'CTRADER_REFRESH_TOKEN' in missing else 'NOT_DETERMINED_UNTIL_TOKEN_SCOPE_IS_VERIFIED','private_atomic_refresh_rotation':'NOT_PROVISIONED;DO_NOT_CONSUME_REFRESH_TOKEN_UNTIL_DURABLE_PRIVATE_CHECKPOINT_EXISTS'}
 Path(out).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)

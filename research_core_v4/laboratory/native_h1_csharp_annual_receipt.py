"""Read-only machine-side actual C# policy execution over encrypted derived PRIMARY145 H1 tape.

Only the existing MxmRelativeStrengthPortfolio.cs and its existing CLI harness run.
Never submit broker orders, access cTrader, open protected forward, retune model, or
publish private quotes/target-level returns. Native .NET is offline, not Cloud.
Owner PRIMARY145 original M5 source series SHA256 authenticated independently.
"""
from __future__ import annotations
import argparse,base64,collections,datetime as dt,hashlib,json,os,pathlib,struct,subprocess,tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
CIPHER_DIR=ROOT/'research_core_v4/runtime_inputs/native_h1_annual_20261030'
RECEIPT_DIR=ROOT/'verification/native-h1-csharp-20261030'
KEY=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
DOTNET_PROJECT=ROOT/'research_core_v4/laboratory/csharp/portfolio_policy/MxmPortfolioPolicy.csproj'
MAGIC=b'MXM_SHALLOW_M5_V2_ENC1\x00'
EXPECTED_KEY_FINGERPRINT='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
EXPECTED_PLAINTEXT_SHA='7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb'
EXPECTED_CIPHER_SHA='1434d71a5f22fec2e8b98ab268297c4b673ca741ebe21afd186cecfdcd39f013'
POLICY_GIT_BLOB_SHA='25019b000745058c6d7a59196a1fe8256ee41ea3'
FIRST=dt.datetime(2025,9,29,tzinfo=dt.timezone.utc)
LAST=dt.datetime(2026,6,1,tzinfo=dt.timezone.utc)
IDS={'EURJPY':3,'GBPJPY':7,'EURGBP':9,'EURCHF':10,'AUDJPY':11,'NZDUSD':12,'CHFJPY':13,'EURAUD':14}
PUBLIC_SOURCE='docs/economic-development/20261030/PRIMARY145_NATIVE_H1_POLICY_DEVELOPMENT_REFERENCE.json'
COSTS=(10,20,40)

def need(flag,why):
    if not flag:raise ValueError('MXM_NATIVE_H1_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def week(d):return d.strftime('%G-W%V')
def parse_utc(s):
    need(isinstance(s,str) and s.endswith('Z'),'UTC_FORMAT')
    return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def selftest():
    need(FIRST.isocalendar().week==40 and FIRST.year==2025,'START_WEEK')
    need(LAST.isocalendar().week==23 and LAST.year==2026,'END_WEEK')
    need(len(IDS)==8 and sorted(IDS.values())==list((3,7,9,10,11,12,13,14)),'ROSTER')
    need(sha(b'test')=='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08','SHA')
    need(parse_utc('2025-09-29T07:00:00Z')==FIRST+dt.timedelta(hours=7),'UTC')
    need(POLICY_GIT_BLOB_SHA and len(POLICY_GIT_BLOB_SHA)==40,'NATIVE_POLICY_PIN')
    print('MXM_NATIVE_H1_CSHARP_SOURCE_BLIND_SELFTEST_PASS')

def decrypt(source:bytes,private_pem:bytes,temp:pathlib.Path)->bytes:
    need(sha(source)==EXPECTED_CIPHER_SHA,'ENCRYPTED_TAPE_SHA')
    need(source.startswith(MAGIC),'ENVELOPE_MAGIC')
    o=len(MAGIC);n=struct.unpack('>I',source[o:o+4])[0];o+=4
    need(256<=n<=1024 and o+n<len(source),'WRAPPED_KEY_SIZE')
    wrapped=source[o:o+n];cipher=source[o+n:]
    key=temp/'private.pem';key.write_bytes(private_pem);key.chmod(0o600)
    verified=subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-outform','DER'],capture_output=True,check=True).stdout
    need(sha(verified)==EXPECTED_KEY_FINGERPRINT,'CUSTODY_PRIVATE_KEY_IDENTITY')
    for name,data in [('wrapped',wrapped),('cipher.gpg',cipher)]: (temp/name).write_bytes(data)
    subprocess.run(['openssl','pkeyutl','-decrypt','-inkey',str(key),'-in',str(temp/'wrapped'),'-out',str(temp/'pass'),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],capture_output=True,check=True)
    (temp/'pass').chmod(0o600)
    gnupg=temp/'gpg';gnupg.mkdir(mode=0o700)
    subprocess.run(['gpg','--homedir',str(gnupg),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(temp/'pass'),'--output',str(temp/'input.json'),'--decrypt',str(temp/'cipher.gpg')],capture_output=True,check=True)
    plaintext=(temp/'input.json').read_bytes()
    need(sha(plaintext)==EXPECTED_PLAINTEXT_SHA,'ORIGINAL_DERIVED_TAPE_SHA')
    return plaintext

def encrypt_private_output(data:bytes,temp:pathlib.Path,dest:pathlib.Path):
    (temp/'output.json').write_bytes(data)
    password=base64.urlsafe_b64encode(os.urandom(32))+b'\n'
    (temp/'out-pass').write_bytes(password);(temp/'out-pass').chmod(0o600)
    subprocess.run(['gpg','--homedir',str(temp/'gpg'),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(temp/'out-pass'),'--symmetric','--cipher-algo','AES256','--force-mdc','--output',str(temp/'out.gpg'),str(temp/'output.json')],check=True,capture_output=True)
    subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(KEY),'-in',str(temp/'out-pass'),'-out',str(temp/'out.key'),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],check=True,capture_output=True)
    wrapped=(temp/'out.key').read_bytes()
    dest.write_bytes(MAGIC+struct.pack('>I',len(wrapped))+wrapped+(temp/'out.gpg').read_bytes())

def classify(tape:dict,targets:list)->dict:
    need(len(tape['symbols'])==8 and set(tape['symbols'])==set(IDS),'SOURCE_IDENTITY')
    need(len(tape['bars'])>=30000,'H1_SOURCE_COVERAGE')
    prices=tape['outcome_lookup_PRIVATE_NOT_NATIVE_INPUT']
    week_rows=collections.defaultdict(list); last=None;eligible=0;seen={}
    for row in targets:
        bound=parse_utc(row['BoundaryUtc']);available=parse_utc(row['AvailableUtc'])
        need(available>=bound and available<bound+dt.timedelta(hours=1),'RESULT_AVAILABILITY')
        need(last is None or bound>last,'RESULT_ORDER_AND_SINGLE_PORTFOLIO')
        last=bound
        if not FIRST<=bound<LAST:continue
        if row['Reason']!='JOINT_RELATIVE_STRENGTH_TARGET':continue
        sid=row['Symbol'];direction=row['Direction']
        need(sid in IDS and direction in (-1,1),'NATIVE_TARGET')
        need(bound.weekday()<5 and 7<=bound.hour<=15,'EXPECTED_SESSION')
        stamp=bound.isoformat().replace('+00:00','Z');p=prices.get(sid+'|'+stamp)
        eps={'sid':IDS[sid],'week':week(bound),'boundary':stamp,'direction':direction,'observable':p is not None}
        if p is not None:
            a,b=float(p['entry']),float(p['exit']);need(a>0 and b>0,'FUTURE_QUOTE')
            eps['gross_bps']=10000*direction*(b/a-1)
        week_rows[week(bound)].append(eps)
    curr=FIRST;weeks=[]
    while curr<LAST:
        iso=week(curr);eps=week_rows[iso];obs=[x['gross_bps'] for x in eps if x['observable']]
        weeks.append({'iso_week':iso,'proposals':len(eps),'observable':len(obs),'censored':len(eps)-len(obs),
          'gross_bps_sum':round(sum(obs),7),'hypothetical_20bps_net_bps_sum':round(sum(obs)-20*len(obs),7),
          'at_least_21_PROPOSALS_not_fills':len(eps)>=21})
        curr+=dt.timedelta(days=7)
    visible=[x for r in week_rows.values() for x in r]
    gross=sum(x.get('gross_bps',0) for x in visible)
    n=sum(x['observable'] for x in visible)
    return {'schema':'mxm.existing-csharp-h1-native-policy-authentic-year-development.v1',
       'native_CSharp_executed':True,'csharp_actual_program':'MxmPortfolioPolicy.csproj / existing source MxmRelativeStrengthPortfolio.cs',
       'native_csharp_policy_git_blob_sha1':POLICY_GIT_BLOB_SHA,
       'original_primary145_zip_authentication_pinned':True,'source_plaintext_derived_tape_sha256':EXPECTED_PLAINTEXT_SHA,
       'csharp_observation_only_no_broker':True,'period':['2025-W40','2026-W22'],'full_weeks':len(weeks),
       'frozen_source_roster_method':'eight lowest verified forex symbol IDs in PRIMARY145; NOT outcome-ranked',
       'roster_symbol_ids':sorted(IDS.values()),'observed_proposals':len(visible),
       'gross_observed':n,'censored':len(visible)-n,'gross_bps_sum':gross,
       'hypothetical_cost_10_20_40_bps':{str(cost):gross-cost*n for cost in COSTS},
       'weeks_reaching_21_proposals_not_fills':sum(w['at_least_21_PROPOSALS_not_fills'] for w in weeks),
       'weeks_positive_hypothetical_20bps':sum(w['hypothetical_20bps_net_bps_sum']>0 for w in weeks),
       'weeks':weeks,
       'historical_Pepperstone_BIDASK_and_cost_fills_certified':False,'capital_200_EUR_account_PnL':False,
       'HARD21_native_broker_trades':False,'Cloud_or_LIVE_DEMO_orders':False,
       'classification':'REJECT_NATIVE_OBSERVATION_POLICY_ECONOMIC_QUALIFICATION_IF_HYPOTHETICAL_20BPS_ALL_WEEKS_FAIL',
       'native_ctrader_H1_bar_time_parity_verified':False,
       'interpretation':'C# policy executed offline against original-derived private annual H1 tape; percentage bps return sums, not EUR/equity or observed broker cost.'}

def protected():
    need(CIPHER_DIR.is_dir(),'SOURCE_CIPHERTEXT_UNAVAILABLE')
    parts=sorted(CIPHER_DIR.glob('chunk-*.b64'))
    need(len(parts)==7,'ENCRYPTED_PART_COUNT')
    cipher=b''.join(base64.b64decode(p.read_text(),validate=False) for p in parts)
    private=os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')
    need(private is not None and 'BEGIN' in private,'R3_SECRET_UNAVAILABLE')
    RECEIPT_DIR.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mxm-native-h1-csharp-') as dirname:
        t=pathlib.Path(dirname);raw=decrypt(cipher,private.encode(),t)
        tape=json.loads(raw)
        # Original-derived custodied tape encodes OHLC prices as decimal strings to
        # preserve their exact textual identity. Existing C# CLI JsonElement.GetDecimal
        # requires a JSON NUMBER, not a JSON STRING. Normalize only the H1 close
        # field on a disposable runner-local copy; do not touch the signed source,
        # future settlement observations, identity roster or signal specification.
        native_input={'symbols':tape['symbols'],'bars':[
            {'symbol':r['symbol'],'end':r['end'],'close':float(r['close']),
             'available':r['available']} for r in tape['bars']]}
        (t/'native_numeric_input.json').write_text(json.dumps(native_input,separators=(',',':')))
        cmd=['dotnet','run','--project',str(DOTNET_PROJECT),'-c','Release','--',str(t/'native_numeric_input.json'),str(t/'native_targets.json')]
        subprocess.run(cmd,cwd=ROOT,check=True)
        output=(t/'native_targets.json').read_bytes()
        targets=json.loads(output)
        report=classify(tape,targets)
        # A different result is an actual C# vs Python reference discrepancy, NOT silent retuning.
        ref=json.loads((ROOT/PUBLIC_SOURCE).read_bytes())
        report['python_reference_observed_proposals']=ref['proposals']
        report['python_reference_gross_bps_sum']=ref['gross_bps_sum']
        report['independent_csharp_python_proposal_count_same']=report['observed_proposals']==ref['proposals']
        report['independent_csharp_python_gross_bps_within_1bp']=abs(report['gross_bps_sum']-ref['gross_bps_sum'])<1
        report['private_csharp_target_sha256']=sha(output)
        out=RECEIPT_DIR/'PUBLIC_NATIVE_CSHARP_ANNUAL_RESULT.json'
        out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        encrypt_private_output(output,t,RECEIPT_DIR/'PRIVATE_NATIVE_CSHARP_TARGETS_ENCRYPTED.bin')
        need(report['independent_csharp_python_proposal_count_same'] and report['independent_csharp_python_gross_bps_within_1bp'],'NATIVE_REFERENCE_DISCREPANCY')
        print('MXM_AUTHENTIC_NATIVE_CSHARP_ANNUAL_RECEIPT '+json.dumps({k:report[k] for k in ('observed_proposals','gross_observed','gross_bps_sum','weeks_reaching_21_proposals_not_fills','weeks_positive_hypothetical_20bps','classification')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['selftest','protected']);mode=parser.parse_args().mode
    selftest()
    if mode=='protected':protected()

"""Verify original aggregate margin evidence offline; never decrypt or price a trade."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
from .durable_spot_observation import FOLDER as ORIGINAL,MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/current-margin-40483982559'
ZIP_SHA='51309d5c92de4ee69a9c13a46a001e367037b2ae1ef2b41837d5a20530d02ce6';RECEIPT_SHA='fb689e2cbd53effac7c941166b71c6901fb476260edd75f8fdfce092dcc4152a';HEAD='b87f2c0334efe7e559f515bdd599a73a58d814b0';POLICY='1e241f750958e58501506c8e462eae2f54b929b04919bad46147a446a3440741'
def need(ok,why):
    if not ok:raise ValueError('CURRENT_MARGIN_RESULT_'+why)
def read(p):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=30000,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(folder=FOLDER):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER')
    raw=base64.b64decode(read(folder/'artifact.zip.b64').strip(),validate=True)
    need(len(raw)==1518 and sha(raw)==ZIP_SHA,'ORIGINAL_NATIVE_ZIP')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(z.namelist()==['receipt.json'] and z.infolist()[0].file_size==4180,'SOLE_ORIGINAL_MEMBER');receipt=z.read('receipt.json')
    need(read(folder/'receipt.json')==receipt and sha(receipt)==RECEIPT_SHA,'EXACT_NATIVE_RECEIPT')
    r=json.loads(receipt);original=read(ORIGINAL/'MANIFEST.json');need(sha(original)==MANIFEST_SHA,'ORIGINAL_SOURCE_MANIFEST');m=json.loads(original)
    need(r['schema']=='mxm.current-margin-native-reception.v1' and r['run_id']==40483982559 and r['source_sha']==HEAD and
      r['policy_sha256']==POLICY and r['original_source_run']==40455704891 and r['original_source_head']==m['head'] and
      r['original_manifest_sha256']==MANIFEST_SHA and r['original_private_sha256']==m['private_sha256'],'EXACT_PROVENANCE')
    need(r['reference_capital_eur']=='200' and r['reference_is_not_a_funded_account_or_reset'] is True and
      r['all_estimates_independently_reconciled'] is True and r['runtime_roll_forward_allowed'] is True and
      set(r['csharp_assembly_sha256'])==set(r['actual_execution_runtimes'])=={'net6.0','net8.0'},'EXACT_REFERENCE_AND_RECONCILIATION')
    need([p['symbol_id'] for p in r['panel']]==[1,2,250],'COMPLETE_FIXED_PANEL')
    for p in r['panel']:
        need(p['full_entry_admission'] is False and p['stop_risk_proven'] is False and p['dated_historical_terms_proven'] is False and p['round_trip_fee_eur'] is None,'NO_PER_INSTRUMENT_PROMOTION')
        if p['margin'] is not None:
            v=p['margin'];need(v['SymbolId']==p['symbol_id'] and v['FullEntryAdmission'] is False and v['HistoricalApplicability'] is False and v['ActualBrokerCharge'] is False,'MARGIN_ONLY_NOT_ADMISSION')
    for k in ('market_prices_exported','directional_response_tested','full_entry_admission','historical_applicability_proven','actual_broker_charges_proven','loss_side_fx_proven','stop_risk_proven','original_source_policy_changed','economic_edge_proven','hard21_proven','native_robot_operational_reception_proven','cloud_activated','individual_metadata_response_timestamps_available'):
        need(r[k] is False,'NO_PROMOTION_'+k)
    for k in ('new_broker_requests','economic_model_runs','orders'):need(type(r[k]) is int and r[k]==0,'NO_SIDE_EFFECT_'+k)
    return {'schema':'mxm.immutable-current-margin-verification.v1','run_id':40483982559,'head':HEAD,'original_source_run':40455704891,
      'instruments':3,'source_decrypted':False,'economic_edge_proven':False,'full_entry_admission':False,'new_broker_requests':0,'orders':0}
if __name__=='__main__':print('MXM_VERIFIED_ORIGINAL_CURRENT_MARGIN '+json.dumps(verify(),sort_keys=True))

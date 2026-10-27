"""Receive the exact native aggregate cause artifact offline, without decrypt/replay."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
from .durable_spot_observation import FOLDER as ORIGINAL,MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/spot-source-causes-40463984769'
ZIP_SHA='98d5d2b44f53b42a2c4be007ee45712a51a3a27672e90eed14d1187d4e42719e'
RECEIPT_SHA='fc677ee78cbe6c63fb18766eb57ad07a290dda8db922d96ae558844b3f941a0a'
HEAD='9b268d814eb21e446f8447b388326cbbaff52ec0'
def need(ok,why):
    if not ok:raise ValueError('SPOT_CAUSE_RESULT_'+why)
def read(p):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=20000,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(folder=FOLDER):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER')
    raw=base64.b64decode(read(folder/'artifact.zip.b64').strip(),validate=True)
    need(len(raw)==1483 and sha(raw)==ZIP_SHA,'ORIGINAL_NATIVE_ZIP')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(z.namelist()==['receipt.json'] and z.infolist()[0].file_size==3732,'SOLE_ORIGINAL_MEMBER');receipt=z.read('receipt.json')
    need(read(folder/'receipt.json')==receipt and sha(receipt)==RECEIPT_SHA,'EXACT_NATIVE_RECEIPT')
    r=json.loads(receipt);s=r['csharp_result'];original=(ORIGINAL/'MANIFEST.json').read_bytes()
    need(sha(original)==MANIFEST_SHA,'ORIGINAL_CAPTURE_MANIFEST')
    m=json.loads(original)
    need(r['schema']=='mxm.native-spot-source-cause-reception.v1' and r['run_id']==40463984769 and r['source_sha']==HEAD and
      r['original_source_run']==40455704891 and r['original_source_head']==m['head'] and
      r['original_manifest_sha256']==MANIFEST_SHA and r['original_private_sha256']==m['private_sha256'],'NATIVE_AND_ORIGINAL_SOURCE_PROVENANCE')
    need(r['policy_sha256']=='893ed00af3d4cd1e438712198e1d7f5ad13a1453e3e41178ccf066498b76fe42' and
      r['derived_input_sha256']=='839fa07c0e8fe15011d76d7151b9db61224d76f31b48e0e62fa581e01819c6b4' and
      r['csharp_assembly_sha256']=='c0620bcda23f22a954027b63dd7dca0a51cf7a44a1de90e6da686c6e5bbb9041' and
      s['event_disposition_sha256']=='2f2a15df450c3cd569caace4d813da6eebb877c5bb0e3d7a50feadcc7ef0de2e','ORIGINAL_POLICY_INPUT_BINARY_DISPOSITIONS')
    need(s['events']==1140 and s['profile']==m['profile'] and s['fixed_age_ms']==5000 and s['fixed_observed_span_ms']==300000,'UNCHANGED_ORIGINAL_PROFILE')
    expected={'1':(153,183,115,10,5,252,53,31),'2':(37,445,10,7,3,266,97,119),'250':(0,322,0,7,7,322,0,0)}
    for key,(locked,positive,both,gaps,healthy_gaps,both_fields,bid_only,ask_only) in expected.items():
        c=s['causes'][key];shape=c['book_shapes'];field=c['field_patterns']
        need(shape.get('LOCKED',0)==locked and shape.get('POSITIVE',0)==positive and
          set(shape)<= {'LOCKED','POSITIVE'} and sum(shape.values())==s['profile'][key]['events'] and
          c['locked_with_both_fields']==both and c['crossed_with_both_fields']==0 and
          c['gaps_over_5s']==gaps and c['healthy_to_healthy_gap_breaks']==healthy_gaps and
          field.get('both',0)==both_fields and field.get('bid_only',0)==bid_only and field.get('ask_only',0)==ask_only and
          sum(field.values())==s['profile'][key]['events'] and
          c['explicit_same_price_bid_updates']==c['explicit_same_price_ask_updates']==c['server_clock_failures']==0,
          'ALL_ORIGINAL_CAUSE_COUNTS_'+key)
    for k in ('every_event_disposition_independently_reconciled','original_profile_unchanged','original_capture_remains_development_excluded_from_confirmation'):
        need(r[k] is True,'POSITIVE_PROOF_'+k)
    for k in ('native_product_geometry_predicate_changed','cloud_activated','economic_edge_proven','hard21_proven','native_robot_operational_reception_proven'):
        need(r[k] is False,'NO_PROMOTION_'+k)
    for k in ('new_broker_requests','new_response_tests','economic_model_runs','orders'):need(type(r[k]) is int and r[k]==0,'NO_SIDE_EFFECT_'+k)
    need(s['source_authenticated_in_program'] is False and s['original_consumer_policy_changed'] is False and
      s['economic_model_executed'] is False and s['broker_orders']==0 and s['economic_edge_proven'] is False and s['hard21_proven'] is False,'CORRECT_CSHARP_SCOPE')
    return {'schema':'mxm.immutable-spot-source-cause-verification.v1','run_id':40463984769,'head':HEAD,
      'original_source_run':40455704891,'events':1140,'locked':190,'crossed':0,'locked_in_two_sided_message':125,
      'original_profile_unchanged':True,'source_decrypted':False,'new_broker_requests':0,'orders':0,
      'economic_edge_proven':False,'native_robot_operational_reception_proven':False}
if __name__=='__main__':print('MXM_VERIFIED_ORIGINAL_SOURCE_CAUSES '+json.dumps(verify(),sort_keys=True))

"""Authenticate exact first reference-unit/calendar result; never decrypt or replay."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'docs/economic-development/20261028/commodity-anchor-40717023905'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(base=DIR):
 m=json.loads((base/'manifest.json').read_bytes());raw=(base/'runtime-original.zip').read_bytes()
 if len(raw)!=m['bytes'] or sha(raw)!=m['sha256']:raise ValueError('ORIGINAL_ARCHIVE')
 with zipfile.ZipFile(base/'runtime-original.zip') as z:
  if sorted(z.namelist())!=sorted(m['members']) or sum(x.file_size for x in z.infolist())>20000000:raise ValueError('ORIGINAL_ARCHIVE_MEMBERS')
  b={p:z.read(p) for p in m['members']}
 for p,h in m['members'].items():
  if len(b[p])!=h['bytes'] or sha(b[p])!=h['sha256']:raise ValueError('ORIGINAL_MEMBER_'+p)
 r=json.loads(b['receipt.json']);producer=json.loads(b['producer.json']);cache=json.loads(b['cache.json']);cold=json.loads(b['cold.json'])
 if r!=json.loads((base/'logged-receipt.json').read_bytes()):raise ValueError('ORIGINAL_LOGGED_RESULT')
 if r['run_id']!=40717023905 or r['source_sha']!='2c0d94ca194c35e60e0dcf88d544cad830ce5f9e':raise ValueError('ORIGINAL_RUN')
 provenance=json.loads((base/'provenance.json').read_bytes())
 admission=ROOT/'research_core_v4/laboratory/COMMODITY_ANCHOR_REFERENCE_UNITS_V1.json'
 if provenance['source_admission_sha256']!='276d516f61179dae7aed5f265bf352e1100a4c8dc56fc8df3756b3430a472720' or sha(admission.read_bytes())!=provenance['source_admission_sha256'] or provenance['source_commit']!=r['source_sha']:raise ValueError('EXTERNAL_PREOUTCOME_ADMISSION_BINDING')
 if r['spec_sha256']!='f135ebf57cee3302f70e399695ec7dff40123fed3d2c3996933b5727a016f7e1':raise ValueError('ORIGINAL_ADMISSION')
 if r['source_calendar_ms']!={'start':1785283200000,'evaluation_start':1785715200000,'end':1788134400000} or r['reference_quote']!='USC' or r['reference_fx_conversion_assumed']:raise ValueError('SOURCE_CALENDAR_OR_REFERENCE')
 for member,key in [('source.mxmenc','source_sha256'),('result.mxmenc','cipher_sha256'),('evaluator.dll','evaluator_sha256'),('cache-input.mxmenc','cache_input_sha256')]:
  if sha(b[member])!=r[key]:raise ValueError('RESULT_MEMBER_BINDING')
 if producer['cipher_sha256']!=r['source_sha256'] or cache['cache_input_sha256']!=r['cache_input_sha256'] or cold['cipher_sha256']!=r['cipher_sha256'] or not cold['original_readback'] or cold['model_reexecuted']:raise ValueError('ORIGINAL_PRODUCER_CACHE_COLD')
 if r['models_executed'] not in (0,1) or r['initial_funding_count']!=r['models_executed'] or r['conditional_cost_scenarios']!=r['models_executed'] or r['initial_capital_eur']!=200:raise ValueError('ONE_MODEL_ACCOUNT')
 for k in ('orders','cloud_activated','automatic_followup','closed_configuration_reexecuted','protected_opened','hard21_proven','actual_fills_proven','historical_costs_proven','economic_edge_proven','independent_confirmation'):
  if r[k]:raise ValueError('UNPROVEN_OR_FORBIDDEN_'+k)
 if r['models_executed']==0:
  if r['disposition']!='SOURCE_NOT_ADMITTED' or r['gates'] or r['causal_forecasts'] or r['causal_proposals']:raise ValueError('ZERO_MODEL_SOURCE_STOP')
 else:
  if not r['forecasts_independently_reconciled'] or r['new_anchor_rows_independently_redecoded']<128 or r['authenticated_cached_rows']<256:raise ValueError('ORIGINAL_MODEL_SOURCE_RECONCILIATION')
  if set(r['opportunity_capacity_by_week'])!={'2026-W32','2026-W33','2026-W34','2026-W35'} or any(v<21 for v in r['opportunity_capacity_by_week'].values()):raise ValueError('UNCHANGED_PREMODEL_CAPACITY')
  if set(r['gates'])!={'complete_conditional_account','net_positive_in_declared_scenario','every_complete_week_21_modeled_entries','drawdown_at_most40eur','every_complete_week_net_positive'}:raise ValueError('ORIGINAL_GATE_SET')
 if r['disposition']!='NET_FAIL_SCENARIO' or r['models_executed']!=1 or r['causal_forecasts']!=500 or r['causal_proposals']!=0 or r['native_h1_requests']!=1 or r['metadata_requests']!=1:raise ValueError('FIRST_NEGATIVE_OUTCOME_NOT_REINTERPRETED')
 summary=r['conditional_account_summary']
 if any(summary[k]!=0 for k in ('AcceptedEntries','ExecutedExits','RejectedEntries','OpenPositions','UsedMarginEur','MaxDrawdownEur')) or any(str(summary[k])!='200' for k in ('InitialCapitalEur','FinalCashEur','MarkedEquityEur')) or r['conditional_week_equity_marks']!=['200']*5:raise ValueError('INACTIVE_ACCOUNT_NOT_A_TRADING_LOSS')
 if r['source_rows']!={'7393':792} or r['authenticated_cached_rows']!=1071 or r['new_anchor_rows_independently_redecoded']!=792 or cache['existing_source_overlap_rows']!={'1':547,'250':524}:raise ValueError('AUTHENTIC_SOURCE_COUNTS')
 return {'run':r['run_id'],'disposition':r['disposition'],'models':r['models_executed'],'exact_originals_verified':True,'market_decrypted':False,'model_reexecuted':False}
if __name__=='__main__':
 import sys
 if sys.argv[1:]==['--self-test']:
  import shutil,tempfile
  verify()
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)/'original';shutil.copytree(DIR,d);p=d/'runtime-original.zip';b=bytearray(p.read_bytes());b[len(b)//2]^=1;p.write_bytes(b)
   try:verify(d)
   except ValueError:pass
   else:raise AssertionError('CORRUPT_ORIGINAL_ACCEPTED')
  print(json.dumps({'original':verify(),'corruption_rejected':True}))
 elif not sys.argv[1:]:print(json.dumps(verify()))
 else:raise ValueError('ORIGINAL_VERIFIER_ARGUMENT')

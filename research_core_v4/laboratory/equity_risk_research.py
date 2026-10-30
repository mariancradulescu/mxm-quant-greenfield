"""OWNER clarification: research-only equity adaptive risk vs historic DIRECTOR settings.

Reuse the ONE previous authenticated C# portfolio's original ENTRY/EXIT tape.
The previous policy/model/quotes/ledger are never rerun or modified. This
is deliberately NOT a strategy backtest: skipped opportunities cannot be
replaced with hypothetical new signals or fictitious fills. No real ruin
probability can be estimated from this dependent, exposed sample.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
from pathlib import Path
from decimal import Decimal
import subprocess
import tempfile
from .portfolio_forensics import (analyze,need,num,EXPECTED_CIPHER,
                                  EXPECTED_HEAD,EXPECTED_RUN)
from .portfolio_programme import account_checks

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'verification/portfolio-programme-20261030'
OUT=ROOT/'verification/risk-research-20261030'
PROJECT=ROOT/'research_core_v4/laboratory/csharp/risk_research/MxmRiskResearch.csproj'
TOL=Decimal('0.0000001')


def fixed_policies():
    # These are sensitivity hypotheses, not OWNER numeric decisions.
    return [
      {'Id':'HISTORICAL_DIRECTOR_CONFIG',
       'MaxMarginToFreeFraction':'0.40',
       'MinimumPostEntryFreeToEquityFraction':'0',
       'MaxEntryStopAndFrictionToEquityFraction':'0.01',
       'RoundTripFrictionReserveEur':'0.40',
       'MaximumTicketMarginEur':'80',
       'MinimumFreeMarginEur':'120','MaximumTicketRiskEur':'2'},
      {'Id':'ADAPTIVE_EQUITY_CONSERVATIVE',
       'MaxMarginToFreeFraction':'0.25',
       'MinimumPostEntryFreeToEquityFraction':'0.55',
       'MaxEntryStopAndFrictionToEquityFraction':'0.005',
       'RoundTripFrictionReserveEur':'0.40',
       'MaximumTicketMarginEur':None,
       'MinimumFreeMarginEur':None,'MaximumTicketRiskEur':None},
      {'Id':'ADAPTIVE_EQUITY_BALANCED',
       'MaxMarginToFreeFraction':'0.60',
       'MinimumPostEntryFreeToEquityFraction':'0.25',
       'MaxEntryStopAndFrictionToEquityFraction':'0.02',
       'RoundTripFrictionReserveEur':'0.40',
       'MaximumTicketMarginEur':None,
       'MinimumFreeMarginEur':None,'MaximumTicketRiskEur':None},
    ]


def build_original_tape(original,receipt):
    # First independently reconstruct and reconcile the already published
    # original trade economics using existing PR273 cold forensic validator.
    prior=analyze(original,receipt)
    result=original['programme_checkpoint']['progress']['results']['account']['value']
    need(account_checks(result)==original['metrics'],'PRIOR_CSHARP_ACCOUNT_RECONCILIATION')
    account=result['account']
    params=original['feed']['parameters']
    need(num(params['MaxMarginFraction'])==Decimal('.4') and
         num(params['MinimumFreeMarginReserveEur'])==120 and
         num(params['MaxEstimatedStopRiskFraction'])==Decimal('.01') and
         num(params['RoundTripRiskReserveEur'])==Decimal('.4') and
         params['MaxPositions']==1 and
         result['reset_count']==0 and result['deposit_count']==1,'HISTORICAL_SETTINGS_AND_SINGLE_DEPOSIT')
    quote={}
    for item in original['feed']['events']:
        if item['$feed']!='quote':continue
        key=(item['Symbol'],item['Utc'])
        need(key not in quote,'DUPLICATE_QUOTE_EPOCH')
        quote[key]=item
    pending=None;episodes=[]
    for row in account['Ledger']:
        key=(row['Symbol'],row['Utc'])
        need(key in quote,'NOT_CSHARP_QUOTE_ORIGINAL')
        if row['Kind']=='ENTRY':
            need(pending is None,'NOT_ONE_SHARED_POSITION')
            pending=(row,quote[key])
            continue
        need(row['Kind']=='EXIT' and pending is not None,'UNMATCHED_EXIT')
        entry,q=pending;pending=None
        need(entry['Symbol']==row['Symbol'] and
             entry['Direction']==row['Direction'] and
             num(entry['Units'])==num(row['Units']),'MATCHED_POSITION')
        units=num(entry['Units'])
        # Exact prospective stop-capital estimate semantics of the old C#
        # native-sizing replay; not a historical worst-case stop guarantee.
        stop=(num(q['StopDistanceQuote'])*units*
              num(q.get('QuoteLossToEur') or q['QuoteToEur'])
              if q.get('StopDistanceQuote') is not None
              else num(q['EstimatedStopRiskEur']))
        need(stop>0 and num(q['InitialMarginEur'])>0 and
             num(row['CommissionEur'])>=0 and
             num(entry['CommissionEur'])>=0 and
             num(entry['Units'])==num(q['ExecutableUnits']) and
             num(q['BrokerVolumeMinUnits'])==units and
             num(q['BrokerVolumeMaxUnits'])==units,
             'EXACT_ORIGINAL_NATIVE_MINIMUM_TICKET')
        episodes.append({
          'Symbol':entry['Symbol'],'EntryUtc':entry['Utc'],'ExitUtc':row['Utc'],
          'Units':str(units),'MarginEur':str(num(q['InitialMarginEur'])),
          'StopRiskEur':str(stop),
          'EntryFeeEur':str(num(entry['CommissionEur'])),
          'ExitFeeEur':str(num(row['CommissionEur'])),
          'GrossEur':str(num(row['GrossEur']))
        })
    need(pending is None and len(episodes)==len(prior['round_trips']) and
         len(episodes)==account['AcceptedEntries'] and
         account['OpenPositions']==0,'ORIGINAL_TAPE_COMPLETENESS')
    gross=sum((num(x['GrossEur']) for x in episodes),Decimal(0))
    fees=sum((num(x['EntryFeeEur'])+num(x['ExitFeeEur']) for x in episodes),Decimal(0))
    need(abs(gross-fees-num(original['metrics']['net_eur']))<TOL,
         'CLOSED_ORIGINAL_NET')
    return {'Schema':'mxm.cold-risk-research.tape.v1','InitialCapitalEur':'200',
            'Episodes':episodes,'Policies':fixed_policies()}


def assess_original(original,receipt,runner):
    tape=build_original_tape(original,receipt)
    with tempfile.TemporaryDirectory(prefix='mxm-risk-tape-') as folder:
        root=Path(folder)
        inp=root/'input.json';out=root/'risk.json'
        inp.write_text(json.dumps(tape,separators=(',',':')))
        subprocess.run(['dotnet','run','--no-build','-c','Release',
                        '--project',str(PROJECT),'--',str(inp),str(out)],
                       check=True,text=True,capture_output=True,timeout=120)
        study=json.loads(out.read_bytes())
    need(study['Schema']=='mxm.closed-portfolio-research-risk-surface.v1' and
         study['EpisodeCount']==len(tape['Episodes']) and
         study['CounterfactualEntryTapeOnly'] is True and
         study['OriginalModelRerun'] is False,'COLD_RISK_STUDY_SCHEMA')
    modes={'RECORDED_CSHARP','DOUBLE_COMMISSION','ALL_ESTIMATED_STOPS','ALL_STOP_GAP_2X'}
    need(len(study['Scenarios'])==12 and
         {(x['Policy'],x['Stress']) for x in study['Scenarios']}==
         {(p['Id'],m) for p in tape['Policies'] for m in modes},'COLD_RISK_SCENARIOS')
    old=next(x for x in study['Scenarios'] if
             x['Policy']=='HISTORICAL_DIRECTOR_CONFIG' and x['Stress']=='RECORDED_CSHARP')
    need(old['Accepted']==len(tape['Episodes']) and old['Skipped']==0 and
         abs(num(old['FinalCashEur'])-num(original['metrics']['final_equity_eur']))<TOL,
         'HISTORICAL_DIRECTOR_CONFIG_MUST_RECONCILE_ORIGINAL_CSHARP')
    for x in study['Scenarios']:
        need(x['Accepted']+x['Skipped']==len(tape['Episodes']) and
             0<=x['InsolvencyBreaches']<=x['Accepted'] and
             sum(x['EntryCountsByIsoWeek'].values())==x['Accepted'] and
             num(x['MaximumClosedDrawdownEur'])>=0 and
             num(x['MaximumUsedMarginEur'])>=0,'RISK_SCENARIO_ACCOUNT_INVARIANTS')
    return {'schema':'mxm.integrated-offline-equity-risk-study.v1',
            'original_run_id':EXPECTED_RUN,'original_head':EXPECTED_HEAD,
            'previous_closed_net_eur':original['metrics']['net_eur'],
            'original_final_eur':original['metrics']['final_equity_eur'],
            'reference_policy_is_director_historical_not_owner':True,
            'research_alternatives_are_not_operational':True,
            'all_risk_scenarios_from_same_original_entered_positions_only':True,
            'scenarios':study['Scenarios'],'episode_count':len(tape['Episodes']),
            'policy_specs':tape['Policies'],
            'risk_of_ruin_probability_estimable':False,
            'intrabar_stopout_or_real_broker_risk_certified':False,
            'new_strategy_models_rerun':0,'new_broker_requests':0,
            'orders':0,'cloud_activations':0,'operational_risk_modified':False}


def cold():
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and
         os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','CUSTODY_SCOPE')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import unpack
    from research_core_v4.successor_c_20261018.readback import FP
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    receipt=json.loads((SOURCE/'receipt.json').read_bytes())
    original_cipher=(SOURCE/'private.mxmenc').read_bytes()
    need(receipt['run_id']==EXPECTED_RUN and receipt['head']==EXPECTED_HEAD and
         hashlib.sha256(original_cipher).hexdigest()==EXPECTED_CIPHER==
         receipt['private_cipher_sha256'],'FROZEN_CIPHER')
    cold=json.loads((SOURCE/'cold.json').read_bytes())
    need(cold['originals_verified'] is True and cold['models_rerun']==0 and
         cold['source_reopened'] is False and cold['orders']==0 and
         cold['private_cipher_sha256']==EXPECTED_CIPHER,'FROZEN_COLD_VERIFIED')
    pub=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(pub)==FP,'FROZEN_RECIPIENT')
    with tempfile.TemporaryDirectory(prefix='mxm-risk-custody-') as directory:
        temp=Path(directory);key,fp=_private_key_from_secret(temp)
        need(fp==FP,'CUSTODY_KEY_IDENTITY')
        raw=unpack(owner.bounded_decrypt(original_cipher,key,temp))
        need(hashlib.sha256(raw).hexdigest()==receipt['private_plain_sha256'],
             'ORIGINAL_PLAINTEXT_IDENTITY')
        for journal in receipt['journals']:
            data=(SOURCE/journal['path']).read_bytes()
            need(hashlib.sha256(data).hexdigest()==journal['cipher_sha256'] and
                 hashlib.sha256(unpack(owner.bounded_decrypt(data,key,temp))).hexdigest()==journal['plain_sha256'],
                 'ORIGINAL_CSHARP_JOURNAL_CHECK')
        original=json.loads(raw)
        risk=assess_original(original,receipt,None)
    OUT.mkdir(parents=True,exist_ok=False)
    raw=json.dumps(risk,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=OUT/'original-risk-surface.mxmenc')
    public={'schema':risk['schema'],'original_run_id':EXPECTED_RUN,
            'original_head':EXPECTED_HEAD,'original_cipher_sha256':EXPECTED_CIPHER,
            'encrypted_study_sha256':hashlib.sha256((OUT/'original-risk-surface.mxmenc').read_bytes()).hexdigest(),
            'episode_count':risk['episode_count'],'previous_closed_net_eur':risk['previous_closed_net_eur'],
            'reference_policy_is_director_historical_not_owner':True,
            'scenarios':[{
              k:v for k,v in x.items() if k!='EntryCountsByIsoWeek'
            } for x in risk['scenarios']],
            'research_policies_not_operational':True,
            'risk_of_ruin_probability_estimable':False,
            'historical_broker_stops_fills_and_total_costs_certified':False,
            'new_strategy_models_rerun':0,'new_broker_requests':0,'orders':0,
            'cloud_activations':0,'operational_risk_modified':False}
    (OUT/'public.json').write_text(json.dumps(public,sort_keys=True,separators=(',',':'))+'\n')
    print('MXM_RISK_RESEARCH_COLD_COMPLETED_WITHOUT_TRADING; BASELINE_RECONCILED')


if __name__=='__main__':
    import sys
    need(sys.argv[1:]==['cold'],'ONLY_AUTHORIZED_COLD_MODE')
    cold()

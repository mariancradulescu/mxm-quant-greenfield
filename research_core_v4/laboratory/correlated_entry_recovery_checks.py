"""Nonsecret adapter integration checks and original artificial process-proof reception."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'native_tick_replay_v1/csharp'
def need(ok,why):
    if not ok:raise ValueError('MXM_CORRELATED_ENTRY_RECOVERY_'+why)
def adapter():
    bot=(BASE/'MxmReferenceProductBot.cs').read_text()
    start=bot[bot.index('protected override void OnStart'):bot.index('protected override void OnBar')]
    apply=bot[bot.index('void ApplyPortfolioDecision'):bot.index('string? ReadEntryCheckpoint')]
    need(start.index('entryCheckpoint.InspectRecovery()')<start.index('entryCheckpoint.Initialize()')<
         start.index('confirmedEntries.Initialize(')<start.index('entryCheckpoint.RecoverVerifiedOpen(')<start.index('series.BarClosed+='),
         'RECOVER_BEFORE_ANY_MARKET_CALLBACK')
    need('requireExisting:recoveryInspection==MxmEntryRecoveryInspection.Recoverable' in start,'NO_RECREATED_LOST_LEDGER')
    need('RecoveryBook(),PendingOrders.Count,BrokerClock()' in start and 'ExecuteMarketOrder' not in start,'STARTUP_READS_BOOK_ONLY')
    need(apply.index('entryCheckpoint.PrepareRecoverable(')<apply.index('MxmAccountIsolation.Check(')<
         apply.index('MxmCapitalAdmission.Check(')<apply.rindex('fence.IsCurrent(')<
         apply.index('entryCheckpoint.MarkSubmitted()')<apply.index('brokerAttempted=true')<apply.index('ExecuteMarketOrder('),
         'CORRELATION_DURABLE_BEFORE_FRESH_RISK_AND_ONE_CALL')
    need('ExecuteMarketOrder(direction,instrumentName,units,Label,stopPips,null,requestComment)' in apply and
         'requestComment=entryCheckpoint.SubmissionComment' in apply,'EXACT_DURABLE_COMMENT_SENT')
    need('SequenceEqual(beforeIds) || PendingOrders.Count!=0' in apply and 'currentUnits!=units' in apply and
         'instrument.PipSize!=pipSize' in apply,'NO_CHANGED_BOOK_OR_GEOMETRY_AFTER_PREPARE')
    book=bot[bot.index('MxmEntryRecoveryPosition[] RecoveryBook'):bot.index('MxmProtectionPosition[] ProtectionBook')]
    need('x.Comment' in book and 'x.EntryTime' in book and 'x.StopLoss' in book and 'x.Symbol.PipSize' in book,'ACTUAL_BROKER_ATTRIBUTES')
    checkpoint=(BASE/'MxmEntryCheckpoint.cs').read_text()
    recover=checkpoint[checkpoint.index('public bool RecoverVerifiedOpen'):checkpoint.index('public bool MarkSubmitted')]
    need(recover.index('MxmEntryRecovery.Match(')<recover.index('ledger.RecordConfirmed(')<recover.index('WriteVerified(ready)'),
         'POSITIVE_ATTRIBUTION_AND_DURABLE_COUNT_BEFORE_READY')
    need('!ledger.RestoredFromExisting' in recover and 'ledger.ScopeFingerprint!=scopeHash' in recover and
         'store.Read()!=recoveryRaw || Halted || ledger.Halted' in recover,'NO_MISSING_WRONG_SCOPE_OR_CALLBACK_POISON_CLEAR')
    need('ExecuteMarketOrder' not in recover and 'ClosePosition' not in recover,'RECOVERY_HAS_NO_TRADING_SIDE_EFFECT')
    need('DefaultValue=false' in bot and 'EnableDemoTrading && !Account.IsLive' in bot,'AUTHORITY_DEFAULTS_UNCHANGED')
    return {'adapter_checked':True,'broker_orders':0,'native_runtime_reception':False}
def proof(value):
    need(value['schema']=='mxm.csharp.correlated-open-entry-recovery.artificial.v1' and value['checks']>=100 and
         value['hard_kills']==4 and value['new_os_processes']==8,'COMPILED_PROCESS_PROOF')
    need([(x['phase'],x['restart_admitted'],x['unique_recorded_entries'],x['synthetic_calls'],x['resubmissions']) for x in value['cases']]==[
         ('before-call',False,0,0,0),('unknown-accepted',True,1,1,0),('recorded',True,1,1,0),('ready',True,1,1,0)],
         'FOUR_COLD_BOUNDARIES_NO_RESUBMISSION_OR_DOUBLE_COUNT')
    need(all(value[k] is False for k in ('native_ctrader_execution','native_storage_durability_proven',
        'broker_history_reconciliation','economic_edge_proven','hard21_proven')) and
         value['broker_orders']==value['new_strategy_trials']==0,'NO_NATIVE_OR_ECONOMIC_PROMOTION')
    return {'artificial_checks':value['checks'],'cold_boundaries_verified':4,'synthetic_resubmissions':0,'native_reception':False}
if __name__=='__main__':
    import sys
    adapter()
    if len(sys.argv)==2:print(json.dumps(proof(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
    else:print(json.dumps(adapter(),sort_keys=True))

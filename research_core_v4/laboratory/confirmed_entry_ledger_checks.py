"""Independent ISO-week arithmetic and adapter barrier checks. No market/custody access."""
import datetime as dt
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]/'native_tick_replay_v1/csharp'
def need(value,why):
    if not value:raise ValueError('MXM_CONFIRMED_ENTRY_'+why)
def instant(raw):
    value=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
    need(value.tzinfo==dt.timezone.utc,'UTC_REQUIRED')
    return value
def iso(value):
    year,week,_=value.isocalendar()
    return f'{year:04d}-W{week:02d}'
def check(proof):
    need(proof['schema']=='mxm.confirmed-entry-ledger.artificial.v1','ARTIFICIAL_SCHEMA')
    need(proof['hard_kills']==3 and proof['new_os_processes']==6 and proof['checks']>=60,'PROCESS_PROOF')
    for flag in ('native_storage_reception','native_broker_fills','broker_history_coverage_proven','hard21_proven','economic_edge_proven'):
        need(proof[flag] is False,'NO_PROMOTION_'+flag)
    need(proof['broker_orders']==0,'NO_ORDERS')
    env=proof['contracts']['journal'];payload=env['Payload']
    need(hashlib.sha256(payload.encode()).hexdigest()==env['Sha256'],'ORIGINAL_PAYLOAD_DIGEST')
    entries=json.loads(payload)['Entries'];need(len(entries)==22,'SYNTHETIC_ENTRIES')
    ids=set();counts={}
    for entry in entries:
        need(entry['PositionId'] not in ids and entry['PositionId']>0,'UNIQUE_POSITIONS')
        ids.add(entry['PositionId']);key=iso(instant(entry['EntryUtc']))
        need(instant(entry['ObservedUtc'])>=instant(entry['EntryUtc']),'BROKER_TIME_PRECEDES_OBSERVATION')
        counts[key]=counts.get(key,0)+1
    # Independent Python ISO-year calculation, includes zero weeks and the open week.
    need(counts=={'2020-W53':21,'2021-W01':1},'ISO_COUNTS_FROM_BROKER_ENTRY_TIME')
    expected=dt.datetime(2020,12,28,tzinfo=dt.timezone.utc);asof=expected+dt.timedelta(days=21)
    weeks=proof['contracts']['weeks'];need(len(weeks)==4,'NO_DROPPED_ZERO_WEEKS')
    for week in weeks:
        key=iso(expected);n=counts.get(key,0)
        need(week['IsoWeek']==key and instant(week['StartUtc'])==expected,'CALENDAR_IDENTITY')
        need(week['ConfirmedProtectedEntries']==n and week['RecordedThresholdMet']==(n>=21),'WEEK_COUNT')
        need(week['CalendarWeekElapsed']==(expected+dt.timedelta(days=7)<=asof),'ELAPSED_NOT_COVERAGE')
        need(week['MeasurementStartedBeforeWeek'] is True and week['BrokerHistoryCoverageProven'] is False and
             week['Hard21Proven'] is False,'NO_COVERAGE_CERTIFICATION')
        expected+=dt.timedelta(days=7)
    need([(x['phase'],x['restart_admitted'],x['confirmed_lower_bound'],x['orders']) for x in proof['cases']]==[
        ('before-ledger',False,0,0),('ledger-before-ready',False,1,0),('ready',True,1,0)],'PERSIST_BEFORE_READY_KILL_RESULTS')
    return {'independent_iso_weeks_checked':4,'independent_entries_checked':22,'orders':0,'hard21_proven':False}
def check_adapter():
    bot=(BASE/'MxmReferenceProductBot.cs').read_text()
    startup=bot[bot.index('protected override void OnStart'):bot.index('protected override void OnBar')]
    apply=bot[bot.index('void ApplyPortfolioDecision'):bot.index('string? ReadEntryCheckpoint')]
    need(startup.index('entryCheckpoint.Initialize()')<startup.index('confirmedEntries.Initialize(')<
         startup.index('series.BarClosed+='),'NO_SUBSCRIPTION_BEFORE_JOURNAL')
    need(apply.index('confirmedEntries.VerifyCurrent(')<apply.index('entryCheckpoint.Prepare(')<
         apply.index('entryCheckpoint.MarkSubmitted()')<apply.index('ExecuteMarketOrder('),'PRECALL_DURABLE_ADMISSION')
    need(apply.index('orderProtection.Reconcile(')<apply.index('else if(!protection.Accepted)')<
         apply.index('RecordProtectedEntry(placed.Position!)')<apply.index('entryCheckpoint.CompleteReconciled()'),
         'CONFIRMED_RECORD_ONLY_AFTER_POSITIVE_RECONCILIATION_BEFORE_READY')
    need(apply.count('RecordProtectedEntry(')==1,'ONE_COUNT_PATH')
    record=bot[bot.index('bool RecordProtectedEntry'):bot.index('void ReportRecordedWeeks')]
    need('position.Id,position.SymbolName' in record and 'position.EntryTime' in record and
         '(decimal)position.VolumeInUnits' in record,'BROKER_IDENTITY_NOT_SIGNAL_OR_CLOCK')
    need('confirmedEntries?.Halt();' in bot and 'LocalStorage.Flush(LocalStorageScope.Type)' in bot and
         'LocalStorage.Reload(LocalStorageScope.Type)' in bot,'DURABLE_FAULT_POISON')
    need('MxmConfirmedEntryLedger.cs' in (BASE/'MxmReferenceBot.csproj').read_text(),'ACTUAL_PRODUCT_INCLUDES_LEDGER')
    need('DefaultValue=false' in bot and 'EnableDemoTrading && !Account.IsLive' in bot,'TRADING_AUTHORITY_UNCHANGED')
    return {'adapter_barrier_wiring_checked':True,'native_reception_proven':False}
if __name__=='__main__':
    import sys
    check_adapter()
    if len(sys.argv)>1:print(json.dumps(check(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
    else:print('MXM_CONFIRMED_ENTRY_ADAPTER_BARRIER_WIRING_PASS_NOT_NATIVE_RECEPTION')

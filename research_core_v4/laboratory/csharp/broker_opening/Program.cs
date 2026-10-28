using System.Text.Json;
using Mxm.Replay;
var options=new JsonSerializerOptions{PropertyNameCaseInsensitive=true};
var p=JsonDocument.Parse(File.ReadAllText(args[0])).RootElement;
if(p.TryGetProperty("recover",out var recoveryMode) && recoveryMode.GetBoolean()) {
 var scope=p.GetProperty("scope").GetString()!;var now=p.GetProperty("now").GetDateTime();
 var start=new DateTime(2026,8,24,12,0,0,DateTimeKind.Utc);
 var store=new MxmMemoryEntryStore();var old=new MxmEntryCheckpoint(store,scope);
 if(!old.Initialize() || !old.PrepareRecoverable("EURUSD",1,start,start.AddSeconds(1),start.AddMinutes(5),
  "OWNER",1000,12,.0001,.00001,Array.Empty<long>()))throw new Exception("PREPARE_FIXTURE");
 string original=store.Read()!;var fillsStore=new MxmMemoryEntryStore();
 if(!new MxmConfirmedEntryLedger(fillsStore,scope).Initialize(start))throw new Exception("LEDGER_FIXTURE");
 var cold=new MxmEntryCheckpoint(store,scope);
 if(cold.InspectRecovery()!=MxmEntryRecoveryInspection.Recoverable)throw new Exception("INSPECTION_FIXTURE");
 var ledger=new MxmConfirmedEntryLedger(fillsStore,scope);
 if(!ledger.Initialize(now,true))throw new Exception("COLD_LEDGER_FIXTURE");
 var request=cold.RecoveryIntentSnapshot!;
 var supplied=JsonSerializer.Deserialize<MxmBrokerOpeningFill[]>(p.GetProperty("fills").GetRawText(),options)!;
 var data=supplied.Select(x=>x with {Comment=request.Comment}).ToArray();
 var inventory=new MxmBrokerOpeningInventory(scope,now,data);var proof=inventory.ObservePending(request);
 var book=new[]{new MxmEntryRecoveryPosition(new MxmProtectionPosition(9,"OWNER","EURUSD",1,1000,1.1,1.0988),
  request.Comment,start.AddMinutes(1),.0001,.00001)};
 bool restored=proof.Correlated && proof.RequestedUnitsObserved && cold.RecoverVerifiedOpen(ledger,book,0,now);
 File.WriteAllText(args[1],JsonSerializer.Serialize(new {restored,confirmed=ledger.Count,pendingRetained=store.Read()==original,
  resubmissions=0,proof.MayClearPending,proof.MayResubmit}));return;
}
try {
 var inventory=new MxmBrokerOpeningInventory(p.GetProperty("scope").GetString()!,p.GetProperty("now").GetDateTime(),
  JsonSerializer.Deserialize<MxmBrokerOpeningFill[]>(p.GetProperty("fills").GetRawText(),options)!);
 var request=p.TryGetProperty("request",out var r)?JsonSerializer.Deserialize<MxmRecoverableEntry>(r.GetRawText(),options):null;
 File.WriteAllText(args[1],JsonSerializer.Serialize(new {status="OBSERVED",inventory.ScopeFingerprint,inventory.FactsSha256,
  inventory.Fills,inventory.Orders,inventory.HistoryCoverageProven,inventory.CapitalContinuityProven,inventory.Hard21Proven,
  inventory.MaySubmitOrClearPending,Pending=request==null?null:inventory.ObservePending(request)}));
} catch(Exception e) when(e is ArgumentException || e is OverflowException) {
 File.WriteAllText(args[1],"{\"status\":\"UNAVAILABLE\"}");
}

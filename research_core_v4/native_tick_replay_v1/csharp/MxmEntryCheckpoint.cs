using System;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Replay {
public interface IMxmEntryCheckpointStore {
 // Production Read must reload the persisted scope; Write must flush before returning.
 string? Read();
 void Write(string value);
}
public sealed class MxmDelegateEntryStore : IMxmEntryCheckpointStore {
 readonly Func<string?> read;readonly Action<string> write;
 public MxmDelegateEntryStore(Func<string?> read,Action<string> write){this.read=read;this.write=write;}
 public string? Read()=>read();public void Write(string value)=>write(value);
}
public sealed class MxmMemoryEntryStore : IMxmEntryCheckpointStore {
 string? value;public string? Read()=>value;public void Write(string next)=>value=next;
}
/// <summary>Before-call persistence barrier, not a broker idempotency key or fill ledger.
/// Legacy/unknown pending blocks. V2 may recover only through positive broker
/// attribution plus an existing durable fill ledger. No unknown request is replayed.
/// One owning instance and one unchanged storage domain are required.</summary>
public sealed class MxmEntryCheckpoint {
 enum Phase {New,Ready,Prepared,Submitted,Halted}
 readonly IMxmEntryCheckpointStore store;
 readonly string ready;
 readonly string scopeHash;
 MxmRecoverableEntry? preparedRecovery,recovery;
 string? recoveryRaw;
 bool inspected;
 public string? SubmissionComment=>!Halted && (phase==Phase.Prepared || phase==Phase.Submitted)?preparedRecovery?.Comment:null;
 public string RecoveryReason {get;private set;}="NOT_RECOVERED";
 Phase phase;
 string? pending;
 public bool Halted {get;private set;}
 public string StorageKey {get;}
 public MxmEntryCheckpoint(IMxmEntryCheckpointStore store,string accountScope){
  if(store==null || string.IsNullOrWhiteSpace(accountScope) || accountScope.Length>1024)
   throw new ArgumentException("INVALID_ENTRY_CHECKPOINT_SCOPE");
  this.store=store;
  string identity=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(accountScope))).ToLowerInvariant();
  StorageKey="MXM Entry V1 "+identity.Substring(0,32); // <=50 alphanumeric/space characters.
  ready="MXM_ENTRY_CHECKPOINT_V1_READY_"+identity;scopeHash=identity;
 }
 public static string AccountScope(string broker,long number,bool live){
  if(string.IsNullOrWhiteSpace(broker) || broker.Length>256 || number<=0)
   throw new ArgumentException("INVALID_ENTRY_CHECKPOINT_ACCOUNT");
  return JsonSerializer.Serialize(new[]{"MXM_CSHARP_REFERENCE_V1",broker.Trim().ToUpperInvariant(),
   number.ToString(System.Globalization.CultureInfo.InvariantCulture),live?"LIVE":"DEMO"});
 }
 public void Halt(){Halted=true;phase=Phase.Halted;}
 bool Fail(){Halt();return false;}
 bool WriteVerified(string value){
  store.Write(value);
  if(Halted)return false; // A platform OnException may poison us without throwing.
  string? actual=store.Read();return !Halted && actual==value;
 }
 public bool Initialize(){
  if(Halted || phase!=Phase.New || recovery!=null)return Fail();
  try {
   string? prior=store.Read();if(Halted || (!string.IsNullOrEmpty(prior) && prior!=ready))return Fail();
   // Probe explicit save/reload even on a fresh store. Native environment must
   // separately establish persistence support; memory echo alone cannot do that.
   if(!WriteVerified(ready))return Fail();phase=Phase.Ready;return true;
  }catch{return Fail();}
 }
 public bool Prepare(string symbol,int direction,DateTime boundaryUtc){
  if(Halted || phase!=Phase.Ready)return Fail();
  try {
   if(string.IsNullOrWhiteSpace(symbol) || symbol.Length>128 || (direction!=1 && direction!=-1) ||
      boundaryUtc.Kind!=DateTimeKind.Utc || boundaryUtc==default)return Fail();
   if(store.Read()!=ready || Halted)return Fail();
   pending=JsonSerializer.Serialize(new {Schema="mxm.pending-entry.v1",Scope=ready,
    Attempt=Guid.NewGuid().ToString("N"),Symbol=symbol,Direction=direction,BoundaryUtc=boundaryUtc});
   if(!WriteVerified(pending))return Fail();phase=Phase.Prepared;return true;
  }catch{return Fail();}
 }
 public bool PrepareRecoverable(string symbol,int direction,DateTime boundaryUtc,DateTime preparedUtc,DateTime deadlineUtc,
  string label,double units,double stopPips,double pipSize,double tickSize,IReadOnlyCollection<long> beforeIds){
  if(Halted || phase!=Phase.Ready)return Fail();
  try {
   var record=new MxmRecoverableEntry(ready,Guid.NewGuid().ToString("N"),label,symbol,direction,units,stopPips,
    pipSize,tickSize,boundaryUtc,preparedUtc,deadlineUtc,beforeIds.OrderBy(x=>x).ToArray());
   if(!MxmEntryRecovery.Valid(record,ready) || store.Read()!=ready || Halted)return Fail();
   pending=MxmEntryRecovery.Encode(record);
   if(!WriteVerified(pending))return Fail();preparedRecovery=record;phase=Phase.Prepared;return true;
  }catch{return Fail();}
 }
 public MxmEntryRecoveryInspection InspectRecovery(){
  if(Halted || phase!=Phase.New || inspected){Fail();return MxmEntryRecoveryInspection.Blocked;}
  inspected=true;
  try {
   string? raw=store.Read();
   if(Halted){Fail();return MxmEntryRecoveryInspection.Blocked;}
   if(string.IsNullOrEmpty(raw) || raw==ready)return MxmEntryRecoveryInspection.Normal;
   recovery=MxmEntryRecovery.Decode(raw,ready);
   if(recovery==null){RecoveryReason="LEGACY_CORRUPT_OR_UNSUPPORTED_PENDING";Fail();return MxmEntryRecoveryInspection.Blocked;}
   recoveryRaw=raw;return MxmEntryRecoveryInspection.Recoverable;
  }catch{RecoveryReason="RECOVERY_STORAGE_READ_FAILED";Fail();return MxmEntryRecoveryInspection.Blocked;}
 }
 public bool RecoverVerifiedOpen(MxmConfirmedEntryLedger ledger,IReadOnlyCollection<MxmEntryRecoveryPosition> book,
  int pendingOrders,DateTime observedUtc){
  if(Halted || phase!=Phase.New || recovery==null || recoveryRaw==null)return Fail();
  try {
   if(store.Read()!=recoveryRaw || Halted){RecoveryReason="RECOVERY_PENDING_CHANGED";return Fail();}
   if(ledger==null || !ledger.RestoredFromExisting || ledger.ScopeFingerprint!=scopeHash ||
      ledger.StartedUtc>recovery.PreparedUtc || !ledger.VerifyCurrent(observedUtc)){
    RecoveryReason="RECOVERY_REQUIRES_ORIGINAL_ACCOUNT_LEDGER";return Fail();
   }
   var verdict=MxmEntryRecovery.Match(recovery,book,pendingOrders,observedUtc);RecoveryReason=verdict.Reason;
   if(!verdict.Accepted)return Fail();
   var match=verdict.Match!;
   if(!ledger.RecordConfirmed(new MxmConfirmedEntry(match.Position.Id,match.Position.Symbol,match.Position.Direction,
      (decimal)match.Position.Units,match.EntryUtc,observedUtc)) || ledger.Halted){
    RecoveryReason="RECOVERY_ENTRY_LEDGER_NOT_DURABLE";return Fail();
   }
   // Positive attribution persists BEFORE pending is cleared. A crash here is
   // recoverable by the same identity and the idempotent existing fill ledger.
   if(Halted || store.Read()!=recoveryRaw || Halted || ledger.Halted || !WriteVerified(ready) || ledger.Halted){
    RecoveryReason="RECOVERY_READY_WRITE_UNVERIFIED";return Fail();
   }
   recovery=null;recoveryRaw=null;pending=null;preparedRecovery=null;phase=Phase.Ready;
   RecoveryReason="RECOVERED_CONFIRMED_OPEN_POSITION_NO_RESUBMISSION";return true;
  }catch{RecoveryReason="RECOVERY_EXCEPTION_NO_ADMISSION";return Fail();}
 }
 public bool MarkSubmitted(){
  if(Halted || phase!=Phase.Prepared)return Fail();
  phase=Phase.Submitted;return true;
 }
 bool Finish(Phase required){
  if(Halted || phase!=required || pending==null)return Fail();
  try {
   if(store.Read()!=pending || Halted)return Fail();
   if(!WriteVerified(ready))return Fail();pending=null;preparedRecovery=null;phase=Phase.Ready;return true;
  }catch{return Fail();}
 }
 // Clear only if the broker call was never attempted, or its result/book/stop
 // have been reconciled. Unknown/exception/halt has no completion operation.
 public bool CompleteNotSubmitted()=>Finish(Phase.Prepared);
 public bool CompleteReconciled()=>Finish(Phase.Submitted);
}
}

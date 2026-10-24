using System;
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
/// Any non-ready checkpoint on startup blocks; no unknown request is ever replayed.
/// One owning instance and one unchanged storage domain are required.</summary>
public sealed class MxmEntryCheckpoint {
 enum Phase {New,Ready,Prepared,Submitted,Halted}
 readonly IMxmEntryCheckpointStore store;
 readonly string ready;
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
  ready="MXM_ENTRY_CHECKPOINT_V1_READY_"+identity;
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
  if(Halted || phase!=Phase.New)return Fail();
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
 public bool MarkSubmitted(){
  if(Halted || phase!=Phase.Prepared)return Fail();
  phase=Phase.Submitted;return true;
 }
 bool Finish(Phase required){
  if(Halted || phase!=required || pending==null)return Fail();
  try {
   if(store.Read()!=pending || Halted)return Fail();
   if(!WriteVerified(ready))return Fail();pending=null;phase=Phase.Ready;return true;
  }catch{return Fail();}
 }
 // Clear only if the broker call was never attempted, or its result/book/stop
 // have been reconciled. Unknown/exception/halt has no completion operation.
 public bool CompleteNotSubmitted()=>Finish(Phase.Prepared);
 public bool CompleteReconciled()=>Finish(Phase.Submitted);
}
}

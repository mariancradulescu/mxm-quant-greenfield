using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using Mxm.Replay;

static class EntryRecoveryFixture {
 static int checks;
 static readonly DateTime Boundary=new(2026,8,24,12,0,0,DateTimeKind.Utc);
 static readonly DateTime Now=Boundary.AddHours(1);
 static readonly string Scope=MxmEntryCheckpoint.AccountScope("Synthetic Broker",123,false);
 static void Need(bool value,string why){if(!value)throw new Exception("MXM_ENTRY_RECOVERY_FIXTURE_"+why);checks++;}
 sealed class Store : IMxmEntryCheckpointStore {
  public string? Value;public bool DropWrite,FailWrite;public Action? AfterRead,AfterWrite;
  public string? Read(){var value=Value;AfterRead?.Invoke();return value;}
  public void Write(string value){if(FailWrite)throw new IOException("INJECTED_WRITE");if(!DropWrite)Value=value;AfterWrite?.Invoke();}
 }
 sealed class FileStore : IMxmEntryCheckpointStore {
  readonly string path;public FileStore(string path){this.path=path;}
  public string? Read()=>File.Exists(path)?File.ReadAllText(path):null;
  public void Write(string value){
   string temp=path+".partial";
   using(var f=new FileStream(temp,FileMode.Create,FileAccess.Write,FileShare.None)){
    f.Write(Encoding.UTF8.GetBytes(value));f.Flush(true);
   }
   File.Move(temp,path,true);
  }
 }
 static MxmEntryCheckpoint Guard(IMxmEntryCheckpointStore store)=>new(store,Scope);
 static MxmConfirmedEntryLedger Ledger(IMxmEntryCheckpointStore store)=>new(store,Scope);
 static bool Prepare(MxmEntryCheckpoint guard,long[]? before=null)=>guard.PrepareRecoverable("EURUSD",1,Boundary,
  Boundary.AddSeconds(1),Boundary.AddMinutes(5),"OWNER",1000,12,.0001,.00001,before??Array.Empty<long>());
 static MxmEntryRecoveryPosition Position(string comment,long id=100)=>new(
  new MxmProtectionPosition(id,"OWNER","EURUSD",1,1000,1.1,1.0988),comment,Boundary.AddSeconds(2),.0001,.00001);
 static MxmConfirmedEntry Confirmed(MxmEntryRecoveryPosition p,DateTime observed)=>new(p.Position.Id,p.Position.Symbol,
  p.Position.Direction,(decimal)p.Position.Units,p.EntryUtc,observed);
 sealed record Setup(Store Pending,Store Fills,MxmEntryRecoveryPosition Position,string PendingBytes);
 static Setup Staged(long[]? before=null){
  var p=new Store();var f=new Store();var cp=Guard(p);var ledger=Ledger(f);
  Need(cp.Initialize() && ledger.Initialize(Boundary.AddDays(-1)),"FRESH_BASELINE");
  Need(Prepare(cp,before) && cp.SubmissionComment!=null && cp.MarkSubmitted(),"V2_DURABLE_BEFORE_SYNTHETIC_CALL");
  return new(p,f,Position(cp.SubmissionComment!),p.Value!);
 }
 static void Refusal(string name,Func<MxmEntryRecoveryPosition,MxmEntryRecoveryPosition[]> change,int pending=0,long[]? before=null){
  var s=Staged(before);var cold=Guard(s.Pending);var ledger=Ledger(s.Fills);
  Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true),"REFUSAL_START_"+name);
  Need(!cold.RecoverVerifiedOpen(ledger,change(s.Position),pending,Now),"REFUSE_"+name);
  Need(s.Pending.Value==s.PendingBytes && ledger.Count==0 && cold.Halted,"NO_CLEAR_OR_COUNT_"+name);
 }
 static void Contracts(){
  Refusal("EMPTY_BOOK",_=>Array.Empty<MxmEntryRecoveryPosition>());
  Refusal("MISSING_COMMENT",p=>new[]{p with {Comment=null}});
  Refusal("TRUNCATED_COMMENT",p=>new[]{p with {Comment=p.Comment![..20]}});
  Refusal("WRONG_LABEL",p=>new[]{p with {Position=p.Position with {Label="FOREIGN"}}});
  Refusal("WRONG_SYMBOL",p=>new[]{p with {Position=p.Position with {Symbol="GBPUSD"}}});
  Refusal("WRONG_DIRECTION",p=>new[]{p with {Position=p.Position with {Direction=-1}}});
  Refusal("PARTIAL_VOLUME",p=>new[]{p with {Position=p.Position with {Units=500}}});
  Refusal("EXCESS_VOLUME",p=>new[]{p with {Position=p.Position with {Units=2000}}});
  Refusal("NO_STOP",p=>new[]{p with {Position=p.Position with {Stop=null}}});
  Refusal("WIDE_STOP",p=>new[]{p with {Position=p.Position with {Stop=1.09}}});
  Refusal("PREEXISTING_ID",p=>new[]{p},before:new long[]{100});
  Refusal("MULTIPLE_TAGS",p=>new[]{p,p with {Position=p.Position with {Id=101}}});
  Refusal("DUPLICATE_BOOK_IDS",p=>new[]{p,p});
  Refusal("OTHER_NEW_POSITION",p=>new[]{p,Position("OTHER",101)});
  Refusal("PENDING_ORDER",p=>new[]{p},1);
  Refusal("OLD_ENTRY",p=>new[]{p with {EntryUtc=Boundary}});
  Refusal("FUTURE_ENTRY",p=>new[]{p with {EntryUtc=Now.AddSeconds(1)}});
  Refusal("NON_UTC_ENTRY",p=>new[]{p with {EntryUtc=DateTime.SpecifyKind(p.EntryUtc,DateTimeKind.Unspecified)}});
  Refusal("PIP_CHANGED",p=>new[]{p with {PipSize=.001}});
  Refusal("TICK_CHANGED",p=>new[]{p with {TickSize=.001}});
  // Known pre-call positions may remain or have closed. They are not new fills.
  foreach(bool stillOpen in new[]{false,true}){
   var s=Staged(new long[]{99});var cold=Guard(s.Pending);var ledger=Ledger(s.Fills);
   Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true),"MATCH_START");
   var book=stillOpen?new[]{s.Position,Position("PREEXISTING",99) with {EntryUtc=Boundary.AddHours(-1),Position=Position("PREEXISTING",99).Position with {Symbol="GBPUSD"}}}:new[]{s.Position};
   Need(cold.RecoverVerifiedOpen(ledger,book,0,Now) && ledger.Count==1 && !cold.Halted,"POSITIVE_OPEN_RECOVERY");
   Need(Guard(s.Pending).Initialize(),"ONLY_POSITIVE_DURABLE_RECOVERY_READY");
   Need(!cold.RecoverVerifiedOpen(ledger,book,0,Now) && ledger.Count==1,"RECOVERY_CANNOT_RUN_TWICE_IN_SAME_INSTANCE");
  }
  {
   var ps=new Store();var fs=new Store();var first=Guard(ps);var initial=Ledger(fs);
   Need(first.Initialize() && initial.Initialize(Boundary.AddDays(-1)) &&
    first.PrepareRecoverable("EURUSD",-1,Boundary,Boundary.AddSeconds(1),Boundary.AddMinutes(5),
      "OWNER",1000,12,.0001,.00001,Array.Empty<long>()) && first.MarkSubmitted(),"SHORT_REQUEST_DURABLE");
   var shortPosition=Position(first.SubmissionComment!) with {
    Position=Position(first.SubmissionComment!).Position with {Direction=-1,Stop=1.1012}};
   var cold=Guard(ps);var ledger=Ledger(fs);
   Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true) &&
    cold.RecoverVerifiedOpen(ledger,new[]{shortPosition},0,Now) && ledger.Count==1,"SHORT_POSITIVE_RECOVERY");
  }
  var legacy=new Store();var old=Guard(legacy);Need(old.Initialize() && old.Prepare("EURUSD",1,Boundary) && old.MarkSubmitted(),"OLD_PENDING_BASELINE");
  string bytes=legacy.Value!;Need(Guard(legacy).InspectRecovery()==MxmEntryRecoveryInspection.Blocked && legacy.Value==bytes,"V1_NOT_REINTERPRETED_OR_CLEARED");
  foreach(string mode in new[]{"corrupt","wrong_scope"}){
   var s=Staged();s.Pending.Value=mode=="corrupt"?s.PendingBytes.Replace("EURUSD","GBPUSD"):s.PendingBytes;
   var cold=mode=="wrong_scope"?new MxmEntryCheckpoint(s.Pending,Scope+"WRONG"):Guard(s.Pending);
   string keep=s.Pending.Value!;Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Blocked && s.Pending.Value==keep,"SCOPE_OR_DIGEST_REFUSAL");
  }
  {
   var s=Staged();var cold=Guard(s.Pending);Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable,"MISSING_LEDGER_START");
   var missing=new Store();var ledger=Ledger(missing);Need(!ledger.Initialize(Now,true) && missing.Value==null,"REQUIRED_LEDGER_ABSENCE_NOT_RECREATED");
   Need(!cold.RecoverVerifiedOpen(ledger,new[]{s.Position},0,Now) && s.Pending.Value==s.PendingBytes,"NO_READY_ON_LEDGER_LOSS");
  }
  foreach(bool wrongScope in new[]{false,true}){
   var s=Staged();var cold=Guard(s.Pending);Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable,"LEDGER_IDENTITY_START");
   var fresh=new Store();var first=wrongScope?new MxmConfirmedEntryLedger(fresh,Scope+"OTHER"):Ledger(fresh);
   Need(first.Initialize(Boundary.AddDays(-1)),"OTHER_OR_NEW_LEDGER_BASELINE");
   var supplied=first;
   if(wrongScope){supplied=new MxmConfirmedEntryLedger(fresh,Scope+"OTHER");Need(supplied.Initialize(Now,true),"WRONG_SCOPE_RESTORED");}
   Need(!cold.RecoverVerifiedOpen(supplied,new[]{s.Position},0,Now) && supplied.Count==0 && s.Pending.Value==s.PendingBytes,"REJECT_NEW_OR_WRONG_SCOPE_LEDGER");
  }
  foreach(string fault in new[]{"ledger_write","ready_drop","pending_read_callback"}){
   var s=Staged();var cold=Guard(s.Pending);var ledger=Ledger(s.Fills);
   int reads=0;
   if(fault=="pending_read_callback")s.Pending.AfterRead=()=>{if(++reads==3)cold.Halt();};
   Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true),"FAULT_START");
   if(fault=="ledger_write")s.Fills.FailWrite=true;
   if(fault=="ready_drop")s.Pending.DropWrite=true;
   Need(!cold.RecoverVerifiedOpen(ledger,new[]{s.Position},0,Now) && s.Pending.Value==s.PendingBytes,"FAULT_NEVER_PREMATURE_READY_"+fault);
   Need(ledger.Count==(fault=="ledger_write"?0:1),"FAULT_COUNT_AT_ACKNOWLEDGED_BOUNDARY");
  }
  {
   var s=Staged();var cold=Guard(s.Pending);var ledger=Ledger(s.Fills);
   Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true),"POISON_START");
   s.Fills.AfterWrite=()=>{ledger.Halt();cold.Halt();};
   Need(!cold.RecoverVerifiedOpen(ledger,new[]{s.Position},0,Now) && s.Pending.Value==s.PendingBytes,"NONTHROWING_PLATFORM_CALLBACK_POISON");
  }
  {
   var s=Staged();var cold=Guard(s.Pending);var ledger=Ledger(s.Fills);
   Need(cold.InspectRecovery()==MxmEntryRecoveryInspection.Recoverable && ledger.Initialize(Now,true),"STALE_START");
   s.Pending.Value="OTHER_WRITER";
   Need(!cold.RecoverVerifiedOpen(ledger,new[]{s.Position},0,Now) && s.Pending.Value=="OTHER_WRITER" && ledger.Count==0,"NO_OVERWRITE_CHANGED_PENDING");
  }
 }
 static int Worker(string[] args){
  string phase=args[1],prefix=args[2];var cp=Guard(new FileStore(prefix+".pending"));var ledger=Ledger(new FileStore(prefix+".fills"));
  if(phase=="probe"){
   var inspection=cp.InspectRecovery();bool admitted=false;
   if(inspection==MxmEntryRecoveryInspection.Normal)admitted=cp.Initialize() && ledger.Initialize(Now);
   else if(inspection==MxmEntryRecoveryInspection.Recoverable){
    var book=File.Exists(prefix+".book")?JsonSerializer.Deserialize<MxmEntryRecoveryPosition[]>(File.ReadAllText(prefix+".book"))!:Array.Empty<MxmEntryRecoveryPosition>();
    admitted=ledger.Initialize(Now,true) && cp.RecoverVerifiedOpen(ledger,book,0,Now);
   }
   Need(admitted==bool.Parse(args[3]) && ledger.Count==int.Parse(args[4]),"COLD_PROBE_ADMISSION_AND_UNIQUE_COUNT");
   Console.WriteLine("PROBED");return 0;
  }
  Need(cp.Initialize() && ledger.Initialize(Boundary.AddDays(-1)) && Prepare(cp),"WORKER_PREPARED");
  if(phase!="before-call"){
   Need(cp.MarkSubmitted(),"WORKER_CALL_BARRIER");var position=Position(cp.SubmissionComment!);
   new FileStore(prefix+".book").Write(JsonSerializer.Serialize(new[]{position}));
   using(var f=new FileStream(prefix+".calls",FileMode.Create,FileAccess.Write,FileShare.None)){f.WriteByte(1);f.Flush(true);}
   if(phase=="recorded" || phase=="ready")Need(ledger.RecordConfirmed(Confirmed(position,Boundary.AddSeconds(3))),"WORKER_CONFIRMED_ENTRY_SAVED");
   if(phase=="ready")Need(cp.CompleteReconciled(),"WORKER_READY_AFTER_ENTRY_DURABLE");
  }
  Console.WriteLine("STAGED");Console.Out.Flush();Thread.Sleep(Timeout.Infinite);return 1;
 }
 static Process Spawn(params string[] args){
  var info=new ProcessStartInfo("dotnet"){UseShellExecute=false,RedirectStandardOutput=true,RedirectStandardError=true};
  info.ArgumentList.Add(Assembly.GetEntryAssembly()!.Location);info.ArgumentList.Add("--worker");
  foreach(var arg in args)info.ArgumentList.Add(arg);return Process.Start(info)!;
 }
 public static int Main(string[] args){
  try {
   if(args.Length>=3 && args[0]=="--worker")return Worker(args);
   Need(args.Length==0,"ONLY_SYNTHETIC_FIXTURE");Contracts();var cases=new List<object>();
   string root=Path.Combine(Path.GetTempPath(),"mxm-entry-recovery-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
   try {
    foreach(string phase in new[]{"before-call","unknown-accepted","recorded","ready"}){
     string prefix=Path.Combine(root,phase);
     using(var first=Spawn(phase,prefix)){
      try{Need(first.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(20)).GetAwaiter().GetResult()=="STAGED","STAGED_"+phase);}
      finally{if(!first.HasExited)first.Kill(true);Need(first.WaitForExit(10000),"HARD_KILL");}
     }
     long before=File.Exists(prefix+".calls")?new FileInfo(prefix+".calls").Length:0;
     bool expected=phase!="before-call";int count=expected?1:0;
     using(var cold=Spawn("probe",prefix,expected.ToString(),count.ToString())){
      Need(cold.WaitForExit(20000) && cold.ExitCode==0,"COLD_PROCESS_"+phase);
      Need(cold.StandardOutput.ReadToEnd().Trim()=="PROBED","COLD_OUTPUT");
     }
     long after=File.Exists(prefix+".calls")?new FileInfo(prefix+".calls").Length:0;
     Need(before==after && before==(expected?1:0),"NO_SYNTHETIC_RESUBMISSION");
     cases.Add(new {phase,restart_admitted=expected,unique_recorded_entries=count,synthetic_calls=before,resubmissions=0});
    }
   }finally{Directory.Delete(root,true);}
   var proof=new {schema="mxm.csharp.correlated-open-entry-recovery.artificial.v1",checks,
    source_sha=Environment.GetEnvironmentVariable("GITHUB_SHA")??"LOCAL",hard_kills=4,new_os_processes=8,cases,
    native_ctrader_execution=false,native_storage_durability_proven=false,broker_history_reconciliation=false,
    broker_orders=0,new_strategy_trials=0,economic_edge_proven=false,hard21_proven=false};
   string path="verification/correlated-entry-recovery/proof.json";Directory.CreateDirectory(Path.GetDirectoryName(path)!);
   File.WriteAllText(path,JsonSerializer.Serialize(proof,new JsonSerializerOptions{WriteIndented=true}));
   Console.WriteLine(JsonSerializer.Serialize(proof));return 0;
  }catch(Exception e){Console.Error.WriteLine(e);return 1;}
 }
}

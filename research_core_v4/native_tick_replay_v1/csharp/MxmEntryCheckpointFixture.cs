using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using Mxm.Replay;

static class EntryCheckpointFixture {
 static int checks;
 static readonly DateTime Boundary=new(2026,8,24,12,0,0,DateTimeKind.Utc);
 static readonly string Scope=MxmEntryCheckpoint.AccountScope("Synthetic Broker",123,false);
 static void Need(bool value,string code){if(!value)throw new Exception("MXM_ENTRY_CHECKPOINT_FIXTURE_"+code);checks++;}
 sealed class Store : IMxmEntryCheckpointStore {
  public string? Value;public bool FailRead,FailWrite,DropWrite;public Action? AfterWrite;
  public string? Read(){if(FailRead)throw new IOException("INJECTED_READ");return Value;}
  public void Write(string value){if(FailWrite)throw new IOException("INJECTED_WRITE");if(!DropWrite)Value=value;AfterWrite?.Invoke();}
 }
 sealed class FileStore : IMxmEntryCheckpointStore {
  readonly string path;public FileStore(string path){this.path=path;}
  public string? Read()=>File.Exists(path)?File.ReadAllText(path):null;
  public void Write(string value){
   string temp=path+".partial";
   using(var f=new FileStream(temp,FileMode.Create,FileAccess.Write,FileShare.None)){
    byte[] raw=System.Text.Encoding.UTF8.GetBytes(value);f.Write(raw);f.Flush(true);
   }
   File.Move(temp,path,true);
  }
 }
 static MxmEntryCheckpoint Guard(IMxmEntryCheckpointStore store)=>new(store,Scope);
 static int Worker(string[] args){
  string action=args[1],path=args[2];var journal=Guard(new FileStore(path));
  bool allowed=journal.Initialize();
  if(action=="probe"){
   bool expected=bool.Parse(args[3]);Need(allowed==expected,"COLD_PROCESS_ADMISSION");
   Console.WriteLine(allowed?"READY":"BLOCKED");return 0;
  }
  Need(allowed && journal.Prepare("EURUSD",1,Boundary),"WORKER_PREPARE");
  if(action!="prepared"){
   Need(journal.MarkSubmitted(),"WORKER_SUBMIT");
   using(var f=new FileStream(path+".fakebroker",FileMode.Append,FileAccess.Write,FileShare.None)){
    f.WriteByte(1);f.Flush(true);
   }
   if(action=="halted")journal.Halt();
   if(action=="resolved")Need(journal.CompleteReconciled(),"WORKER_RESOLVE");
  }
  Console.WriteLine("STAGED");Console.Out.Flush();
  Thread.Sleep(Timeout.Infinite);return 1; // Parent kills process; no finally/OnStop cleanup.
 }
 static Process Start(params string[] args){
  var info=new ProcessStartInfo("dotnet"){UseShellExecute=false,RedirectStandardOutput=true,RedirectStandardError=true};
  info.ArgumentList.Add(Assembly.GetEntryAssembly()!.Location);info.ArgumentList.Add("--worker");
  foreach(var arg in args)info.ArgumentList.Add(arg);
  return Process.Start(info)??throw new Exception("WORKER_START_FAILED");
 }
 static void Contracts(){
  var old=new MxmOrderProtection();old.HaltUnknown();
  Need(old.Halted && !new MxmOrderProtection().Halted,"OLD_MEMORY_ONLY_RESTART_COUNTEREXAMPLE");
  var store=new Store();var journal=Guard(store);
  Need(journal.Initialize(),"NEW_STORE_READY");
  Need(journal.StorageKey.Length<=50 && journal.StorageKey.All(c=>char.IsAsciiLetterOrDigit(c)||c==' '),"PLATFORM_KEY_RESTRICTIONS");
  Need(journal.StorageKey==new MxmEntryCheckpoint(new Store(),MxmEntryCheckpoint.AccountScope(" synthetic broker ",123,false)).StorageKey,
   "BROKER_CASE_WHITESPACE_CANONICAL");
  Need(journal.StorageKey!=new MxmEntryCheckpoint(new Store(),MxmEntryCheckpoint.AccountScope("Synthetic Broker",124,false)).StorageKey,
   "ACCOUNT_SCOPE_DISTINCT");
  Need(journal.StorageKey!=new MxmEntryCheckpoint(new Store(),MxmEntryCheckpoint.AccountScope("Synthetic Broker",123,true)).StorageKey,
   "DEMO_LIVE_SCOPE_DISTINCT");
  Need(journal.Prepare("EURUSD",1,Boundary),"PENDING_SAVED_BEFORE_SUBMIT");
  string? pending=store.Value;
  Need(!Guard(store).Initialize() && store.Value==pending,"NEW_INSTANCE_CANNOT_ERASE_PENDING");
  Need(journal.CompleteNotSubmitted(),"KNOWN_NOT_SENT_CAN_CLEAR");
  Need(Guard(store).Initialize(),"KNOWN_NOT_SENT_RESTART_READY");
  Need(journal.Prepare("EURUSD",-1,Boundary) && journal.MarkSubmitted(),"ENTER_SUBMITTED_PHASE");
  Need(!journal.CompleteNotSubmitted() && journal.Halted,"SUBMITTED_CANNOT_BE_CALLED_NOT_SENT");
  Need(!Guard(store).Initialize(),"RESTART_BLOCKS_UNRESOLVED_SUBMISSION");
  foreach(string corruption in new[]{"garbage","{}"," ","MXM_ENTRY_CHECKPOINT_V2_UNKNOWN"}){
   var bad=new Store{Value=corruption};Need(!Guard(bad).Initialize() && bad.Value==corruption,"UNKNOWN_FORMAT_FAILS_CLOSED");
  }
  foreach(string fault in new[]{"READ","WRITE","DROP"}){
   var bad=new Store{FailRead=fault=="READ",FailWrite=fault=="WRITE",DropWrite=fault=="DROP"};
   Need(!Guard(bad).Initialize(),"BOOT_STORAGE_"+fault);
   var later=new Store();var g=Guard(later);Need(g.Initialize(),"FAULT_PREREQUISITE");
   later.FailRead=fault=="READ";later.FailWrite=fault=="WRITE";later.DropWrite=fault=="DROP";
   Need(!g.Prepare("EURUSD",1,Boundary) && !g.MarkSubmitted(),"PREORDER_STORAGE_"+fault+"_NO_SIDE_EFFECT");
  }
  var callback=new Store();var poisoned=Guard(callback);Need(poisoned.Initialize(),"CALLBACK_BASELINE");
  callback.AfterWrite=poisoned.Halt;
  Need(!poisoned.Prepare("EURUSD",1,Boundary) && !poisoned.MarkSubmitted(),"NONTHROWING_CALLBACK_POISON_IS_IRREVERSIBLE");
  Need(!Guard(callback).Initialize(),"CALLBACK_PENDING_SURVIVES_RESTART");
  var changed=new Store();var conflict=Guard(changed);Need(conflict.Initialize() && conflict.Prepare("EURUSD",1,Boundary) &&
   conflict.MarkSubmitted(),"CONFLICT_BASELINE");changed.Value="OTHER_ATTEMPT";
  Need(!conflict.CompleteReconciled() && changed.Value=="OTHER_ATTEMPT","NEVER_CLEAR_CHANGED_CHECKPOINT");
  foreach(string replacement in new[]{"OTHER_ATTEMPT","", "garbage"}) {
   var disk=new Store();var guard=Guard(disk);
   Need(guard.Initialize() && guard.Prepare("EURUSD",1,Boundary),"RELOAD_PREPARE");
   disk.Value=replacement;
   Need(!guard.VerifyPreparedCurrent() && guard.Halted && !guard.MarkSubmitted() && disk.Value==replacement,
    "CHANGED_OR_MISSING_DURABLE_INTENT_NEVER_SUBMITS_OR_OVERWRITES");
  }
  var unreadable=new Store();var unreadableGuard=Guard(unreadable);
  Need(unreadableGuard.Initialize() && unreadableGuard.Prepare("EURUSD",1,Boundary),"RELOAD_FAULT_PREPARE");
  unreadable.FailRead=true;
  Need(!unreadableGuard.VerifyPreparedCurrent() && !unreadableGuard.MarkSubmitted(),"RELOAD_READ_FAULT_NO_SUBMIT");
  var intact=new Store();var intactGuard=Guard(intact);
  Need(intactGuard.Initialize() && intactGuard.Prepare("EURUSD",1,Boundary) &&
   intactGuard.VerifyPreparedCurrent() && intactGuard.MarkSubmitted(),"EXACT_DURABLE_INTENT_RECHECK_ADMITS");
  var resolved=new Store();var success=Guard(resolved);Need(success.Initialize() && success.Prepare("EURUSD",1,Boundary) &&
   success.MarkSubmitted() && success.CompleteReconciled() && Guard(resolved).Initialize(),"RECONCILED_READY_CAN_RESTART");
  var declined=new Store();var uncertain=Guard(declined);
  Need(uncertain.Initialize() && uncertain.Prepare("EURUSD",1,Boundary) && uncertain.MarkSubmitted(),"UNSUCCESSFUL_BASELINE");
  var negative=new MxmOrderProtection().Reconcile(false,null,"OWNER","EURUSD",1,1000,12,.0001,.00001,
   Array.Empty<long>(),Array.Empty<MxmProtectionPosition>());
  Need(!negative.Accepted && !negative.Halt,"OLD_FALSE_EMPTY_BOOK_IS_NOT_POSITIVE_FILL_ACK");
  uncertain.Halt();Need(!uncertain.CompleteReconciled() && !Guard(declined).Initialize(),
   "UNSUCCESSFUL_RESULT_CANNOT_DISARM_DURABLE_PENDING");
  var flat=new Store();var stopped=Guard(flat);Need(stopped.Initialize() && stopped.Prepare("EURUSD",1,Boundary) &&
   stopped.MarkSubmitted(),"HALT_BASELINE");stopped.Halt();
  Need(!stopped.CompleteReconciled() && !Guard(flat).Initialize(),"FLAT_BOOK_OR_HALT_CANNOT_CLEAR_UNKNOWN");
 }
 public static int Main(string[] args){
  try {
   if(args.Length>=3 && args[0]=="--worker")return Worker(args);
   Need(args.Length==0,"NO_OTHER_MODE");Contracts();
   string root=Path.Combine(Path.GetTempPath(),"mxm-entry-checkpoint-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
   var cases=new List<object>();
   try {
    foreach(string action in new[]{"prepared","submitted","halted","resolved"}){
     string path=Path.Combine(root,action+".txt");
     using(var first=Start(action,path)){
      try {
       string? message=first.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(20)).GetAwaiter().GetResult();
       Need(message=="STAGED","PERSISTED_BEFORE_KILL_"+action);
      }finally{if(!first.HasExited)first.Kill(true);Need(first.WaitForExit(10000),"HARD_KILL_COMPLETED");}
     }
     long callsBefore=File.Exists(path+".fakebroker")?new FileInfo(path+".fakebroker").Length:0;
     bool expected=action=="resolved";
     using(var cold=Start("probe",path,expected.ToString())){
      Need(cold.WaitForExit(20000) && cold.ExitCode==0,"NEW_OS_PROCESS_CORRECT_RECOVERY_"+action);
      Need(cold.StandardOutput.ReadToEnd().Trim()==(expected?"READY":"BLOCKED"),"COLD_PROOF_"+action);
     }
     long callsAfter=File.Exists(path+".fakebroker")?new FileInfo(path+".fakebroker").Length:0;
     Need(callsBefore==callsAfter && callsBefore==(action=="prepared"?0:1),"NO_SYNTHETIC_RESUBMISSION_"+action);
     cases.Add(new {phase=action,restart_admitted=expected,synthetic_calls=callsBefore,resubmissions=0});
    }
   }finally{Directory.Delete(root,true);}
   var proof=new {schema="mxm.csharp.entry-checkpoint.artificial-process-recovery.v1",checks,
    source_sha=Environment.GetEnvironmentVariable("GITHUB_SHA")??"LOCAL",hard_kills=4,new_os_processes=8,cases,
    memory_only_restart_counterexample_reproduced=true,native_ctrader_execution=false,native_storage_durability_proven=false,broker_orders=0,new_scientific_trials=0,
    economic_edge_proven=false,hard21_proven=false};
   string output=Path.Combine("verification","entry-checkpoint","proof.json");Directory.CreateDirectory(Path.GetDirectoryName(output)!);
   File.WriteAllText(output,JsonSerializer.Serialize(proof,new JsonSerializerOptions{WriteIndented=true}));
   Console.WriteLine("MXM_ENTRY_CHECKPOINT_FOUR_HARD_KILLS_EIGHT_COLD_PROCESSES_NO_RESUBMISSION_PASS_NOT_NATIVE_PROOF");
   Console.WriteLine(JsonSerializer.Serialize(proof));return 0;
  }catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}
 }
}

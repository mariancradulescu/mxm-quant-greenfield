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

static class ConfirmedEntryLedgerFixture {
 static int checks;
 static readonly DateTime Start=new(2020,12,28,0,0,0,DateTimeKind.Utc);
 static readonly string Scope=MxmEntryCheckpoint.AccountScope("Synthetic",123,false);
 static void Need(bool ok,string name){if(!ok)throw new Exception("CONFIRMED_ENTRY_FIXTURE_"+name);checks++;}
 sealed class Store : IMxmEntryCheckpointStore {
  public string? Value;public bool ReadFault,WriteFault,Drop;public Action? AfterWrite;
  public string? Read(){if(ReadFault)throw new IOException("READ_FAULT");return Value;}
  public void Write(string value){if(WriteFault)throw new IOException("WRITE_FAULT");if(!Drop)Value=value;AfterWrite?.Invoke();}
 }
 sealed class FileStore : IMxmEntryCheckpointStore {
  readonly string path;public FileStore(string path){this.path=path;}
  public string? Read()=>File.Exists(path)?File.ReadAllText(path):null;
  public void Write(string value){
   string temporary=path+".partial";
   using(var stream=new FileStream(temporary,FileMode.Create,FileAccess.Write,FileShare.None)){
    stream.Write(Encoding.UTF8.GetBytes(value));stream.Flush(true);
   }
   File.Move(temporary,path,true);
  }
 }
 static MxmConfirmedEntry Entry(long id,DateTime when,DateTime? observed=null)=>new(id,"EURUSD",1,1000,when,observed??when);
 static MxmConfirmedEntryLedger Ledger(IMxmEntryCheckpointStore store)=>new(store,Scope);
 static object Contracts(){
  var store=new Store();var ledger=Ledger(store);Need(ledger.Initialize(Start),"FIRST_USE");
  Need(ledger.StorageKey.Length<=50 && ledger.StorageKey.All(c=>char.IsAsciiLetterOrDigit(c)||c==' '),"NATIVE_KEY");
  Need(ledger.StorageKey!=new MxmEntryCheckpoint(new Store(),Scope).StorageKey,"SEPARATE_BARRIER_KEY");
  DateTime sunday=Start.AddDays(7).AddSeconds(-1),monday=Start.AddDays(7);
  for(int id=1;id<=21;id++)Need(ledger.RecordConfirmed(Entry(id,sunday,monday)),"BROKER_ENTRY_TIME_WEEK");
  Need(ledger.RecordConfirmed(Entry(22,monday)),"NEXT_WEEK_ENTRY");
  Need(ledger.RecordConfirmed(Entry(22,monday,monday.AddDays(1))) && ledger.Count==22,"IDENTICAL_ID_LOWER_BOUND_ONCE");
  string original=store.Value!;
  var cold=Ledger(store);Need(cold.Initialize(monday.AddDays(1)) && cold.Count==22,"COLD_RESTART_KEEPS_CONTINUOUS_COUNTS");
  Need(cold.RecordConfirmed(Entry(22,monday,monday.AddDays(1))) && cold.Count==22,"COLD_DUPLICATE_NO_INCREMENT");
  var weeks=cold.Snapshot(Start.AddDays(21));
  Need(weeks.Select(x=>x.IsoWeek).SequenceEqual(new[]{"2020-W53","2021-W01","2021-W02","2021-W03"}),"ISO_YEAR_NOT_CALENDAR_YEAR");
  Need(weeks.Select(x=>x.ConfirmedProtectedEntries).SequenceEqual(new[]{21,1,0,0}),"INCLUDE_ZERO_WEEKS");
  Need(weeks.Take(3).All(x=>x.CalendarWeekElapsed) && !weeks[3].CalendarWeekElapsed,"ELAPSED_WEEK_BOUNDARY");
  Need(weeks[0].RecordedThresholdMet && weeks.Skip(1).All(x=>!x.RecordedThresholdMet),"THRESHOLD_WITHOUT_FILLER_TRADES");
  Need(weeks.All(x=>!x.Hard21Proven && !x.BrokerHistoryCoverageProven),"NEVER_CERTIFY_FROM_COUNTERS");
  var partial=Ledger(new Store());Need(partial.Initialize(Start.AddDays(2)),"MIDWEEK_START");
  Need(!partial.Snapshot(monday)[0].MeasurementStartedBeforeWeek,"PARTIAL_FIRST_WEEK_NOT_COMPLETE");
  Need(MxmConfirmedEntryLedger.WeekId(new DateTime(2018,12,31,0,0,0,DateTimeKind.Utc))=="2019-W01","DECEMBER_ISO_NEXT_YEAR");
  Need(!new MxmConfirmedEntryLedger(new Store{Value=original},Scope+"other").Initialize(monday),"CROSS_ACCOUNT_REFUSED");
  foreach(var corrupt in new[]{"", " ","{}",original.Replace("EURUSD","GBPUSD")}){
   var bad=new Store{Value=corrupt};Need(!Ledger(bad).Initialize(monday) && bad.Value==corrupt,"CORRUPTION_NOT_OVERWRITTEN");
  }
  foreach(string mode in new[]{"read","write","drop","callback"}){
   var fault=new Store();var target=Ledger(fault);Need(target.Initialize(Start),"FAULT_BASELINE");
   fault.ReadFault=mode=="read";fault.WriteFault=mode=="write";fault.Drop=mode=="drop";
   if(mode=="callback")fault.AfterWrite=target.Halt;
   Need(!target.RecordConfirmed(Entry(1,Start.AddSeconds(1))) && target.Halted,"DURABILITY_FAULT_"+mode);
  }
  foreach(string mode in new[]{"symbol","direction","volume","time"}){
   var duplicate=new Store{Value=original};var target=Ledger(duplicate);Need(target.Initialize(monday),"CONFLICT_BASELINE");
   var entry=Entry(22,monday);
   entry=mode switch {"symbol"=>entry with {Symbol="GBPUSD"},"direction"=>entry with {Direction=-1},
    "volume"=>entry with {Units=2000},_=>entry with {EntryUtc=monday.AddTicks(-1)}};
   Need(!target.RecordConfirmed(entry) && duplicate.Value==original,"CONTRADICTORY_POSITION_ID_"+mode);
  }
  foreach(var invalid in new[]{Entry(0,Start),Entry(1,Start.AddTicks(-1)),Entry(1,Start,Start.AddTicks(-1)),
   Entry(1,DateTime.SpecifyKind(Start,DateTimeKind.Unspecified)),Entry(1,Start) with {Units=0},
   Entry(1,Start) with {Direction=0}}){
   var bad=Ledger(new Store());Need(bad.Initialize(Start) && !bad.RecordConfirmed(invalid),"INVALID_FILL_NOT_COUNTED");
  }
  var changedStore=new Store();var changed=Ledger(changedStore);Need(changed.Initialize(Start),"CHANGED_BASELINE");
  changedStore.Value="OTHER_WRITER";
  Need(!changed.VerifyCurrent(Start) && changed.Halted && changedStore.Value=="OTHER_WRITER","PREFLIGHT_STALE_STORE_NO_ORDER");
  var backwards=Ledger(new Store());Need(backwards.Initialize(Start) && backwards.RecordConfirmed(Entry(1,Start.AddHours(2))),"CLOCK_BASELINE");
  Need(!backwards.VerifyCurrent(Start.AddHours(1)),"BACKWARD_CLOCK_NO_ORDER");
  return new {journal=JsonSerializer.Deserialize<JsonElement>(original),weeks};
 }
 static int Worker(string[] args){
  string phase=args[1],root=args[2];var checkpoint=new MxmEntryCheckpoint(new FileStore(root+".pending"),Scope);
  var ledger=Ledger(new FileStore(root+".fills"));
  if(phase=="probe"){
   bool allowed=checkpoint.Initialize();Need(ledger.Initialize(Start.AddDays(8)),"COLD_LEDGER_READ");
   Need(allowed==bool.Parse(args[3]) && ledger.Count==int.Parse(args[4]),"COLD_BARRIER_AND_COUNT");
   if(allowed)Need(ledger.RecordConfirmed(Entry(1,Start.AddHours(1))) && ledger.Count==1,"POST_READY_DUPLICATE_ONCE");
   Console.WriteLine("PROBED");return 0;
  }
  Need(checkpoint.Initialize() && ledger.Initialize(Start),"FRESH_DURABLE_BOTH");
  Need(ledger.VerifyCurrent(Start) && checkpoint.Prepare("EURUSD",1,Start) && checkpoint.MarkSubmitted(),"BEFORE_FAKE_ACK");
  if(phase!="before-ledger"){
   Need(ledger.RecordConfirmed(Entry(1,Start.AddHours(1))),"ACK_DURABLE_BEFORE_READY");
   if(phase=="ready")Need(checkpoint.CompleteReconciled(),"READY_AFTER_DURABLE_ACK");
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
   Need(args.Length==0,"ONLY_FIXTURE");var contracts=Contracts();var cases=new List<object>();
   string root=Path.Combine(Path.GetTempPath(),"mxm-confirmed-entries-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
   try {
    foreach(string phase in new[]{"before-ledger","ledger-before-ready","ready"}){
     string prefix=Path.Combine(root,phase);using(var first=Spawn(phase,prefix)){
      try {Need(first.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(20)).GetAwaiter().GetResult()=="STAGED","STAGED_"+phase);}
      finally{if(!first.HasExited)first.Kill(true);Need(first.WaitForExit(10000),"KILLED");}
     }
     bool ready=phase=="ready";int count=phase=="before-ledger"?0:1;
     using(var cold=Spawn("probe",prefix,ready.ToString(),count.ToString())){
      Need(cold.WaitForExit(20000) && cold.ExitCode==0,"COLD_PROBE_"+phase);
      Need(cold.StandardOutput.ReadToEnd().Trim()=="PROBED","COLD_OUTPUT");
     }
     cases.Add(new {phase,restart_admitted=ready,confirmed_lower_bound=count,orders=0});
    }
   }finally{Directory.Delete(root,true);}
   var proof=new {schema="mxm.confirmed-entry-ledger.artificial.v1",source_sha=Environment.GetEnvironmentVariable("GITHUB_SHA")??"LOCAL",
    checks,contracts,cases,hard_kills=3,new_os_processes=6,broker_orders=0,native_storage_reception=false,
    native_broker_fills=false,broker_history_coverage_proven=false,hard21_proven=false,economic_edge_proven=false};
   string path="verification/confirmed-entry-ledger/proof.json";Directory.CreateDirectory(Path.GetDirectoryName(path)!);
   File.WriteAllText(path,JsonSerializer.Serialize(proof,new JsonSerializerOptions{WriteIndented=true}));
   Console.WriteLine(JsonSerializer.Serialize(proof));return 0;
  }catch(Exception e){Console.Error.WriteLine(e);return 1;}
 }
}

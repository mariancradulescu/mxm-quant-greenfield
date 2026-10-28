using System.Text.Json;
using Mxm.Replay;
using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var reports=new List<object>();
foreach(var c in input.RootElement.EnumerateArray()) {
 var fence=new MxmNativeRunFence();int syntheticPermits=0;var stages=new List<object>();
 bool Begin(bool obs,bool demo,bool sim,string env)=>fence.Begin(obs,demo,sim,env,out _);
 bool first=Begin(c.GetProperty("obs").GetBoolean(),c.GetProperty("demo").GetBoolean(),c.GetProperty("sim").GetBoolean(),c.GetProperty("env").GetString()!);
 void Capture(string operation) {
  bool permit=true;try{fence.DemandAccountMutationPath();syntheticPermits++;}catch(InvalidOperationException){permit=false;}
  stages.Add(new{operation,mode=fence.Mode.ToString(),observing=fence.IsObserving,latched=fence.ObservationLatched,permit,syntheticPermits});
 }
 Capture("begin");
 foreach(var a in c.GetProperty("actions").EnumerateArray()) {
  string op=a.GetString()!;
  if(op=="stop")fence.Stop();
  if(op=="escalate")Begin(false,true,false,"Desktop");
  Capture(op);
 }
 var book=MxmBookObservations.NativeSnapshots();book.BeginEpoch(0);
 book.Observe(1.1,1.1001,1,1000,null);book.Observe(1.1,1.1,2,1001,null);var view=book.Snapshot(3);
 reports.Add(new{first,stages,view,orders=0,cloud_activated=false,native_callbacks_received=false});
}
File.WriteAllText(args[1],JsonSerializer.Serialize(reports));

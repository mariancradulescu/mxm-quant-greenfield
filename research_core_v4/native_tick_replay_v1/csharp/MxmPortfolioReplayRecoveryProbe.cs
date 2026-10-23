using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
namespace Mxm.Replay {
public sealed record MxmReplayRecoveryProof(string Schema,string SourceSha256,int ColdProcesses,
 long[] CutOrdinals,bool AllReportsIdentical,int InitialCapitalEur,bool NativeCtraderRecovery,int NewStrategyTrials,int Orders);
/// <summary>Fault-boundary regression, not a strategy, independent market evidence or broker emulator.</summary>
public static class MxmPortfolioReplayRecoveryProbe {
 sealed record Request(string Capsule,string TrustedSha,string SourceSha,MxmReplayParameters Parameters,
  string[] Symbols,long Cursor,string Tail,string Output);
 public static bool TryWorker(string[] args,out int exitCode){
  exitCode=0;if(args.Length!=2 || args[0]!="--recovery-worker")return false;
  try {
   var r=JsonSerializer.Deserialize<Request>(File.ReadAllBytes(args[1]))!;
   var restored=MxmPortfolioAccountReplay.RestoreReplay(File.ReadAllBytes(r.Capsule),r.TrustedSha,r.SourceSha,r.Parameters,r.Symbols);
   var report=restored.Continue(File.ReadLines(r.Tail).Select(line=>JsonSerializer.Deserialize<MxmAccountFeed>(line)!),r.Cursor);
   File.WriteAllBytes(r.Output,JsonSerializer.SerializeToUtf8Bytes(report));
  } catch {exitCode=1;}
  return true;
 }
 static void WriteDurably(string target,byte[] bytes){
  string temp=target+".partial";
  using(var file=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){
   file.Write(bytes);file.Flush(true);
  }
  File.Move(temp,target,true);
 }
 public static MxmReplayRecoveryProof Verify(IReadOnlyList<MxmAccountFeed> feed,MxmReplayParameters parameters,
  string[] symbols,string sourceSha,MxmPortfolioAccountReport baseline,IEnumerable<int>? requestedCuts=null){
  if(feed.Count<2)throw new ArgumentException("RECOVERY_PROBE_FEED_TOO_SHORT");
  var cuts=(requestedCuts??new[]{1,feed.Count/3,feed.Count/2,feed.Count-1})
   .Where(x=>x>0 && x<feed.Count).Distinct().OrderBy(x=>x).ToArray();
  if(cuts.Length==0)throw new ArgumentException("RECOVERY_PROBE_NO_CUTS");
  string expected=JsonSerializer.Serialize(baseline);
  string root=Path.Combine(Path.GetTempPath(),"mxm-replay-recovery-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
  try {
   foreach(int cut in cuts){
    var first=new MxmPortfolioAccountReplay(symbols,parameters);
    first.Run(feed.Take(cut));var capsule=first.CaptureReplay(sourceSha);
    string payload=Path.Combine(root,"capsule.json"),tail=Path.Combine(root,"tail.ndjson"),output=Path.Combine(root,"report.json");
    WriteDurably(payload,capsule.Payload);
    using(var writer=new StreamWriter(tail,false))foreach(var item in feed.Skip(cut))writer.WriteLine(JsonSerializer.Serialize(item));
    var request=new Request(payload,capsule.Sha256,sourceSha,parameters,symbols,capsule.NextEventOrdinal,tail,output);
    string requestPath=Path.Combine(root,"request.json");WriteDurably(requestPath,JsonSerializer.SerializeToUtf8Bytes(request));
    // A NEW OS process cannot inherit parent account/kernel/intent memory.
    var start=new ProcessStartInfo("dotnet"){UseShellExecute=false,RedirectStandardOutput=true,RedirectStandardError=true};
    start.ArgumentList.Add(Assembly.GetEntryAssembly()!.Location);start.ArgumentList.Add("--recovery-worker");start.ArgumentList.Add(requestPath);
    using var child=Process.Start(start)??throw new InvalidOperationException("RECOVERY_WORKER_START");
    if(!child.WaitForExit(60000)){child.Kill(true);throw new InvalidOperationException("RECOVERY_WORKER_TIMEOUT");}
    if(child.ExitCode!=0 || !File.Exists(output) || File.ReadAllText(output)!=expected)
     throw new InvalidOperationException("RECOVERY_COLD_PROCESS_ACCOUNT_DIVERGED");
   }
  } finally {Directory.Delete(root,true);}
  return new("mxm.csharp.single-account.cold-process-recovery.v1",sourceSha,cuts.Length,
   cuts.Select(x=>(long)x).ToArray(),true,200,false,0,0);
 }
}
}

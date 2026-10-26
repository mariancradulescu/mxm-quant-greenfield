using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
using Mxm.Research;
if(MxmPortfolioReplayRecoveryProbe.TryWorker(args,out int workerExit)){Environment.ExitCode=workerExit;return;}
string Hash(byte[] b)=>Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
string Policy=new('d',64); // Replaced at invocation by the frozen spec identity.
MxmReplayParameters Settings()=>new(StrategyMode.TrendOnly,.4m,1,0m,.02m,.2m,ExplicitPolicySha256:Policy);
if(args.SequenceEqual(new[]{"--selftest"})){
 int checks=0;void Need(bool ok){checks++;if(!ok)throw new Exception("INTRINSIC_ARTIFICIAL_CHECK_"+checks);}
 void Bad(Action a){bool bad=false;try{a();}catch(ArgumentException){bad=true;}Need(bad);}
 var t=new DateTime(2026,8,24,7,0,0,DateTimeKind.Utc);
 MxmQuote Q(DateTime at,decimal bid=1.10m)=>new(at,"EURUSD",bid,bid+.0001m,1m/(bid+.0001m),1000m,50m,.1m,.00002m,1.2m,
  1m/bid,StopDistanceQuote:.0012m,BidSourceUtc:at,AskSourceUtc:at);
 var first=new MxmExplicitDecision(t,"EURUSD",1,1,t.AddMilliseconds(250),t.AddSeconds(5),Policy);
 var feed=new List<MxmAccountFeed>{Q(t),first,Q(t.AddMilliseconds(100)),Q(t.AddMilliseconds(250)),
  new MxmExplicitDecision(t.AddSeconds(1),"EURUSD",2,0,t.AddMilliseconds(1250),t.AddSeconds(6),Policy),Q(t.AddMilliseconds(1250),1.101m)};
 var account=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings());var report=account.Run(feed);
 Need(report.AcceptedEntries==1 && report.ExecutedExits==1 && report.OpenPositions==0);
 Need(report.Ledger[0].Utc==t.AddMilliseconds(250) && report.Ledger[1].Reason=="EXPLICIT_POLICY_FLAT");
 for(int cut=0;cut<=feed.Count;cut++){
  var p=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings());p.Run(feed.Take(cut));var c=p.CaptureReplay(Policy);
  var r=MxmPortfolioAccountReplay.RestoreReplay(c.Payload,c.Sha256,Policy,Settings(),new[]{"EURUSD"});
  Need(JsonSerializer.Serialize(report)==JsonSerializer.Serialize(r.Continue(feed.Skip(cut),cut)));
 }
 Need(MxmPortfolioReplayRecoveryProbe.Verify(feed,Settings(),new[]{"EURUSD"},Policy,report,new[]{2,3,4}).ColdProcesses==3);
 foreach(var bad in new[]{first with {Sequence=2},first with {PolicySha256=new string('a',64)},first with {ValidFromUtc=t},first with {Desired=2}})
  Bad(()=>new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings()).Run(new MxmAccountFeed[]{Q(t),bad}));
 var expiry=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings()).Run(new MxmAccountFeed[]{Q(t),first,Q(t.AddSeconds(5))});Need(expiry.AcceptedEntries==0);
 var rejected=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings() with {MaxMarginFraction=.1m});
 var rejectReport=rejected.Run(new MxmAccountFeed[]{Q(t),first,Q(t.AddMilliseconds(250)),Q(t.AddMilliseconds(500))});
 Need(rejectReport.AcceptedEntries==0 && rejectReport.RejectedEntries==1);
 Bad(()=>new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings()).Run(new MxmAccountFeed[]{new MxmBarClose(t,"EURUSD",1.1m)}));
 var stopped=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings());stopped.Run(feed.Take(4));
 var stoppedReport=stopped.Continue(new MxmAccountFeed[]{Q(t.AddSeconds(1),1.098m),first with {Utc=t.AddSeconds(1),Sequence=2,ValidFromUtc=t.AddMilliseconds(1250),ExpiresUtc=t.AddSeconds(6)},Q(t.AddMilliseconds(1250))},4);
 Need(stoppedReport.AcceptedEntries==1 && stoppedReport.ExecutedExits==1);
 var broken=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings());broken.Run(feed.Take(4));
 Bad(()=>broken.Continue(new[]{new MxmInstrumentQuoteUnavailable(t.AddSeconds(1),"EURUSD","SOURCE_STALE")},4));Bad(()=>broken.Report());
 var k=new IntrinsicKernel(Policy);Need(k.Quote(t,1.1m)==null);Need(k.Quote(t.AddSeconds(1),1.1005m)!.Desired==1);
 Need(k.Quote(t.AddSeconds(2),1.101m)==null);Need(k.Quote(t.AddSeconds(3),1.1005m)!.Desired==-1);
 var saved=JsonSerializer.Deserialize<IntrinsicState>(JsonSerializer.Serialize(k.State))!;var restored=new IntrinsicKernel(Policy,saved);
 Need(JsonSerializer.Serialize(k.Quote(t.AddSeconds(304),1.1005m))==JsonSerializer.Serialize(restored.Quote(t.AddSeconds(304),1.1005m)));
 Console.WriteLine(JsonSerializer.Serialize(new{checks,orders=0,economic_trials=0,native_ctrader_runtime=false}));return;
}
if(args.Length!=6 || args[0]!="--segment")throw new ArgumentException("INTRINSIC_EXACT_ARGUMENTS");
// input/output, bound source-context digest, frozen policy digest, previous output or '-'.
string input=args[1],output=args[2],source=args[3];Policy=args[4];string previous=args[5];
if(source.Length!=64 || Policy.Length!=64)throw new ArgumentException("INTRINSIC_CONTEXT");
MxmPortfolioAccountReplay engine;IntrinsicKernel kernel;
if(previous=="-"){engine=new(new[]{"EURUSD"},Settings());kernel=new(Policy);}
else{
 using var doc=JsonDocument.Parse(File.ReadAllBytes(previous));var p=doc.RootElement;
 if(p.GetProperty("fault").ValueKind!=JsonValueKind.Null || p.GetProperty("source_context").GetString()!=source || p.GetProperty("policy_sha256").GetString()!=Policy)throw new ArgumentException("INTRINSIC_RESUME_CONTEXT");
 byte[] payload=Convert.FromBase64String(p.GetProperty("capsule_b64").GetString()!);
 engine=MxmPortfolioAccountReplay.RestoreReplay(payload,p.GetProperty("capsule_sha256").GetString()!,source,Settings(),new[]{"EURUSD"});
 string state=p.GetProperty("kernel_json").GetString()!;
 if(Hash(Encoding.UTF8.GetBytes(state))!=p.GetProperty("kernel_sha256").GetString())throw new ArgumentException("INTRINSIC_KERNEL_DIGEST");
 kernel=new(Policy,JsonSerializer.Deserialize<IntrinsicState>(state)!);
}
long rows=0,groups=0,invalid=0,decisions=0;long? bt=null,at=null;long? bid=null,ask=null;
using var digest=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
IEnumerable<MxmAccountFeed> Feed(){
 // The exporter preserves raw side events. Aggregate only an atomic source ms;
 // contradictory same-side revisions invalidate, never fall back to old values.
 long stamp=-1;var bids=new HashSet<long>();var asks=new HashSet<long>();
 IEnumerable<MxmAccountFeed> Group(){
  groups++;var utc=DateTimeOffset.FromUnixTimeMilliseconds(stamp).UtcDateTime;
  if(bids.Count>0){bid=bids.Count==1?bids.Single():null;bt=stamp;}
  if(asks.Count>0){ask=asks.Count==1?asks.Single():null;at=stamp;}
  string? reason=bid==null||ask==null?"MISSING_OR_CONTRADICTORY":ask<=bid?"CROSSED_OR_ZERO":stamp-bt>5000||stamp-at>5000?"STALE":null;
  if(reason!=null){invalid++;kernel.Invalidate(utc);yield return new MxmInstrumentQuoteUnavailable(utc,"EURUSD",reason);yield break;}
  decimal b=bid!.Value/100000m,a=ask!.Value/100000m;
  yield return new MxmQuote(utc,"EURUSD",b,a,1m/a,1000m,50m,0m,.00002m,1.2m,1m/b,
   new MxmEurUsdCapturedCosts(100000,100000,100000,10000000,1,3000000000,1000000,"USD"),
   .0012m,DateTimeOffset.FromUnixTimeMilliseconds(bt!.Value).UtcDateTime,DateTimeOffset.FromUnixTimeMilliseconds(at!.Value).UtcDateTime);
  var d=kernel.Quote(utc,(a+b)/2m);
  if(d!=null){decisions++;digest.AppendData(Encoding.ASCII.GetBytes($"{stamp}|{d.Sequence}|{d.Desired}\n"));yield return d;}
 }
 foreach(string line in File.ReadLines(input)){
  using var doc=JsonDocument.Parse(line);var e=doc.RootElement;long t=e.GetProperty("t").GetInt64(),v=e.GetProperty("raw").GetInt64();string side=e.GetProperty("side").GetString()!;
  if(t<stamp || v<=0 || side is not ("bid" or "ask"))throw new ArgumentException("INTRINSIC_SOURCE_ROW");
  if(stamp>=0 && t!=stamp){foreach(var f in Group())yield return f;bids.Clear();asks.Clear();}
  stamp=t;(side=="bid"?bids:asks).Add(v);rows++;
 }
 if(stamp>=0)foreach(var f in Group())yield return f;
}
MxmPortfolioAccountReport? accountResult=null;string? fault=null;MxmReplayCapsule? capsule=null;
try{accountResult=engine.Continue(Feed(),engine.NextEventOrdinal);capsule=engine.CaptureReplay(source);}catch(ArgumentException e){fault=e.Message;}
string kernelJson=JsonSerializer.Serialize(kernel.State);
var result=new{schema="mxm.intrinsic-continuous-account.v1",source_context=source,policy_sha256=Policy,
 input_sha256=Hash(File.ReadAllBytes(input)),rows_processed=rows,groups_processed=groups,invalid_groups=invalid,decisions,
 decision_sha256=Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant(),account=accountResult,fault,
 capsule_b64=capsule==null?null:Convert.ToBase64String(capsule.Payload),capsule_sha256=capsule?.Sha256,
 kernel_json=kernelJson,kernel_sha256=Hash(Encoding.UTF8.GetBytes(kernelJson)),broker_orders=0,
 historical_costs_proven=false,native_ctrader_runtime_reception=false,hard21_proven=false,economic_edge_proven=false};
File.WriteAllText(output,JsonSerializer.Serialize(result));Console.WriteLine("INTRINSIC_SEGMENT_RESULT_PRIVATE");

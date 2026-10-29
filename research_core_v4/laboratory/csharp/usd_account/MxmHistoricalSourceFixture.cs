using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Replay;
namespace Mxm.Research;
// Engineering source continuity only. No hypothesis, response label or model PnL.
public static class MxmHistoricalSourceFixture {
 sealed record NativeRow(string symbol,long t,string side,long raw);
 sealed record Request(string Declaration,string Rows,string Capsule,string TrustedSha,string SourceSha,
  string StreamSha,int Cut,string Output);
 static void Need(bool ok,string why){if(!ok)throw new InvalidOperationException("HISTORICAL_SOURCE_PROBE_"+why);}
 static string Hash(byte[] bytes)=>Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
 static MxmReplayParameters Settings(string declaration)=>new(StrategyMode.TrendOnly,.8m,3,0m,.03m,.2m,
  UseSharedUsdConversion:true,UsdQuoteMetadataJson:declaration);
 static string[] Roster(string declaration){using var doc=JsonDocument.Parse(declaration);
  return doc.RootElement.GetProperty("symbols").EnumerateArray().Select(x=>x.GetProperty("symbol").GetString()!).ToArray();}
 static string Source(string declaration){using var doc=JsonDocument.Parse(declaration);
  return doc.RootElement.GetProperty("source_sha256").GetString()!;}
 static MxmHistoricalQuoteGroup[] Read(string path,string trustedStream){
  byte[] raw=File.ReadAllBytes(path);Need(raw.Length<=2000000 && Hash(raw)==trustedStream,"AUTHENTICATED_STREAM");
  var rows=new List<NativeRow>();long previous=-1;
  foreach(string line in File.ReadLines(path)){
   using var doc=JsonDocument.Parse(line);var root=doc.RootElement;
   Need(root.EnumerateObject().Select(p=>p.Name).OrderBy(s=>s,StringComparer.Ordinal)
    .SequenceEqual(new[]{"raw","side","symbol","t"}),"EXACT_ROW_FIELDS");
   var r=JsonSerializer.Deserialize<NativeRow>(line)!;
   Need(r.t>=1786442400000L && r.t<1786443000000L && r.t>=previous && r.raw>0 &&
    new[]{"AUDUSD","Copper","SpotCrude"}.Contains(r.symbol) && new[]{"bid","ask"}.Contains(r.side),"SOURCE_ROW");
   rows.Add(r);previous=r.t;Need(rows.Count<=2969,"EVENT_CAP");
  }
  var expected=new Dictionary<string,int>{{"AUDUSD/bid",637},{"AUDUSD/ask",667},{"Copper/bid",208},
   {"Copper/ask",210},{"SpotCrude/bid",623},{"SpotCrude/ask",624}};
  Need(rows.Count==2969 && expected.All(p=>rows.Count(r=>r.symbol+"/"+r.side==p.Key)==p.Value),"AUTHENTIC_SIDE_COUNTS");
  return rows.GroupBy(r=>(r.t,r.symbol)).OrderBy(g=>g.Key.t).ThenBy(g=>g.Key.symbol,StringComparer.Ordinal)
   .Select(g=>new MxmHistoricalQuoteGroup(g.Key.t,g.Key.symbol,g.Where(r=>r.side=="bid").Select(r=>r.raw).ToArray(),
    g.Where(r=>r.side=="ask").Select(r=>r.raw).ToArray())).ToArray();
 }
 static MxmPortfolioAccountReplay Fresh(string declaration,string stream){
  var a=new MxmPortfolioAccountReplay(Roster(declaration),Settings(declaration));
  a.BeginHistoricalSource(Source(declaration),stream,1786442400000L,1786443000000L,2969);return a;
 }
 static void Tail(MxmPortfolioAccountReplay a,IEnumerable<MxmHistoricalQuoteGroup> groups){
  foreach(var group in groups)a.ObserveHistoricalGroup(group,a.HistoricalSource!.Groups);
 }
 static void Durable(string path,byte[] bytes){
  using(var f=new FileStream(path+".partial",FileMode.CreateNew,FileAccess.Write,FileShare.None)){f.Write(bytes);f.Flush(true);}
  File.Move(path+".partial",path,true);
 }
 static void Worker(string requestPath){
  var r=JsonSerializer.Deserialize<Request>(File.ReadAllBytes(requestPath))!;
  string declaration=File.ReadAllText(r.Declaration);
  Need(Source(declaration)==r.SourceSha,"WORKER_SOURCE");
  var groups=Read(r.Rows,r.StreamSha);
  var a=MxmPortfolioAccountReplay.RestoreReplay(File.ReadAllBytes(r.Capsule),r.TrustedSha,r.SourceSha,Settings(declaration),Roster(declaration));
  Need(a.HistoricalSource!.StreamSha256==r.StreamSha && a.HistoricalSource.Groups==r.Cut,"WORKER_CURSOR");
  Tail(a,groups.Skip(r.Cut));Durable(r.Output,a.CaptureReplay(r.SourceSha).Payload);
 }
 public static bool TryRun(string[] args){
  if(args.Length==2 && args[0]=="--historical-source-worker"){Worker(args[1]);return true;}
  if(args.SequenceEqual(new[]{"--historical-source-fixture"})){Fixture();return true;}
  if(args.Length!=4 || args[0]!="--w33-cursor-recovery")return false;
  string declarationPath=Path.GetFullPath(args[1]),rowsPath=Path.GetFullPath(args[2]);
  string declaration=File.ReadAllText(declarationPath),source=Source(declaration),stream=Hash(File.ReadAllBytes(rowsPath));
  Need(source=="4a5531b87136ae065acf7019d4601d209f27bab3df9489ce7fc13494ad4f3e42","ORIGINAL_PRIVATE_SOURCE");
  var groups=Read(rowsPath,stream);var direct=Fresh(declaration,stream);Tail(direct,groups);
  var expected=direct.CaptureReplay(source);
  // Include a cut after a missing opposite side, not only complete books.
  var cuts=new[]{1,groups.Length/2,groups.Length-1}.Distinct().OrderBy(x=>x).ToArray();
  string folder=Path.Combine(Path.GetTempPath(),"mxm-historical-source-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
  try {
   foreach(int cut in cuts){
    var first=Fresh(declaration,stream);Tail(first,groups.Take(cut));var capsule=first.CaptureReplay(source);
    string payload=Path.Combine(folder,"capsule"),output=Path.Combine(folder,"resumed"),requestPath=Path.Combine(folder,"request");
    Durable(payload,capsule.Payload);if(File.Exists(output))File.Delete(output);
    Durable(requestPath,JsonSerializer.SerializeToUtf8Bytes(new Request(declarationPath,rowsPath,payload,capsule.Sha256,source,stream,cut,output)));
    var start=new ProcessStartInfo("dotnet"){UseShellExecute=false,RedirectStandardOutput=true,RedirectStandardError=true};
    start.ArgumentList.Add(Assembly.GetEntryAssembly()!.Location);start.ArgumentList.Add("--historical-source-worker");start.ArgumentList.Add(requestPath);
    using var child=Process.Start(start)??throw new Exception("HISTORICAL_WORKER_START");
    if(!child.WaitForExit(60000)){child.Kill(true);throw new Exception("HISTORICAL_WORKER_TIMEOUT");}
    Need(child.ExitCode==0 && File.Exists(output) && File.ReadAllBytes(output).SequenceEqual(expected.Payload),"EVERY_STATE_BYTE_COLD_PARITY");
   }
  } finally {Directory.Delete(folder,true);}
  var h=direct.HistoricalSource!;var report=direct.Report();
  Need(h.Rows==2969 && direct.NextEventOrdinal==h.Groups && report.FinalCashEur==200m && report.AcceptedEntries==0,"FINAL_SINGLE_ACCOUNT");
  var receipt=new {schema="mxm.authentic-historical-account-cursor-recovery.v1",source_sha256=source,stream_sha256=stream,
   original_quote_events=h.Rows,atomic_groups=h.Groups,account_events=direct.NextEventOrdinal,cold_processes=cuts.Length,
   cut_group_ordinals=cuts,all_capsule_bytes_identical=true,source_books_and_side_clocks_recovered=true,
   ambiguous_groups=h.Books.Sum(b=>b.AmbiguousGroups),source_and_account_cursor_atomic=true,
   capsule_sha256=expected.Sha256,assembly_sha256=Hash(File.ReadAllBytes(Assembly.GetEntryAssembly()!.Location)),
   initial_capital_eur=report.InitialCapitalEur,final_cash_eur=report.FinalCashEur,entries=report.AcceptedEntries,
   decisions=0,broker_orders=0,broker_requests=0,new_economic_models=0,source_clock_is_historical_not_receipt_clock=true,
   historical_costs_proven=false,economic_edge_proven=false,native_cloud_recovery_proven=false};
  File.WriteAllText(args[3],JsonSerializer.Serialize(receipt)+"\n");Console.WriteLine("MXM_AUTHENTIC_SOURCE_CURSOR_RECOVERY "+JsonSerializer.Serialize(receipt));return true;
 }
 static void Fixture(){
  string source=new('a',64),stream=new('b',64);
  string declaration=JsonSerializer.Serialize(new{schema="mxm.declared-quote-assets.v1",source_sha256=source,
   symbols=new[]{new{symbol="AUDUSD",symbol_id=5,quote_asset="USD"}}});
  long t=1786442400000L;var settings=Settings(declaration);var names=new[]{"AUDUSD"};
  MxmPortfolioAccountReplay New(){var a=new MxmPortfolioAccountReplay(names,settings);a.BeginHistoricalSource(source,stream,t,t+600000,20);return a;}
  int checks=0;
  void Check(bool ok,string why){checks++;Need(ok,why);}
  void Reject(Action action,string why){bool rejected=false;try{action();}catch(ArgumentException){rejected=true;}Check(rejected,why);}
  MxmPortfolioAccountReplay Restore(MxmPortfolioAccountReplay a){var c=a.CaptureReplay(source);
   return MxmPortfolioAccountReplay.RestoreReplay(c.Payload,c.Sha256,source,settings,names);}
  var active=New();Check(Restore(active).HistoricalSource==active.HistoricalSource ||
   JsonSerializer.Serialize(Restore(active).HistoricalSource)==JsonSerializer.Serialize(active.HistoricalSource),"EMPTY_RESTORE");
  var g=new[]{new MxmHistoricalQuoteGroup(t,"AUDUSD",new long[]{100},Array.Empty<long>()),
   new MxmHistoricalQuoteGroup(t+1,"AUDUSD",Array.Empty<long>(),new long[]{102}),
   new MxmHistoricalQuoteGroup(t+2,"AUDUSD",new long[]{101,103},Array.Empty<long>()),
   new MxmHistoricalQuoteGroup(t+3,"AUDUSD",Array.Empty<long>(),new long[]{104}),
   new MxmHistoricalQuoteGroup(t+4,"AUDUSD",new long[]{102},Array.Empty<long>())};
  foreach(var group in g){
   var cold=Restore(active);active.ObserveHistoricalGroup(group,active.HistoricalSource!.Groups);
   cold.ObserveHistoricalGroup(group,cold.HistoricalSource!.Groups);
   Check(active.CaptureReplay(source).Payload.SequenceEqual(cold.CaptureReplay(source).Payload),"ALL_PREFIX_STATE_PARITY");
   if(group.SourceMs==t+2 || group.SourceMs==t+3)Check(active.HistoricalSource!.Books[0].Bid==null,"AMBIGUOUS_SIDE_NOT_HEALED");
  }
  Check(active.HistoricalSource!.Books[0].Bid==102 && active.HistoricalSource.Books[0].BidMs==t+4 &&
   active.HistoricalSource.Rows==6 && active.HistoricalSource.Groups==5 && active.NextEventOrdinal==5,"CAUSAL_SIDES_AND_CURSORS");
  Reject(()=>active.Continue(new MxmAccountFeed[]{new MxmBarClose(DateTimeOffset.FromUnixTimeMilliseconds(t+5).UtcDateTime,"AUDUSD",1m)},5),"NO_SOURCE_PROMOTION_TO_STRATEGY");
  Reject(()=>active.CaptureReplay(new string('c',64)),"NO_SOURCE_REBIND");
  foreach(var bad in new[]{g[0],g[4] with {SourceMs=t+5,Symbol="unknown"},g[4] with {SourceMs=t+600000},g[4] with {SourceMs=t+5,Bids=new long[]{0}}}){
   var a=Restore(active);Reject(()=>a.ObserveHistoricalGroup(bad,5),"BAD_GROUP");Reject(()=>a.CaptureReplay(source),"FAULTED_GROUP_CANNOT_CHECKPOINT");
  }
  var wrong=Restore(active);Reject(()=>wrong.ObserveHistoricalGroup(g[4] with {SourceMs=t+5},4),"DUPLICATE_CURSOR");
  var capsule=active.CaptureReplay(source);var tampered=JsonSerializer.Deserialize<System.Text.Json.Nodes.JsonObject>(capsule.Payload)!;
  tampered["HistoricalSource"]!["Rows"]=7;byte[] bytes=JsonSerializer.SerializeToUtf8Bytes(tampered);
  Reject(()=>MxmPortfolioAccountReplay.RestoreReplay(bytes,Hash(bytes),source,settings,names),"RECOMPUTED_HASH_CANNOT_HIDE_COUNTER_CORRUPTION");
  Check(active.Report().FinalCashEur==200m && active.Report().OpenPositions==0,"NO_FUNDING_OR_FEES_INVENTED");
  Console.WriteLine(JsonSerializer.Serialize(new{schema="mxm.historical-source-artificial-fixture.v1",checks,orders=0,new_economic_models=0}));
 }
}

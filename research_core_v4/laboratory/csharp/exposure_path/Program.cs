using System.Text.Json;
using System.Text.Json.Nodes;
using System.Security.Cryptography;
using Mxm.Replay;
using var data=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var output=new List<object>();
foreach(var scenario in data.RootElement.EnumerateArray()) {
 bool shared=scenario.TryGetProperty("shared",out var x) && x.GetBoolean();
 int maxAge=scenario.TryGetProperty("maxAge",out var age)?age.GetInt32():300;
 string policy=new('e',64),source=new('a',64);
 var symbols=scenario.GetProperty("symbols").EnumerateArray().Select(v=>v.GetString()!).ToArray();
 var settings=new MxmReplayParameters(StrategyMode.TrendOnly,.8m,4,0m,.5m,0m,
  MaxQuoteAgeSeconds:maxAge,UseSharedUsdConversion:shared,ExplicitPolicySha256:policy);
 var account=new MxmPortfolioAccountReplay(symbols,settings);account.Run(Array.Empty<MxmAccountFeed>());
 DateTime start=new(2026,1,5,0,0,0,DateTimeKind.Utc);
 decimal fxBid=1.1m,fxAsk=1.11m;
 var results=new List<object>();
 foreach(var a in scenario.GetProperty("actions").EnumerateArray()) {
  long stamp=a.GetProperty("t").GetInt64();DateTime now=start.AddMilliseconds(stamp);
  long Side(string name)=>a.TryGetProperty(name,out var v)?v.GetInt64():stamp;
  string op=a.GetProperty("op").GetString()!;
  string symbol=a.TryGetProperty("s",out var sym)?sym.GetString()!:symbols[0];
  try {
   if(op=="cold") {
    var saved=account.CaptureReplay(source);
    account=MxmPortfolioAccountReplay.RestoreReplay(saved.Payload,saved.Sha256,source,settings,symbols);
   }else if(op=="restore-aged") {
    var saved=account.CaptureReplay(source);var node=JsonNode.Parse(saved.Payload)!;
    node["LastFeed"]=now;byte[] altered=JsonSerializer.SerializeToUtf8Bytes(node);
    string digest=Convert.ToHexString(SHA256.HashData(altered)).ToLowerInvariant();
    account=MxmPortfolioAccountReplay.RestoreReplay(altered,digest,source,settings,symbols);
   }else if(op!="report") {
    MxmAccountFeed e=op switch {
     "quote"=>new MxmQuote(now,symbol,100m,101m,shared?1m/fxAsk:1m,1m,10m,.1m,0m,1m,
      shared?1m/fxBid:1m,BidSourceUtc:start.AddMilliseconds(Side("bt")),AskSourceUtc:start.AddMilliseconds(Side("at"))),
     "decision"=>new MxmExplicitDecision(now,symbol,a.GetProperty("seq").GetInt64(),a.GetProperty("d").GetInt32(),
      now.AddMilliseconds(1),now.AddMilliseconds(Math.Min(4000,maxAge*1000)),policy),
     "fx"=>new MxmUsdEurMark(now,start.AddMilliseconds(Side("bt")),start.AddMilliseconds(Side("at")),fxBid,fxAsk),
     "missing"=>new MxmInstrumentQuoteUnavailable(now,symbol,"ARTIFICIAL_UNAVAILABLE"),
     _=>throw new ArgumentException("UNKNOWN_ARTIFICIAL_ACTION")
    };
    account.Continue(new[]{e},account.NextEventOrdinal);
   }
   var r=account.Report();
   results.Add(new {status="OK",entries=r.AcceptedEntries,exits=r.ExecutedExits,open=r.OpenPositions,
    funding=r.InitialCapitalEur,hard21=r.Hard21Proven,broker_fills=r.BrokerFillsProven});
  }catch(ArgumentException) {
   bool blocked=false;try{account.Report();}catch(ArgumentException){blocked=true;}
   results.Add(new {status="HOLD",report_blocked=blocked});
  }
 }
 output.Add(results);
}
File.WriteAllText(args[1],JsonSerializer.Serialize(output));

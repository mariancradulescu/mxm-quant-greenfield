using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Research;
using Mxm.Replay;
var assumptions=new MxmUsdAccountAssumptions(1000m,50m,.1m,.00002m,1.2m,.0012m);
if(args.SequenceEqual(new[]{"--selftest"})){
 int checks=0;void Need(bool ok){checks++;if(!ok)throw new Exception("EUR_BOOK_FIXTURE_"+checks);}
 long t=1787554800000;AlignedUsdSnapshot S(long bid=110000,long ask=110000,long age=0)=>
  new(t,"FX_VALUATION_ONLY","GBP_MISSING",null,null,null,null,bid,t,ask,t-age,null,null);
 var q=(MxmQuote)MxmEurAccountInput.FromAlignment(S(),assumptions);
 Need(q.Bid==q.Ask && q.CommissionPerSideEur>0m && q.SlipPerSideQuote>0);
 Need(q.BidSourceUtc==q.Utc && q.AskSourceUtc==q.Utc && q.QuoteToEur==1m/q.Ask);
 Need(MxmEurAccountInput.FromAlignment(S(110000,110001,5000),assumptions) is MxmQuote);
 Need(MxmEurAccountInput.FromAlignment(S(110000,110001,5001),assumptions) is MxmInstrumentQuoteUnavailable);
 Need(MxmEurAccountInput.FromAlignment(S(110001,110000),assumptions) is MxmInstrumentQuoteUnavailable);
 void Bad(Action a){bool bad=false;try{a();}catch(ArgumentException){bad=true;}Need(bad);}
 Bad(()=>MxmEurAccountInput.FromAlignment(S() with {FxAskMs=t+1},assumptions));
 Bad(()=>MxmEurAccountInput.FromAlignment(S() with {GbpAskRaw=100},assumptions));
 Bad(()=>MxmEurAccountInput.FromAlignment(S(),assumptions with {Units=0}));
 var settings=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,0m,.02m,.2m,ExplicitPolicySha256:new string('c',64));
 var utc=q.Utc;var d=new MxmExplicitDecision(utc,"EURUSD",1,1,utc.AddMilliseconds(250),utc.AddSeconds(5),new string('c',64));
 var a=new MxmPortfolioAccountReplay(new[]{"EURUSD"},settings);
 var report=a.Run(new MxmAccountFeed[]{q,d,q with {Utc=utc.AddMilliseconds(250)}});
 Need(report.AcceptedEntries==1 && report.OpenPositions==1 && report.Ledger[0].CommissionEur>0);
 Bad(()=>a.Continue(new[]{new MxmInstrumentQuoteUnavailable(utc.AddSeconds(1),"EURUSD","SOURCE_AGE_LIMIT")},3));
 Bad(()=>a.Report());
 Console.WriteLine(JsonSerializer.Serialize(new{checks,classification="ARTIFICIAL_ONLY",market_account_replay=false,orders=0}));return;
}
if(args.Length!=3 || !long.TryParse(args[1],out long target) || target<0)throw new ArgumentException("EUR_BOOK_PATH_TARGET_OUTPUT");
long groups=0;string? targetCode=null;var counts=new SortedDictionary<string,long>();
using var digest=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
static IEnumerable<QuoteRow> Rows(string path){
 foreach(var line in File.ReadLines(path)){
  if(line.Length>512)throw new InvalidDataException("EUR_BOOK_ROW_BOUND");using var d=JsonDocument.Parse(line);var e=d.RootElement;
  if(e.EnumerateObject().Count()!=3)throw new InvalidDataException("EUR_BOOK_ROW_SCHEMA");
  yield return new(e.GetProperty("t").GetInt64(),"EURUSD",e.GetProperty("side").GetString()??"",e.GetProperty("raw").GetInt64());
 }
}
string N(long? value)=>value?.ToString(CultureInfo.InvariantCulture)??"-";
var result=MxmUsdPairAlignment.Run(Rows(args[0]),observer:s=>{
 groups++;string code=MxmEurAccountInput.SourceCode(s);var feed=MxmEurAccountInput.FromAlignment(s,assumptions);
 if(code.StartsWith("OBSERVED_",StringComparison.Ordinal) != (feed is MxmQuote))throw new InvalidDataException("EUR_TYPED_ACCOUNT_SOURCE_DISAGREES");
 counts[code]=counts.GetValueOrDefault(code)+1;if(groups==target)targetCode=code;
 digest.AppendData(Encoding.ASCII.GetBytes($"{s.T}|{code}|{N(s.FxBidRaw)}|{N(s.FxBidMs)}|{N(s.FxAskRaw)}|{N(s.FxAskMs)}\n"));
});
if(target>groups)throw new InvalidDataException("EUR_TARGET_OUTSIDE_SOURCE");
string Hash(byte[] b)=>Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
File.WriteAllText(args[2],JsonSerializer.Serialize(new{schema="mxm.eur-account-source-reception.v1",rows=result.Rows,groups,codes=counts,
 source_sha256=Hash(File.ReadAllBytes(args[0])),every_group_sha256=Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant(),
 target_code=targetCode,market_account_replay=false,orders=0,historical_fills_proven=false}));

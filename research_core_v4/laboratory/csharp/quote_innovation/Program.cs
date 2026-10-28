using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
using Mxm.Research;
string Hash(byte[] x)=>Convert.ToHexString(SHA256.HashData(x)).ToLowerInvariant();
string F(decimal x)=>decimal.Round(x,8,MidpointRounding.AwayFromZero).ToString("F8",CultureInfo.InvariantCulture);
if(args.Length==2 && args[0]=="--kernel") {
 using var doc=JsonDocument.Parse(File.ReadAllBytes(args[1]));var k=new MxmQuoteInnovationKernel();var output=new List<object?>();
 foreach(var e in doc.RootElement.EnumerateArray()) {
  if(e.TryGetProperty("cold",out _))k=new(JsonSerializer.Deserialize<MxmInnovationState>(JsonSerializer.Serialize(k.Capture())));
  else output.Add(k.Completed(e.GetProperty("t").GetInt64(),e.GetProperty("x").GetDecimal(),e.GetProperty("mid").GetDecimal()));
 }
 Console.WriteLine(JsonSerializer.Serialize(output));return;
}
if(args.Length<4)throw new ArgumentException("INNOVATION_ARGUMENTS");
string outputPath=args[0],policy=args[1],context=args[2];string[] paths=args.Skip(3).ToArray();
var settings=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,120m,.01m,.2m,
 MaxQuoteAgeSeconds:5,ExplicitPolicySha256:policy,NativeSizingScenarioSha256:policy,RequireObservedExposurePath:true);
var account=new MxmPortfolioAccountReplay(new[]{"EURUSD"},settings);account.Run(Array.Empty<MxmAccountFeed>());
var kernel=new MxmQuoteInnovationKernel();string? fault=null;long sequence=0,rows=0,groups=0,predictions=0,signals=0,invalid=0;
long nextAllowed=0,flatDue=0;var audits=new List<object>();var summaries=new List<object>();
using var predictionsHash=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
using var decisionsHash=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
void Feed(MxmAccountFeed e) {
 if(fault!=null)return;
 try{account.Continue(new[]{e},account.NextEventOrdinal);}catch(ArgumentException ex){fault=ex.Message;}
}
void Decision(long t,int desired){
 sequence++;var utc=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
 var d=new MxmExplicitDecision(utc,"EURUSD",sequence,desired,utc.AddMilliseconds(250),utc.AddSeconds(5),policy);
 decisionsHash.AppendData(Encoding.ASCII.GetBytes($"{t}|{sequence}|{desired}\n"));Feed(d);
}
foreach(string path in paths){
 // Restoring the existing ACCOUNT and the new LEARNER does not fund again.
 // This machine-side capsule is not evidence of durable Cloud storage.
 if(fault==null){var c=account.CaptureReplay(context);account=MxmPortfolioAccountReplay.RestoreReplay(c.Payload,c.Sha256,context,settings,new[]{"EURUSD"});}
 kernel=new(JsonSerializer.Deserialize<MxmInnovationState>(JsonSerializer.Serialize(kernel.Capture())));
 long? bid=null,ask=null,bt=null,at=null;long bucket=-1,minuteSigned=0,minuteChanges=0;decimal minuteMid=0;
 long stamp=-1;var bids=new HashSet<long>();var asks=new HashSet<long>();
 long localPredictions=0,localSignals=0,localInvalid=0,localRows=0;var forecasts=new List<object>();
 void Group(){
  groups++;long current=stamp/60000*60000;
  var utc=DateTimeOffset.FromUnixTimeMilliseconds(stamp).UtcDateTime;
  // The prior bucket becomes available only at the first actual next quote.
  MxmInnovationForecast? forecast=null;
  if(bucket>=0 && current!=bucket && minuteMid>0){
   forecast=kernel.Completed(bucket,minuteChanges==0?0m:(decimal)minuteSigned/minuteChanges,minuteMid);
   if(forecast!=null){predictions++;localPredictions++;
    predictionsHash.AppendData(Encoding.ASCII.GetBytes($"{stamp}|{forecast.Bucket}|{forecast.Samples}|{F(forecast.X)}|{F(forecast.PredictionBps)}\n"));
    forecasts.Add(new{available=stamp,bucket=forecast.Bucket,samples=forecast.Samples,x=F(forecast.X),prediction=F(forecast.PredictionBps),mid=F(minuteMid)});
   }
  }
  if(current!=bucket){bucket=current;minuteSigned=minuteChanges=0;minuteMid=0;}
  void Update(HashSet<long> values,ref long? value,ref long? time){
   if(values.Count==0)return;
   long? v=values.Count==1?values.Single():null;
   if(v.HasValue && value.HasValue && v.Value!=value.Value){minuteSigned+=Math.Sign(v.Value-value.Value);minuteChanges++;}
   value=v;time=stamp;
  }
  Update(bids,ref bid,ref bt);Update(asks,ref ask,ref at);
  if(bid.HasValue && ask.HasValue && ask>=bid)minuteMid=(bid.Value+ask.Value)/200000m;
  bool healthy=bid.HasValue && ask.HasValue && ask>bid && stamp-bt<=5000 && stamp-at<=5000;
  if(!healthy){invalid++;localInvalid++;Feed(new MxmInstrumentQuoteUnavailable(utc,"EURUSD","STRICT_ORIGINAL_SIDE_OBSERVATION_CONTRACT"));return;}
  decimal b=bid!.Value/100000m,a=ask!.Value/100000m;
  var costs=new MxmEurUsdCapturedCosts(100000,100000,100000,10000000,2,300000000,0,"USD");
  Feed(new MxmQuote(utc,"EURUSD",b,a,1m/a,1000m,33.33m,0m,.00002m,1.2m,1m/b,costs,.0012m,
   DateTimeOffset.FromUnixTimeMilliseconds(bt!.Value).UtcDateTime,DateTimeOffset.FromUnixTimeMilliseconds(at!.Value).UtcDateTime,
   policy,1000m,1000m,1000m));
  if(flatDue>0 && stamp>=flatDue){Decision(stamp,0);flatDue=0;nextAllowed=Math.Max(nextAllowed,stamp+5000);return;}
  if(forecast==null || current!=forecast.Bucket+60000 || stamp<nextAllowed || flatDue>0)return;
  // Declared intraday scenario: no overnight financing is invented. A position
  // unpriceable before flattening permanently faults the SAME account.
  if(utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday || utc.Hour<7 || utc.Hour>=15)return;
  decimal hurdle=10000m*((a-b)+.00004m+.00006m)/((a+b)/2m);
  int direction=forecast.PredictionBps>hurdle?1:forecast.PredictionBps< -hurdle?-1:0;
  if(direction==0)return;
  signals++;localSignals++;audits.Add(new{t=stamp,direction,prediction=F(forecast.PredictionBps),hurdle=F(hurdle)});
  Decision(stamp,direction);flatDue=stamp+60000;nextAllowed=stamp+65000;
 }
 foreach(string line in File.ReadLines(path)){
  using var j=JsonDocument.Parse(line);var e=j.RootElement;
  if(e.EnumerateObject().Count()!=3)throw new ArgumentException("INNOVATION_SOURCE_SCHEMA");
  long t=e.GetProperty("t").GetInt64(),v=e.GetProperty("raw").GetInt64();string side=e.GetProperty("side").GetString()!;
  if(t<stamp || v<=0 || side is not ("bid" or "ask"))throw new ArgumentException("INNOVATION_SOURCE_CHRONOLOGY");
  if(stamp>=0 && t!=stamp){Group();bids.Clear();asks.Clear();}
  stamp=t;(side=="bid"?bids:asks).Add(v);rows++;localRows++;
 }
 if(stamp>=0)Group();
 // Never close a partial final minute with an invented next timestamp.
 summaries.Add(new{input_sha256=Hash(File.ReadAllBytes(path)),rows=localRows,predictions=localPredictions,signals=localSignals,invalid=localInvalid,forecasts});
}
MxmPortfolioAccountReport? report=null;if(fault==null)report=account.Report();
var result=new{schema="mxm.quote-innovation-development.v1",policy,context,rows,groups,predictions,signals,invalid,
 prediction_sha256=Convert.ToHexString(predictionsHash.GetHashAndReset()).ToLowerInvariant(),
 decision_sha256=Convert.ToHexString(decisionsHash.GetHashAndReset()).ToLowerInvariant(),summaries,audits,account=report,fault,
 learned_samples=kernel.Capture().Samples.Length,initial_funding_count=1,initial_capital_eur=200,
 economic_edge_proven=false,hard21_proven=false,historical_costs_proven=false,broker_fills_proven=false,orders=0};
File.WriteAllText(outputPath,JsonSerializer.Serialize(result));

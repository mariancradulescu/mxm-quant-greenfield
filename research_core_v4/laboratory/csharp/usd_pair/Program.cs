using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Research;
static IEnumerable<QuoteRow> Read(string path,string symbol){
 long last=-1;
 foreach(string line in File.ReadLines(path)){
  using var doc=JsonDocument.Parse(line);var r=doc.RootElement;
  long t=r.GetProperty("t").GetInt64();
  if(t<last)throw new InvalidDataException("PAIR_SOURCE_TIME_ORDER");last=t;
  yield return new(t,symbol,r.GetProperty("side").GetString()??"",r.GetProperty("raw").GetInt64());
 }
}
static IEnumerable<QuoteRow> Merge(IEnumerable<QuoteRow> left,IEnumerable<QuoteRow> right){
 using var l=left.GetEnumerator();using var r=right.GetEnumerator();bool a=l.MoveNext(),b=r.MoveNext();
 while(a||b){
  if(a&&(!b||l.Current.T<=r.Current.T)){yield return l.Current;a=l.MoveNext();}
  else{yield return r.Current;b=r.MoveNext();}
 }
}
if(args.Length!=3)throw new ArgumentException("PAIR_EUR_FILE_GBP_FILE_REPORT_REQUIRED");
long observedRouting=0,observedValuation=0;
var result=MxmUsdPairAlignment.Run(Merge(Read(args[0],"EURUSD"),Read(args[1],"GBPUSD")),observer:s=>{
 if(s.Purpose=="GBP_QUOTE_GROUP"){
  observedRouting++;
  if(s.Code=="READY_STRICT_PRIOR_FX" && !(s.FxBidMs<s.T && s.FxAskMs<s.T && s.Positive100UsdEur>0 && s.Negative100UsdEur<0))
   throw new InvalidDataException("PAIR_TYPED_ROUTING_CONTRACT");
 }else if(s.Purpose=="FX_VALUATION_ONLY")observedValuation++;
 else throw new InvalidDataException("PAIR_UNKNOWN_PURPOSE");
});
string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
var receipt=new {schema="mxm.csharp.usd-pair-source-alignment.v1",eur_file_sha256=Hash(args[0]),gbp_file_sha256=Hash(args[1]),
 max_age_ms=MxmUsdPairAlignment.MaxAgeMs,result,typed_routing_snapshots=observedRouting,typed_valuation_snapshots=observedValuation,broker_orders=0,strategy_trials=0,economic_outcomes=0,
 economic_edge_proven=false,hard21_proven=false,historical_arrival_order_proven=false,historical_fills_proven=false,
 account_replay_executed=false,source_timestamps_not_arrivals=true};
File.WriteAllText(args[2],JsonSerializer.Serialize(receipt,new JsonSerializerOptions{WriteIndented=true})+"\n");

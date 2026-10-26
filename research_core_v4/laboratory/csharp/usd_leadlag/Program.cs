using System.Security.Cryptography;
using System.Text.Json;
using Mxm.Research;
static IEnumerable<QuoteRow> Read(string path,string symbol){long last=-1;foreach(var line in File.ReadLines(path)){
 using var doc=JsonDocument.Parse(line);var r=doc.RootElement;long t=r.GetProperty("t").GetInt64();
 if(t<last)throw new InvalidDataException("SOURCE_TIME_ORDER");last=t;
 yield return new(t,symbol,r.GetProperty("side").GetString()??"",r.GetProperty("raw").GetInt64());}}
static IEnumerable<QuoteRow> Merge(IEnumerable<QuoteRow> left,IEnumerable<QuoteRow> right){using var l=left.GetEnumerator();using var r=right.GetEnumerator();bool a=l.MoveNext(),b=r.MoveNext();
 while(a||b){if(a&&(!b||l.Current.T<=r.Current.T)){yield return l.Current;a=l.MoveNext();}else{yield return r.Current;b=r.MoveNext();}}}
if(args.Length!=3)throw new ArgumentException("EXACT_EUR_GBP_OUTPUT_ARGUMENTS");
var model=new MxmUsdLeadLag();var source=MxmUsdPairAlignment.Run(Merge(Read(args[0],"EURUSD"),Read(args[1],"GBPUSD")),observer:model.Observe);
string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
var result=new{schema="mxm.csharp.usd-leadlag-development.v1",eur_sha256=Hash(args[0]),gbp_sha256=Hash(args[1]),source,result=model.Finish(),
 broker_orders=0,capital_replay=false,hard21_proven=false,edge_confirmed=false,historical_costs_proven=false,native_fills_proven=false};
File.WriteAllText(args[2],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true})+"\n");

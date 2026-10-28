using System.Globalization;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
static class PeerResidual {
 sealed record Row([property:JsonPropertyName("time_utc")]string Time,[property:JsonPropertyName("open")]decimal Open,
  [property:JsonPropertyName("high")]decimal High,[property:JsonPropertyName("low")]decimal Low,[property:JsonPropertyName("close")]decimal Close);
 sealed record Packet(int Ordinal,int Group,bool Eligible,long[] EligibleTimes,Row[] Rows);
 sealed record Feature(long T,int Ordinal,int Group,bool Eligible,long Move);
 sealed record Decision(long T,int N,int? Ordinal,int? Group,int? Direction,long? Residual2,long? Entry,long? Exit,string Status,long? GrossUnits);
 static readonly JsonSerializerOptions Options=new(){PropertyNameCaseInsensitive=true,NumberHandling=JsonNumberHandling.AllowReadingFromString};
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("PEER_RESIDUAL_"+why);}
 static long Sec(string t)=>DateTimeOffset.Parse(t,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind).ToUnixTimeSeconds();
 static readonly long First=Sec("2026-08-20T00:00:00Z"),Eval=Sec("2026-08-27T00:00:00Z"),End=Sec("2026-09-17T00:00:00Z");
 static (BigInteger N,BigInteger D) Ratio(decimal x){var b=decimal.GetBits(x);BigInteger n=(uint)b[0]+((BigInteger)(uint)b[1]<<32)+((BigInteger)(uint)b[2]<<64);if(b[3]<0)n=-n;return(n,BigInteger.Pow(10,(b[3]>>16)&255));}
 static long Move(decimal a,decimal b){var x=Ratio(a);var y=Ratio(b);BigInteger n=y.N*x.D-x.N*y.D,d=x.N*y.D;
  Need(d>0,"POSITIVE_PRICE");BigInteger q=BigInteger.DivRem(BigInteger.Abs(n)*1000000000000L,d,out var r);if(r*2>=d)q++;
  Need(q<=long.MaxValue,"MOVE_RANGE");return n<0?-(long)q:(long)q;
 }
 public static void Main(string[] args){
  Need(args.Length==2,"ARGUMENTS");var data=new Dictionary<int,Dictionary<long,(decimal Open,decimal Close)>>();
  var features=new SortedDictionary<long,List<Feature>>();long rows=0;var signature=new StringBuilder();
  foreach(string line in File.ReadLines(args[0])){
   var p=JsonSerializer.Deserialize<Packet>(line,Options)!;Need(p.Ordinal is >=1 and <=1576 && p.Group>=0 && p.Rows!=null && p.EligibleTimes!=null && !data.ContainsKey(p.Ordinal),"IDENTITY");
   var map=new Dictionary<long,(decimal Open,decimal Close)>();var eligibleTimes=new HashSet<long>(p.EligibleTimes!);long previous=-1;
   foreach(var r in p.Rows!){long t=Sec(r.Time);Need(r.Time.EndsWith("Z",StringComparison.Ordinal) && t>=First && t<End && t%300==0 && t>previous && r.Low>0 && r.High>=r.Low && r.Open>=r.Low && r.Open<=r.High && r.Close>=r.Low && r.Close<=r.High,"SOURCE_FENCE_CHRONOLOGY_OHLC");map.Add(t,(r.Open,r.Close));previous=t;rows++;}
   data.Add(p.Ordinal,map);
   foreach(long d in map.Keys.Select(t=>t+300).Where(t=>t%3600==0 && t<End).OrderBy(t=>t)){
    if(!Enumerable.Range(1,12).All(k=>map.ContainsKey(d-k*300)))continue;
    var f=new Feature(d,p.Ordinal,p.Group,p.Eligible && eligibleTimes.Contains(d),Move(map[d-3600].Open,map[d-300].Close));
    if(!features.ContainsKey(d))features[d]=new();features[d].Add(f);
   }
  }
  foreach(var pair in features)foreach(var f in pair.Value.OrderBy(f=>f.Ordinal))signature.Append(f.T).Append(',').Append(f.Ordinal).Append(',').Append(f.Group).Append(',').Append(f.Eligible?1:0).Append(',').Append(f.Move).Append('\n');
  var ledger=new List<Decision>();
  for(long d=Eval;d<End;d+=3600){
   int n=0;Feature? best=null;long bestResidual=0,bestAbs=-1;
   if(features.TryGetValue(d,out var at))foreach(var group in at.GroupBy(f=>f.Group)){
    var ordered=group.OrderBy(f=>f.Move).ThenBy(f=>f.Ordinal).ToArray();if(ordered.Length<11)continue;
    int peerCount=ordered.Length-1,lo=(peerCount-1)/2,hi=peerCount/2;
    for(int i=0;i<ordered.Length;i++){
     var f=ordered[i];if(!f.Eligible)continue;n++;
     long median2=checked(ordered[lo+(lo>=i?1:0)].Move+ordered[hi+(hi>=i?1:0)].Move);
     long residual=checked(2*f.Move-median2),score=Math.Abs(residual);
     if(score>bestAbs || score==bestAbs && f.Ordinal<best!.Ordinal){best=f;bestResidual=residual;bestAbs=score;}
    }
   }
   if(best==null || bestAbs<4000000000L){ledger.Add(new(d,n,null,null,null,null,null,null,"NO_SIGNAL",null));continue;}
   int direction=bestResidual>0?-1:1;long entry=d+300,exit=d+3300;var prices=data[best.Ordinal];
   bool complete=Enumerable.Range(0,11).All(k=>prices.ContainsKey(entry+k*300));
   ledger.Add(new(d,n,best.Ordinal,best.Group,direction,bestResidual,entry,exit,complete?"COMPLETE":"CENSORED",
    complete?checked(direction*Move(prices[entry].Open,prices[exit].Open)):null));
  }
  string hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signature.ToString()))).ToLowerInvariant();
  File.WriteAllText(args[1],JsonSerializer.Serialize(new {Packets=data.Count,Rows=rows,FeatureSha256=hash,Ledger=ledger}));
 }
}

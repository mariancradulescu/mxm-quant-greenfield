using System.Globalization;
using System.Security.Cryptography;
using System.Text;
namespace Mxm.Research;
public sealed record QuoteRow(long T,string Symbol,string Side,long Raw);
public sealed record AlignedUsdSnapshot(long T,string Purpose,string Code,
 long? GbpBidRaw,long? GbpBidMs,long? GbpAskRaw,long? GbpAskMs,
 long? FxBidRaw,long? FxBidMs,long? FxAskRaw,long? FxAskMs,
 decimal? Positive100UsdEur,decimal? Negative100UsdEur);
public sealed record PairResult(long Rows,long Groups,Dictionary<string,long> SourceRows,
 Dictionary<string,long> Routing,Dictionary<string,long> Conflicts,Dictionary<string,long> Crossed,
 long FxOnlyMarkGroups,string StateSha256,string RoutingSha256,string MarkSha256);
// Source-time alignment only. A quote timestamp is not a historical arrival or fill.
// All updates at one global ms are atomic; GBP routing uses EUR strictly BEFORE it.
public static class MxmUsdPairAlignment {
 public const long MaxAgeMs=5000;
 sealed record Side(long? Raw=null,long? T=null,bool Conflict=false);
 sealed record Book(Side Bid,Side Ask);
 static Book Empty()=>new(new(),new());
 static string N(long? n)=>n?.ToString(CultureInfo.InvariantCulture)??"-";
 static string Canon(Book b)=>$"{N(b.Bid.Raw)},{N(b.Bid.T)},{(b.Bid.Conflict?1:0)},{N(b.Ask.Raw)},{N(b.Ask.T)},{(b.Ask.Conflict?1:0)}";
 static void Need(bool ok,string code){if(!ok)throw new InvalidDataException("PAIR_"+code);}
 static string Check(Book b,long now,string label){
  if(b.Bid.Conflict || b.Ask.Conflict)return label+"_CONFLICT";
  if(!b.Bid.Raw.HasValue || !b.Ask.Raw.HasValue)return label+"_MISSING";
  if(b.Ask.Raw.Value<b.Bid.Raw.Value)return label+"_CROSSED";
  if(now-b.Bid.T!.Value>MaxAgeMs || now-b.Ask.T!.Value>MaxAgeMs)return label+"_STALE";
  return "";
 }
 static string Convert(Book fx)=>decimal.Round(10000000m/fx.Ask.Raw!.Value,8,MidpointRounding.AwayFromZero).ToString("F8",CultureInfo.InvariantCulture)+","+
  decimal.Round(-10000000m/fx.Bid.Raw!.Value,8,MidpointRounding.AwayFromZero).ToString("F8",CultureInfo.InvariantCulture);
 public static PairResult Run(IEnumerable<QuoteRow> input,Action<string>? routeTrace=null,Action<AlignedUsdSnapshot>? observer=null){
  var books=new Dictionary<string,Book>{{"EURUSD",Empty()},{"GBPUSD",Empty()}};
  var counts=new Dictionary<string,long>{{"EURUSD",0},{"GBPUSD",0}};
  var conflicts=new Dictionary<string,long>{{"EURUSD",0},{"GBPUSD",0}};
  var crossed=new Dictionary<string,long>{{"EURUSD",0},{"GBPUSD",0}};
  var routing=new Dictionary<string,long>();long rows=0,groups=0,fxOnly=0;long? last=null;
  using var states=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
  using var routes=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
  using var marks=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
  void Hash(IncrementalHash hash,string line)=>hash.AppendData(Encoding.UTF8.GetBytes(line+"\n"));
  void Emit(long t,string purpose,string code,Book gbp,Book fx,bool valid){
   observer?.Invoke(new(t,purpose,code,gbp.Bid.Raw,gbp.Bid.T,gbp.Ask.Raw,gbp.Ask.T,
    fx.Bid.Raw,fx.Bid.T,fx.Ask.Raw,fx.Ask.T,
    valid?decimal.Round(10000000m/fx.Ask.Raw!.Value,8,MidpointRounding.AwayFromZero):null,
    valid?decimal.Round(-10000000m/fx.Bid.Raw!.Value,8,MidpointRounding.AwayFromZero):null));
  }
  using var it=input.GetEnumerator();bool available=it.MoveNext();
  while(available){
   long stamp=it.Current.T;Need(stamp>=0 && (!last.HasValue || stamp>last),"TIME_ORDER");
   // Preserve the FX state from strictly earlier timestamps, not an arbitrary
   // serialisation order among simultaneous symbols.
   var previousFx=books["EURUSD"];
   var batch=new Dictionary<(string,string),HashSet<long>>();var touched=new HashSet<string>();
   do{
    var r=it.Current;Need(r.T==stamp && books.ContainsKey(r.Symbol) && (r.Side=="bid" || r.Side=="ask") && r.Raw>0,"ROW");
    rows++;counts[r.Symbol]++;touched.Add(r.Symbol);
    var key=(r.Symbol,r.Side);if(!batch.TryGetValue(key,out var values))batch[key]=values=new();values.Add(r.Raw);
    available=it.MoveNext();
   }while(available && it.Current.T==stamp);
   foreach(var symbol in touched){
    var prior=books[symbol];
    Side Apply(string side,Side old){
     if(!batch.TryGetValue((symbol,side),out var values))return old;
     return values.Count==1?new(values.Single(),stamp):new(null,stamp,true);
    }
    var next=new Book(Apply("bid",prior.Bid),Apply("ask",prior.Ask));books[symbol]=next;
    if(batch.Any(x=>x.Key.Item1==symbol && x.Value.Count>1))conflicts[symbol]++;
    if(next.Bid.Raw.HasValue && next.Ask.Raw.HasValue && next.Ask.Raw<next.Bid.Raw)crossed[symbol]++;
   }
   Hash(states,$"{stamp}|{Canon(books["EURUSD"])}|{Canon(books["GBPUSD"])}");
   if(touched.Contains("GBPUSD")){
    var gbp=books["GBPUSD"];string code=Check(gbp,stamp,"GBP");if(code=="")code=Check(previousFx,stamp,"FX");if(code=="")code="READY_STRICT_PRIOR_FX";
    routing[code]=routing.GetValueOrDefault(code)+1;
    if(code=="READY_STRICT_PRIOR_FX")Need(previousFx.Bid.T<stamp && previousFx.Ask.T<stamp,"FX_NOT_STRICT_PRIOR");
    string line=$"{stamp}|{code}|{Canon(gbp)}|{Canon(previousFx)}|"+(code=="READY_STRICT_PRIOR_FX"?Convert(previousFx):"-");
    Hash(routes,line);routeTrace?.Invoke(line);
    Emit(stamp,"GBP_QUOTE_GROUP",code,gbp,previousFx,code=="READY_STRICT_PRIOR_FX");
   }
   if(touched.Contains("EURUSD")){
    if(!touched.Contains("GBPUSD"))fxOnly++;
    string code=Check(books["GBPUSD"],stamp,"GBP");if(code=="")code=Check(books["EURUSD"],stamp,"FX");if(code=="")code="VALUATION_ONLY";
    Hash(marks,$"{stamp}|{code}|{Canon(books["GBPUSD"])}|{Canon(books["EURUSD"])}|"+(code=="VALUATION_ONLY"?Convert(books["EURUSD"]):"-"));
    Emit(stamp,"FX_VALUATION_ONLY",code,books["GBPUSD"],books["EURUSD"],code=="VALUATION_ONLY");
   }
   last=stamp;groups++;
  }
  string Finish(IncrementalHash h)=>System.Convert.ToHexString(h.GetHashAndReset()).ToLowerInvariant();
  return new(rows,groups,counts,routing,conflicts,crossed,fxOnly,Finish(states),Finish(routes),Finish(marks));
 }
}

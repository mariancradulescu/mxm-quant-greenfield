using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
namespace Mxm.Replay {
public sealed record MxmFxInstrument(string Source,string BaseAsset,string QuoteAsset);
public sealed record MxmFxLeg(string Source,bool Reverse);
public sealed record MxmObservedFxBook(string Source,decimal? Bid,decimal? Ask,MxmBookObservationView Observation);
public sealed record MxmObservedCostFxEstimate(decimal Rate,MxmFxLeg[] Path,long MaximumSideAgeMs) {
 public string Classification=>"OBSERVED_UPWARD_ROUNDED_COST_SIDE_ESTIMATE_NOT_BROKER_CHARGE";
 public bool ExecutabilityProven=>false;
 public bool SourceTimestampCertified=>false;
}
/// <summary>Explicit metadata topology, then observed BID/ASK cost-side pricing.
/// No price-dependent path selection, implicit AssetConverter or stale fallback.
/// A local callback observation is not a firm quote or source timestamp proof.</summary>
public sealed class MxmObservedCostFx {
 public const long MaximumSideAgeMs=5000;
 // Native backtest events must age on simulated time, independent of process
 // speed. This is observation-time bookkeeping, never a source event stamp.
 public static long ObservationClock(bool simulation,long processMonotonicMs,DateTime simulatedUtc) {
  if(!simulation) {
   if(processMonotonicMs<0)throw new ArgumentException("FX_INVALID_PROCESS_CLOCK");
   return processMonotonicMs;
  }
  if(simulatedUtc.Kind!=DateTimeKind.Utc || simulatedUtc==default)
   throw new ArgumentException("FX_INVALID_SIMULATION_CLOCK");
  long stamp=new DateTimeOffset(simulatedUtc).ToUnixTimeMilliseconds();
  if(stamp<0)throw new ArgumentException("FX_INVALID_SIMULATION_CLOCK");
  return stamp;
 }
 readonly MxmFxInstrument[] instruments;
 readonly Dictionary<(string,string),MxmFxLeg[]> routes=new();
 public MxmObservedCostFx(IEnumerable<MxmFxInstrument> declared) {
  if(declared==null)throw new ArgumentException("FX_MISSING_CATALOGUE");
  instruments=declared.ToArray();
  bool Name(string s)=>!string.IsNullOrWhiteSpace(s) && s.Length<=128;
  if(instruments.Length>32 || instruments.Any(x=>x==null || !Name(x.Source) || !Name(x.BaseAsset) || !Name(x.QuoteAsset) || x.BaseAsset==x.QuoteAsset) ||
    instruments.Select(x=>x.Source).Distinct(StringComparer.Ordinal).Count()!=instruments.Length)
   throw new ArgumentException("FX_INVALID_EXPLICIT_METADATA");
  instruments=instruments.OrderBy(x=>x.Source,StringComparer.Ordinal).ToArray();
 }
 public MxmFxLeg[] Route(string from,string to) {
  if(string.IsNullOrWhiteSpace(from)||string.IsNullOrWhiteSpace(to))throw new ArgumentException("FX_MISSING_ASSET");
  if(from==to)return Array.Empty<MxmFxLeg>();
  if(routes.TryGetValue((from,to),out var cached))return cached.ToArray();
  for(int depth=1;depth<=3;depth++) {
   var found=new List<MxmFxLeg[]>();
   void Walk(string asset,List<MxmFxLeg> path,HashSet<string> visited) {
    if(found.Count>1)return;
    if(path.Count==depth){if(asset==to)found.Add(path.ToArray());return;}
    foreach(var i in instruments) {
     bool reverse=i.QuoteAsset==asset;
     if(!reverse && i.BaseAsset!=asset)continue;
     string next=reverse?i.BaseAsset:i.QuoteAsset;
     if(visited.Contains(next))continue;
     visited.Add(next);path.Add(new(i.Source,reverse));Walk(next,path,visited);
     path.RemoveAt(path.Count-1);visited.Remove(next);
    }
   }
   Walk(from,new(),new(StringComparer.Ordinal){from});
   if(found.Count>1)throw new ArgumentException("FX_AMBIGUOUS_SHORTEST_METADATA_PATH");
   if(found.Count==1){routes[(from,to)]=found[0];return found[0].ToArray();}
  }
  throw new ArgumentException("FX_NO_DECLARED_PATH_WITHIN_THREE_LEGS");
 }
 // Decimal division/multiplication round to the 96-bit decimal domain BEFORE
 // Round(...,18,ToPositiveInfinity). A tiny positive remainder can disappear
 // there, violating the advertised debit-side upper rounding. Preserve exact
 // integer ratios until a single ceiling to the representable decimal grid.
 static (BigInteger Coefficient,int Scale) Parts(decimal value) {
  if(value<=0m)throw new ArgumentException("FX_NONPOSITIVE_COST_RATE");
  var bits=decimal.GetBits(value);
  return ((BigInteger)(uint)bits[0]+((BigInteger)(uint)bits[1]<<32)+
   ((BigInteger)(uint)bits[2]<<64),(bits[3]>>16)&255);
 }
 static decimal CeilingRatio(BigInteger numerator,BigInteger denominator) {
  if(numerator<=0 || denominator<=0)throw new ArgumentException("FX_NONPOSITIVE_COST_RATE");
  int scale=18;
  BigInteger coefficient=BigInteger.DivRem(numerator*BigInteger.Pow(10,scale),denominator,out var remainder);
  if(remainder>0)coefficient++;
  BigInteger maximum=(BigInteger.One<<96)-1;
  // Large valid decimals have fewer than18fractional places. Coarsen upward
  // only as far as required to fit, never truncate, underflow or return zero.
  while(coefficient>maximum && scale>0) {
   coefficient=BigInteger.DivRem(coefficient,10,out remainder);
   if(remainder>0)coefficient++;
   scale--;
  }
  if(coefficient>maximum)throw new OverflowException();
  return new decimal((int)(uint)(coefficient&uint.MaxValue),
   (int)(uint)((coefficient>>32)&uint.MaxValue),
   (int)(uint)((coefficient>>64)&uint.MaxValue),false,(byte)scale);
 }
 static decimal LegCeiling(decimal value,bool reverse) {
  var p=Parts(value);var unit=BigInteger.Pow(10,p.Scale);
  return reverse?CeilingRatio(unit,p.Coefficient):CeilingRatio(p.Coefficient,unit);
 }
 static decimal ProductCeiling(decimal left,decimal right) {
  var a=Parts(left);var b=Parts(right);
  return CeilingRatio(a.Coefficient*b.Coefficient,BigInteger.Pow(10,a.Scale+b.Scale));
 }
 public static long RequireObservedBookAge(MxmObservedFxBook? b,string source,long now) {
  var v=b?.Observation;
  if(now<0)throw new ArgumentException("FX_INVALID_RECEIPT_CLOCK_OR_READER");
    if(b==null || b.Source!=source || v==null || !v.SessionOpen || v.Faulted || v.Epoch<=0 ||
       v.ReportedTransport==MxmReportedTransport.Down ||
       v.Origin is not (MxmObservationOrigin.RawPartialFields or MxmObservationOrigin.NativeCallbackSnapshot) || !b.Bid.HasValue || !b.Ask.HasValue ||
       b.Bid<=0 || b.Ask<b.Bid || !MxmBookShape.NonCrossed(v.Shape) ||
       MxmBookShape.Classify(b.Bid,b.Ask)!=v.Shape ||
       !v.BidObservedMs.HasValue || !v.AskObservedMs.HasValue || !v.LastEventMs.HasValue ||
       v.BidObservedMs<0 || v.AskObservedMs<0 || v.LastEventMs>now ||
       v.BidObservedMs>v.LastEventMs || v.AskObservedMs>v.LastEventMs ||
       now-v.BidObservedMs.Value>MaximumSideAgeMs || now-v.AskObservedMs.Value>MaximumSideAgeMs)
     throw new ArgumentException("FX_REQUIRED_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD");
  return Math.Max(now-v!.BidObservedMs!.Value,now-v.AskObservedMs!.Value);
 }
 public MxmObservedCostFxEstimate CostRate(string from,string to,long now,
  Func<string,MxmObservedFxBook?> readBook) {
  if(now<0 || readBook==null)throw new ArgumentException("FX_INVALID_RECEIPT_CLOCK_OR_READER");
  var path=Route(from,to);decimal rate=1m;long maximumAge=0;
  try {checked {
   foreach(var leg in path) {
    var b=readBook(leg.Source);
    long age=RequireObservedBookAge(b,leg.Source,now);maximumAge=Math.Max(maximumAge,age);
    // Cover a debit in FROM asset using TO: buy base at ASK or sell
    // quote at inverse BID. Credit valuation requires a separate contract.
    decimal legRate=LegCeiling(leg.Reverse?b!.Bid!.Value:b!.Ask!.Value,leg.Reverse);
    rate=ProductCeiling(rate,legRate);
   }
  }}catch(OverflowException){throw new ArgumentException("FX_COST_RATE_OVERFLOW");}
  return new(rate,path,maximumAge);
 }
}
}

using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
public sealed record MxmPortfolioTarget(DateTime BoundaryUtc,DateTime AvailableUtc,
 string? Symbol,int Direction,string Reason,Dictionary<string,decimal> Scores);
/// <summary>One joint, causal portfolio target; no orders, sizing or profit claim.
/// Twelve-hour signed displacement / observed one-hour absolute variation,
/// ranked against the contemporaneous cross-market median. No fitted parameters.
/// Missing past endpoints are unavailable, never compressed into twelve bars.
/// </summary>
public sealed class MxmRelativeStrengthPortfolio {
 readonly Dictionary<string,SortedDictionary<DateTime,decimal>> series=new(StringComparer.Ordinal);
 readonly Dictionary<string,DateTime> clocks=new(StringComparer.Ordinal);
 DateTime lastDecision;
 public MxmRelativeStrengthPortfolio(IEnumerable<string> symbols) {
  foreach(var s in symbols) {
   if(string.IsNullOrWhiteSpace(s)||!series.TryAdd(s,new()))throw new ArgumentException("INVALID_POLICY_ROSTER");
  }
  if(series.Count<3||series.Count>16)throw new ArgumentException("POLICY_REQUIRES_JOINT_MARKETS");
 }
 public MxmPortfolioTarget? Observe(string symbol,DateTime end,decimal close,DateTime available) {
  if(!series.TryGetValue(symbol,out var bars)||close<=0||end.Kind!=DateTimeKind.Utc||
   available.Kind!=DateTimeKind.Utc||end.Ticks%TimeSpan.TicksPerHour!=0||available<end||available>=end.AddHours(1))
   throw new ArgumentException("INVALID_CAUSAL_POLICY_BAR");
  if(bars.Count>0 && end<=bars.Last().Key)throw new ArgumentException("POLICY_BAR_REPLAY");
  bars.Add(end,close);clocks[symbol]=available;
  foreach(var old in bars.Keys.Where(t=>t<end.AddHours(-12)).ToArray())bars.Remove(old);
  if(end<=lastDecision||series.Values.Any(b=>b.Count==0||b.Last().Key!=end))return null;
  lastDecision=end;
  var now=clocks.Values.Max();var scores=new Dictionary<string,decimal>(StringComparer.Ordinal);
  if(end.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday || end.Hour<7||end.Hour>15)
   return new(end,now,null,0,"OUTSIDE_SESSION_FLAT",scores);
  foreach(var pair in series.OrderBy(p=>p.Key,StringComparer.Ordinal)) {
   var b=pair.Value;
   if(!b.TryGetValue(end.AddHours(-12),out var prior))return new(end,now,null,0,"PAST_ENDPOINT_UNAVAILABLE_FLAT",scores);
   decimal variation=0;int pairs=0;
   foreach(var item in b)if(b.TryGetValue(item.Key.AddHours(-1),out var previous)) {
    variation+=Math.Abs(item.Value/previous-1m);pairs++;
   }
   if(pairs<9||variation<=0)return new(end,now,null,0,"PAST_VARIATION_UNAVAILABLE_FLAT",scores);
   scores.Add(pair.Key,Math.Max(-1m,Math.Min(1m,(b[end]/prior-1m)/variation)));
  }
  var values=scores.Values.OrderBy(x=>x).ToArray();
  decimal median=values.Length%2==1?values[values.Length/2]:(values[values.Length/2-1]+values[values.Length/2])/2m;
  var ranked=scores.Select(p=>new {p.Key,Relative=p.Value-median})
   .OrderByDescending(p=>Math.Abs(p.Relative)).ThenBy(p=>p.Key,StringComparer.Ordinal).ToArray();
  var winner=ranked[0];
  if(values[^1]-values[0]<.5m||Math.Abs(winner.Relative)<.25m)
   return new(end,now,null,0,"NO_RELATIVE_DISPERSION_FLAT",scores);
  return new(end,now,winner.Key,winner.Relative>0?1:-1,"JOINT_RELATIVE_STRENGTH_TARGET",scores);
 }
}
}

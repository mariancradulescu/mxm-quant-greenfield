using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using Mxm.Replay;
namespace cAlgo.Robots {
public sealed partial class MxmReferenceProductBot {
 [Parameter("Observe Relative Strength Policy",DefaultValue=false)]
 public bool ObserveRelativeStrengthPolicy {get;set;}
 MxmRelativeStrengthPortfolio? observedPortfolioPolicy;
 readonly List<Bars> policyObservationBars=new();
 readonly Dictionary<string,DateTime> policyObservationEnds=new(StringComparer.Ordinal);
 void StartRelativeStrengthObservation() {
  if(!ObserveRelativeStrengthPolicy)return;
  if(!nativeRun.IsObserving)throw new InvalidOperationException("POLICY_REQUIRES_OBSERVATION_FENCE");
  var names=PortfolioSymbols.Split(',').Select(s=>s.Trim()).ToArray();
  observedPortfolioPolicy=new MxmRelativeStrengthPortfolio(names);
  foreach(var name in names) {
   var bars=MarketData.GetBars(cAlgo.API.TimeFrame.Hour,name);
   if(bars==null)throw new InvalidOperationException("POLICY_SOURCE_UNAVAILABLE");
   policyObservationBars.Add(bars);bars.BarClosed+=OnRelativeStrengthObservation;
  }
  Print("MXM_PORTFOLIO_POLICY_OBSERVING coldStart=true orders=false economicQualification=false");
 }
 void OnRelativeStrengthObservation(BarClosedEventArgs args) {
  if(!nativeRun.IsObserving||observedPortfolioPolicy==null)return;
  try {
   var bars=args.Bars;if(bars.Count<1)return;
   var end=DateTime.SpecifyKind(bars.OpenTimes.Last(0).AddHours(1),DateTimeKind.Utc);
   var now=DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
   if(policyObservationEnds.TryGetValue(bars.SymbolName,out var prior)&&end<=prior)return;
   policyObservationEnds[bars.SymbolName]=end;
   if(now<end||now>=end.AddHours(1))return; // delayed/old session closure is unavailable
   var target=observedPortfolioPolicy.Observe(bars.SymbolName,end,(decimal)bars.ClosePrices.Last(0),now);
   if(target!=null)Print("MXM_PORTFOLIO_POLICY_OBSERVATION orders=false target={0}",
    System.Text.Json.JsonSerializer.Serialize(target));
  } catch(Exception e) {
   nativeRun.Stop();Print("MXM_PORTFOLIO_POLICY_OBSERVATION_STOP_"+e.GetType().Name);Stop();
  }
 }
 void StopRelativeStrengthObservation() {
  foreach(var bars in policyObservationBars)bars.BarClosed-=OnRelativeStrengthObservation;
  policyObservationBars.Clear();observedPortfolioPolicy=null;
 }
}
}

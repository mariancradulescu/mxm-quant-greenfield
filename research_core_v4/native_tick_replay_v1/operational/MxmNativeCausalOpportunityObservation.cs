using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>
/// One order-free product's original policy kernel + native target quote
/// + existing EUR min-ticket economic observation. Frozen reference files
/// and frozen policy thresholds are never modified or re-registered.
/// Signal != net qualification != entry authorization.
/// </summary>
public sealed partial class MxmReferenceProductBot {
 readonly Dictionary<string,Symbol> causalQuoteSymbols=
  new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,MxmBookObservation<double>> causalQuoteBooks=
  new(StringComparer.OrdinalIgnoreCase);
 readonly List<Bars> joinedPolicyBars=new();
 long observedJointDecisions,observedNonFlatCandidates;
 void StartNativeCausalOpportunityObservation() {
  if(!ObserveRelativeStrengthPolicy)return;
  if(!nativeRun.IsObserving)throw new InvalidOperationException(
   "NATIVE_JOINT_OPPORTUNITY_ONLY_IN_ORDER_FREE_MODE");
  var roster=PortfolioSymbols.Split(',').Select(x=>x.Trim()).ToArray();
  if(roster.Length<3 || roster.Length>16 ||
     roster.Any(x=>x.Length==0) ||
     roster.Distinct(StringComparer.OrdinalIgnoreCase).Count()!=roster.Length)
   throw new InvalidOperationException("NATIVE_JOINT_POLICY_ROSTER_INVALID");
  // THIS is the existing frozen policy class, evaluated exactly once from
  // native Bars. The original shared observational adapter is preserved
  // byte-for-byte but NOT subscribed in the operational observation lane.
  observedPortfolioPolicy=new MxmRelativeStrengthPortfolio(roster);
  policyObservationEnds.Clear();
  foreach(var name in roster) {
   var symbol=Symbols.GetSymbol(name);
   if(symbol==null || !string.Equals(symbol.Name,name,StringComparison.OrdinalIgnoreCase))
    throw new InvalidOperationException("NATIVE_JOINT_PRICE_SOURCE_UNVERIFIED");
   var bars=MarketData.GetBars(cAlgo.API.TimeFrame.Hour,name);
   if(bars==null || !string.Equals(bars.SymbolName,name,StringComparison.OrdinalIgnoreCase))
    throw new InvalidOperationException("NATIVE_JOINT_H1_SOURCE_UNVERIFIED");
   var book=MxmBookObservations.NativeSnapshots();
   book.BeginEpoch(Environment.TickCount64);
   causalQuoteSymbols.Add(name,symbol);causalQuoteBooks.Add(name,book);
   joinedPolicyBars.Add(bars);
   symbol.Tick+=OnNativeCausalQuoteTick;
   bars.BarClosed+=OnNativeJointPolicyBarClosed;
  }
  Print("MXM_NATIVE_JOINT_OPPORTUNITY_SOURCE_READY symbols={0} policy=EXISTING_FROZEN_H1_ONCE prices=native_target_tick_callbacks account=ONE_CSHARP_EUR commissions=UNKNOWN storage=false orders=false cloudOrders=false",
   string.Join(",",roster));
 }
 void OnNativeCausalQuoteTick(SymbolTickEventArgs args) {
  if(!nativeRun.IsObserving)return;
  try {
   if(!causalQuoteBooks.TryGetValue(args.SymbolName,out var book))
    throw new InvalidOperationException("NATIVE_JOINT_UNREGISTERED_QUOTE");
   book.Observe(args.Bid,args.Ask,Environment.TickCount64,
    DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),null);
  }catch(Exception e) {
   nativeRun.Stop();Print("MXM_NATIVE_JOINT_QUOTE_SOURCE_STOP_{0}",e.GetType().Name);
   Stop();
  }
 }
 void OnNativeJointPolicyBarClosed(BarClosedEventArgs args) {
  if(!nativeRun.IsObserving || observedPortfolioPolicy==null)return;
  try {
   var bars=args.Bars;
   if(bars.Count<1)return;
   var end=DateTime.SpecifyKind(bars.OpenTimes.Last(0).AddHours(1),DateTimeKind.Utc);
   var now=DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
   if(policyObservationEnds.TryGetValue(bars.SymbolName,out var prior)&&end<=prior)return;
   policyObservationEnds[bars.SymbolName]=end;
   if(now<end||now>=end.AddHours(1))return;
   // Identical H1 source timing and actual original existing policy decision
   // as the frozen source observer. No new signal, model or threshold.
   var target=observedPortfolioPolicy.Observe(
    bars.SymbolName,end,(decimal)bars.ClosePrices.Last(0),now);
   if(target==null)return;
   Print("MXM_PORTFOLIO_POLICY_OBSERVATION orders=false target={0}",
    System.Text.Json.JsonSerializer.Serialize(target));
   ReportNativeCausalPortfolioOpportunity(target);
  }catch(Exception e) {
   nativeRun.Stop();Print("MXM_NATIVE_JOINT_CAUSAL_SOURCE_STOP_{0}",e.GetType().Name);Stop();
  }
 }
 void ReportNativeCausalPortfolioOpportunity(MxmPortfolioTarget target) {
  if(!nativeRun.IsObserving || !ObserveRelativeStrengthPolicy)return;
  try {
   var now=DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
   if(target.BoundaryUtc.Kind!=DateTimeKind.Utc ||
      target.AvailableUtc.Kind!=DateTimeKind.Utc ||
      target.AvailableUtc<target.BoundaryUtc || target.AvailableUtc>now ||
      now>=target.BoundaryUtc.AddHours(1))
    throw new InvalidOperationException("NATIVE_JOINT_POLICY_CLOCK_UNVERIFIED");
   observedJointDecisions=checked(observedJointDecisions+1);
   if(target.Symbol==null || target.Direction==0) {
    if(target.Symbol!=null || target.Direction!=0)
     throw new InvalidOperationException("NATIVE_JOINT_FLAT_INCONSISTENT");
    Print("MXM_NATIVE_JOINT_CAUSAL_DECISION boundaryUTC={0:O} availableUTC={1:O} policyReason={2} observedJointDecisions={3} selectedSymbol=NONE direction=0 status=NO_CANDIDATE economicQualified=false orderAdmission=false orders=false",
     target.BoundaryUtc,target.AvailableUtc,target.Reason,observedJointDecisions);
    return;
   }
   if(target.Direction is not (1 or -1) ||
      target.Reason!="JOINT_RELATIVE_STRENGTH_TARGET" ||
      !causalQuoteSymbols.TryGetValue(target.Symbol,out var selected) ||
      !causalQuoteBooks.TryGetValue(target.Symbol,out var selectedBook))
    throw new InvalidOperationException("NATIVE_JOINT_CAUSAL_TARGET_UNVERIFIED");
   observedNonFlatCandidates=checked(observedNonFlatCandidates+1);
   // Exact selected instrument's native callback book and the same preexisting
   // min-volume EUR-capital/cost observation. Never chart-symbol fallback.
   string necessary=ReportNativeMinimumTicketAperture(selected,selectedBook);
   Print("MXM_NATIVE_JOINT_CAUSAL_OPPORTUNITY boundaryUTC={0:O} availableUTC={1:O} observedUTC={2:O} selectedSymbol={3} direction={4} causalMechanism=EXISTING_H1_RELATIVE_STRENGTH observedJointDecisions={5} observedNonFlatCandidates={6} nativeSelectedSymbolMinTicket={7} causalSignalObserved=true selectedNativeQuoteAndVisibleRisk={8} historicalBidAskProven=false expectedGrossEUR=UNKNOWN completeRoundTripCostEUR=UNKNOWN expectedNetEUR=UNKNOWN independentValidation=false HARD21=false economicQualified=false entryAuthorized=false orders=false accountMutation=false",
    target.BoundaryUtc,target.AvailableUtc,now,target.Symbol,target.Direction,
    observedJointDecisions,observedNonFlatCandidates,selected.VolumeInUnitsMin,
    necessary);
  }catch(Exception e) {
   nativeRun.Stop();Print("MXM_NATIVE_JOINT_CAUSAL_OPPORTUNITY_STOP_{0}",
    e.GetType().Name);Stop();
  }
 }
 void StopNativeCausalOpportunityObservation() {
  foreach(var bars in joinedPolicyBars)bars.BarClosed-=OnNativeJointPolicyBarClosed;
  joinedPolicyBars.Clear();
  foreach(var pair in causalQuoteSymbols)pair.Value.Tick-=OnNativeCausalQuoteTick;
  causalQuoteSymbols.Clear();
  foreach(var book in causalQuoteBooks.Values) {
   try {book.EndEpoch(Environment.TickCount64);}catch(Exception){/* already stopped */}
  }
  causalQuoteBooks.Clear();observedPortfolioPolicy=null;policyObservationEnds.Clear();
 }
}

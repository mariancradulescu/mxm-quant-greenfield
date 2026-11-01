using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>
/// The ONLY production cBot's order-free observation bridge:
/// *existing* H1 joint causal market target -> fresh native callback book
/// for that exact target -> *existing* min-ticket EUR risk/cost viewer.
/// No new policy, signal threshold, execution engine or second cBot.
/// Candidate != economic qualification != authorized entry.
/// </summary>
public sealed partial class MxmReferenceProductBot {
 readonly Dictionary<string,Symbol> causalQuoteSymbols=
  new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,MxmBookObservation<double>> causalQuoteBooks=
  new(StringComparer.OrdinalIgnoreCase);
 long observedJointDecisions,observedNonFlatCandidates;
 void StartNativeCausalOpportunityObservation() {
  if(!ObserveRelativeStrengthPolicy)return;
  if(!nativeRun.IsObserving)throw new InvalidOperationException(
   "NATIVE_JOINT_OPPORTUNITY_ONLY_IN_ORDER_FREE_MODE");
  var roster=PortfolioSymbols.Split(',').Select(x=>x.Trim())
   .Where(x=>x.Length>0).ToArray();
  if(roster.Length<3 || roster.Length>16 ||
     roster.Distinct(StringComparer.OrdinalIgnoreCase).Count()!=roster.Length)
   throw new InvalidOperationException("NATIVE_JOINT_POLICY_ROSTER_INVALID");
  // A native tick subscription is a READ-ONLY source; no broker requests,
  // account mutation, order handlers, storage or runtime source polling.
  foreach(var name in roster) {
   var symbol=Symbols.GetSymbol(name);
   if(symbol==null || !string.Equals(symbol.Name,name,StringComparison.OrdinalIgnoreCase))
    throw new InvalidOperationException("NATIVE_JOINT_PRICE_SOURCE_UNVERIFIED");
   var book=MxmBookObservations.NativeSnapshots();
   book.BeginEpoch(Environment.TickCount64);
   causalQuoteSymbols.Add(name,symbol);
   causalQuoteBooks.Add(name,book);
   symbol.Tick+=OnNativeCausalQuoteTick;
  }
  Print("MXM_NATIVE_JOINT_OPPORTUNITY_SOURCE_READY symbols={0} strategy=EXISTING_JOINT_H1_UNQUALIFIED prices=native_tick_callbacks commissions=UNKNOWN oneCbot=true accountMutation=false orders=false cloudOrders=false",
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
   nativeRun.Stop();
   Print("MXM_NATIVE_JOINT_QUOTE_SOURCE_STOP_{0}",e.GetType().Name);
   Stop();
  }
 }
 // Optional bridge from the EXISTING MxmRelativeStrengthPortfolio, not a
 // copied/inverted/retuned evaluator. Historical bot erases this partial hook.
 partial void OnNativeCausalPortfolioTarget(MxmPortfolioTarget target) {
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
   // SAME existing original native BIDASK/fee/stop/capital viewer, now called
   // for the selected H1 policy target, NOT the host chart symbol. A return
   // of PASSES_VISIBLE_NECESSARY_ONLY_NO_ADMISSION is NOT NET evidence.
   string necessary=ReportNativeMinimumTicketAperture(selected,selectedBook);
   Print("MXM_NATIVE_JOINT_CAUSAL_OPPORTUNITY boundaryUTC={0:O} availableUTC={1:O} observedUTC={2:O} selectedSymbol={3} direction={4} causalMechanism=EXISTING_H1_RELATIVE_STRENGTH observedJointDecisions={5} observedNonFlatCandidates={6} nativeSelectedSymbolMinTicket={7} causalSignalObserved=true selectedNativeQuoteAndVisibleRisk={8} historicalBidAskProven=false expectedGrossEUR=UNKNOWN completeRoundTripCostEUR=UNKNOWN expectedNetEUR=UNKNOWN independentValidation=false HARD21=false economicQualified=false entryAuthorized=false orders=false accountMutation=false",
    target.BoundaryUtc,target.AvailableUtc,now,target.Symbol,target.Direction,
    observedJointDecisions,observedNonFlatCandidates,selected.VolumeInUnitsMin,
    necessary);
  }catch(Exception e) {
   // No fallback to an older quote, chart-symbol price or fabricated cost.
   nativeRun.Stop();Print("MXM_NATIVE_JOINT_CAUSAL_OPPORTUNITY_STOP_{0}",
    e.GetType().Name);Stop();
  }
 }
 void StopNativeCausalOpportunityObservation() {
  foreach(var pair in causalQuoteSymbols)pair.Value.Tick-=OnNativeCausalQuoteTick;
  causalQuoteSymbols.Clear();
  foreach(var book in causalQuoteBooks.Values) {
   try {book.EndEpoch(Environment.TickCount64);}catch(Exception){/* already stopped */}
  }
  causalQuoteBooks.Clear();
 }
}
}
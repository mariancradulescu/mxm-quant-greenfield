using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>Source-compatible cloud-facing adapter; never activated by the CI workflow.
/// OnBarClosed uses the exact same C# decision state as the machine-side reference.</summary>
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public sealed class MxmReferenceProductBot : Robot {
 const string Label="MXM_CSHARP_REFERENCE_V1";
 // This Robot intentionally has no separately-trading chart-local kernel.
 ExitMode exitMode=ExitMode.ReverseOnly;
 [Parameter("Portfolio Symbols (comma separated)",DefaultValue="")]
 public string PortfolioSymbols {get;set;}="";
 readonly Dictionary<string,MxmDecisionKernel> portfolioKernels=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,Bars> subscribedBars=new(StringComparer.OrdinalIgnoreCase);
 MxmPortfolioSequencer? sequencer;
 [Parameter("Enable DEMO Trading",DefaultValue=false)]
 public bool EnableDemoTrading {get;set;}
 [Parameter("Stop Loss Pips",DefaultValue=12,MinValue=1)]
 public int StopLossPips {get;set;}
 [Parameter("Regime Family",DefaultValue="Adaptive")]
 public string RegimeFamily {get;set;}="Adaptive";
 [Parameter("Exit Mode",DefaultValue="ReverseOnly")]
 public string ExitPolicy {get;set;}="ReverseOnly";
 [Parameter("Bar Minutes",DefaultValue=5,MinValue=1)]
 public int BarMinutes {get;set;}
 [Parameter("Max Margin Fraction",DefaultValue=0.4,MinValue=0.1,MaxValue=1.0)]
 public double MaxMarginFraction {get;set;}=0.4;
 [Parameter("Max MXM Account Positions",DefaultValue=1,MinValue=1)]
 public int MaxMxmAccountPositions {get;set;}=1;
 [Parameter("Minimum Free Margin Reserve EUR",DefaultValue=0,MinValue=0)]
 public double MinimumFreeMarginReserveEur {get;set;}=0;
 [Parameter("Max Estimated MXM Stop Risk Percent",DefaultValue=2.0,MinValue=0.1,MaxValue=100.0)]
 public double MaxEstimatedMxmStopRiskPercent {get;set;}=2.0;
 [Parameter("Estimated Round Trip Friction Reserve EUR",DefaultValue=0.2,MinValue=0.0)]
 public double EstimatedRoundTripFrictionReserveEur {get;set;}=0.2;
 [Parameter("Requested Units",DefaultValue=1000,MinValue=1)]
 public double RequestedUnits {get;set;}
 protected override void OnStart() {
  if(!Enum.TryParse<StrategyMode>(RegimeFamily,true,out var mode)){
   Print("MXM_UNKNOWN_FAMILY_SAFE_HOLD");Stop();return;
  }
  if(!Enum.TryParse<ExitMode>(ExitPolicy,true,out exitMode)){
   Print("MXM_INVALID_EXIT_MODE_SAFE_HOLD");Stop();return;
  }
  bool supported=(BarMinutes==1 && TimeFrame==cAlgo.API.TimeFrame.Minute) ||
   (BarMinutes==5 && TimeFrame==cAlgo.API.TimeFrame.Minute5) ||
   (BarMinutes==15 && TimeFrame==cAlgo.API.TimeFrame.Minute15);
  if(!supported){Print("MXM_UNSUPPORTED_TIMEFRAME_HOLD");Stop();return;}
  // There is one owning Robot instance and a single sequential order path.
  // No independent per-chart signal bot may open another portfolio position.
  // Explicit roster required: empty configuration does NOT trade even on DEMO.
  var names=PortfolioSymbols.Split(',').Select(x=>x.Trim())
   .Where(x=>x.Length>0).ToArray();
  if(names.Length==0 || names.Length>16 ||
     names.Distinct(StringComparer.OrdinalIgnoreCase).Count()!=names.Length) {
   Print("MXM_PORTFOLIO_ROSTER_INVALID_OR_EMPTY_SAFE_HOLD");Stop();return;
  }
  // A portfolio that excludes an existing MXM-labelled position cannot safely
  // claim to orchestrate the complete account, including on cold restart.
  foreach(var position in Positions.FindAll(Label)) {
   if(!names.Contains(position.SymbolName,StringComparer.OrdinalIgnoreCase)) {
    Print("MXM_UNMANAGED_EXISTING_MXM_POSITION_SAFE_HOLD");Stop();return;
   }
  }
  var resolved=new List<string>();
  foreach(var name in names) {
   var instrument=Symbols.GetSymbol(name);
   if(instrument==null || !string.Equals(instrument.Name,name,StringComparison.OrdinalIgnoreCase)){
    Print("MXM_UNKNOWN_OR_AMBIGUOUS_PORTFOLIO_SYMBOL_SAFE_HOLD_"+name);Stop();return;
   }
   resolved.Add(instrument.Name);
  }
  sequencer=new MxmPortfolioSequencer(resolved);
  // Subscribe only after full validation. Each symbol has independent cold
  // six-complete-bar strategy state; there is ONE shared real broker account.
  foreach(var name in resolved) {
   var series=MarketData.GetBars(TimeFrame,name);
   if(series==null){Print("MXM_PORTFOLIO_SERIES_MISSING_SAFE_HOLD_"+name);Stop();return;}
   subscribedBars.Add(name,series);
   portfolioKernels.Add(name,new MxmDecisionKernel(mode));
  }
  foreach(var series in subscribedBars.Values)series.BarClosed+=OnPortfolioBarClosed;
  Print("MXM_SINGLE_ROBOT_PORTFOLIO_BARS_READY_NO_INTERINSTANCE_MUTEX_"+resolved.Count);
 }
 // Deliberately no legacy per-chart order path. All symbols, including chart
 // symbol, enter via one Bars.BarClosed dispatcher, never OnBar plus BarClosed.
 protected override void OnBar() { }
 protected override void OnStop() {
  foreach(var series in subscribedBars.Values)series.BarClosed-=OnPortfolioBarClosed;
 }
 void OnPortfolioBarClosed(BarClosedEventArgs args) {
  var series=args.Bars;
  if(series.Count<2 || sequencer==null)return;
  var instrumentName=series.SymbolName;
  DateTime closedOpenTime=series.OpenTimes.Last(0);
  if(!sequencer.TryEnter(instrumentName,closedOpenTime,out var reason)){
   // Duplicate/stale bars are normal after feed reload and must not trade twice.
   if(reason=="REENTRANT_OR_CONCURRENT_DECISION"){
    Print("MXM_REENTRANT_PORTFOLIO_CALLBACK_SAFE_STOP");Stop();
   }
   return;
  }
  try {
   var instrument=Symbols.GetSymbol(instrumentName);
   if(instrument==null || !portfolioKernels.TryGetValue(instrumentName,out var kernel)){
    Print("MXM_PORTFOLIO_SYMBOL_DISAPPEARED_SAFE_STOP");Stop();return;
   }
   bool contiguous=(series.OpenTimes.Last(0)-series.OpenTimes.Last(1)).TotalMinutes==BarMinutes;
   if(!contiguous)kernel.Reset();
   // Bars.BarClosed excludes the newly opened bar; Last(0) IS the closed one.
   // No historical warm-start or double-processed boundary tick.
   int desired=kernel.OnCompletedBar((decimal)series.ClosePrices.Last(0));
   var currentOpenTime=closedOpenTime.AddMinutes(BarMinutes);
   ApplyPortfolioDecision(instrument,instrumentName,desired,contiguous,kernel.CompletedBars,currentOpenTime);
  } catch(Exception e) {
   Print("MXM_PORTFOLIO_CALLBACK_UNVERIFIED_SAFE_STOP_"+e.GetType().Name);
   Stop();
  } finally {sequencer.Exit();}
 }
 void ApplyPortfolioDecision(Symbol instrument,string instrumentName,int desired,
  bool contiguous,int completedBars,DateTime currentOpenTime) {
  bool simulation=IsBacktesting;
  if(!(simulation || (EnableDemoTrading && !Account.IsLive)) || !instrument.MarketHours.IsOpened())return;
  var owned=Positions.FindAll(Label,instrumentName);
  if(owned.Length>1){Print("MXM_MULTIPLE_POSITIONS_SAFE_HOLD");return;}
  TradeType direction=desired>0?TradeType.Buy:TradeType.Sell;
  if(owned.Length==1){
   var current=owned[0];
   // A neutral signal has no broker order unless this specific exit policy is selected.
   // A discontinuity is never reinterpreted as a valid causal neutral exit.
   bool neutralExit=contiguous && completedBars>=6 && exitMode==ExitMode.NeutralFlat && desired==0;
   // Age measured against the existing position's actual broker entry time.
   bool horizonExit=exitMode==ExitMode.Horizon12 &&
     (currentOpenTime-current.EntryTime).TotalMinutes>=12*BarMinutes;
   if(neutralExit || horizonExit){
    var closed=ClosePosition(current);
    if(!closed.IsSuccessful)Print("MXM_POLICY_EXIT_FAILED_SAFE_HOLD");
    return; // Never manufacture a same-bar entry after a discretionary exit.
   }
   if(desired==0)return;
   if(current.TradeType==direction)return;
   var result=ClosePosition(current);
   if(!result.IsSuccessful){Print("MXM_CLOSE_FAILED_SAFE_HOLD");return;}
  }
  if(desired==0)return;
  // Inspect actual broker minimum/step/margin; do not assume EUR200 volume feasibility.
  if(Account.Equity<=0||Account.FreeMargin<=0||Account.Asset.Name!="EUR")return;
  // This is an account-wide snapshot, not atomic inter-instance order locking.
  // Broker book (all symbols using this MXM label), not local kernel memory, is authoritative.
  int accountOwned=Positions.FindAll(Label).Length;
  if(!double.IsFinite(Account.Equity)||!double.IsFinite(Account.FreeMargin)||
     !double.IsFinite(MaxMarginFraction)||!double.IsFinite(MinimumFreeMarginReserveEur)||
     MinimumFreeMarginReserveEur<0)return;
  double units=instrument.NormalizeVolumeInUnits(Math.Max(RequestedUnits,instrument.VolumeInUnitsMin),RoundingMode.Up);
  if(units<=0 || units>instrument.VolumeInUnitsMax)return;
  double margin=instrument.GetEstimatedMargin(direction,units);
  if(!double.IsFinite(margin)||margin<=0)return;
  string admit=MxmCapitalAdmission.Check((decimal)Account.Equity,(decimal)Account.FreeMargin,
    (decimal)margin,0m,(decimal)MaxMarginFraction,(decimal)MinimumFreeMarginReserveEur,
    accountOwned,MaxMxmAccountPositions);
  // Exact historical broker commissions are not known here; commission=0
  // means this is an estimated account gate, never a fill/fee certificate.
  if(admit!=MxmCapitalAdmission.Admit){Print("MXM_CAPITAL_HOLD_"+admit);return;}
  // Complete-account MXM estimated stop exposure. Do not interpret a stop
  // as a maximum loss, or this snapshot as an atomic inter-cBot lock.
  if(!double.IsFinite(MaxEstimatedMxmStopRiskPercent) ||
     MaxEstimatedMxmStopRiskPercent<=0 || MaxEstimatedMxmStopRiskPercent>100 ||
     !double.IsFinite(EstimatedRoundTripFrictionReserveEur) ||
     EstimatedRoundTripFrictionReserveEur<0 || StopLossPips<=0) {
    Print("MXM_STOP_RISK_INPUT_UNVERIFIED_SAFE_HOLD");return;
  }
  double newStopRisk=instrument.AmountRisked(units,StopLossPips);
  if(!double.IsFinite(newStopRisk)||newStopRisk<=0) {
    Print("MXM_NEW_STOP_RISK_UNVERIFIED_SAFE_HOLD");return;
  }
  double existingRisk=0;
  int protectedExisting=0;
  foreach(var active in Positions.FindAll(Label)) {
   // No new orders if ANY existing MXM position has no broker stop
   // or if its symbol/volume/pip geometry cannot be validated.
   if(!active.StopLoss.HasValue || !double.IsFinite(active.StopLoss.Value) ||
      !double.IsFinite(active.EntryPrice) || !double.IsFinite(active.VolumeInUnits) ||
      !double.IsFinite(active.Symbol.PipSize) || active.Symbol.PipSize<=0 ||
      active.EntryPrice<=0 || active.VolumeInUnits<=0) {
    Print("MXM_EXISTING_STOP_UNVERIFIED_SAFE_HOLD");return;
   }
   double distancePips=Math.Abs(active.EntryPrice-active.StopLoss.Value)/active.Symbol.PipSize;
   if(!double.IsFinite(distancePips)||distancePips<0) {
    Print("MXM_EXISTING_STOP_DISTANCE_UNVERIFIED_SAFE_HOLD");return;
   }
   double risk=active.instrument.AmountRisked(active.VolumeInUnits,distancePips);
   if(!double.IsFinite(risk)||risk<0) {
    Print("MXM_EXISTING_STOP_RISK_UNVERIFIED_SAFE_HOLD");return;
   }
   existingRisk+=risk;
   protectedExisting++;
   if(!double.IsFinite(existingRisk)) {
    Print("MXM_EXISTING_STOP_RISK_SUM_UNVERIFIED_SAFE_HOLD");return;
   }
  }
  string stopRiskGate=MxmStopRiskAdmission.Check(
   (decimal)Account.Equity,(decimal)existingRisk,(decimal)newStopRisk,
   (decimal)(MaxEstimatedMxmStopRiskPercent/100.0),
   (decimal)EstimatedRoundTripFrictionReserveEur,
   (decimal)EstimatedRoundTripFrictionReserveEur*protectedExisting);
  if(stopRiskGate!=MxmStopRiskAdmission.Admit) {
   Print("MXM_ACCOUNT_STOP_RISK_HOLD_"+stopRiskGate);return;
  }
  var placed=ExecuteMarketOrder(direction,instrumentName,units,Label,StopLossPips,null);
  if(!placed.IsSuccessful)Print("MXM_ORDER_REJECTED_NO_SYNTHETIC_FILL");
 }
}
}

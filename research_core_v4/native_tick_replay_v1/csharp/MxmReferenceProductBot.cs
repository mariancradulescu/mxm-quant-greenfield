using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>Native account adapter; never activated by CI. Durable entry barrier requires Desktop.
/// OnBarClosed uses the exact same C# decision state as the machine-side reference.</summary>
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public sealed class MxmReferenceProductBot : Robot {
 const string Label="MXM_CSHARP_REFERENCE_V1";
 // This Robot intentionally has no separately-trading chart-local kernel.
 ExitMode exitMode=ExitMode.ReverseOnly;
 [Parameter("Portfolio Symbols (comma separated)",DefaultValue="")]
 public string PortfolioSymbols {get;set;}="";
 readonly Dictionary<string,MxmDecisionSource> portfolioKernels=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,Bars> subscribedBars=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,Symbol> subscribedSymbols=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,MxmCausalIntent> causalIntents=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,MxmBrokerIntentFence> brokerIntentFences=new(StringComparer.OrdinalIgnoreCase);
 bool applyingDecision;
 readonly MxmOrderProtection orderProtection=new();
 MxmEntryCheckpoint? entryCheckpoint;
 MxmConfirmedEntryLedger? confirmedEntries;
 bool entryStorageFault;
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
 [Parameter("Minimum Free Margin Reserve EUR",DefaultValue=120,MinValue=0)]
 public double MinimumFreeMarginReserveEur {get;set;}=120;
 [Parameter("Max Estimated MXM Stop Risk Percent",DefaultValue=1.0,MinValue=0.1,MaxValue=100.0)]
 public double MaxEstimatedMxmStopRiskPercent {get;set;}=1.0;
 [Parameter("Estimated Round Trip Friction Reserve EUR",DefaultValue=0.2,MinValue=0.0)]
 public double EstimatedRoundTripFrictionReserveEur {get;set;}=0.2;
 [Parameter("Requested Units",DefaultValue=1000,MinValue=1)]
 public double RequestedUnits {get;set;}
 protected override void OnStart() {
  bool onlineAr1=string.Equals(RegimeFamily,"OnlineAr1",StringComparison.OrdinalIgnoreCase);
  var mode=StrategyMode.Adaptive;
  if(!onlineAr1 && (!Enum.TryParse<StrategyMode>(RegimeFamily,true,out mode) ||
     !Enum.IsDefined(typeof(StrategyMode),mode))){
   Print("MXM_UNKNOWN_FAMILY_SAFE_HOLD");Stop();return;
  }
  if(!Enum.TryParse<ExitMode>(ExitPolicy,true,out exitMode) ||
     !Enum.IsDefined(typeof(ExitMode),exitMode) ||
     (onlineAr1 && (BarMinutes!=5 || exitMode!=ExitMode.NeutralFlat))){
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
  try {
   if(!IsBacktesting && Application.EnvironmentType!=cAlgo.API.EnvironmentType.Desktop) {
    Print("MXM_ENTRY_PERSISTENCE_ENVIRONMENT_UNQUALIFIED_SAFE_STOP");Stop();return;
   }
   string scope=IsBacktesting?"ISOLATED_BACKTEST":MxmEntryCheckpoint.AccountScope(
    Account.BrokerName,Account.Number,Account.IsLive);
   IMxmEntryCheckpointStore store=IsBacktesting?new MxmMemoryEntryStore():
    new MxmDelegateEntryStore(ReadEntryCheckpoint,WriteEntryCheckpoint);
   entryCheckpoint=new MxmEntryCheckpoint(store,scope);
   var recoveryInspection=entryCheckpoint.InspectRecovery();
   if(recoveryInspection==MxmEntryRecoveryInspection.Blocked ||
      (recoveryInspection==MxmEntryRecoveryInspection.Normal && !entryCheckpoint.Initialize())) {
    orderProtection.HaltUnknown();
    Print("MXM_UNRESOLVED_ENTRY_CHECKPOINT_OR_STORAGE_FAULT_SAFE_STOP");Stop();return;
   }
   IMxmEntryCheckpointStore fillStore=IsBacktesting?new MxmMemoryEntryStore():
    new MxmDelegateEntryStore(ReadConfirmedEntries,WriteConfirmedEntries);
   confirmedEntries=new MxmConfirmedEntryLedger(fillStore,scope);
   if(!confirmedEntries.Initialize(BrokerClock(),requireExisting:recoveryInspection==MxmEntryRecoveryInspection.Recoverable)) {
    orderProtection.HaltUnknown();entryCheckpoint.Halt();
    Print("MXM_CONFIRMED_ENTRY_LEDGER_UNVERIFIED_SAFE_STOP");Stop();return;
   }
   if(recoveryInspection==MxmEntryRecoveryInspection.Recoverable &&
      !entryCheckpoint.RecoverVerifiedOpen(confirmedEntries,RecoveryBook(),PendingOrders.Count,BrokerClock())) {
    orderProtection.HaltUnknown();confirmedEntries.Halt();
    Print("MXM_ENTRY_RECOVERY_SAFE_STOP_"+entryCheckpoint.RecoveryReason);Stop();return;
   }
   if(recoveryInspection==MxmEntryRecoveryInspection.Recoverable)
    Print("MXM_ENTRY_RECOVERY_"+entryCheckpoint.RecoveryReason);
   ReportRecordedWeeks();
  }catch(Exception e) {
   orderProtection.HaltUnknown();
   Print("MXM_ENTRY_CHECKPOINT_STARTUP_SAFE_STOP_"+e.GetType().Name);Stop();return;
  }
  sequencer=new MxmPortfolioSequencer(resolved);
  // Subscribe only after full validation. Each symbol has independent cold
  // strategy state (online learner cold-rewarms at least 128 pairs); there is ONE shared real broker account.
  foreach(var name in resolved) {
   var series=MarketData.GetBars(TimeFrame,name);
   if(series==null){Print("MXM_PORTFOLIO_SERIES_MISSING_SAFE_HOLD_"+name);Stop();return;}
   subscribedBars.Add(name,series);
   portfolioKernels.Add(name,new MxmDecisionSource(new MxmDecisionKernel(mode),onlineAr1));
   subscribedSymbols.Add(name,Symbols.GetSymbol(name));
   causalIntents.Add(name,new MxmCausalIntent());
  }
  // Seed from the actual recovered broker book; cold start has no intent.
  foreach(var name in resolved) {
   var recovered=Positions.FindAll(Label,name);
   if(recovered.Length>1){Print("MXM_MULTIPLE_RECOVERED_POSITIONS_SAFE_STOP");Stop();return;}
   if(recovered.Length==1) {
    var active=recovered[0];var instrument=subscribedSymbols[name];
    var recoveryProtection=MxmOrderProtection.ValidateOpenPosition(active.Id,
     Label,name,active.TradeType==TradeType.Buy?1:-1,active.VolumeInUnits,
     StopLossPips,instrument.PipSize,instrument.TickSize,Array.Empty<long>(),ProtectionBook());
    if(recoveryProtection.Length!=0) {
     Print("MXM_RECOVERED_POSITION_PROTECTION_SAFE_STOP_"+recoveryProtection);Stop();return;
    }
   }
   brokerIntentFences.Add(name,new MxmBrokerIntentFence(causalIntents[name],BarMinutes,
    recovered.Length==0?null:recovered[0].Id));
  }
  Positions.Closed+=OnBrokerPositionClosed;
  foreach(var series in subscribedBars.Values)series.BarClosed+=OnPortfolioBarClosed;
  foreach(var instrument in subscribedSymbols.Values)instrument.Tick+=OnPortfolioTick;
  Print("MXM_SINGLE_ROBOT_PORTFOLIO_BARS_READY_NO_INTERINSTANCE_MUTEX_"+resolved.Count);
 }
 // Deliberately no legacy per-chart order path. All symbols, including chart
 // symbol, enter via one Bars.BarClosed dispatcher, never OnBar plus BarClosed.
 protected override void OnBar() { }
 long? BrokerPositionId(string symbolName) {
  var owned=Positions.FindAll(Label,symbolName);
  if(owned.Length>1)throw new InvalidOperationException("AMBIGUOUS_OWNED_POSITION_IDENTITY");
  return owned.Length==0?null:owned[0].Id;
 }
 DateTime BrokerClock()=>DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
 void OnBrokerPositionClosed(PositionClosedEventArgs args) {
  // Never seize, modify or cancel another owner's position or pending order.
  if(args.Position.Label!=Label ||
     !brokerIntentFences.TryGetValue(args.Position.SymbolName,out var fence))return;
  try {
   fence.Closed(args.Position.Id,args.Reason==PositionCloseReason.Closed,BrokerClock());
   Print("MXM_BROKER_CLOSE_FENCE reason={0} revision={1} symbol={2}",
    args.Reason,fence.Capture().Revision,args.Position.SymbolName);
  } catch(Exception e) {
   foreach(var intent in causalIntents.Values)intent.Clear();
   Print("MXM_BROKER_CLOSE_RECONCILIATION_SAFE_STOP_"+e.GetType().Name);Stop();
  }
 }
 protected override void OnStop() {
  Timer.Stop();
  Positions.Closed-=OnBrokerPositionClosed;
  foreach(var fence in brokerIntentFences.Values)fence.Reset();
  foreach(var series in subscribedBars.Values)series.BarClosed-=OnPortfolioBarClosed;
  foreach(var instrument in subscribedSymbols.Values)instrument.Tick-=OnPortfolioTick;
  foreach(var intent in causalIntents.Values)intent.Clear();
 }
 void OnPortfolioBarClosed(BarClosedEventArgs args) {
  if(orderProtection.Halted)return;
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
   var observedUtc=DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
   var currentOpenTime=DateTime.SpecifyKind(closedOpenTime.AddMinutes(BarMinutes),DateTimeKind.Utc);
   // A weekend/reconnect tick can close the last OLD session bar. That bar
   // is not a fresh decision, even if its predecessor was contiguous.
   if(observedUtc>=currentOpenTime.AddMinutes(BarMinutes)) {
    kernel.Reset();causalIntents[instrumentName].Clear();
    Print("MXM_DELAYED_BAR_EXPIRED_COLD_REWARM_"+instrumentName);return;
   }
   bool contiguous=(series.OpenTimes.Last(0)-series.OpenTimes.Last(1)).TotalMinutes==BarMinutes;
   if(!contiguous)kernel.Reset();
   // Bars.BarClosed excludes the newly opened bar; Last(0) IS the closed one.
   // No historical warm-start or double-processed boundary tick.
   int desired=kernel.OnCompletedBar((decimal)series.ClosePrices.Last(0));
   // Publish only. The tick delivering this callback must not execute its signal.
   // UTC is the robot's declared clock; cTrader DateTime Kind is normalized here.
   var fence=brokerIntentFences[instrumentName];
   fence.Observe(BrokerPositionId(instrumentName),observedUtc);
   causalIntents[instrumentName].Publish(desired,contiguous,kernel.CompletedBars,
    DateTime.SpecifyKind(currentOpenTime,DateTimeKind.Utc),observedUtc,BarMinutes);
   // A stop notification before BarClosed must also suppress a new publication
   // for that same boundary; the next genuinely new bar may proceed normally.
   if(!fence.CanPublish(currentOpenTime))causalIntents[instrumentName].Clear();
  } catch(Exception e) {
   Print("MXM_PORTFOLIO_CALLBACK_UNVERIFIED_SAFE_STOP_"+e.GetType().Name);
   Stop();
  } finally {sequencer.Exit();}
 }
 void OnPortfolioTick(SymbolTickEventArgs args) {
  if(orderProtection.Halted)return;
  if(!causalIntents.TryGetValue(args.SymbolName,out var queue))return;
  bool acquired=false;
  try {
   var quoteUtc=DateTime.SpecifyKind(Server.TimeInUtc,DateTimeKind.Utc);
   if(!double.IsFinite(args.Bid) || !double.IsFinite(args.Ask) ||
      args.Bid<=0 || args.Ask<args.Bid)return;
   if(applyingDecision){Print("MXM_REENTRANT_EXECUTION_SAFE_STOP");Stop();return;}
   var fence=brokerIntentFences[args.SymbolName];
   // The book may have changed before its Closed callback is dispatched.
   fence.Observe(BrokerPositionId(args.SymbolName),quoteUtc);
   var lease=fence.Capture();
   if(!queue.TryConsume(quoteUtc,out var intent))return;
   applyingDecision=true;acquired=true;
   // Consumed BEFORE broker calls. A rejected or unknown result cannot retry
   // the same intent on every tick or fabricate a broker fill.
   ApplyPortfolioDecision(args.Symbol,args.SymbolName,intent!.Desired,
    intent.Contiguous,intent.CompletedBars,intent.BoundaryUtc,lease);
  } catch(Exception e) {
   Print("MXM_PORTFOLIO_TICK_UNVERIFIED_SAFE_STOP_"+e.GetType().Name);Stop();
  } finally {if(acquired)applyingDecision=false;}
 }
 void ApplyPortfolioDecision(Symbol instrument,string instrumentName,int desired,
  bool contiguous,int completedBars,DateTime currentOpenTime,MxmBrokerDecisionLease lease) {
  bool simulation=IsBacktesting;
  if(!(simulation || (EnableDemoTrading && !Account.IsLive)) || !instrument.MarketHours.IsOpened())return;
  var fence=brokerIntentFences[instrumentName];
  if(!fence.IsCurrent(lease,BrokerPositionId(instrumentName),BrokerClock()))return;
  var owned=Positions.FindAll(Label,instrumentName);
  if(owned.Length>1){Print("MXM_MULTIPLE_POSITIONS_SAFE_HOLD");return;}
  TradeType direction=desired>0?TradeType.Buy:TradeType.Sell;
  if(owned.Length==1){
   var current=owned[0];
   string? exitReason=MxmExitPolicy.Reason(exitMode,desired,
    current.TradeType==TradeType.Buy?1:-1,contiguous,completedBars,
    DateTime.SpecifyKind(currentOpenTime,DateTimeKind.Utc),
    DateTime.SpecifyKind(current.EntryTime,DateTimeKind.Utc),BarMinutes);
   if(exitReason==null)return;
   if(exitReason!="REVERSAL") {
    var closed=ClosePosition(current);
    if(!closed.IsSuccessful)Print("MXM_POLICY_EXIT_FAILED_SAFE_HOLD");
    return; // No entry following a discretionary policy exit on this intent.
   }
   if(!fence.BeginReversal(lease,current.Id,BrokerPositionId(instrumentName),BrokerClock()))return;
   var result=ClosePosition(current);
   // A successful call alone cannot certify whether a concurrent broker stop
   // closed the position. Require the matching Closed event and identity.
   if(!fence.FinishReversal(lease,current.Id,result.IsSuccessful,result.Position?.Id,
      BrokerPositionId(instrumentName),BrokerClock(),out var continuation)) {
    Print("MXM_REVERSAL_CLOSE_UNRECONCILED_NO_SAME_INTENT_ENTRY");return;
   }
   lease=continuation!;
  }
  if(desired==0)return;
  if(!double.IsFinite(RequestedUnits) || RequestedUnits<=0)return;
  double stopPips=StopLossPips,pipSize=instrument.PipSize,tickSize=instrument.TickSize;
  // The caller's requested units form a CAP. Search the broker lattice within
  // that cap BEFORE committing an irreversible durable pending order intent.
  double units=SelectAffordableNativeUnits(instrument,direction,RequestedUnits,stopPips);
  if(!double.IsFinite(units) || units<=0 || units>instrument.VolumeInUnitsMax)return;
  var beforeIds=Positions.Select(x=>(long)x.Id).OrderBy(x=>x).ToArray();
  if(confirmedEntries==null || !confirmedEntries.VerifyCurrent(BrokerClock()) ||
     entryCheckpoint==null || !entryCheckpoint.PrepareRecoverable(instrumentName,desired>0?1:-1,currentOpenTime,
      BrokerClock(),currentOpenTime.AddMinutes(BarMinutes),Label,units,stopPips,pipSize,tickSize,beforeIds)) {
   orderProtection.HaltUnknown();LatchProtectionHalt();return;
  }
  bool brokerAttempted=false;
  try {
  // All account/risk snapshots are taken AFTER the potentially slow durable write.
  // Inspect actual broker minimum/step/margin; do not assume EUR200 volume feasibility.
  // Read one estimated account observation after durable preparation.
  double initialEquity=Account.Equity,initialFreeMargin=Account.FreeMargin;
  if(!double.IsFinite(initialEquity)||!double.IsFinite(initialFreeMargin)||
     initialEquity<=0||initialFreeMargin<=0||Account.Asset.Name!="EUR")return;
  // This is an account-wide snapshot, not atomic inter-instance order locking.
  // Broker book (all symbols using this MXM label), not local kernel memory, is authoritative.
  int accountOwned=Positions.FindAll(Label).Length;
  int allAccountPositions=0;
  foreach(var accountPosition in Positions)allAccountPositions++;
  int accountPendingOrders=0;
  foreach(var brokerPendingOrder in PendingOrders)accountPendingOrders++;
  // The capital is unique and continuously shared. No new order can be
  // admitted while an unowned position or any broker pending order can
  // change exposure behind this robot's account-wide budget. Owned exits
  // above remain permitted, to reduce risk rather than seize foreign trades.
  string isolation=MxmAccountIsolation.Check(
   allAccountPositions,accountOwned,accountPendingOrders);
  if(isolation!=MxmAccountIsolation.Admit){
   Print("MXM_SHARED_ACCOUNT_ISOLATION_HOLD_"+isolation);return;
  }
  // This is a broker snapshot, NOT an atomic inter-instance lease.
  if(!double.IsFinite(initialEquity)||!double.IsFinite(initialFreeMargin)||
     !double.IsFinite(MaxMarginFraction)||!double.IsFinite(MinimumFreeMarginReserveEur)||
     MinimumFreeMarginReserveEur<0)return;
  double currentUnits=instrument.NormalizeVolumeInUnits(units,RoundingMode.Down);
  if(!double.IsFinite(currentUnits) || currentUnits!=units || units>instrument.VolumeInUnitsMax ||
     StopLossPips!=stopPips || instrument.PipSize!=pipSize || instrument.TickSize!=tickSize)return;
  double margin=instrument.GetEstimatedMargin(direction,units);
  if(!double.IsFinite(margin)||margin<=0)return;
  // Native symbol properties are observed NOW; no unsupported historic terms or
  // assumed zero entry fee. FX via AssetConverter is an estimate, not an exact
  // future fee or independent timestamped loss-side price.
  double feeBookBid=instrument.Bid,feeBookAsk=instrument.Ask;
  var feeType=instrument.CommissionType;
  var feeMinimumType=instrument.MinCommissionType;
  double feeRate=instrument.Commission,feeMinimum=instrument.MinCommission;
  long feeLotSize=instrument.LotSize;
  string feeQuoteAsset=instrument.QuoteAsset?.Name??"";
  string feeMinimumAsset=instrument.MinCommissionAsset?.Name??"";
  MxmNativeCommissionEstimate nativeFee;
  try {nativeFee=CurrentNativeCommission(instrument,units,feeBookBid,feeBookAsk);}
  catch(Exception e){
   Print("MXM_NATIVE_FEE_UNVERIFIED_SAFE_HOLD_"+e.GetType().Name);return;
  }
  if((decimal)EstimatedRoundTripFrictionReserveEur<nativeFee.RoundTripReserveEur) {
   Print("MXM_NATIVE_FEE_EXCEEDS_DECLARED_FRICTION_RESERVE_HOLD");return;
  }
  string admit=MxmCapitalAdmission.Check((decimal)initialEquity,(decimal)initialFreeMargin,
    (decimal)margin,nativeFee.PerSideCeilingEur,(decimal)MaxMarginFraction,(decimal)MinimumFreeMarginReserveEur,
    accountOwned,MaxMxmAccountPositions);
  // No claim that API-estimated commission equals an eventual broker charge.
  if(admit!=MxmCapitalAdmission.Admit){Print("MXM_CAPITAL_HOLD_"+admit);return;}
  // Complete-account MXM estimated stop exposure. Do not interpret a stop
  // as a maximum loss, or this snapshot as an atomic inter-cBot lock.
  if(!double.IsFinite(MaxEstimatedMxmStopRiskPercent) ||
     MaxEstimatedMxmStopRiskPercent<=0 || MaxEstimatedMxmStopRiskPercent>100 ||
     !double.IsFinite(EstimatedRoundTripFrictionReserveEur) ||
     EstimatedRoundTripFrictionReserveEur<0 || stopPips<=0) {
    Print("MXM_STOP_RISK_INPUT_UNVERIFIED_SAFE_HOLD");return;
  }
  double newStopRisk=instrument.AmountRisked(units,stopPips);
  if(!double.IsFinite(newStopRisk)||newStopRisk<=0) {
    Print("MXM_NEW_STOP_RISK_UNVERIFIED_SAFE_HOLD");return;
  }
  // Freeze the exact owned position identities/stop/volume/other-symbol marks
  // BEFORE any risk computation; order book IDs alone cannot detect a changed stop.
  var originalRiskBook=CaptureNativeRiskBook();
  double existingRisk=0;
  int protectedExisting=0;
  foreach(var active in Positions.FindAll(Label)) {
   // No new orders if ANY existing MXM position has no broker stop
   // or if its symbol/volume/pip geometry cannot be validated.
   if(!active.StopLoss.HasValue || !double.IsFinite(active.StopLoss.Value) ||
      !double.IsFinite(active.EntryPrice) || !double.IsFinite(active.VolumeInUnits) ||
      !double.IsFinite(active.Symbol.Bid) || !double.IsFinite(active.Symbol.Ask) ||
      !double.IsFinite(active.Symbol.PipSize) || active.Symbol.PipSize<=0 ||
      active.EntryPrice<=0 || active.VolumeInUnits<=0) {
    Print("MXM_EXISTING_STOP_UNVERIFIED_SAFE_HOLD");return;
   }
   // Account.Equity already includes floating PnL. Estimate its potential
   // drawdown to the stop from the CURRENT BID (long) / ASK (short).
   string geometry=MxmStopRiskGeometry.TryDistance(active.TradeType==TradeType.Buy?1:-1,
    (decimal)active.Symbol.Bid,(decimal)active.Symbol.Ask,(decimal)active.StopLoss.Value,
    (decimal)active.Symbol.PipSize,out var currentDistancePips);
   if(geometry!=MxmStopRiskGeometry.Valid) {
    Print("MXM_EXISTING_MARK_TO_STOP_HOLD_"+geometry);return;
   }
   double distancePips=(double)currentDistancePips;
   if(!double.IsFinite(distancePips)||distancePips<0) {
    Print("MXM_EXISTING_STOP_DISTANCE_UNVERIFIED_SAFE_HOLD");return;
   }
   double risk=active.Symbol.AmountRisked(active.VolumeInUnits,distancePips);
   if(!double.IsFinite(risk)||risk<0) {
    Print("MXM_EXISTING_STOP_RISK_UNVERIFIED_SAFE_HOLD");return;
   }
   existingRisk+=risk;
   protectedExisting++;
   if(!double.IsFinite(existingRisk)) {
    Print("MXM_EXISTING_STOP_RISK_SUM_UNVERIFIED_SAFE_HOLD");return;
   }
  }
  if(!originalRiskBook.SequenceEqual(CaptureNativeRiskBook())) {
   Print("MXM_RISK_BOOK_CHANGED_DURING_ESTIMATE_HOLD");return;
  }
  string stopRiskGate=MxmStopRiskAdmission.Check(
   (decimal)initialEquity,(decimal)existingRisk,(decimal)newStopRisk,
   (decimal)(MaxEstimatedMxmStopRiskPercent/100.0),
   (decimal)EstimatedRoundTripFrictionReserveEur,
   (decimal)EstimatedRoundTripFrictionReserveEur*protectedExisting);
  if(stopRiskGate!=MxmStopRiskAdmission.Admit) {
   Print("MXM_ACCOUNT_STOP_RISK_HOLD_"+stopRiskGate);return;
  }
  // Immutable OWNER absolute limits supplement configured percent/reserve.
  // Native observed fees are estimates, not actual future fill charges;
  // EUR120 reserve and EUR2 proposed risk remain estimates, not guarantees.
  string ownerEnvelope=MxmOwnerEntryEnvelope.Check(
   (decimal)initialFreeMargin,(decimal)margin,nativeFee.PerSideCeilingEur,(decimal)newStopRisk,
   (decimal)EstimatedRoundTripFrictionReserveEur);
  if(ownerEnvelope!=MxmOwnerEntryEnvelope.Admit) {
   Print("MXM_OWNER_ENTRY_ENVELOPE_HOLD_"+ownerEnvelope);return;
  }
  // Last local admission check, after all expensive risk/margin calculations.
  // This does not make the broker check+order atomic or lock other instances.
  var finalClock=BrokerClock();
  if(!fence.IsCurrent(lease,BrokerPositionId(instrumentName),finalClock) ||
     finalClock<currentOpenTime || finalClock>=currentOpenTime.AddMinutes(BarMinutes)) {
   Print("MXM_BROKER_BOOK_CHANGED_OR_EXPIRED_NO_STALE_INTENT_ENTRY");return;
  }
  if(instrument.Bid!=feeBookBid || instrument.Ask!=feeBookAsk ||
     instrument.CommissionType!=feeType || instrument.Commission!=feeRate ||
     instrument.MinCommissionType!=feeMinimumType ||
     instrument.MinCommission!=feeMinimum || instrument.LotSize!=feeLotSize ||
     (instrument.QuoteAsset?.Name??"")!=feeQuoteAsset ||
     (instrument.MinCommissionAsset?.Name??"")!=feeMinimumAsset) {
   Print("MXM_NATIVE_FEE_SNAPSHOT_CHANGED_BEFORE_ORDER_HOLD");return;
  }
  // A slow durable/risk path can outlive a cost-FX snapshot. Reprice the
  // advertised symbol and conversion just before submission; any increased
  // fee would invalidate the earlier cash reserve and is never silently used.
  try {
   var latestFee=CurrentNativeCommission(instrument,units,feeBookBid,feeBookAsk);
   if(!MxmNativeCommission.StillCovered(nativeFee,latestFee)) {
    Print("MXM_NATIVE_FEE_INCREASED_BEFORE_ORDER_HOLD");return;
   }
  }catch(Exception e) {
   Print("MXM_NATIVE_FEE_RECHECK_UNVERIFIED_HOLD_"+e.GetType().Name);return;
  }
  if(!originalRiskBook.SequenceEqual(CaptureNativeRiskBook())) {
   Print("MXM_RISK_BOOK_CHANGED_BEFORE_SUBMISSION_HOLD");return;
  }
  double finalEquity=Account.Equity,finalFreeMargin=Account.FreeMargin;
  double finalMargin=instrument.GetEstimatedMargin(direction,units);
  double finalNewStopRisk=instrument.AmountRisked(units,stopPips);
  if(!double.IsFinite(finalEquity)||!double.IsFinite(finalFreeMargin)||
     !double.IsFinite(finalMargin)||!double.IsFinite(finalNewStopRisk)) {
   Print("MXM_FINAL_ACCOUNT_OBSERVATION_UNVERIFIED_HOLD");return;
  }
  string finalAccount=MxmNativeFinalAccountFence.Check(
   new MxmNativeEntrySnapshot((decimal)initialEquity,(decimal)initialFreeMargin,(decimal)margin,(decimal)newStopRisk),
   new MxmNativeEntrySnapshot((decimal)finalEquity,(decimal)finalFreeMargin,(decimal)finalMargin,(decimal)finalNewStopRisk));
  if(finalAccount!=MxmNativeFinalAccountFence.Admit) {
   Print("MXM_FINAL_ACCOUNT_CHANGE_HOLD_"+finalAccount);return;
  }
  if(!Positions.Select(x=>(long)x.Id).OrderBy(x=>x).SequenceEqual(beforeIds) || PendingOrders.Count!=0) {
   Print("MXM_ACCOUNT_BOOK_CHANGED_AFTER_DURABLE_PREPARE_NO_ENTRY");return;
  }
  string? requestComment=entryCheckpoint.SubmissionComment;
  if(requestComment==null) {orderProtection.HaltUnknown();LatchProtectionHalt();return;}
  TradeResult placed;
  if(orderProtection.Halted || !entryCheckpoint.MarkSubmitted()) {
   orderProtection.HaltUnknown();LatchProtectionHalt();return;
  }
  brokerAttempted=true; // Durable pending marker exists BEFORE this side effect.
  try {placed=ExecuteMarketOrder(direction,instrumentName,units,Label,stopPips,null,requestComment);}
  catch(Exception e) {
   orderProtection.HaltUnknown();
   LatchProtectionHalt();
   Print("MXM_ORDER_CALL_EXCEPTION_UNKNOWN_OUTCOME_HALTED_"+e.GetType().Name);
   return; // No returned identity: never infer which broker position to close.
  }
  Print("MXM_ORDER_CALL_RETURNED fenceRevision={0} intentBoundary={1:O} symbol={2} success={3}",
   lease.Revision,currentOpenTime,instrumentName,placed.IsSuccessful);
  var protection=orderProtection.Reconcile(placed.IsSuccessful,placed.Position?.Id,
   Label,instrumentName,desired>0?1:-1,units,stopPips,pipSize,tickSize,
   beforeIds,ProtectionBook());
  Print("MXM_ORDER_PROTECTION_"+protection.Reason);
  if(protection.Halt) {
   LatchProtectionHalt();
  }else if(!protection.Accepted) {
   // An unsuccessful API result plus an empty book is not a durable negative ACK.
   // Keep PENDING rather than assume the request cannot have reached the broker.
   orderProtection.HaltUnknown();LatchProtectionHalt();
   Print("MXM_UNSUCCESSFUL_ORDER_REQUIRES_RECONCILIATION_NO_CHECKPOINT_CLEAR");
  }else if(!RecordProtectedEntry(placed.Position!)) {
   // Keep the pre-call pending marker if a confirmed entry cannot be saved.
   // No successful READY transition may outrun this durable lower-bound ledger.
   orderProtection.HaltUnknown();LatchProtectionHalt();
   Print("MXM_CONFIRMED_ENTRY_PERSISTENCE_FAILED_PENDING_RETAINED");
  }else if(!entryCheckpoint.CompleteReconciled()) {
   orderProtection.HaltUnknown();LatchProtectionHalt();
  }
  } finally {
   if(!brokerAttempted && !orderProtection.Halted && !entryCheckpoint.CompleteNotSubmitted()) {
    orderProtection.HaltUnknown();LatchProtectionHalt();
   }
  }
 }
 // Sample all relevant existing-position risk inputs; a same-ID position can
 // change stop/size/marks during the durable admission path.
 sealed record NativeRiskMark(long Id,string Symbol,TradeType Side,double Units,
  double EntryPrice,double? StopLoss,double Bid,double Ask,double PipSize,double TickSize);
 NativeRiskMark[] CaptureNativeRiskBook()=>Positions.FindAll(Label)
  .Select(x=>new NativeRiskMark(x.Id,x.SymbolName,x.TradeType,x.VolumeInUnits,
    x.EntryPrice,x.StopLoss,x.Symbol.Bid,x.Symbol.Ask,x.Symbol.PipSize,x.Symbol.TickSize))
  .OrderBy(x=>x.Id).ToArray();
 // The preliminary broker-lattice choice is NOT admission and has no side
 // effect. Its selected volume MUST be independently revalidated after the
 // durable prepared intent, with the unchanged original complete-account gates.
 double SelectAffordableNativeUnits(Symbol symbol,TradeType direction,
  double requested,double stopPips) {
  if(!double.IsFinite(requested)||!double.IsFinite(stopPips)||stopPips<=0 ||
     !double.IsFinite(symbol.VolumeInUnitsMin)||!double.IsFinite(symbol.VolumeInUnitsMax)||
     !double.IsFinite(symbol.VolumeInUnitsStep)||
     !double.IsFinite(Account.Equity)||!double.IsFinite(Account.FreeMargin)||
     !double.IsFinite(MaxMarginFraction)||!double.IsFinite(MaxEstimatedMxmStopRiskPercent)||
     !double.IsFinite(MinimumFreeMarginReserveEur)||
     !double.IsFinite(EstimatedRoundTripFrictionReserveEur) ||
     Account.Asset.Name!="EUR" ||
     requested<symbol.VolumeInUnitsMin || Account.Equity<=0 ||
     Account.FreeMargin<=0 || MaxEstimatedMxmStopRiskPercent<=0 ||
     MaxEstimatedMxmStopRiskPercent>100 || EstimatedRoundTripFrictionReserveEur<0)
   return 0d;
  try {
   decimal equity=(decimal)Account.Equity,free=(decimal)Account.FreeMargin;
   decimal friction=(decimal)EstimatedRoundTripFrictionReserveEur;
   decimal riskPercent=(decimal)(MaxEstimatedMxmStopRiskPercent/100.0);
   int owned=Positions.FindAll(Label).Length;
   decimal? chosen=MxmNativeVolumeSearch.LargestAffordable(
     (decimal)symbol.VolumeInUnitsMin,(decimal)symbol.VolumeInUnitsMax,
     (decimal)symbol.VolumeInUnitsStep,(decimal)requested,amount=>{
    try {
     double candidate=(double)amount;
     double normalized=symbol.NormalizeVolumeInUnits(candidate,RoundingMode.Down);
     if(!double.IsFinite(normalized)||normalized!=candidate ||
        candidate<symbol.VolumeInUnitsMin || candidate>symbol.VolumeInUnitsMax)
      return false;
     double margin=symbol.GetEstimatedMargin(direction,candidate);
     double risk=symbol.AmountRisked(candidate,stopPips);
     if(!double.IsFinite(margin)||!double.IsFinite(risk)||margin<=0||risk<=0)
      return false;
     var fee=CurrentNativeCommission(symbol,candidate,symbol.Bid,symbol.Ask);
     if(friction<fee.RoundTripReserveEur)return false;
     if(MxmCapitalAdmission.Check(equity,free,(decimal)margin,fee.PerSideCeilingEur,
       (decimal)MaxMarginFraction,(decimal)MinimumFreeMarginReserveEur,
       owned,MaxMxmAccountPositions)!=MxmCapitalAdmission.Admit)return false;
     if(MxmStopRiskAdmission.Check(equity,0m,(decimal)risk,riskPercent,
       friction,0m)!=MxmStopRiskAdmission.Admit)return false;
     return MxmOwnerEntryEnvelope.Check(free,(decimal)margin,
       fee.PerSideCeilingEur,(decimal)risk,friction)==MxmOwnerEntryEnvelope.Admit;
    }catch(Exception){return false;}
   });
   if(!chosen.HasValue) {
    Print("MXM_NO_BROKER_LATTICE_VOLUME_ADMISSIBLE_WITH_CURRENT_FEES_AND_CAPITAL");
    return 0d;
   }
   return (double)chosen.Value;
  }catch(Exception e) {
   Print("MXM_NATIVE_VOLUME_SEARCH_UNVERIFIED_HOLD_"+e.GetType().Name);
   return 0d;
  }
 }
 // Never infer asset names from ticker substrings or hardcode EURUSD.
 decimal CostRate(string from,string to) {
  if(string.IsNullOrWhiteSpace(from) || string.IsNullOrWhiteSpace(to))
   throw new ArgumentException("NATIVE_COST_ASSET_MISSING");
  if(from==to)return 1m;
  double converted=AssetConverter.Convert(1d,from,to);
  if(!double.IsFinite(converted)||converted<=0d)
   throw new ArgumentException("NATIVE_COST_FX_UNAVAILABLE");
  return checked((decimal)converted);
 }
 MxmNativeCommissionEstimate CurrentNativeCommission(Symbol instrument,
  double volume,double bid,double ask) {
  if(!double.IsFinite(volume)||!double.IsFinite(bid)||!double.IsFinite(ask) ||
    !double.IsFinite(instrument.Commission)||!double.IsFinite(instrument.MinCommission))
   throw new ArgumentException("NATIVE_FEE_UNVERIFIED_AMOUNT");
  int kind=instrument.CommissionType switch {
   SymbolCommissionType.UsdPerMillionUsdVolume=>0,
   SymbolCommissionType.UsdPerOneLot=>1,
   SymbolCommissionType.PercentageOfTradingVolume=>2,
   SymbolCommissionType.QuoteCurrencyPerOneLot=>3,
   _=>throw new ArgumentException("NATIVE_FEE_UNKNOWN_TYPE")
  };
  int minKind=instrument.MinCommissionType switch {
   SymbolMinCommissionType.Asset=>0,
   SymbolMinCommissionType.QuoteAsset=>1,
   _=>throw new ArgumentException("NATIVE_FEE_UNKNOWN_MINIMUM_TYPE")
  };
  string quoteAsset=instrument.QuoteAsset?.Name??"";
  string minimumAsset=minKind==0?instrument.MinCommissionAsset?.Name??"":quoteAsset;
  var terms=new MxmNativeCommissionTerms(kind,minKind,quoteAsset,minimumAsset,
   checked((decimal)instrument.Commission),checked((decimal)instrument.MinCommission),
   (decimal)instrument.LotSize);
  decimal qUsd=kind==0 && terms.Commission>0m?CostRate(quoteAsset,"USD"):0m;
  decimal usdEur=(kind==0 || kind==1) && terms.Commission>0m?CostRate("USD","EUR"):0m;
  decimal qEur=((kind==2 || kind==3) && terms.Commission>0m ||
    minKind==1 && terms.Minimum>0m)?CostRate(quoteAsset,"EUR"):0m;
  decimal minEur=minKind==0 && terms.Minimum>0m?CostRate(minimumAsset,"EUR"):0m;
  return MxmNativeCommission.Price(terms,checked((decimal)volume),
   checked((decimal)bid),checked((decimal)ask),qUsd,usdEur,qEur,minEur);
 }
 string? ReadEntryCheckpoint() {
  CheckEntryStorage();LocalStorage.Reload(LocalStorageScope.Type);CheckEntryStorage();
  string? value=LocalStorage.GetString(entryCheckpoint!.StorageKey,LocalStorageScope.Type);
  CheckEntryStorage();return value;
 }
 void WriteEntryCheckpoint(string value) {
  CheckEntryStorage();LocalStorage.SetString(entryCheckpoint!.StorageKey,value,LocalStorageScope.Type);
  CheckEntryStorage();LocalStorage.Flush(LocalStorageScope.Type);CheckEntryStorage();
 }
 string? ReadConfirmedEntries() {
  CheckEntryStorage();LocalStorage.Reload(LocalStorageScope.Type);CheckEntryStorage();
  string? value=LocalStorage.GetString(confirmedEntries!.StorageKey,LocalStorageScope.Type);
  CheckEntryStorage();return MxmConfirmedEntryLedger.NormalizeNativeRead(value);
 }
 void WriteConfirmedEntries(string value) {
  CheckEntryStorage();LocalStorage.SetString(confirmedEntries!.StorageKey,value,LocalStorageScope.Type);
  CheckEntryStorage();LocalStorage.Flush(LocalStorageScope.Type);CheckEntryStorage();
 }
 bool RecordProtectedEntry(Position position) {
  if(confirmedEntries==null || !confirmedEntries.RecordConfirmed(new MxmConfirmedEntry(
    position.Id,position.SymbolName,position.TradeType==TradeType.Buy?1:-1,
    (decimal)position.VolumeInUnits,DateTime.SpecifyKind(position.EntryTime,DateTimeKind.Utc),BrokerClock())))return false;
  ReportRecordedWeeks();return !confirmedEntries.Halted && !entryStorageFault;
 }
 void ReportRecordedWeeks() {
  if(confirmedEntries==null)return;
  // Calendar completeness never asserts broker-history coverage or native reception.
  // Backtesting uses a fresh isolated memory ledger, never a real execution claim.
  Print("MXM_RECORDED_PROTECTED_ENTRY_LOWER_BOUND simulation={0} weeks={1}",IsBacktesting,
   System.Text.Json.JsonSerializer.Serialize(confirmedEntries.Snapshot(BrokerClock())));
 }
 void CheckEntryStorage() {
  if(entryStorageFault)throw new InvalidOperationException("ENTRY_STORAGE_CALLBACK_FAULT");
 }
 protected override void OnException(Exception exception) {
  // LocalStorage can notify OnException instead of throwing at the call site.
  // Poison first; a matching memory echo must never erase this fault.
  if(entryStorageFault)return; // Avoid recursive failure while stopping an already poisoned instance.
  entryStorageFault=true;entryCheckpoint?.Halt();orderProtection.HaltUnknown();
  confirmedEntries?.Halt();
  foreach(var intent in causalIntents.Values)intent.Clear();
  Print("MXM_UNHANDLED_EXCEPTION_ENTRY_CHECKPOINT_SAFE_STOP_"+exception.GetType().Name);Stop();
 }
 void LatchProtectionHalt() {
  entryCheckpoint?.Halt(); // Never clear the durable unresolved attempt, even after flattening.
  confirmedEntries?.Halt();
  foreach(var intent in causalIntents.Values)intent.Clear();
  // Halt stays latched even after successful flattening. No new entry or retry.
  // Timer retries only the attributable returned position, never foreign exposure.
  Timer.Start(TimeSpan.FromSeconds(5));
  TryDefensiveClose();
 }
 MxmEntryRecoveryPosition[] RecoveryBook()=>Positions.Select(x=>new MxmEntryRecoveryPosition(
  new MxmProtectionPosition(x.Id,x.Label,x.SymbolName,x.TradeType==TradeType.Buy?1:-1,
   x.VolumeInUnits,x.EntryPrice,x.StopLoss),x.Comment,
  DateTime.SpecifyKind(x.EntryTime,DateTimeKind.Utc),x.Symbol.PipSize,x.Symbol.TickSize)).ToArray();
 MxmProtectionPosition[] ProtectionBook()=>Positions.Select(x=>new MxmProtectionPosition(
  x.Id,x.Label,x.SymbolName,x.TradeType==TradeType.Buy?1:-1,
  x.VolumeInUnits,x.EntryPrice,x.StopLoss)).ToArray();
 protected override void OnTimer() {
  if(!orderProtection.Halted || applyingDecision)return;
  TryDefensiveClose();
 }
 void TryDefensiveClose() {
  try {
   long? id=orderProtection.DefensiveCloseId(ProtectionBook());
   if(id==null)return; // Ambiguous identity stays halted; no guessed close.
   var candidate=Positions.FirstOrDefault(x=>x.Id==id);
   if(candidate==null)return;
   var result=ClosePosition(candidate);
   bool absent=!Positions.Any(x=>x.Id==id);
   Print("MXM_DEFENSIVE_CLOSE id={0} success={1} absent={2} ADMISSION_REMAINS_HALTED",
    id,result.IsSuccessful,absent);
  } catch(Exception e) {
   Print("MXM_DEFENSIVE_CLOSE_UNVERIFIED_HALTED_"+e.GetType().Name);
  }
 }
}
}

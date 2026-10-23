using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Replay {

// Accounting-only quote stream. Amounts, conversion rates, broker minima,
// margins and costs MUST come from an external, separately authenticated source
// for any claim beyond explicit counterfactual engineering. These are never fills.
public abstract record MxmAccountFeed(DateTime Utc, string Symbol);
// Utc is the ACTUAL time the first next-bar quote was observed and the
// closed bar became actionable. BoundaryUtc is the fixed 5m bucket boundary
// used only for deciding whether consecutive completed bars are contiguous.
// The two clocks MUST NOT be conflated: first-tick arrival has feed jitter.
public sealed record MxmBarClose(
 DateTime Utc, string Symbol, decimal Close, DateTime? BoundaryUtc=null
) : MxmAccountFeed(Utc, Symbol);
public sealed record MxmQuote(
 DateTime Utc, string Symbol, decimal Bid, decimal Ask, decimal QuoteToEur,
 decimal ExecutableUnits, decimal InitialMarginEur, decimal CommissionPerSideEur,
 decimal SlipPerSideQuote, decimal EstimatedStopRiskEur,
 decimal? QuoteLossToEur=null, MxmEurUsdCapturedCosts? CapturedCosts=null,
 decimal? StopDistanceQuote=null
) : MxmAccountFeed(Utc, Symbol);
public sealed record MxmPortfolioTrade(
 string Kind, DateTime Utc, string Symbol, int Direction, decimal Price,
 decimal Units, decimal CashEur, decimal CommissionEur, decimal GrossEur,
 string Reason="LEGACY"
);
public sealed record MxmPortfolioAccountReport(
 string Classification, decimal InitialCapitalEur, decimal FinalCashEur,
 decimal MarkedEquityEur, decimal UsedMarginEur, decimal FreeMarginEur,
 decimal MaxDrawdownEur, int AcceptedEntries, int ExecutedExits,
 int RejectedEntries, int OpenPositions, int CompleteIsoUtcWeeks,
 bool Hard21Proven, bool BrokerFillsProven, bool CostsBrokerVerified,
 Dictionary<string,int> EntriesByIsoWeek,
 IReadOnlyList<MxmPortfolioTrade> Ledger, IReadOnlyList<string> Rejections
);
public sealed record MxmReplayParameters(
 StrategyMode Strategy, decimal MaxMarginFraction,
 int MaxPositions, decimal MinimumFreeMarginReserveEur,
 decimal MaxEstimatedStopRiskFraction, decimal RoundTripRiskReserveEur,
 int BarMinutes=5, int MaxQuoteAgeSeconds=300, ExitMode ExitPolicy=ExitMode.ReverseOnly
);

/// <summary>
/// One actual sequential C# causal strategy kernel per symbol, ONE EUR cash
/// balance, combined floating PnL and margin across all positions.
/// Signals from closed bars may trade ONLY on a STRICTLY LATER broker quote;
/// the same close cannot become an executable fill or a look-ahead price.
/// Optional fixed stop triggers model first observed BID/ASK and adverse slippage.
/// No financing/partial fill/real stop routing or native cTrader fill proof.
/// These omissions are explicit blockers to economic/candidate qualification.
/// </summary>
public sealed class MxmPortfolioAccountReplay {
 sealed class State {
  public readonly MxmDecisionKernel Kernel;
  public DateTime LastBar;
  public DateTime LastQuote;
  public MxmQuote? Latest;
  public readonly MxmCausalIntent Intent=new();
  public State(StrategyMode mode) {Kernel=new MxmDecisionKernel(mode);}
 }
 sealed record Holding(int Direction,decimal Entry,decimal Units,decimal Margin,
  decimal StopRisk,decimal QuoteToEur,DateTime EntryUtc,decimal? StopPrice);
 readonly Dictionary<string,State> state=new(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,Holding> open=new(StringComparer.OrdinalIgnoreCase);
 readonly List<MxmPortfolioTrade> trades=new();
 readonly List<string> rejected=new();
 readonly Dictionary<string,int> entriesByWeek=new();
 readonly MxmReplayParameters parameters;
 decimal balance=200m,peak=200m,drawdown=0m;
 int accepted,exits;
 bool halted;
 public MxmPortfolioAccountReplay(IEnumerable<string> symbols,MxmReplayParameters settings) {
  parameters=settings;
  if(settings.BarMinutes<1 || settings.MaxQuoteAgeSeconds<1 || settings.MaxPositions<1 ||
     settings.MaxMarginFraction<=0 || settings.MaxMarginFraction>1 ||
     settings.MaxEstimatedStopRiskFraction<=0 || settings.MaxEstimatedStopRiskFraction>1 ||
     settings.MinimumFreeMarginReserveEur<0 || settings.RoundTripRiskReserveEur<0 ||
     !Enum.IsDefined(typeof(ExitMode),settings.ExitPolicy))
   throw new ArgumentException("INVALID_EUR200_PORTFOLIO_SETTINGS");
  foreach(var raw in symbols) {
   if(string.IsNullOrWhiteSpace(raw) || !state.TryAdd(raw.Trim(),new State(settings.Strategy)))
    throw new ArgumentException("INVALID_OR_DUPLICATE_SYMBOL");
  }
  if(state.Count==0)throw new ArgumentException("EMPTY_PORTFOLIO");
 }
 static void Need(bool ok,string code) {
  if(!ok)throw new ArgumentException("MXM_PORTFOLIO_REPLAY_"+code);
 }
 static string Week(DateTime utc)=>ISOWeek.GetYear(utc)+"-W"+ISOWeek.GetWeekOfYear(utc).ToString("D2",CultureInfo.InvariantCulture);
 decimal MarkedEquity() {
  decimal value=balance;
  foreach(var pair in open) {
   var tick=state[pair.Key].Latest ?? throw new ArgumentException("MISSING_POSITION_QUOTE");
   var h=pair.Value;
   decimal usd=(h.Direction>0?tick.Bid-h.Entry:h.Entry-tick.Ask)*h.Units;
   value+=ConvertQuote(tick,usd);
  }
  return value;
 }
 decimal Margin()=>open.Values.Sum(x=>x.Margin);
 decimal StopRisk()=>open.Sum(pair=> {
  var h=pair.Value;
  if(h.StopPrice==null)return h.StopRisk; // Explicit legacy estimate retained.
  var q=state[pair.Key].Latest!;
  decimal distance=h.Direction>0 ? q.Bid-h.StopPrice.Value : h.StopPrice.Value-q.Ask;
  // Current equity already includes floating PnL; measure from liquidation mark.
  return ConvertQuote(q,-Math.Max(0m,distance)*h.Units)*-1m;
 });
 static decimal ConvertQuote(MxmQuote quote,decimal amount)=>
  amount*(amount>=0?quote.QuoteToEur:quote.QuoteLossToEur??quote.QuoteToEur);
 static decimal Fee(MxmQuote quote,decimal units,decimal price)=>
  quote.CapturedCosts?.FeeEur(units,price,quote.Bid,quote.Ask)??quote.CommissionPerSideEur;
 void Mark() {
  decimal equity=MarkedEquity();
  if(equity>peak)peak=equity;
  if(peak-equity>drawdown)drawdown=peak-equity;
  if(equity<=0 || equity<Margin()) {
   halted=true;
   rejected.Add("SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT");
  }
 }
 void Exit(string symbol,MxmQuote tick,string reason) {
  var position=open[symbol];
  decimal price=position.Direction>0?tick.Bid-tick.SlipPerSideQuote:tick.Ask+tick.SlipPerSideQuote;
  decimal gross=ConvertQuote(tick,(price-position.Entry)*position.Units*position.Direction);
  decimal fee=Fee(tick,position.Units,price);
  balance+=gross-fee;
  open.Remove(symbol);exits++;
  trades.Add(new MxmPortfolioTrade("EXIT",tick.Utc,symbol,position.Direction,price,
   position.Units,balance,fee,gross,reason));
 }
 void Enter(string symbol,int desired,MxmQuote tick) {
  if(tick.CapturedCosts!=null && !tick.CapturedCosts.Allows(tick.ExecutableUnits)) {
   rejected.Add("REJECT_CAPTURED_VOLUME_LATTICE");return;
  }
  decimal price=desired>0?tick.Ask+tick.SlipPerSideQuote:tick.Bid-tick.SlipPerSideQuote;
  decimal fee=Fee(tick,tick.ExecutableUnits,price);
  // A stop already touched by the entry spread/slippage is not admitted.
  if(tick.StopDistanceQuote is decimal entryDistance &&
     (price-desired*entryDistance<=0 ||
      (desired>0 ? price-entryDistance>=tick.Bid : price+entryDistance<=tick.Ask))) {
   rejected.Add("REJECT_STOP_ALREADY_TOUCHED_AT_ENTRY");return;
  }
  // No admission against absent, future or stale marks on any other open
  // instrument. Broker arrival ordering of same-ms quotes remains unproven.
  foreach(var existing in open.Keys) {
   var latest=state[existing].Latest;
   if(latest==null || latest.Utc>tick.Utc ||
      (tick.Utc-latest.Utc).TotalSeconds>parameters.MaxQuoteAgeSeconds) {
    rejected.Add("REJECT_UNVERIFIED_OR_STALE_ACCOUNT_MARK");
    return;
   }
  }
  var equity=MarkedEquity();
  var free=equity-Margin();
  string isolation=MxmAccountIsolation.Check(open.Count,open.Count,0);
  string admission=isolation==MxmAccountIsolation.Admit ?
   MxmCapitalAdmission.Check(equity,free,tick.InitialMarginEur,fee,
     parameters.MaxMarginFraction,parameters.MinimumFreeMarginReserveEur,open.Count,parameters.MaxPositions)
   : isolation;
  if(admission!=MxmCapitalAdmission.Admit) {rejected.Add(admission);return;}
  string risk=MxmStopRiskAdmission.Check(equity,StopRisk(),
   tick.StopDistanceQuote is decimal stopDistance ?
    -ConvertQuote(tick,-stopDistance*tick.ExecutableUnits) : tick.EstimatedStopRiskEur,
   parameters.MaxEstimatedStopRiskFraction,parameters.RoundTripRiskReserveEur,
   parameters.RoundTripRiskReserveEur*open.Count);
  if(risk!=MxmStopRiskAdmission.Admit){rejected.Add(risk);return;}
  // A quote can never buy from bid or sell from ask. One continuous cash
  // balance pays each explicit entry fee once; spread resides in prices.
  balance-=fee;
  open.Add(symbol,new Holding(desired,price,tick.ExecutableUnits,
   tick.InitialMarginEur,tick.EstimatedStopRiskEur,tick.QuoteToEur,tick.Utc,
   tick.StopDistanceQuote is decimal distance?price-desired*distance:null));
  accepted++;
  string week=Week(tick.Utc);
  entriesByWeek[week]=entriesByWeek.GetValueOrDefault(week)+1;
  trades.Add(new MxmPortfolioTrade("ENTRY",tick.Utc,symbol,desired,price,
   tick.ExecutableUnits,balance,fee,0m));
 }
 public MxmPortfolioAccountReport Run(IEnumerable<MxmAccountFeed> feed) {
  Need(!halted && trades.Count==0 && balance==200m,"REPLAY_NOT_FRESH");
  DateTime last=default;
  foreach(var e in feed) {
   if(e is null)throw new ArgumentException("NULL_PORTFOLIO_FEED_EVENT");
   Need(e.Utc.Kind==DateTimeKind.Utc && e.Utc!=default,"INVALID_UTC");
   Need(e.Utc>=last,"OUT_OF_ORDER_GLOBAL_FEED");
   last=e.Utc;
   if(!state.TryGetValue(e.Symbol,out var st))throw new ArgumentException("UNREGISTERED_SYMBOL");
   if(e is MxmBarClose bar) {
    // A broker's first tick of a new bar does NOT arrive at the exact
    // timestamp of its UTC bucket boundary. Check continuous bar identity
    // against the boundary and execution causality against observed Utc.
    DateTime boundary=bar.BoundaryUtc??bar.Utc;
    Need(boundary.Kind==DateTimeKind.Utc &&
         boundary<=bar.Utc && boundary!=default &&
         (bar.Utc-boundary).TotalMinutes<parameters.BarMinutes &&
         bar.Close>0 && (st!.LastBar==default || boundary>st.LastBar),
         "INVALID_BAR_BOUNDARY_OR_NONCAUSAL_ARRIVAL");
    if(st.LastBar!=default &&
       (boundary-st.LastBar).TotalMinutes!=parameters.BarMinutes)
      st.Kernel.Reset();
    st.LastBar=boundary;
    var signal=st.Kernel.OnCompletedBar(bar.Close);
    // Pending signals never skip execution to reuse an older quote.
    // Replaced intents before a tradable quote are NOT broker executions.
    st.Intent.Publish(signal,true,st.Kernel.CompletedBars,boundary,bar.Utc,parameters.BarMinutes);
    if(st.Kernel.CompletedBars<6)st.Intent.Clear();
   } else if(e is MxmQuote quote) {
    Need(quote.Bid>0 && quote.Ask>=quote.Bid && quote.QuoteToEur>0 &&
      quote.ExecutableUnits>0 && quote.InitialMarginEur>0 &&
      quote.CommissionPerSideEur>=0 && quote.SlipPerSideQuote>=0 &&
      (quote.QuoteLossToEur==null || quote.QuoteLossToEur>=quote.QuoteToEur) &&
      quote.EstimatedStopRiskEur>0 &&
      (quote.StopDistanceQuote==null || quote.StopDistanceQuote>0),"INVALID_EXECUTION_QUOTE");
    Need(quote.CapturedCosts==null || quote.Symbol=="EURUSD","CAPTURED_COSTS_ONLY_EURUSD");
    Need(st!.LastQuote==default || quote.Utc>st.LastQuote,"DUPLICATE_OR_STALE_QUOTE");
    st.Latest=quote;st.LastQuote=quote.Utc;
    // Stop checks do not need a fresh bar intent. Use the FIRST observed
    // executable liquidation side, including a gap, never the requested stop.
    bool stopped=false;
    if(!halted && open.TryGetValue(quote.Symbol,out var protectedPosition) &&
       protectedPosition.StopPrice is decimal stop &&
       (protectedPosition.Direction>0 ? quote.Bid<=stop : quote.Ask>=stop)) {
     Exit(quote.Symbol,quote,"OBSERVED_QUOTE_STOP");
     st.Intent.Clear();stopped=true;
    }
    if(!halted && !stopped && st.Intent.TryConsume(quote.Utc,out var intent)) {
     int signal=intent!.Desired;
     if(open.TryGetValue(quote.Symbol,out var position)) {
      string? reason=MxmExitPolicy.Reason(parameters.ExitPolicy,signal,position.Direction,
       intent.Contiguous,intent.CompletedBars,intent.BoundaryUtc,position.EntryUtc,parameters.BarMinutes);
      if(reason!=null) {
       Exit(quote.Symbol,quote,reason);
       // Only a reversal may admit another position on this consumed intent.
       if(reason=="REVERSAL" && !halted)Enter(quote.Symbol,signal,quote);
      }
     } else if(signal!=0)Enter(quote.Symbol,signal,quote);
    }
   } else throw new ArgumentException("UNRECOGNIZED_PORTFOLIO_EVENT");
   Mark();
   if(halted)break;
  }
  decimal equity=MarkedEquity(),used=Margin();
  return new MxmPortfolioAccountReport(
   "ARTIFICIAL_OR_UNCERTIFIED_QUOTES_SINGLE_ACCOUNT_CAUSAL_DEVELOPMENT_ONLY",
   200m,balance,equity,used,equity-used,drawdown,accepted,exits,
   rejected.Count,open.Count,0,false,false,false,
   new Dictionary<string,int>(entriesByWeek),trades.ToArray(),rejected.ToArray());
 }
}
}

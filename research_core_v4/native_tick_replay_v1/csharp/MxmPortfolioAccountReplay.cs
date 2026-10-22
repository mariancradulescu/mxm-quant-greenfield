using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Mxm.Replay {

// Accounting-only quote stream. Amounts, conversion rates, broker minima,
// margins and costs MUST come from an external, separately authenticated source
// for any claim beyond explicit counterfactual engineering. These are never fills.
public abstract record MxmAccountFeed(DateTime Utc, string Symbol);
public sealed record MxmBarClose(DateTime Utc, string Symbol, decimal Close) : MxmAccountFeed(Utc, Symbol);
public sealed record MxmQuote(
 DateTime Utc, string Symbol, decimal Bid, decimal Ask, decimal QuoteToEur,
 decimal ExecutableUnits, decimal InitialMarginEur, decimal CommissionPerSideEur,
 decimal SlipPerSideQuote, decimal EstimatedStopRiskEur
) : MxmAccountFeed(Utc, Symbol);
public sealed record MxmPortfolioTrade(
 string Kind, DateTime Utc, string Symbol, int Direction, decimal Price,
 decimal Units, decimal CashEur, decimal CommissionEur, decimal GrossEur
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
 int BarMinutes=5
);

/// <summary>
/// One actual sequential C# causal strategy kernel per symbol, ONE EUR cash
/// balance, combined floating PnL and margin across all positions.
/// Signals from closed bars may trade ONLY on a STRICTLY LATER broker quote;
/// the same close cannot become an executable fill or a look-ahead price.
/// No financing/partial fill/real stop routing or native cTrader fill proof.
/// These omissions are explicit blockers to economic/candidate qualification.
/// </summary>
public sealed class MxmPortfolioAccountReplay {
 sealed class State {
  public readonly MxmDecisionKernel Kernel;
  public DateTime LastBar;
  public DateTime LastQuote;
  public MxmQuote? Latest;
  public int? Pending;
  public DateTime PendingAt;
  public State(StrategyMode mode) {Kernel=new MxmDecisionKernel(mode);}
 }
 sealed record Holding(int Direction,decimal Entry,decimal Units,decimal Margin,
  decimal StopRisk,decimal QuoteToEur);
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
  if(settings.BarMinutes<1 || settings.MaxPositions<1 ||
     settings.MaxMarginFraction<=0 || settings.MaxMarginFraction>1 ||
     settings.MaxEstimatedStopRiskFraction<=0 || settings.MaxEstimatedStopRiskFraction>1 ||
     settings.MinimumFreeMarginReserveEur<0 || settings.RoundTripRiskReserveEur<0)
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
   var tick=state[pair.Key].Latest;
   Need(tick!=null,"MISSING_POSITION_QUOTE");
   var h=pair.Value;
   value+=(h.Direction>0?tick.Bid-h.Entry:h.Entry-tick.Ask)*h.Units*tick.QuoteToEur;
  }
  return value;
 }
 decimal Margin()=>open.Values.Sum(x=>x.Margin);
 decimal StopRisk()=>open.Values.Sum(x=>x.StopRisk);
 void Mark() {
  decimal equity=MarkedEquity();
  if(equity>peak)peak=equity;
  if(peak-equity>drawdown)drawdown=peak-equity;
  if(equity<=0 || equity<Margin()) {
   halted=true;
   rejected.Add("SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT");
  }
 }
 void Exit(string symbol,MxmQuote tick) {
  var position=open[symbol];
  decimal price=position.Direction>0?tick.Bid-tick.SlipPerSideQuote:tick.Ask+tick.SlipPerSideQuote;
  decimal gross=(price-position.Entry)*position.Units*tick.QuoteToEur*position.Direction;
  balance+=gross-tick.CommissionPerSideEur;
  open.Remove(symbol);exits++;
  trades.Add(new MxmPortfolioTrade("EXIT",tick.Utc,symbol,position.Direction,price,
   position.Units,balance,tick.CommissionPerSideEur,gross));
 }
 void Enter(string symbol,int desired,MxmQuote tick) {
  var equity=MarkedEquity();
  var free=equity-Margin();
  string isolation=MxmAccountIsolation.Check(open.Count,open.Count,0);
  string admission=isolation==MxmAccountIsolation.Admit ?
   MxmCapitalAdmission.Check(equity,free,tick.InitialMarginEur,tick.CommissionPerSideEur,
     parameters.MaxMarginFraction,parameters.MinimumFreeMarginReserveEur,open.Count,parameters.MaxPositions)
   : isolation;
  if(admission!=MxmCapitalAdmission.Admit) {rejected.Add(admission);return;}
  string risk=MxmStopRiskAdmission.Check(equity,StopRisk(),tick.EstimatedStopRiskEur,
   parameters.MaxEstimatedStopRiskFraction,parameters.RoundTripRiskReserveEur,
   parameters.RoundTripRiskReserveEur*open.Count);
  if(risk!=MxmStopRiskAdmission.Admit){rejected.Add(risk);return;}
  decimal price=desired>0?tick.Ask+tick.SlipPerSideQuote:tick.Bid-tick.SlipPerSideQuote;
  // A quote can never buy from bid or sell from ask. One continuous cash
  // balance pays each explicit entry fee once; spread resides in prices.
  balance-=tick.CommissionPerSideEur;
  open.Add(symbol,new Holding(desired,price,tick.ExecutableUnits,
   tick.InitialMarginEur,tick.EstimatedStopRiskEur,tick.QuoteToEur));
  accepted++;
  string week=Week(tick.Utc);
  entriesByWeek[week]=entriesByWeek.GetValueOrDefault(week)+1;
  trades.Add(new MxmPortfolioTrade("ENTRY",tick.Utc,symbol,desired,price,
   tick.ExecutableUnits,balance,tick.CommissionPerSideEur,0m));
 }
 public MxmPortfolioAccountReport Run(IEnumerable<MxmAccountFeed> feed) {
  Need(!halted && trades.Count==0 && balance==200m,"REPLAY_NOT_FRESH");
  DateTime last=default;
  foreach(var e in feed) {
   Need(e!=null && e.Utc.Kind==DateTimeKind.Utc && e.Utc!=default,"INVALID_UTC");
   Need(e.Utc>=last,"OUT_OF_ORDER_GLOBAL_FEED");
   last=e.Utc;
   Need(state.TryGetValue(e.Symbol,out var st),"UNREGISTERED_SYMBOL");
   if(e is MxmBarClose bar) {
    Need(bar.Close>0 && (st!.LastBar==default || bar.Utc>st.LastBar),"INVALID_BAR");
    if(st.LastBar!=default && (bar.Utc-st.LastBar).TotalMinutes!=parameters.BarMinutes)st.Kernel.Reset();
    st.LastBar=bar.Utc;
    var signal=st.Kernel.OnCompletedBar(bar.Close);
    // Pending signals never skip execution to reuse an older quote.
    // Replaced intents before a tradable quote are NOT broker executions.
    st.Pending=st.Kernel.CompletedBars>=6?signal:null;
    st.PendingAt=bar.Utc;
   } else if(e is MxmQuote quote) {
    Need(quote.Bid>0 && quote.Ask>=quote.Bid && quote.QuoteToEur>0 &&
      quote.ExecutableUnits>0 && quote.InitialMarginEur>0 &&
      quote.CommissionPerSideEur>=0 && quote.SlipPerSideQuote>=0 &&
      quote.EstimatedStopRiskEur>0,"INVALID_EXECUTION_QUOTE");
    Need(st!.LastQuote==default || quote.Utc>st.LastQuote,"DUPLICATE_OR_STALE_QUOTE");
    st.Latest=quote;st.LastQuote=quote.Utc;
    if(st.Pending.HasValue && quote.Utc>st.PendingAt && !halted) {
     int signal=st.Pending.Value;
     st.Pending=null;
     if(open.TryGetValue(quote.Symbol,out var position)) {
      // This model deliberately matches the product's default ReverseOnly
      // policy, not unimplemented cTrader stop/horizon/neutral behavior.
      if(signal!=0 && signal!=position.Direction) {
       Exit(quote.Symbol,quote);
       if(!halted)Enter(quote.Symbol,signal,quote);
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

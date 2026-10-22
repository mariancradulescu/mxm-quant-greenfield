using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mxm.Replay;

record Quote(long T,string Side,long Raw);
sealed class Position {
 public int Direction; public long OpenT;public decimal OpenPrice;
}
sealed class Replay {
 readonly long BarMs;
 readonly StrategyMode family;
 readonly ExitMode exitPolicy;
 readonly MxmDecisionKernel kernel;
 readonly bool synthetic,scenario;
 bool Simulated=>synthetic||scenario;
 decimal Fx=>scenario?1m/1.10m:1m;
 readonly decimal slippage, commission, extraHalfSpread, margin, maxMarginFraction;
 readonly int stopPips;
 decimal Slippage=>slippage;
 decimal PriceUnits=>1000m;
 decimal ExecutionFriction=>slippage+extraHalfSpread;
 readonly List<object> trades=new(),equityPath=new(),signals=new();
 long lastT=-1,bidAt=-1,askAt=-1,barStart=-1;
 decimal bid,ask,closeOfBar,realized=200m,peak=200m,maxDrawdown=0m,totalCosts=0m;
 int pendingSignal,ambiguousGroups,gapBars,invalidSnapshots,entries,exits;
 int missingSideSnapshots,crossedSnapshots,staleSnapshots,zeroSpreadSnapshots,crossSideSameMsGroups,stopTriggeredExits,marginHeadroomRejections,neutralPolicyExits,horizonPolicyExits;
 Position? pos;
 public Replay(bool fixture,bool modeledScenario=false,StrategyMode mode=StrategyMode.Adaptive,
   int minutes=5,decimal? slip=null,decimal? fee=null,decimal extraSpread=0m,decimal marginEur=50m,int stopLossPips=0,decimal maxMarginFraction=0.4m,ExitMode exitMode=ExitMode.ReverseOnly){
  if(minutes<1 || marginEur<=0m || extraSpread<0m || stopLossPips<0 || maxMarginFraction<=0m || maxMarginFraction>1m)throw new ArgumentOutOfRangeException();
  synthetic=fixture;scenario=modeledScenario;family=mode;exitPolicy=exitMode;BarMs=checked((long)minutes*60000L);
  slippage=slip??(scenario?0.00002m:0.00001m);
  commission=fee??0.10m;extraHalfSpread=extraSpread/2m;margin=marginEur;stopPips=stopLossPips;this.maxMarginFraction=maxMarginFraction;
  if(slippage<0||commission<0)throw new ArgumentOutOfRangeException();
  kernel=new MxmDecisionKernel(mode);
 }
 static decimal Round(decimal x)=>Math.Round(x,6,MidpointRounding.ToEven);
 decimal Equity(decimal b,decimal a) =>
  realized+(pos is null?0m:pos.Direction*PriceUnits*((pos.Direction==1?b:a)-pos.OpenPrice)*Fx);
 void Mark(long t){
  var current=Equity(bid,ask);if(current>peak)peak=current;
  if(peak-current>maxDrawdown)maxDrawdown=peak-current;
  equityPath.Add(new{timestamp_ms=t,equity_eur=Round(current),balance_eur=Round(realized),margin_eur=pos is null?0m:margin,
   position_direction=pos?.Direction??0,position_open_price=pos is null?(decimal?)null:Round(pos.OpenPrice),
   marked_bid=Round(bid),marked_ask=Round(ask),quote_conversion_eur_per_usd=Fx});
  if(pos is not null && current<=25m)throw new InvalidDataException("SYNTHETIC_STOP_OUT_HALT");
 }
 void Open(long t,int direction) {
  if(pos is not null)throw new InvalidDataException("MARGIN_OR_POSITION");
  // Product adapter's free-margin fraction is configurable, never proof of broker acceptance.
  // This scenario has no other positions; modeled flat free margin equals realized cash.
  if(margin>realized*maxMarginFraction){marginHeadroomRejections++;return;}
  if(Equity(bid,ask)<margin+commission || realized<margin+commission)return; // deterministic skipped order; no invented fill
  decimal price=direction>0?ask+ExecutionFriction:bid-ExecutionFriction;
  pos=new Position{Direction=direction,OpenT=t,OpenPrice=price};
  realized-=commission;totalCosts+=commission+PriceUnits*ExecutionFriction*Fx;entries++;
  trades.Add(new{kind="ENTRY",timestamp_ms=t,direction,price=Round(price),units=1000,
   charged_commission_eur=Round(commission),slippage_eur=Round(PriceUnits*Slippage*Fx),
   additional_spread_scenario_eur=Round(PriceUnits*extraHalfSpread*Fx),quoted_bid=Round(bid),quoted_ask=Round(ask),
   margin_eur=margin,balance_eur=Round(realized)});
 }
 void Close(long t,string reason="REVERSE_SIGNAL") {
  if(pos is null)throw new InvalidDataException("NO_POSITION");
  decimal exit=pos.Direction>0?bid-ExecutionFriction:ask+ExecutionFriction;
  decimal pnl=pos.Direction*PriceUnits*(exit-pos.OpenPrice)*Fx;
  realized+=pnl-commission;totalCosts+=commission+PriceUnits*ExecutionFriction*Fx;exits++;
  trades.Add(new{kind="EXIT",timestamp_ms=t,direction=pos.Direction,price=Round(exit),units=1000,
   gross_price_pnl_eur=Round(pnl),charged_commission_eur=Round(commission),
   slippage_eur=Round(PriceUnits*Slippage*Fx),additional_spread_scenario_eur=Round(PriceUnits*extraHalfSpread*Fx),
   quoted_bid=Round(bid),quoted_ask=Round(ask),
   balance_eur=Round(realized),entry_timestamp_ms=pos.OpenT,exit_reason=reason});
  pos=null;
 }
 Dictionary<string,int> WeekCounts(IReadOnlyList<Quote> ticks){
  var counts=new Dictionary<string,int>();
  if(ticks.Count==0)return counts;
  var start=DateTimeOffset.FromUnixTimeMilliseconds(ticks[0].T).UtcDateTime;
  var end=DateTimeOffset.FromUnixTimeMilliseconds(ticks[ticks.Count-1].T).UtcDateTime;
  var monday=start.Date.AddDays(-(((int)start.DayOfWeek+6)%7));
  while(monday<=end){
   var k=System.Globalization.ISOWeek.GetYear(monday)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(monday).ToString("D2");
   counts[k]=0;monday=monday.AddDays(7);
  }
  foreach(var row in trades){
   // Ledger rows are anonymous event records; no economic counting from signals.
   var item=JsonSerializer.SerializeToElement(row);
   if(item.GetProperty("kind").GetString()!="ENTRY")continue;
   var t=DateTimeOffset.FromUnixTimeMilliseconds(item.GetProperty("timestamp_ms").GetInt64()).UtcDateTime;
   var k=System.Globalization.ISOWeek.GetYear(t)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(t).ToString("D2");
   counts[k]++;
  }
  return counts;
 }
 public object Run(IReadOnlyList<Quote> ticks) {
  if(ticks.Count==0)throw new InvalidDataException("EMPTY_TICK_INPUT");
  for(int i=0;i<ticks.Count;i++){
   Quote x=ticks[i];
   if(x.T<0||x.Raw<=0||!(x.Side=="bid"||x.Side=="ask"))throw new InvalidDataException("INVALID_QUOTE");
   if(i>0 && x.T<ticks[i-1].T)throw new InvalidDataException("NONMONOTONIC_EVENTS");
  }
  foreach(var group in ticks.GroupBy(x=>x.T)){
   var g=group.ToArray();long t=g[0].T;
   if(g.Any(x=>x.Side=="bid")&&g.Any(x=>x.Side=="ask"))crossSideSameMsGroups++;
   if(g.Where(x=>x.Side=="bid").Select(x=>x.Raw).Distinct().Count()>1 ||
      g.Where(x=>x.Side=="ask").Select(x=>x.Raw).Distinct().Count()>1){
    ambiguousGroups++;continue; // Different same-ms revisions have no trusted cross-side order.
   }
   foreach(var x in g) {
    if(x.Side=="bid"){bid=x.Raw/100000m;bidAt=t;}
    else {ask=x.Raw/100000m;askAt=t;}
   }
   if(bidAt<0||askAt<0||bid<=0m||ask<=0m){invalidSnapshots++;missingSideSnapshots++;continue;}
   if(ask<bid){invalidSnapshots++;crossedSnapshots++;continue;}
   // A locked BID=ASK quote is non-crossed, not intrinsically invalid.
   // Historical FIFO/liquidity at a zero spread remains unproven.
   if(ask==bid)zeroSpreadSnapshots++;
   // These are last-observed sides, not a historical arrival-time certification.
   if(t-bidAt>300000||t-askAt>300000){invalidSnapshots++;staleSnapshots++;continue;}
   long bar=t/BarMs*BarMs;
   bool barChanged=bar!=barStart;
   bool contiguousDecision=false;
   if(barStart>=0 && barChanged) {
    if(bar==barStart+BarMs){
     pendingSignal=kernel.OnCompletedBar(closeOfBar);
     contiguousDecision=true;
     signals.Add(new{decision_ms=bar,completed_bar_end_ms=bar,completed_close=Round(closeOfBar),direction=pendingSignal});
    }else{
     gapBars+=(int)Math.Min(1000000,(bar-barStart)/BarMs-1);
     kernel.Reset();pendingSignal=0;
    }
   }
   if(bar!=barStart){barStart=bar;closeOfBar=bid;}
   else closeOfBar=bid;
   if(Simulated){
    // cTrader cBot has a stop; model its observable quote-side trigger without
    // claiming a broker stop fill. On a gap, exit at the NEXT observed quote,
    // plus the selected adverse execution friction, never at the ideal stop level.
    bool stopped=false;
    if(pos is not null && stopPips>0 &&
       (pos.Direction==1 ? bid<=pos.OpenPrice-stopPips*0.0001m
                         : ask>=pos.OpenPrice+stopPips*0.0001m)){
      Close(t,"STOP_QUOTE_MODEL");stopTriggeredExits++;stopped=true;
    }
    if(stopped)pendingSignal=0; // no optimistic same-event re-entry after stop
    if(!stopped && pos is not null && barChanged &&
       ((exitPolicy==ExitMode.NeutralFlat && contiguousDecision && pendingSignal==0) ||
        (exitPolicy==ExitMode.Horizon12 && t-pos.OpenT>=BarMs*12L))){
      if(exitPolicy==ExitMode.NeutralFlat){Close(t,"NEUTRAL_POLICY_EXIT");neutralPolicyExits++;}
      else {Close(t,"HORIZON12_POLICY_EXIT");horizonPolicyExits++;}
      pendingSignal=0;stopped=true; // never reopen at same market event
    }
    if(!stopped && pendingSignal!=0){
     if(pos is not null && pos.Direction!=pendingSignal)Close(t);
     if(pos is null)Open(t,pendingSignal);
     pendingSignal=0;
    }
    Mark(t);
   }
   lastT=t;
  }
  if(Simulated && pos is not null){Close(lastT,"FORCED_DATASET_END_NOT_BROKER_FILL");Mark(lastT);}
  if(synthetic && (entries<1||entries!=exits||realized<=0||totalCosts<=0))
   throw new InvalidDataException("REFERENCE_FIXTURE_DID_NOT_EXERCISE_ACCOUNT");
  return new {
   schema="mxm.csharp.reference-replay.v1",
   classification=synthetic?(scenario?"ARTIFICIAL_SCENARIO_COST_FX_TEST_ONLY":"SYNTHETIC_MATHEMATICAL_ONLY"):scenario?"OBSERVED_PEPPERSTONE_QUOTES_ASSUMPTION_SCENARIO_UNCERTIFIED":"AUTHENTIC_CHRONOLOGY_NONOUTCOME_ONLY",
   pepperstone_historical_fills_proven=false,
   cTrader_native_backtest=false,
   authenticated_market_corpus=false, // Only the protected custody workflow can certify market source bytes.
   broker_historical_costs_verified=false,
   timing_assumption="ATOMIC_PER_MS_WITH_UNKNOWN_INTRA_MS_ORDER;TIMESTAMPS_ARE_NOT_HISTORICAL_ARRIVAL",
   account_convention=synthetic&&!scenario?"FIXTURE_EURUSD_QUOTE_TO_EUR_AT_1;MIN_1000_UNITS;MARGIN_EUR50;PER_SIDE_FEE_EUR0.10;SLIPPAGE_0.00001;NOT_PEPPERSTONE_TERMS":scenario?"UNVERIFIED_SCENARIO_EURUSD_USD_PER_EUR_1.10;1000_UNITS;MARGIN_EUR50;FEE_EUR0.10_PER_SIDE;SLIPPAGE_0.00002;NO_SWAP;NO_STOP_OUT_PARITY":"NONE_NO_ECONOMIC_FILLS",
   no_historical_fee_margin_swap_fx_authority=true,
   modeled_assumptions=new {family=family.ToString(),bar_minutes=(int)(BarMs/60000L),position_units=1000,
     fx_eur_per_usd=Round(Fx),commission_eur_per_side=commission,slippage_price_units=Slippage,
     extra_spread_price_units=extraHalfSpread*2m,margin_eur=margin,financing_eur=0m,
     quote_stop_loss_pips=stopPips,observed_quote_stop_fill_not_broker_certified=true,
     exit_policy=exitPolicy.ToString(),horizon_policy_bars=exitPolicy==ExitMode.Horizon12?12:0,
     max_margin_fraction_of_free_margin=maxMarginFraction,other_positions_and_actual_broker_margin_not_verified=true,
     original_bid_ask_spread_is_already_in_fill_prices=true,slippage_and_extra_spread_are_already_in_fill_prices=true,
     cost_total_is_diagnostic_including_embedded_execution_friction_not_additional_cash_debit=true},
   price_path_timestamps_are_not_historical_arrival_times=true,
   historical_execution_fills_proven=false,
   economic_identity_opened=false,
   terminal_position_exit_is_assumed_not_historical_fill=Simulated,
   initial_equity_eur=200m,final_equity_eur=Simulated?Round(realized):(decimal?)null,
   economic_entries=entries,economic_exits=exits,margin_headroom_rejections=marginHeadroomRejections,charged_cost_eur=Round(totalCosts),
   maximum_absolute_drawdown_eur=Round(maxDrawdown),modeled_stop_exits=stopTriggeredExits,
   modeled_neutral_exits=neutralPolicyExits,modeled_horizon_exits=horizonPolicyExits,
   // Complete ISO weeks require independent interval-coverage evidence, never infer from four-hour capture.
   hard21=false,full_iso_weeks_evaluated=0,entries_per_iso_week=Simulated?WeekCounts(ticks):new Dictionary<string,int>(),
   raw_events=ticks.Count,bar_decisions=signals.Count,
   feature_price_basis="BID_LAST_OBSERVED_QUOTE_APPROXIMATES_NATIVE_CTRADER_BID_CLOSE_NOT_PARITY_CERTIFICATE",
   same_ms_conflict_groups=ambiguousGroups,cross_side_same_ms_order_unknown_groups=crossSideSameMsGroups,
   gap_bars=gapBars,invalid_quote_snapshots=invalidSnapshots,missing_side_snapshots=missingSideSnapshots,
   crossed_snapshots=crossedSnapshots,stale_snapshots=staleSnapshots,zero_spread_accepted_snapshots=zeroSpreadSnapshots,
   ledger=trades,equity=equityPath,causal_signals=signals
  };
 }
}
static class Program {
 static List<Quote> Fixture(){
  // Known mathematical *fixture*, not a Pepperstone quote, fill or hypothesis.
  var list=new List<Quote>();long begin=1736164800000L; // January 2025 UTC
  for(int i=0;i<44;i++){
   decimal drift=i<15?i*0.00016m:i<30?(30-i)*0.00016m:(i-30)*0.00016m;
   for(int j=0;j<2;j++){
    long t=begin+i*300000L+60000+j*120000;
    decimal mid=1.10000m+drift+j*0.00001m;
    list.Add(new Quote(t,"bid",(long)((mid-0.00004m)*100000m)));
    list.Add(new Quote(t,"ask",(long)((mid+0.00004m)*100000m)));
   }
  }
  return list;
 }
 static List<Quote> ZeroSpreadFixture(){
  var original=Fixture();var reference=original.Where(x=>x.Side=="bid").ToDictionary(x=>x.T,x=>x.Raw);
  return original.Select(x=>x.Side=="ask"?new Quote(x.T,x.Side,reference[x.T]):x).ToList();
 }
 static List<Quote> Read(string file){
  var rows=new List<Quote>();
  foreach(string line in File.ReadLines(file)){
   if(string.IsNullOrWhiteSpace(line))continue;
   using var json=JsonDocument.Parse(line);
   var r=json.RootElement;
   rows.Add(new Quote(r.GetProperty("t").GetInt64(),r.GetProperty("side").GetString()??"",r.GetProperty("raw").GetInt64()));
  }
  return rows;
 }
 public static int Main(string[] args){
  try {
   if(args.Length!=3 || !(args[0]=="--fixture"||args[0]=="--zero-spread-fixture"||args[0]=="--model-fixture"||args[0]=="--authentic-nonoutcome"||args[0]=="--authentic-scenario"||args[0]=="--authentic-research"||args[0]=="--research-fixture"||args[0]=="--exit-research"||args[0]=="--exit-fixture"))
    throw new ArgumentException("USAGE: --fixture unused OUT | --model-fixture unused OUT | --authentic-nonoutcome INPUT.ndjson OUT | --authentic-scenario INPUT.ndjson OUT");
   bool fixture=args[0]=="--fixture"||args[0]=="--model-fixture"||args[0]=="--zero-spread-fixture"||args[0]=="--research-fixture"||args[0]=="--exit-fixture";
   if(!fixture && !File.Exists(args[1]))throw new FileNotFoundException("AUTHENTIC_INPUT_REQUIRED");
   var ticks=fixture?(args[0]=="--zero-spread-fixture"?ZeroSpreadFixture():Fixture()):Read(args[1]);
   if(args[0]=="--exit-research"||args[0]=="--exit-fixture"){
    // One preregistered, finite exit-policy sensitivity on an already exposed source.
    // NEVER infer independent selection, actual fills, cost authority or HARD21.
    var models=new List<object>();
    var modes=new[]{ExitMode.ReverseOnly,ExitMode.NeutralFlat,ExitMode.Horizon12};
    var families=new[]{StrategyMode.Adaptive,StrategyMode.TrendOnly,StrategyMode.RangeFade,StrategyMode.Breakout};
    var frames=new[]{1,5,15};
    var stops=new[]{0,12};
    var cases=new[]{
      new {name="LOW_UNVERIFIED",slip=0.00002m,fee=0.10m,spread=0.00002m,margin=50m},
      new {name="BASE_UNVERIFIED",slip=0.00005m,fee=0.20m,spread=0.00004m,margin=90m},
      new {name="STRESS_UNVERIFIED",slip=0.00010m,fee=0.40m,spread=0.00010m,margin=150m}};
    foreach(var family in families)foreach(var tf in frames)
     foreach(var cost in cases)foreach(var stop in stops)foreach(var exit in modes){
      var outcome=new Replay(false,true,family,tf,cost.slip,cost.fee,cost.spread,cost.margin,stop,0.8m,exit).Run(ticks);
      using var json=JsonDocument.Parse(JsonSerializer.Serialize(outcome));var j=json.RootElement;
      models.Add(new {
       family=family.ToString(),timeframe_minutes=tf,cost_case=cost.name,
       stop_loss_pips=stop,exit_policy=exit.ToString(),margin_fraction=0.8m,
       assumed_margin_eur=cost.margin,charged_fee_each_side_eur=cost.fee,
       initial_equity_eur=200m,final_equity_eur=j.GetProperty("final_equity_eur").GetDecimal(),
       modeled_entries=j.GetProperty("economic_entries").GetInt32(),
       modeled_exits=j.GetProperty("economic_exits").GetInt32(),
       modeled_neutral_exits=j.GetProperty("modeled_neutral_exits").GetInt32(),
       modeled_horizon_exits=j.GetProperty("modeled_horizon_exits").GetInt32(),
       modeled_stop_exits=j.GetProperty("modeled_stop_exits").GetInt32(),
       margin_rejections=j.GetProperty("margin_headroom_rejections").GetInt32(),
       max_drawdown_eur=j.GetProperty("maximum_absolute_drawdown_eur").GetDecimal(),
       hypothetical_total_friction_eur=j.GetProperty("charged_cost_eur").GetDecimal(),
       causal_signals=j.GetProperty("bar_decisions").GetInt32()
      });
    }
    Directory.CreateDirectory(args[2]);
    var full=new {schema="mxm.csharp.exposed-quote-exit-lifecycle-sensitivity.v1",
     classification=args[0]=="--exit-fixture"?"ARTIFICIAL_QUOTES_ONLY":"REUSED_AUTHENTIC_QUOTES_DEVELOPMENT_EXPOSED_NO_SELECTION",
     existing_source_reused_with_no_independent_confirmation=true,
     model_leaves=models.Count,underlying_source_events=ticks.Count,complete_iso_utc_weeks=0,
     no_broker_historical_cost_margin_liquidity_fx_authority=true,
     no_portfolio_robustness_or_hard21_claim=true,orders=0,selected_candidate=false,
     individual_model_results=models};
    File.WriteAllText(Path.Combine(args[2],"exit-lifecycle.json"),JsonSerializer.Serialize(full,new JsonSerializerOptions{WriteIndented=true}));
    Console.WriteLine(JsonSerializer.Serialize(new {status="MXM_EXIT_LIFECYCLE_MODEL_EXPOSURE",
     models=models.Count,classification=full.classification,orders=0}));
    return 0;
   }
   if(args[0]=="--authentic-research"||args[0]=="--research-fixture"){
    var matrix=new List<object>(); var families=new[]{StrategyMode.Adaptive,StrategyMode.TrendOnly,StrategyMode.RangeFade,StrategyMode.Breakout};
    var frames=new[]{1,5,15};
    var stopModes=new[]{0,12}; // sensitivity to actual Robot default 12-pip stop vs no stop
    var marginFractions=new[]{0.4m,0.6m,0.8m}; // prospectively declared, not broker authority
    var cases=new[]{new {name="LOW_UNVERIFIED",slip=0.00002m,fee=0.10m,spread=0.00002m,margin=50m},
                     new {name="BASE_UNVERIFIED",slip=0.00005m,fee=0.20m,spread=0.00004m,margin=90m},
                     new {name="STRESS_UNVERIFIED",slip=0.00010m,fee=0.40m,spread=0.00010m,margin=150m}};
    foreach(var family in families)foreach(var tf in frames)foreach(var cost in cases)foreach(var stops in stopModes)foreach(var fraction in marginFractions){
     var outcome=new Replay(false,true,family,tf,cost.slip,cost.fee,cost.spread,cost.margin,stops,fraction).Run(ticks);
     using var e=JsonDocument.Parse(JsonSerializer.Serialize(outcome));var j=e.RootElement;
     matrix.Add(new {family=family.ToString(),timeframe_minutes=tf,cost_case=cost.name,modeled_stop_loss_pips=stops,
      modeled_stop_exits=j.GetProperty("modeled_stop_exits").GetInt32(),
      margin_headroom_rejections=j.GetProperty("margin_headroom_rejections").GetInt32(),max_margin_fraction_of_free_margin=fraction,
      initial_equity_eur=200,final_equity_eur=j.GetProperty("final_equity_eur").GetDecimal(),
      net_pnl_eur=j.GetProperty("final_equity_eur").GetDecimal()-200m,
      entries=j.GetProperty("economic_entries").GetInt32(),exits=j.GetProperty("economic_exits").GetInt32(),
      modeled_cost_eur=j.GetProperty("charged_cost_eur").GetDecimal(),
      max_drawdown_eur=j.GetProperty("maximum_absolute_drawdown_eur").GetDecimal(),
      weeks_covered_full=0,hard21=false,bar_decisions=j.GetProperty("bar_decisions").GetInt32(),
      quoted_fill_prices_not_guaranteed=true,model_not_native_ctrader=true,
      fee_eur_per_side=cost.fee,slippage_price=cost.slip,extra_spread_price=cost.spread,margin_eur=cost.margin});
    }
    Directory.CreateDirectory(args[2]);
    var output=new {schema="mxm.csharp.authentic-exploratory-sensitivity.v1",
     classification=args[0]=="--research-fixture"?"ARTIFICIAL_QUOTES_COST_MATRIX_ONLY":"REAL_PEPPERSTONE_QUOTES_COUNTERFACTUAL_MODELS_UNCERTIFIED_NO_SCIENTIFIC_SELECTION",
     source_authentication_must_be_bound_externally=true,original_market_window_ms=new[]{ticks[0].T,ticks[ticks.Count-1].T},
     raw_events=ticks.Count,model_count=matrix.Count,full_iso_weeks=0,no_independent_trial_or_advantage=true,
     broker_historical_terms_unverified=true,economic_identity_consumed=false,orders=0,
     models=matrix};
    File.WriteAllText(Path.Combine(args[2],"research.json"),JsonSerializer.Serialize(output,new JsonSerializerOptions{WriteIndented=true}));
    Console.WriteLine(JsonSerializer.Serialize(new{status="CSHARP_ECONOMIC_RESEARCH_EXECUTED",models=matrix.Count,classification=output.classification}));
    return 0;
   }
   var report=new Replay(fixture,args[0]=="--model-fixture"||args[0]=="--authentic-scenario").Run(ticks);
   Directory.CreateDirectory(args[2]);
   var options=new JsonSerializerOptions{WriteIndented=true};
   File.WriteAllText(Path.Combine(args[2],"reference-report.json"),JsonSerializer.Serialize(report,options));
   Console.WriteLine(JsonSerializer.Serialize(new{status="REFERENCE_CSHARP_EXECUTED",economic_fixture_only=fixture,modeled_assumptions=args[0]=="--model-fixture"||args[0]=="--authentic-scenario",report=Path.Combine(args[2],"reference-report.json")}));
   return 0;
  } catch(Exception e) {Console.Error.WriteLine("MXM_REFERENCE_FAILED:"+e.GetType().Name+":"+e.Message);return 1;}
 }
}

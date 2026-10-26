using System.Text.Json;
using System.Text.Json.Nodes;
using System.Security.Cryptography;
using Mxm.Replay;
namespace Mxm.Research;
// Mathematical cashflows only: no market outcomes, broker charges or rates.
public static class MxmFinancingFixture {
 public static object Run(){
  int checks=0;
  void Need(bool ok,string why){checks++;if(!ok)throw new Exception("FINANCING_FIXTURE_"+why);}
  void Refuse(Action action,string why){bool bad=false;try{action();}catch(ArgumentException){bad=true;}Need(bad,why);}
  const string scenario="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
  string source=new('a',64);var cases=new List<object>();var sharedCases=new List<object>();
  foreach(int direction in new[]{1,-1}){
   var policy=new MxmReplayParameters(StrategyMode.TrendOnly,.8m,2,0m,.5m,.2m,FinancingScenarioSha256:scenario);
   var input=new List<MxmAccountFeed>();var t=new DateTime(2026,9,7,0,0,0,DateTimeKind.Utc);
   for(int i=0;i<6;i++){
    var at=t.AddMinutes(5*i);decimal mid=1.25m+direction*i*.0002m;
    input.Add(new MxmBarClose(at,"GBPUSD",mid));
    input.Add(new MxmQuote(at.AddSeconds(1),"GBPUSD",mid-.0001m,mid+.0001m,1m,1000m,50m,.1m,0m,1m,StopDistanceQuote:.0012m));
   }
   var preview=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy).Run(input);var entry=preview.Ledger.Single();
   Need(preview.OpenPositions==1 && preview.AcceptedEntries==1,"FUNDED_LONG_OR_SHORT");
   var booked=input.Last().Utc.AddSeconds(1);
   MxmFinancingCashflow Flow(DateTime at,DateTime from,DateTime to,decimal amount)=>
    new(at,"GBPUSD",entry.Utc,direction,entry.Units,from,to,amount,scenario);
   var debit=Flow(booked,entry.Utc,booked,-1.25m);
   var credit=Flow(booked.AddSeconds(1),booked,booked.AddSeconds(1),.40m);
   input.Add(debit);input.Add(credit);
   var nextWeek=input.OfType<MxmQuote>().Last() with {Utc=booked.AddDays(7)};
   input.Add(nextWeek);
   var late=Flow(nextWeek.Utc.AddSeconds(1),credit.AccrualEndUtc,nextWeek.Utc.AddSeconds(1),-.10m);input.Add(late);
   var account=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);var financed=account.Run(input);
   Need(financed.FinalCashEur==198.95m && financed.Ledger.Count(x=>x.Kind=="FINANCING")==3,"SIGNED_CASH_ON_SINGLE_EUR200");
   Need(financed.AcceptedEntries==1 && financed.ExecutedExits==0 && financed.OpenPositions==1 &&
    financed.EntriesByIsoWeek.Count==1 && financed.EntriesByIsoWeek.Values.Single()==1,"FINANCING_NEVER_COUNTS_AS_ENTRY");
   Need(financed.UsedMarginEur==preview.UsedMarginEur && financed.MarkedEquityEur==preview.MarkedEquityEur-.95m &&
    financed.FreeMarginEur==preview.FreeMarginEur-.95m && financed.MaxDrawdownEur>=preview.MaxDrawdownEur,"EQUITY_MARGIN_DRAWDOWN");
   for(int cut=0;cut<=input.Count;cut++){
    var prefix=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);prefix.Run(input.Take(cut));var saved=prefix.CaptureReplay(source);
    var recovered=MxmPortfolioAccountReplay.RestoreReplay(saved.Payload,saved.Sha256,source,policy,new[]{"GBPUSD"});
    Need(JsonSerializer.Serialize(financed)==JsonSerializer.Serialize(recovered.Continue(input.Skip(cut),cut)),"EVERY_EVENT_CUT");
   }
   var process=MxmPortfolioReplayRecoveryProbe.Verify(input,policy,new[]{"GBPUSD"},source,financed,
    new[]{input.IndexOf(debit),input.IndexOf(debit)+1,input.IndexOf(credit)+1});
   Need(process.ColdProcesses==3 && process.AllReportsIdentical,"THREE_COLD_OS_PROCESSES");
   var savedAfter=account.CaptureReplay(source);
   Refuse(()=>account.Continue(new[]{late with {Utc=late.Utc.AddSeconds(1)}},account.NextEventOrdinal),"REBOOKED_PERIOD");
   var cold=MxmPortfolioAccountReplay.RestoreReplay(savedAfter.Payload,savedAfter.Sha256,source,policy,new[]{"GBPUSD"});
   Refuse(()=>cold.Continue(new[]{late with {Utc=late.Utc.AddSeconds(1)}},cold.NextEventOrdinal),"REBOOKED_PERIOD_AFTER_RESTART");
   Refuse(()=>MxmPortfolioAccountReplay.RestoreReplay(savedAfter.Payload,savedAfter.Sha256,source,
    policy with {FinancingScenarioSha256=new string('c',64)},new[]{"GBPUSD"}),"SCENARIO_CHANGE_AT_RESTART");
   // Recompute the transport checksum to test semantic validation separately
   // from authenticated custody, which is an independent caller obligation.
   foreach(string tamper in new[]{"amount","overlap","direction","ordinary_payload"}){
    var node=JsonNode.Parse(savedAfter.Payload)!;var rows=node["Ledger"]!.AsArray();
    var fs=rows.Where(x=>x!["Kind"]!.GetValue<string>()=="FINANCING").ToArray();
    if(tamper=="amount")fs[0]!["Financing"]!["AmountEur"]=-9m;
    if(tamper=="overlap")fs[1]!["Financing"]!["AccrualStartUtc"]=entry.Utc;
    if(tamper=="direction")fs[0]!["Financing"]!["Direction"]=-direction;
    if(tamper=="ordinary_payload")rows[0]!["Financing"]=fs[0]!["Financing"]!.DeepClone();
    byte[] raw=JsonSerializer.SerializeToUtf8Bytes(node);string hash=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();
    Refuse(()=>MxmPortfolioAccountReplay.RestoreReplay(raw,hash,source,policy,new[]{"GBPUSD"}),"TAMPER_"+tamper);
   }
   foreach(var bad in new[]{debit with {ScenarioSha256=new string('c',64)},debit with {Direction=-direction},
    debit with {Units=2000m},debit with {PositionEntryUtc=entry.Utc.AddMilliseconds(1)},
    debit with {AccrualStartUtc=entry.Utc.AddSeconds(-1)},debit with {AccrualEndUtc=debit.Utc.AddSeconds(1)},
    debit with {AccrualEndUtc=entry.Utc},debit with {AccrualStartUtc=DateTime.SpecifyKind(entry.Utc,DateTimeKind.Unspecified)}}){
    var badAccount=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);badAccount.Run(input.Take(input.IndexOf(debit)));
    Refuse(()=>badAccount.Continue(new[]{bad},badAccount.NextEventOrdinal),"MISMATCHED_OR_NONCAUSAL");
   }
   var disabled=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy with {FinancingScenarioSha256=null});disabled.Run(input.Take(input.IndexOf(debit)));
   Refuse(()=>disabled.Continue(new[]{debit},disabled.NextEventOrdinal),"EXPLICIT_OPT_IN");
   var flat=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);flat.Run(Array.Empty<MxmAccountFeed>());
   Refuse(()=>flat.Continue(new[]{debit},flat.NextEventOrdinal),"NO_UNOWNED_FINANCING");
   var overlap=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);overlap.Run(input.Take(input.IndexOf(credit)));
   Refuse(()=>overlap.Continue(new[]{credit with {AccrualStartUtc=entry.Utc}},overlap.NextEventOrdinal),"OVERLAPPING_PERIOD");
   var ruin=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},policy);ruin.Run(input.Take(input.IndexOf(debit)));
   var ruined=ruin.Continue(new[]{debit with {AmountEur=-201m}},ruin.NextEventOrdinal);
   Need(ruined.FinalCashEur<0 && ruined.Rejections.Contains("SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT"),"DEBIT_CAN_HALT_ACCOUNT");
   Refuse(()=>ruin.Continue(Array.Empty<MxmAccountFeed>(),ruin.NextEventOrdinal),"NO_CONTINUATION_AFTER_RUIN");
   var closed=MxmPortfolioAccountReplay.RestoreReplay(savedAfter.Payload,savedAfter.Sha256,source,policy,new[]{"GBPUSD"});
   decimal stopBid=entry.Price-direction*.002m;
   var stopped=closed.Continue(new[]{nextWeek with {Utc=late.Utc.AddSeconds(1),Bid=stopBid,Ask=stopBid+.0002m}},closed.NextEventOrdinal);
   Need(stopped.OpenPositions==0 && stopped.ExecutedExits==1 && stopped.AcceptedEntries==1,"FINANCING_SURVIVES_OBSERVED_STOP_CLOSE");
   var closedSaved=closed.CaptureReplay(source);
   var closedCold=MxmPortfolioAccountReplay.RestoreReplay(closedSaved.Payload,closedSaved.Sha256,source,policy,new[]{"GBPUSD"});
   Need(JsonSerializer.Serialize(closedCold.Report())==JsonSerializer.Serialize(stopped),"CLOSED_FINANCING_HISTORY_RESTORES");
   Refuse(()=>closedCold.Continue(new[]{late with {Utc=late.Utc.AddSeconds(2),AccrualStartUtc=late.AccrualEndUtc,
    AccrualEndUtc=late.Utc.AddSeconds(2)}},closedCold.NextEventOrdinal),"NO_CHARGE_TO_CLOSED_POSITION");
   cases.Add(new{direction,initial_cash_eur=200m,entry_fee_eur=entry.CommissionEur,
    financing_amounts_eur=new[]{-1.25m,.40m,-.10m},cash_eur=financed.FinalCashEur,
    before_equity_eur=preview.MarkedEquityEur,after_equity_eur=financed.MarkedEquityEur,
    before_free_margin_eur=preview.FreeMarginEur,after_free_margin_eur=financed.FreeMarginEur,
    accepted_entries=financed.AcceptedEntries,executed_exits=financed.ExecutedExits,
    next_week_booked=true,cold_processes=process.ColdProcesses,every_event_cut_checked=true,
    mark_bid=nextWeek.Bid,mark_ask=nextWeek.Ask,scenario_sha256=scenario,report=financed});
   // The same EUR cashflow must NOT be converted a second time in shared-FX mode.
   var sharedPolicy=policy with {UseSharedUsdConversion=true};
   var sharedFeed=new List<MxmAccountFeed>();
   foreach(var e in input.Take(input.IndexOf(debit))){
    if(e is MxmBarClose b)sharedFeed.Add(new MxmUsdEurMark(b.Utc,b.Utc,b.Utc,1.10m,1.11m));
    sharedFeed.Add(e is MxmQuote q?q with {QuoteToEur=1m/1.11m,QuoteLossToEur=1m/1.10m,
     BidSourceUtc=q.Utc,AskSourceUtc=q.Utc}:e);
   }
   var shared=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},sharedPolicy);var sharedBefore=shared.Run(sharedFeed);
   var sharedAfter=shared.Continue(new MxmAccountFeed[]{debit,credit},shared.NextEventOrdinal);
   Need(sharedAfter.FinalCashEur==199.05m && sharedAfter.MarkedEquityEur==sharedBefore.MarkedEquityEur-.85m &&
    sharedAfter.UsedMarginEur==sharedBefore.UsedMarginEur,"EUR_BOOKING_NOT_DOUBLE_CONVERTED_BY_SHARED_USD_MODE");
   var sharedSaved=shared.CaptureReplay(source);
   var sharedCold=MxmPortfolioAccountReplay.RestoreReplay(sharedSaved.Payload,sharedSaved.Sha256,source,sharedPolicy,new[]{"GBPUSD"});
   Need(JsonSerializer.Serialize(sharedCold.Report())==JsonSerializer.Serialize(sharedAfter),"FINANCING_AND_SHARED_FX_RESTORE_TOGETHER");
   Refuse(()=>sharedCold.Continue(new[]{credit with {Utc=credit.Utc.AddSeconds(6),AccrualStartUtc=credit.AccrualEndUtc,
    AccrualEndUtc=credit.Utc.AddSeconds(6)}},sharedCold.NextEventOrdinal),"STALE_FUNDED_MARKS_CANNOT_BOOK_FINANCING");
   Refuse(()=>sharedCold.CaptureReplay(source),"FAILED_FINANCING_SEGMENT_CANNOT_SAVE_VALID_PREFIX");
   sharedCases.Add(new{direction,amounts_eur=new[]{-1.25m,.40m},before_cash_eur=sharedBefore.FinalCashEur,
    after_cash_eur=sharedAfter.FinalCashEur,before_equity_eur=sharedBefore.MarkedEquityEur,
    after_equity_eur=sharedAfter.MarkedEquityEur,entries=sharedAfter.AcceptedEntries,
    exits=sharedAfter.ExecutedExits,fx_bid=1.10m,fx_ask=1.11m});
  }
  return new{schema="mxm.financing-scenario.artificial.v1",checks,cases,shared_fx_cases=sharedCases,
   financing_is_explicit_eur_scenario_only=true,historical_financing_proven=false,
   broker_orders=0,native_ctrader_runtime_reception=false,economic_edge_proven=false,hard21_proven=false};
 }
}

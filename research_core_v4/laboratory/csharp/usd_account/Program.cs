using System.Text.Json;
using Mxm.Replay;
using Mxm.Research;
if(MxmPortfolioReplayRecoveryProbe.TryWorker(args,out int workerExit)){Environment.ExitCode=workerExit;return;}
// Source-only registration entry point: no historical ticks enter the event engine.
if(args.Length==2 && args[0]=="--register-usd-quotes"){
 string declaration=File.ReadAllText(args[1]);using var doc=JsonDocument.Parse(declaration);
 var names=doc.RootElement.GetProperty("symbols").EnumerateArray().Select(x=>x.GetProperty("symbol").GetString()!).ToArray();
 var config=new MxmReplayParameters(StrategyMode.TrendOnly,.8m,3,0m,.03m,.2m,
  UseSharedUsdConversion:true,UsdQuoteMetadataJson:declaration);
 var account=new MxmPortfolioAccountReplay(names,config);var report=account.Run(Array.Empty<MxmAccountFeed>());
 string sourceId=doc.RootElement.GetProperty("source_sha256").GetString()!;var saved=account.CaptureReplay(sourceId);
 var restored=MxmPortfolioAccountReplay.RestoreReplay(saved.Payload,saved.Sha256,sourceId,config,names);
 if(JsonSerializer.Serialize(restored.Report())!=JsonSerializer.Serialize(report))throw new Exception("SOURCE_REGISTRATION_RECOVERY");
 Console.WriteLine(JsonSerializer.Serialize(new{schema="mxm.usd-source-registration.v1",source_sha256=sourceId,
  symbols=names,initial_capital_eur=report.InitialCapitalEur,cash_eur=report.FinalCashEur,
  entries=report.AcceptedEntries,open_positions=report.OpenPositions,cold_restore_parity=true,
  market_events=0,orders=0,historical_costs_proven=false,economic_edge_proven=false,native_ctrader_runtime_reception=false}));return;
}
int checks=0;
void Need(bool ok,string why){checks++;if(!ok)throw new Exception("SHARED_USD_FIXTURE_"+why);}
var t=new DateTime(2026,9,7,0,0,0,DateTimeKind.Utc);
var source=new string('a',64);
MxmReplayParameters Settings(bool mode=true)=>new(StrategyMode.TrendOnly,.8m,2,0m,.03m,.2m,UseSharedUsdConversion:mode);
MxmUsdEurMark Fx(DateTime stamp,decimal bid=1.10m,decimal ask=1.11m)=>new(stamp,stamp,stamp,bid,ask);
List<MxmAccountFeed> Start(int direction=1){
 var events=new List<MxmAccountFeed>();
 for(int i=0;i<6;i++){
  var at=t.AddMinutes(5*i);decimal mid=1.25m+direction*i*.0002m;
  events.Add(Fx(at));events.Add(new MxmBarClose(at,"GBPUSD",mid));
  events.Add(new MxmQuote(at.AddSeconds(1),"GBPUSD",mid-.0001m,mid+.0001m,
   1m/1.11m,1000m,50m,.1m,0m,1m,1m/1.10m,StopDistanceQuote:.0012m,BidSourceUtc:at.AddSeconds(1),AskSourceUtc:at.AddSeconds(1)));
 }
 return events;
}
MxmPortfolioAccountReplay Account(int direction=1){
 var a=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());var r=a.Run(Start(direction));
 Need(r.AcceptedEntries==1 && r.OpenPositions==1 && r.InitialCapitalEur==200m,"ONE_INITIAL_CONTINUOUS_ACCOUNT");return a;
}
void Refuse(Action action,string why){bool bad=false;try{action();}catch(ArgumentException){bad=true;}Need(bad,why);}
var proofs=new List<object>();
foreach(int direction in new[]{1,-1}){
 var a=Account(direction);var entry=a.Report().Ledger.Single();var now=Start().Last().Utc;
 // Create either positive or negative floating USD without another strategy bar.
 foreach(int pnlSign in new[]{1,-1}){
  var active=Account(direction);decimal bid=entry.Price+direction*pnlSign*.001m;
  decimal ask=bid+.0002m;
  var q=new MxmQuote(now.AddMilliseconds(500),"GBPUSD",bid,ask,1m/1.11m,1000m,50m,.1m,0m,1m,1m/1.10m);
  // No fixed stop in this derived mark example: original accepted stop remains active.
  // Choose short bid from its ASK liquidation side to make the desired sign exact.
  if(direction<0)q=q with {Ask=entry.Price-pnlSign*.001m,Bid=entry.Price-pnlSign*.001m-.0002m};
  q=q with {BidSourceUtc=q.Utc,AskSourceUtc=q.Utc};
  var before=active.Continue(new[]{q},active.NextEventOrdinal);
  Need(before.OpenPositions==1,"MARK_EXAMPLE_STOP_NOT_TRIGGERED");
  var mark=Fx(q.Utc.AddMilliseconds(1),1.20m,1.21m);
  var after=active.Continue(new[]{mark},active.NextEventOrdinal);
  decimal usd=direction>0?(q.Bid-entry.Price)*1000m:(entry.Price-q.Ask)*1000m;
  decimal expected=after.FinalCashEur+(usd>=0?usd/1.21m:usd/1.20m);
  Need(after.MarkedEquityEur==expected,"CURRENT_SIGNED_FX_MARK");
  Need(after.AcceptedEntries==before.AcceptedEntries && after.ExecutedExits==before.ExecutedExits &&
   after.FinalCashEur==before.FinalCashEur && after.UsedMarginEur==before.UsedMarginEur,"FX_ONLY_NO_ORDER_CASH_OR_MARGIN_CHANGE");
  var capsule=active.CaptureReplay(source);
  var restored=MxmPortfolioAccountReplay.RestoreReplay(capsule.Payload,capsule.Sha256,source,Settings(),new[]{"GBPUSD"});
  Need(JsonSerializer.Serialize(restored.Report())==JsonSerializer.Serialize(after),"EXACT_FX_EXPOSURE_COLD_RESTORE");
  decimal coldEquity=restored.Report().MarkedEquityEur;
  var next=Fx(mark.Utc.AddMilliseconds(1),1.30m,1.31m);
  var direct=active.Continue(new[]{next},active.NextEventOrdinal);var resumed=restored.Continue(new[]{next},restored.NextEventOrdinal);
  Need(JsonSerializer.Serialize(direct)==JsonSerializer.Serialize(resumed),"NO_RESTORE_FUNDING_OR_PNL_RESET");
  proofs.Add(new{direction,pnl_sign=pnlSign,entry_price=entry.Price,mark_bid=q.Bid,mark_ask=q.Ask,units=1000m,
   cash_eur=after.FinalCashEur,fx_bid=mark.Bid,fx_ask=mark.Ask,equity_eur=after.MarkedEquityEur,entries=after.AcceptedEntries,
   exits=after.ExecutedExits,restored_equity_eur=coldEquity,final_fx_bid=next.Bid,final_fx_ask=next.Ask,
   final_equity_eur=resumed.MarkedEquityEur,margin_eur=after.UsedMarginEur});
 }
}
var owned=Account();var last=Start().Last().Utc;
Refuse(()=>owned.Continue(new[]{Fx(last.AddSeconds(6))},owned.NextEventOrdinal),"OPEN_STALE_INSTRUMENT_MARK_REJECTED");
// The new FX itself is fresh above; the shared-mode instrument side ages are capped at5000ms.
// A separately stale FX side is invalid regardless of exposure.
var stale=Account();
Refuse(()=>stale.Continue(new[]{new MxmUsdEurMark(last.AddSeconds(1),last.AddSeconds(-6),last.AddSeconds(1),1.1m,1.11m)},stale.NextEventOrdinal),"ONE_FX_SIDE_STALE");
Refuse(()=>stale.Report(),"FAULT_CANNOT_RETURN_FAVOURABLE_REPORT");
var unavailable=Account();
Refuse(()=>unavailable.Continue(new[]{new MxmUsdConversionUnavailable(last.AddMilliseconds(1),"SOURCE_REJECTED")},unavailable.NextEventOrdinal),"OPEN_UNKNOWN_FX_HALTS");
Refuse(()=>unavailable.CaptureReplay(source),"NO_FAULTED_CHECKPOINT");
var flat=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());flat.Run(new[]{new MxmUsdConversionUnavailable(t,"NO_INITIAL_FX")});
var emptyCapsule=flat.CaptureReplay(source);
Need(MxmPortfolioAccountReplay.RestoreReplay(emptyCapsule.Payload,emptyCapsule.Sha256,source,Settings(),new[]{"GBPUSD"}).Report().FinalCashEur==200m,"FLAT_MISSING_FX_RECOVERY_NOT_FUNDED_AGAIN");
var same=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());same.Run(new[]{Fx(t)});
Refuse(()=>same.Continue(new[]{new MxmQuote(t,"GBPUSD",1.25m,1.2502m,1m/1.11m,1000m,50m,.1m,0m,1m,1m/1.1m)},same.NextEventOrdinal),"SAME_TIMESTAMP_FX_NOT_EXECUTION_AUTHORITY");
var wrong=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());wrong.Run(new[]{Fx(t)});
Refuse(()=>wrong.Continue(new[]{new MxmQuote(t.AddMilliseconds(1),"GBPUSD",1.25m,1.2502m,1m/1.2502m,1000m,50m,.1m,0m,1m,1m/1.25m)},wrong.NextEventOrdinal),"GBP_PRICE_CANNOT_CONVERT_USD_TO_EUR");
var legacy=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings(false));
Refuse(()=>legacy.Run(new[]{Fx(t)}),"SHARED_FX_NOT_OPTED_IN");
Refuse(()=>new MxmPortfolioAccountReplay(new[]{"USDJPY"},Settings()),"UNREGISTERED_QUOTE_CURRENCY");
foreach(var invalid in new[]{Fx(t) with {Symbol="GBPUSD"},new MxmUsdEurMark(t,t.AddMilliseconds(1),t,1.1m,1.11m),Fx(t,1.12m,1.11m),Fx(t,0m,1.11m)}){
 var a=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());
 Refuse(()=>a.Run(new[]{invalid}),"FUTURE_CROSSED_OR_NONPOSITIVE_FX");
}
var conflict=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());conflict.Run(new[]{Fx(t)});
Refuse(()=>conflict.Continue(new[]{new MxmUsdEurMark(t.AddSeconds(1),t,t.AddSeconds(1),1.12m,1.13m)},conflict.NextEventOrdinal),"SAME_SIDE_TIME_CHANGED_PRICE");
var pending=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());var warm=Start();var pendingQuote=(MxmQuote)warm.Last();warm.RemoveAt(warm.Count-1);
pending.Run(warm);var boundary=warm.Last().Utc;
pending.Continue(new[]{Fx(boundary.AddMilliseconds(500),1.20m,1.21m)},pending.NextEventOrdinal);
Need(pending.Report().AcceptedEntries==0,"FX_VALUATION_DOES_NOT_CONSUME_PENDING_ENTRY");
pending.Continue(new[]{pendingQuote with {QuoteToEur=1m/1.21m,QuoteLossToEur=1m/1.20m}},pending.NextEventOrdinal);
Need(pending.Report().AcceptedEntries==1,"ONLY_LATER_INSTRUMENT_QUOTE_EXECUTES_PENDING_INTENT");
var flatStale=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());flatStale.Run(new MxmAccountFeed[]{Fx(t),new MxmBarClose(t.AddSeconds(10),"GBPUSD",1.25m,t)});
var flatSaved=flatStale.CaptureReplay(source);
Need(MxmPortfolioAccountReplay.RestoreReplay(flatSaved.Payload,flatSaved.Sha256,source,Settings(),new[]{"GBPUSD"}).Report().FinalCashEur==200m,"STALE_FLAT_FX_CHECKPOINT_RESTORES_WITHOUT_ADMISSION");
Refuse(()=>MxmPortfolioAccountReplay.RestoreReplay(flatSaved.Payload,flatSaved.Sha256,source,Settings(false),new[]{"GBPUSD"}),"CHECKPOINT_MODE_CANNOT_BE_SWITCHED");
var stamp=new DateTimeOffset(t).ToUnixTimeMilliseconds();
var assumptions=new MxmUsdAccountAssumptions(1000m,50m,.1m,0m,1m,.0012m);
var ready=new AlignedUsdSnapshot(stamp+1000,"GBP_QUOTE_GROUP","READY_STRICT_PRIOR_FX",125000,stamp+1000,125020,stamp+1000,110000,stamp,111000,stamp,null,null);
var mapped=MxmUsdPairAccountInput.FromGbpAlignment(ready,assumptions);
Need(mapped is MxmQuote native && native.QuoteToEur==1m/1.11m && native.QuoteLossToEur==1m/1.10m,"TYPED_SOURCE_BINDS_EXACT_SHARED_FX");
Need(MxmUsdPairAccountInput.FromGbpAlignment(ready with {Code="GBP_CROSSED"},assumptions) is MxmInstrumentQuoteUnavailable,"BAD_GBP_SOURCE_NOT_BAD_GLOBAL_CURRENCY");
Need(MxmUsdPairAccountInput.FromGbpAlignment(ready with {Code="FX_STALE"},assumptions) is MxmUsdConversionUnavailable,"BAD_CURRENCY_INVALIDATES_SHARED_EXPOSURE");
Need(MxmUsdPairAccountInput.FromGbpAlignment(ready with {Purpose="FX_VALUATION_ONLY",T=stamp},assumptions) is MxmUsdEurMark,"FX_ROLE_NEVER_MAPS_TO_GBP_QUOTE");
Refuse(()=>MxmUsdPairAccountInput.FromGbpAlignment(ready with {FxBidMs=ready.T},assumptions),"READY_BOOLEAN_CANNOT_HIDE_FUTURE_FX");
var missingGbp=Account();
Refuse(()=>missingGbp.Continue(new[]{new MxmInstrumentQuoteUnavailable(last.AddMilliseconds(1),"GBPUSD","CROSSED")},missingGbp.NextEventOrdinal),"BAD_FUNDED_INSTRUMENT_CANNOT_SKIP_UNKNOWN_PATH");
var invalidFlat=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());
invalidFlat.Run(new MxmAccountFeed[]{Fx(t),new MxmUsdConversionUnavailable(t.AddMilliseconds(1),"TEMPORARILY_UNKNOWN")});
var invalidSaved=invalidFlat.CaptureReplay(source);
var invalidRestored=MxmPortfolioAccountReplay.RestoreReplay(invalidSaved.Payload,invalidSaved.Sha256,source,Settings(),new[]{"GBPUSD"});
Refuse(()=>invalidRestored.Continue(new[]{new MxmUsdEurMark(t.AddMilliseconds(2),t,t.AddMilliseconds(2),1.12m,1.13m)},invalidRestored.NextEventOrdinal),"INVALIDATION_AND_RESTORE_CANNOT_ERASE_FX_CLOCK_ANCHOR");
var staleSide=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());staleSide.Run(new[]{Fx(t)});
Refuse(()=>staleSide.Continue(new[]{new MxmQuote(t.AddSeconds(1),"GBPUSD",1.25m,1.2502m,1m/1.11m,1000m,50m,.1m,0m,1m,1m/1.10m,
 BidSourceUtc:t.AddSeconds(-5),AskSourceUtc:t.AddSeconds(1))},staleSide.NextEventOrdinal),"NEW_TICK_CANNOT_REFRESH_OLD_OPPOSITE_SIDE");
var sourceClock=Account();var sourceCapsule=sourceClock.CaptureReplay(source);
using(var sourceJson=JsonDocument.Parse(sourceCapsule.Payload)){
 var quote=sourceJson.RootElement.GetProperty("Symbols")[0].GetProperty("Latest");
 Need(quote.GetProperty("BidSourceUtc").GetDateTime()==last && quote.GetProperty("AskSourceUtc").GetDateTime()==last,"CHECKPOINT_PRESERVES_BOTH_INSTRUMENT_SOURCE_CLOCKS");
}
var feeModel=new MxmEurUsdCapturedCosts(100000,100000000,100000,10000000,1,3000000000,0,"USD");
var euroFeed=Start().Select(e=>e switch {
 MxmBarClose bar=>bar with {Symbol="EURUSD"},
 MxmQuote q=>q with {Symbol="EURUSD",CapturedCosts=feeModel},
 _=>e
}).ToArray();
var euroAccount=new MxmPortfolioAccountReplay(new[]{"EURUSD"},Settings());var feeReport=euroAccount.Run(euroFeed);
var feeTrade=feeReport.Ledger.Single();decimal expectedFee=feeTrade.Units*feeTrade.Price*30m/1000000m/1.10m;
Need(feeTrade.CommissionEur==expectedFee && feeReport.FinalCashEur==200m-expectedFee,"CAPTURED_USD_FEE_USES_ADMITTED_FX_BID");
Need(feeTrade.CommissionEur!=feeTrade.Units*feeTrade.Price*30m/1000000m/(feeTrade.Price-.0002m),"EXECUTION_PRICE_IS_NOT_CONVERSION_AUTHORITY");
var feeCase=new{units=feeTrade.Units,execution_price=feeTrade.Price,usd_per_million=30m,fx_bid=1.10m,commission_eur=feeTrade.CommissionEur,cash_eur=feeReport.FinalCashEur};
var badGbpCost=new MxmPortfolioAccountReplay(new[]{"GBPUSD"},Settings());
Refuse(()=>badGbpCost.Run(Start().Select(e=>e is MxmQuote q?q with {CapturedCosts=feeModel}:e)),"NO_UNVERIFIED_GBP_CAPTURED_FEE_PROMOTION");
var rearmed=MxmPortfolioAccountReplay.RestoreReplay(invalidSaved.Payload,invalidSaved.Sha256,source,Settings(),new[]{"GBPUSD"});
rearmed.Continue(new[]{Fx(t.AddMilliseconds(2),1.20m,1.21m)},rearmed.NextEventOrdinal);
Need(rearmed.Report().FinalCashEur==200m && rearmed.Report().AcceptedEntries==0,"NEW_VALID_OBSERVATION_REARMS_FLAT_ACCOUNT_WITHOUT_REFUND");
// Artificial multi-instrument funding/recovery: not a market-performance test.
var roster=new[]{"AUDUSD","Copper","SpotCrude"};
string Registration(string digest)=>JsonSerializer.Serialize(new{schema="mxm.declared-quote-assets.v1",
 source_sha256=digest,symbols=new[]{new{symbol="AUDUSD",symbol_id=5,quote_asset="USD"},
 new{symbol="Copper",symbol_id=111,quote_asset="USD"},new{symbol="SpotCrude",symbol_id=250,quote_asset="USD"}}});
var declared=Settings() with {MaxPositions=3,UsdQuoteMetadataJson=Registration(source)};
var panel=new MxmPortfolioAccountReplay(roster,declared);var feed=new List<MxmAccountFeed>();
for(int i=0;i<6;i++){
 var at=t.AddMinutes(5*i);feed.Add(Fx(at));
 for(int j=0;j<roster.Length;j++){
  decimal mid=(j+1)*10m+i*.01m;feed.Add(new MxmBarClose(at,roster[j],mid));
  feed.Add(new MxmQuote(at.AddSeconds(1),roster[j],mid-.0001m,mid+.0001m,
   1m/1.11m,1m,50m,.1m,0m,1m,1m/1.10m,BidSourceUtc:at.AddSeconds(1),AskSourceUtc:at.AddSeconds(1)));
 }
}
// Keep simultaneous quote timestamps: no fabricated ordering of historical sides.
feed=feed.OrderBy(e=>e.Utc).ToList();var panelReport=panel.Run(feed);
Need(panelReport.AcceptedEntries==3 && panelReport.OpenPositions==3 && panelReport.InitialCapitalEur==200m &&
 panelReport.UsedMarginEur==150m && panelReport.FinalCashEur==199.7m,"DECLARED_PANEL_ONE_ACCOUNT_AND_SHARED_MARGIN");
var marginLimited=new MxmPortfolioAccountReplay(roster,declared);
var marginReport=marginLimited.Run(feed.Select(e=>e is MxmQuote q?q with {InitialMarginEur=90m}:e));
Need(marginReport.AcceptedEntries==1 && marginReport.RejectedEntries==2 && marginReport.UsedMarginEur==90m &&
 marginReport.Rejections.All(x=>x=="REJECT_MARGIN_FRACTION"),"PANEL_MARGIN_USES_REMAINING_SHARED_FREE_MARGIN");
var riskLimited=new MxmPortfolioAccountReplay(roster,declared with {MaxEstimatedStopRiskFraction=.011m});
var riskReport=riskLimited.Run(feed);
Need(riskReport.AcceptedEntries==1 && riskReport.RejectedEntries==2 &&
 riskReport.Rejections.All(x=>x=="REJECT_AGGREGATE_STOP_RISK_EXCESS"),"PANEL_COMBINED_STOP_RISK_AND_FRICTION_RESERVE");
var declaredEmpty=new MxmPortfolioAccountReplay(roster,declared);declaredEmpty.Run(Array.Empty<MxmAccountFeed>());
var declaredEmptySaved=declaredEmpty.CaptureReplay(source);
Need(MxmPortfolioAccountReplay.RestoreReplay(declaredEmptySaved.Payload,declaredEmptySaved.Sha256,source,declared,roster).Report().FinalCashEur==200m,
 "SOURCE_ONLY_EMPTY_REGISTRATION_CAN_RESTORE_WITHOUT_MARKET_EVENTS");
var panelCapsule=panel.CaptureReplay(source);
var panelRestored=MxmPortfolioAccountReplay.RestoreReplay(panelCapsule.Payload,panelCapsule.Sha256,source,declared,roster);
var fxOnly=Fx(feed.Last().Utc.AddMilliseconds(1),1.2m,1.21m);
var panelDirect=panel.Continue(new[]{fxOnly},panel.NextEventOrdinal);
Need(JsonSerializer.Serialize(panelRestored.Continue(new[]{fxOnly},panelRestored.NextEventOrdinal))==JsonSerializer.Serialize(panelDirect),
 "DECLARED_PANEL_RECOVERY_AND_FX_ONLY_PARITY");
// Exercise the SAME funded three-symbol account after a durable checkpoint, not
// three separately replenished tests. Market prices, margin and fees are artificial.
var postRecoveryQuotes=roster.Select((symbol,index)=>{
 var at=fxOnly.Utc.AddMilliseconds(index+1);
 decimal mid=(index+1)*10m+.06m;
 return (MxmAccountFeed)new MxmQuote(at,symbol,mid-.0001m,mid+.0001m,
  1m/1.21m,1m,50m,.1m,0m,1m,1m/1.20m,
  BidSourceUtc:at,AskSourceUtc:at);
}).ToArray();
var directMarked=panel.Continue(postRecoveryQuotes,panel.NextEventOrdinal);
var restoredMarked=panelRestored.Continue(postRecoveryQuotes,panelRestored.NextEventOrdinal);
Need(JsonSerializer.Serialize(restoredMarked)==JsonSerializer.Serialize(directMarked),
 "PANEL_THREE_POST_RESTART_QUOTES_IDENTICAL_CASH_RISK_AND_EQUITY");
Need(directMarked.OpenPositions==3 && directMarked.AcceptedEntries==3 &&
 directMarked.FinalCashEur==199.7m && directMarked.UsedMarginEur==150m &&
 directMarked.Ledger.Count==3 && directMarked.MarkedEquityEur>panelDirect.MarkedEquityEur,
 "PANEL_POST_RESTART_MARKS_ALL_POSITIONS_NO_DUPLICATE_FUNDING_OR_ENTRIES");
var fundedCapsule=panelRestored.CaptureReplay(source);
var fundedAgain=MxmPortfolioAccountReplay.RestoreReplay(fundedCapsule.Payload,fundedCapsule.Sha256,
 source,declared,roster);
Need(JsonSerializer.Serialize(fundedAgain.Report())==JsonSerializer.Serialize(directMarked),
 "PANEL_SECOND_COLD_RESTORE_PRESERVES_FUNDED_THREE_SYMBOL_MARK");
var staleFunded=MxmPortfolioAccountReplay.RestoreReplay(fundedCapsule.Payload,fundedCapsule.Sha256,
 source,declared,roster);
var staleAt=postRecoveryQuotes.Last().Utc.AddSeconds(6);
Refuse(()=>staleFunded.Continue(new[]{new MxmUsdEurMark(staleAt,fxOnly.Utc,staleAt,1.22m,1.23m)},
 staleFunded.NextEventOrdinal),"STALE_FX_BID_HALTS_ALL_THREE_FUNDED_EXPOSURES");
Refuse(()=>staleFunded.CaptureReplay(source),"HALTED_THREE_POSITION_BOOK_CANNOT_CHECKPOINT");
Refuse(()=>MxmPortfolioAccountReplay.RestoreReplay(panelCapsule.Payload,panelCapsule.Sha256,source,
 declared with {UsdQuoteMetadataJson=Registration(new string('b',64))},roster),"DECLARED_SOURCE_CANNOT_CHANGE_ON_RESTORE");
foreach(string bad in new[]{Registration(source).Replace("USD\"}","JPY\"}"),
 Registration(source).Replace("250","111"),Registration(source).Replace("SpotCrude","USDJPY"),
 Registration(source).Replace("\"schema\":","\"extra\":true,\"schema\":"),
 Registration(source).Replace("\"symbol_id\":5","\"symbol_id\":5,\"symbol_id\":5"),
 Registration("bad"),"{}","[]","null","{",Registration(source).Replace("\"USD\"","42")})
 Refuse(()=>new MxmPortfolioAccountReplay(roster,declared with {UsdQuoteMetadataJson=bad}),"INVALID_DECLARATION");
Refuse(()=>new MxmPortfolioAccountReplay(roster,declared with {UseSharedUsdConversion=false}),"DECLARATION_REQUIRES_FX_MODE");
Refuse(()=>new MxmPortfolioAccountReplay(new[]{"AUDUSD","Copper"},declared),"DECLARATION_ROSTER_MUST_MATCH");
Refuse(()=>new MxmPortfolioAccountReplay(roster,Settings()),"NO_IMPLICIT_NEW_CURRENCY_REGISTRATION");
Need(!JsonSerializer.Serialize(Settings()).Contains("UsdQuoteMetadataJson"),"LEGACY_SETTINGS_SERIALIZATION_UNCHANGED");
var declaredPanel=new{symbols=roster,initial_capital_eur=panelDirect.InitialCapitalEur,entries=panelDirect.AcceptedEntries,
 margin_eur=panelDirect.UsedMarginEur,cash_eur=panelDirect.FinalCashEur,equity_eur=panelDirect.MarkedEquityEur,
 margin_limited_entries=marginReport.AcceptedEntries,risk_limited_entries=riskReport.AcceptedEntries,
 declaration_is_broker_authentication=false,synthetic_only=true};
var financing=MxmFinancingFixture.Run();
Console.WriteLine(JsonSerializer.Serialize(new{schema="mxm.shared-usd-account.artificial.v1",checks,proofs,fee_case=feeCase,financing,declared_panel=declaredPanel,
 broker_orders=0,native_ctrader_runtime_reception=false,economic_edge_proven=false,hard21_proven=false}));

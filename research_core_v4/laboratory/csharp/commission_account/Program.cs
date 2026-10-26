using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
if(MxmPortfolioReplayRecoveryProbe.TryWorker(args,out int workerExit)){Environment.ExitCode=workerExit;return;}
if(args.Length==3 && args[0]=="--floors"){
 using var input=JsonDocument.Parse(File.ReadAllBytes(args[1]));var output=new List<object>();
 var fixedFx=new Dictionary<string,decimal>{{"USD",.9m},{"EUR",1m}};
 foreach(var item in input.RootElement.EnumerateArray()){
  var term=MxmInstrumentCommission.Decode(item.GetProperty("full"),item.GetProperty("symbol_id").GetInt64(),item.GetProperty("quote_asset").GetString()!);
  output.Add(MxmCommissionFloorCalculator.Compute(term,fixedFx));
 }
 File.WriteAllText(args[2],JsonSerializer.Serialize(output));return;
}
int checks=0;void Need(bool ok){checks++;if(!ok)throw new Exception("COMMISSION_ACCOUNT_FIXTURE_"+checks);}
void Bad(Action a){bool bad=false;try{a();}catch(ArgumentException){bad=true;}Need(bad);}
string policy=new('e',64),costPolicy=new('c',64),metadata=new('a',64);
var parameters=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,120m,.01m,.6m,ExplicitPolicySha256:policy);
var terms=new MxmCommissionTerms(9999,"USD",2,3000000000,1,10000000,"EUR",100000,100000000,100000,10000000);
var scenario=new MxmCommissionScenario(costPolicy,metadata,"TESTUSD",9999,terms);
var t=new DateTime(2026,1,5,10,0,0,DateTimeKind.Utc);
var fx=new Dictionary<string,decimal>{{"USD",.9m},{"EUR",1m}};
MxmQuote Q(DateTime at,decimal bid)=>new(at,"TESTUSD",bid,bid+.0002m,.9m,1000m,50m,0m,.00002m,1.08m,.9m,
 StopDistanceQuote:.0012m,BidSourceUtc:at,AskSourceUtc:at);
MxmBoundedCommissionQuote Apply(MxmQuote q)=>MxmCommissionQuoteAdapter.Apply(q,scenario,costPolicy,q.Utc,1m,fx,parameters);
var original=Q(t,1.2m);var first=Apply(original);
Need(original.CommissionPerSideEur==0 && first.ChargedPerSideCeilingEur==.27m);
Need(first.Quote.Bid==original.Bid && first.Quote.Ask==original.Ask && first.Quote.ExecutableUnits==original.ExecutableUnits && first.Quote.InitialMarginEur==original.InitialMarginEur);
Bad(()=>MxmCommissionQuoteAdapter.Apply(original,scenario,new string('d',64),t,1m,fx,parameters));
Bad(()=>Apply(original with {Symbol="OTHER"}));Bad(()=>Apply(original with {CommissionPerSideEur=.1m}));
Bad(()=>Apply(original with {BidSourceUtc=t.AddMilliseconds(-5001)}));
Bad(()=>MxmCommissionQuoteAdapter.Apply(original,scenario,costPolicy,t.AddSeconds(1),1m,fx,parameters));
Bad(()=>MxmCommissionQuoteAdapter.Apply(original,scenario,costPolicy,t,1m,fx,parameters with {RoundTripRiskReserveEur=.5m}));
Bad(()=>MxmCommissionQuoteAdapter.Apply(original,scenario,costPolicy,t,1m,new Dictionary<string,decimal>{{"USD",.8m},{"EUR",1m}},parameters));
var percent=scenario with {Terms=terms with {Kind=3,PreciseRate=1000,PreciseMinimum=0}};
var pc=MxmCommissionQuoteAdapter.Apply(original,percent,costPolicy,t,1m,fx,parameters);
Need(pc.BuyCost.UnroundedFeeEur>pc.SellCost.UnroundedFeeEur && pc.ChargedPerSideCeilingEur==pc.BuyCost.UnroundedFeeEur);
var feed=new MxmAccountFeed[]{first.Quote,new MxmExplicitDecision(t,"TESTUSD",1,1,t.AddMilliseconds(250),t.AddSeconds(5),policy),
 Apply(Q(t.AddMilliseconds(250),1.2m)).Quote,
 new MxmExplicitDecision(t.AddSeconds(1),"TESTUSD",2,0,t.AddMilliseconds(1250),t.AddSeconds(6),policy),Apply(Q(t.AddMilliseconds(1250),1.2005m)).Quote};
var engine=new MxmPortfolioAccountReplay(new[]{"TESTUSD"},parameters);var report=engine.Run(feed);
Need(report.InitialCapitalEur==200m && report.AcceptedEntries==1 && report.ExecutedExits==1 && report.OpenPositions==0);
Need(report.Ledger.All(x=>x.CommissionEur==.27m));Need(report.FinalCashEur==199.694m);
string context=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new{scenario,parameters,classification="ARTIFICIAL_ONLY"})))).ToLowerInvariant();
for(int cut=0;cut<=feed.Length;cut++){
 var a=new MxmPortfolioAccountReplay(new[]{"TESTUSD"},parameters);a.Run(feed.Take(cut));var capsule=a.CaptureReplay(context);
 var b=MxmPortfolioAccountReplay.RestoreReplay(capsule.Payload,capsule.Sha256,context,parameters,new[]{"TESTUSD"});
 Need(JsonSerializer.Serialize(report)==JsonSerializer.Serialize(b.Continue(feed.Skip(cut),cut)));
}
var proof=MxmPortfolioReplayRecoveryProbe.Verify(feed,parameters,new[]{"TESTUSD"},context,report,new[]{1,2,4});
Need(proof.ColdProcesses==3);
var live=new MxmPortfolioAccountReplay(new[]{"TESTUSD"},parameters);live.Run(feed.Take(3));
Bad(()=>live.Continue(new[]{new MxmInstrumentQuoteUnavailable(t.AddSeconds(1),"TESTUSD","UNPRICED")},3));Bad(()=>live.Report());
Console.WriteLine(JsonSerializer.Serialize(new{schema="mxm.commission-account-artificial.v1",checks,cold_processes=proof.ColdProcesses,
 classification="ARTIFICIAL_QUOTES_AND_FX_ONLY",context_sha256=context,parameters,source_quote=original,bounded_quote=first,percent_bound=pc,account=report,
 funding_count=1,market_account_replay=false,historical_costs_proven=false,native_ctrader_runtime_reception=false,hard21_proven=false,orders=0}));

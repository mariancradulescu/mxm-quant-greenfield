using System.Text.Json;
using System.Globalization;
using Mxm.Replay;
if(MxmPortfolioReplayRecoveryProbe.TryWorker(args,out int workerExit)){Environment.ExitCode=workerExit;return;}
if(args.Length==2){
 using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var output=new List<object>();
 foreach(var r in doc.RootElement.EnumerateArray()){
  var estimates=new List<object>();string? failure=null;
  foreach(int direction in new[]{1,-1}){
   try{
    if(r.GetProperty("quote_asset").ValueKind==JsonValueKind.Null)throw new ArgumentException("QUOTE_ASSET_UNRESOLVED");
    var f=r.GetProperty("full");long Integer(string k)=>long.Parse(f.GetProperty(k).ToString(),CultureInfo.InvariantCulture);
    long volume=Integer("minVolume"),step=Integer("stepVolume"),max=Integer("maxVolume");
    if(volume<=0 || step<=0 || max<volume || volume%step!=0)throw new ArgumentException("VOLUME_LATTICE_UNRESOLVED");
    int kind=(int)Integer("swapCalculationType");if(kind!=0 && kind!=2)throw new ArgumentException("PERCENTAGE_OR_UNKNOWN_CASH_BASIS_UNRESOLVED");
    int exponent=(int)Integer(kind==0?"pipPosition":"digits");
    var x=new MxmDisplayedFinancing(r.GetProperty("symbol_id").GetInt64(),r.GetProperty("quote_asset").GetString()!,kind,
     f.GetProperty(direction==1?"swapLong":"swapShort").GetString()!,volume,direction,exponent,1,r.GetProperty("source_sha256").GetString()!);
    var q=MxmDisplayedFinancingCalculator.Estimate(x);estimates.Add(new{direction,status="DISPLAYED_RATE_UNIT_COMPONENT_ONLY",component=q});
   }catch(Exception e) when(e is ArgumentException or KeyNotFoundException or FormatException or OverflowException or InvalidOperationException){
    failure=e is ArgumentException?e.Message:"EXPLICIT_FIELD_UNRESOLVED";estimates.Add(new{direction,status="UNRESOLVED",reason=failure});
   }
  }
  output.Add(new{symbol_id=r.GetProperty("symbol_id").GetInt64(),estimates});
 }
 File.WriteAllText(args[1],JsonSerializer.Serialize(output));return;
}
if(args.Length!=0)throw new ArgumentException("ARGUMENTS");
int checks=0;void Need(bool b){checks++;if(!b)throw new Exception("DISPLAYED_FINANCING_ACCOUNT_"+checks);}
string source=new('a',64),policy=new('b',64),scenario=new('c',64);
var settings=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,120m,.01m,.6m,FinancingScenarioSha256:scenario,ExplicitPolicySha256:policy,RequireObservedExposurePath:true);
var t=new DateTime(2026,1,5,10,0,0,DateTimeKind.Utc);
MxmQuote Q(DateTime at)=>new(at,"TESTEUR",1m,1.0002m,1m,1000m,50m,.01m,0m,1m,1m,BidSourceUtc:at,AskSourceUtc:at);
var debit=MxmDisplayedFinancingCalculator.Estimate(new(42,"EUR",0,"-1.234567890123456789",100000,1,4,1,source));
var credit=MxmDisplayedFinancingCalculator.Estimate(new(42,"EUR",2,"1.234567890123456789",100000,1,4,1,source));
void Bad(Action action){bool bad=false;try{action();}catch(ArgumentException){bad=true;}Need(bad);}
Bad(()=>MxmFinancingScenarioAdapter.Bind(debit,new string('e',64),42,"EUR",scenario,"TESTEUR",t,t,1,1000m,t,t,1m,1m));
Bad(()=>MxmFinancingScenarioAdapter.Bind(debit,source,42,"EUR",scenario,"TESTEUR",t,t,-1,1000m,t,t,1m,1m));
Bad(()=>MxmFinancingScenarioAdapter.Bind(debit,source,42,"EUR",scenario,"TESTEUR",t,t,1,999m,t,t,1m,1m));
Bad(()=>MxmDisplayedFinancingCalculator.ConvertScenario(debit,.9m,1m));
var usd=debit with {Asset="USD"};Need(MxmDisplayedFinancingCalculator.ConvertScenario(usd,.9m,1m)==debit.AmountQuote);
Bad(()=>MxmDisplayedFinancingCalculator.ConvertScenario(usd,1m,.9m));
Bad(()=>MxmFinancingScenarioAdapter.Bind(debit,source,43,"EUR",scenario,"TESTEUR",t,t,1,1000m,t,t,1m,1m));
Bad(()=>MxmFinancingScenarioAdapter.Bind(debit,source,42,"USD",scenario,"TESTEUR",t,t,1,1000m,t,t,1m,1m));
var feed=new MxmAccountFeed[]{Q(t),new MxmExplicitDecision(t,"TESTEUR",1,1,t.AddMilliseconds(250),t.AddSeconds(5),policy),Q(t.AddMilliseconds(250)),
 MxmFinancingScenarioAdapter.Bind(debit,source,42,"EUR",scenario,"TESTEUR",t.AddSeconds(1),t.AddMilliseconds(250),1,1000m,t.AddMilliseconds(250),t.AddMilliseconds(750),1m,1m),
 MxmFinancingScenarioAdapter.Bind(credit,source,42,"EUR",scenario,"TESTEUR",t.AddSeconds(2),t.AddMilliseconds(250),1,1000m,t.AddMilliseconds(750),t.AddMilliseconds(1750),1m,1m),
 new MxmExplicitDecision(t.AddSeconds(2),"TESTEUR",2,0,t.AddMilliseconds(2250),t.AddSeconds(5),policy),Q(t.AddMilliseconds(2250))};
var account=new MxmPortfolioAccountReplay(new[]{"TESTEUR"},settings);var report=account.Run(feed);
Need(report.InitialCapitalEur==200m && report.AcceptedEntries==1 && report.ExecutedExits==1 && report.OpenPositions==0);
Need(report.Ledger.Count(x=>x.Kind=="FINANCING")==2);
Need(report.FinalCashEur==199.779999999999999999m); // spread .20 + two .01 fees + adverse quantum dust
string context=new('d',64);
for(int cut=0;cut<=feed.Length;cut++){
 var a=new MxmPortfolioAccountReplay(new[]{"TESTEUR"},settings);a.Run(feed.Take(cut));var capsule=a.CaptureReplay(context);
 var b=MxmPortfolioAccountReplay.RestoreReplay(capsule.Payload,capsule.Sha256,context,settings,new[]{"TESTEUR"});
 Need(JsonSerializer.Serialize(report)==JsonSerializer.Serialize(b.Continue(feed.Skip(cut),cut)));
}
var proof=MxmPortfolioReplayRecoveryProbe.Verify(feed,settings,new[]{"TESTEUR"},context,report,new[]{3,4,5});Need(proof.ColdProcesses==3);
Console.WriteLine(JsonSerializer.Serialize(new{checks,account=report,cold_processes=proof.ColdProcesses,market_account_replay=false,orders=0}));

using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;
using Mxm.Research;
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));var input=doc.RootElement;string policy=input.GetProperty("policy").GetString()!;
Dictionary<long,decimal[]> Bars(string name)=>input.GetProperty(name).EnumerateArray().ToDictionary(x=>x[0].GetInt64(),x=>x.EnumerateArray().Skip(1).Select(y=>y.GetDecimal()).ToArray());
var target=Bars("target");var anchor=Bars("anchor");var fx=Bars("fx");
var terms=input.GetProperty("terms");decimal units=terms.GetProperty("units").GetDecimal(),margin=terms.GetProperty("margin_eur").GetDecimal(),feeUsd=terms.GetProperty("fee_usd").GetDecimal(),pnlRate=terms.GetProperty("pnl_rate").GetDecimal();
var settings=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,120m,.01m,.2m,MaxQuoteAgeSeconds:3601,ExplicitPolicySha256:policy,NativeSizingScenarioSha256:policy,FinancingScenarioSha256:policy);
var account=new MxmPortfolioAccountReplay(new[]{"SpotCrude"},settings);account.Run(Array.Empty<MxmAccountFeed>());
var weekMarks=new List<decimal>();
var kernel=new MxmCommodityAnchorKernel();var decisions=new List<MxmAnchorDecision>();var proposals=new List<object>();string? fault=null;long sequence=0,busy=-1;int entered=0;long? flattenAt=null;MxmPortfolioAccountReport? last=null;int cold=0,missing=0;
DateTime U(long t)=>DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
void Feed(MxmAccountFeed e){if(fault!=null)return;try{last=account.Report();account.Continue(new[]{e},account.NextEventOrdinal);}catch(ArgumentException ex){fault=ex.Message;}}
void Intent(long t,int desired,long valid){sequence++;Feed(new MxmExplicitDecision(U(t),"SpotCrude",sequence,desired,U(valid),U(valid+1000),policy));}
void Q(long t,decimal price,decimal fb,decimal fa) {
 decimal fee=feeUsd/fb+.03m;
 var a=fault==null?account.Report():null;
 if(a!=null && a.OpenPositions>0) {
  var entry=a.Ledger.Last(x=>x.Kind=="ENTRY");decimal worst=Math.Max(Math.Abs(price-.02m-entry.Price),Math.Abs(price+.12m-entry.Price));
  fee+=worst*units*pnlRate/fb; // dated PnL conversion percentage, conditional historical use
 }
 Feed(new MxmQuote(U(t),"SpotCrude",price,price+.10m,1m/fa,units,margin,fee,.02m,.5m*units/fb,1m/fb,
  StopDistanceQuote:.50m,BidSourceUtc:U(t),AskSourceUtc:U(t),NativeSizingScenarioSha256:policy,
  BrokerVolumeMinUnits:units,BrokerVolumeMaxUnits:terms.GetProperty("max_units").GetDecimal(),BrokerVolumeStepUnits:terms.GetProperty("step_units").GetDecimal()));
}
long first=input.GetProperty("start").GetInt64(),end=input.GetProperty("end").GetInt64();
for(long t=first;t<end;t+=3600000) {
 if(t>first && U(t).DayOfWeek==DayOfWeek.Monday && U(t).Hour==0 && fault==null) {
  if(t>=input.GetProperty("evaluation_start").GetInt64())weekMarks.Add(account.Report().MarkedEquityEur);
  var c=account.CaptureReplay(policy);account=MxmPortfolioAccountReplay.RestoreReplay(c.Payload,c.Sha256,policy,settings,new[]{"SpotCrude"});
  kernel=new MxmCommodityAnchorKernel(kernel.Capture());cold++;
 }
 target.TryGetValue(t,out var z);fx.TryGetValue(t,out var f);
 if(z==null || f==null) {missing++;Feed(new MxmInstrumentQuoteUnavailable(U(t),"SpotCrude","H1_SCENARIO_SOURCE_MISSING"));continue;}
 Q(t,z![0],f![0],f[0]+.0003m);
 var r=fault==null?account.Report():null;
 if(r!=null && r.AcceptedEntries>entered){entered=r.AcceptedEntries;flattenAt=t+3600000;Intent(t,0,flattenAt.Value);
   var held=r.Ledger.Last(x=>x.Kind=="ENTRY");
   Feed(new MxmFinancingCashflow(U(t+1),"SpotCrude",held.Utc,held.Direction,units,held.Utc,U(t+1),-.10m,policy));}
 if(flattenAt.HasValue && t>=flattenAt.Value)flattenAt=null;
 MxmAnchorDecision? d=null;
 if(target.TryGetValue(t-3600000,out var prior) && anchor.TryGetValue(t-3600000,out var ap)) {
  d=kernel.Completed(t,prior[3],ap[3]);decisions.Add(d);
 }
 var utc=U(t);
 if(t>=input.GetProperty("evaluation_start").GetInt64() && d!=null && d.Direction!=0 && utc.DayOfWeek is not (DayOfWeek.Saturday or DayOfWeek.Sunday) && utc.Hour>=7 && utc.Hour<17 && t>=busy && !flattenAt.HasValue && (r==null || r.OpenPositions==0)) {
  // Future entry/exit support is deliberately NOT inspected here.
  proposals.Add(new{t,d.Direction});busy=t+7200000;Intent(t,d.Direction,t+3600000);
 }
 // Adverse-first OHLC path: a declared pessimistic scenario, NOT native ticks.
 // Entry at the delayed next OPEN, never this bar's hindsight best price.
 var active=fault==null?account.Report():null;bool shortSide=active!=null && active.OpenPositions>0 && active.Ledger.Last(x=>x.Kind=="ENTRY").Direction<0;
 Q(t+1000,shortSide?z[1]:z[2],f[2],f[1]+.0003m);
 Q(t+1800000,shortSide?z[2]:z[1],f[2],f[1]+.0003m);
 Q(t+3599000,z[3],f[3],f[3]+.0003m);
}
Feed(new MxmInstrumentQuoteUnavailable(U(end),"SpotCrude","DECLARED_ARCHIVE_END_NO_PRICE"));
var report=fault==null?account.Report():null;
if(report!=null)weekMarks.Add(report.MarkedEquityEur);
string hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(decisions)))).ToLowerInvariant();
File.WriteAllText(args[1],JsonSerializer.Serialize(new{schema="mxm.commodity-anchor-h1-scenario.v1",policy,input_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),decisions,proposals,decision_sha256=hash,account=report,fault,last_verified_prefix=fault==null?null:last,missing,cold,weekMarks,
 initial_funding_count=1,initial_capital_eur=200,models=1,cost_scenarios=1,observed_bidask_path=false,historical_costs_proven=false,actual_fills=false,hard21_proven=false,edge_proven=false,orders=0}));

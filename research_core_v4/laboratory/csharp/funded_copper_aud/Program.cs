using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Replay;

if(args.Length!=2)throw new ArgumentException("EXACT_INPUT_OUTPUT");
using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
var source=doc.RootElement;
string policy=source.GetProperty("policy").GetString()!;
Dictionary<long,decimal[]> Bars(string k)=>source.GetProperty(k).EnumerateArray()
 .ToDictionary(z=>z[0].GetInt64(),z=>z.EnumerateArray().Skip(1).Select(v=>v.GetDecimal()).ToArray());
var aud=Bars("aud");var copper=Bars("copper");var fx=Bars("fx");
long start=source.GetProperty("start").GetInt64(),end=source.GetProperty("end").GetInt64();
const long H=3600000L;
DateTime U(long x)=>DateTimeOffset.FromUnixTimeMilliseconds(x).UtcDateTime;
var config=new MxmReplayParameters(StrategyMode.TrendOnly,.4m,1,120m,.01m,.4m,
 MaxQuoteAgeSeconds:3601,ExplicitPolicySha256:policy,NativeSizingScenarioSha256:policy);
var account=new MxmPortfolioAccountReplay(new[]{"AUDUSD"},config);
account.Run(Array.Empty<MxmAccountFeed>());
string? fault=null;long ordinal=0,busy=0;long? exitAt=null;int lastAccepted=0;int restores=0,missing=0;
var decisions=new List<object>();var proposals=new List<object>();var weekly=new List<object>();
MxmPortfolioAccountReport? last=null;
void Feed(MxmAccountFeed e){
 if(fault!=null)return;
 try {last=account.Continue(new[]{e},account.NextEventOrdinal);}
 catch(ArgumentException ex){fault=ex.Message;}
}
void Policy(long at,int desired,long valid){
 ordinal++;
 Feed(new MxmExplicitDecision(U(at),"AUDUSD",ordinal,desired,U(valid),U(valid+1000),policy));
}
void Q(long ts,decimal mark,decimal fxBid,decimal fxAsk){
 if(fault!=null)return;
 if(mark<=.001m || fxBid<=0 || fxAsk<=fxBid)throw new ArgumentException("INVALID_REF_QUOTES");
 const decimal width=.00015m;
 Feed(new MxmQuote(U(ts),"AUDUSD",mark-width/2,mark+width/2,1m/fxAsk,
  1000m,31.04m,.04m,.00005m,1.2m/fxBid,1m/fxBid,
  StopDistanceQuote:.0012m,BidSourceUtc:U(ts),AskSourceUtc:U(ts),
  NativeSizingScenarioSha256:policy,
  BrokerVolumeMinUnits:1000m,BrokerVolumeMaxUnits:1000m,BrokerVolumeStepUnits:1000m));
}
for(long t=start;t<end;t+=H){
 if(fault!=null)break;
 if(t>start && U(t).DayOfWeek==DayOfWeek.Monday && U(t).Hour==0){
  var check=account.Report();weekly.Add(new{iso_week_start=U(t),cash=check.FinalCashEur,equity=check.MarkedEquityEur,entries=check.AcceptedEntries});
  var save=account.CaptureReplay(policy);
  account=MxmPortfolioAccountReplay.RestoreReplay(save.Payload,save.Sha256,policy,config,new[]{"AUDUSD"});
  restores++;
 }
 bool hasAud=aud.TryGetValue(t,out var current);
 bool hasFx=fx.TryGetValue(t,out var currency);
 if(!hasAud || !hasFx || current==null || currency==null){
  missing++;
  if(account.Report().OpenPositions>0) Feed(new MxmInstrumentQuoteUnavailable(U(t),"AUDUSD","MISSING_H1_REFERENCE_EXPOSURE"));
  continue;
 }
 decimal fxRef=currency[0];
 Q(t,current[0],fxRef-.0003m,fxRef+.0003m);
 if(fault!=null)break;
 if(exitAt.HasValue && t==exitAt.Value-H){
  Policy(t,0,exitAt.Value);
 }
 var report=account.Report();
 if(report.AcceptedEntries>lastAccepted){
  if(report.AcceptedEntries!=lastAccepted+1)throw new ArgumentException("MULTI_ENTRY_WITHOUT_RECONCILIATION");
  lastAccepted=report.AcceptedEntries;
  exitAt=t+2*H;
 }
 if(exitAt.HasValue && t>=exitAt.Value)exitAt=null;
 if(U(t).DayOfWeek is not (DayOfWeek.Saturday or DayOfWeek.Sunday) &&
    U(t).Hour>=7 && U(t).Hour<=15 &&
    t>=busy && report.OpenPositions==0 &&
    aud.TryGetValue(t-H,out var audLast)&&aud.TryGetValue(t-4*H,out var audBefore) &&
    copper.TryGetValue(t-H,out var copLast)&&copper.TryGetValue(t-4*H,out var copBefore)){
  decimal ar=audLast[3]/audBefore[3]-1m,cr=copLast[3]/copBefore[3]-1m;
  int direction=Math.Abs(cr)>.004m && Math.Abs(ar)<.001m?(cr>0?1:-1):0;
  decisions.Add(new{t,available=U(t),aud_3h_return=ar,copper_3h_return=cr,direction});
  if(direction!=0){
   proposals.Add(new{t,direction});
   Policy(t,direction,t+H);
   busy=t+3*H;
  }
 }
 // Future OHLC extreme order is a declared pessimistic REFERENCE SCENARIO, never actual tick chronology.
 // For a held BUY the LOW is sampled first; for a held SELL the HIGH is sampled first.
 bool shortSide=account.Report().OpenPositions>0 && account.Report().Ledger.Last(z=>z.Kind=="ENTRY").Direction<0;
 Q(t+1000,shortSide?current[1]:current[2],currency[2]-.0003m,currency[2]+.0003m);
 Q(t+1800000,shortSide?current[2]:current[1],currency[1]-.0003m,currency[1]+.0003m);
 Q(t+3599000,current[3],currency[3]-.0003m,currency[3]+.0003m);
}
var final=account.Report();
weekly.Add(new{iso_week_start=U(end),cash=final.FinalCashEur,equity=final.MarkedEquityEur,entries=final.AcceptedEntries});
var output=new{schema="mxm.funded200.copper-audusd.csharp-original.v1",policy,
 input_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
 initial_cash_eur=200,deposit_count=1,additional_deposits=0,reset_count=0,
 model="COPPER_SHOCK_TO_UNRESPONSIVE_AUDUSD",decisions,proposals,account=final,
 iso_week_boundaries=weekly,restored_process_count=restores,source_gaps=missing,fault,
 first_execution_only=true,market_quotes_observed=false,ohlc_intrabar_event_order_observed=false,
 total_broker_costs_historical=false,historical_broker_fills=false,orders=0,cloud=false};
File.WriteAllText(args[1],JsonSerializer.Serialize(output));
Console.WriteLine("MXM_FUNDED_COPPER_AUDUSD_CSHARP "+JsonSerializer.Serialize(new{
 final.Classification,final.InitialCapitalEur,final.FinalCashEur,final.MarkedEquityEur,final.AcceptedEntries,
 final.ExecutedExits,final.MaxDrawdownEur,final.EntriesByIsoWeek,fault,restores,proposals=proposals.Count,
 model_executes=1,original_broker_quotes=false,stage_b_certified=false}));

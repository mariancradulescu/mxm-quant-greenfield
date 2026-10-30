using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

// Offline research ONLY. This .csproj is not included in the operational cBot.
// Causal policy decisions use cash known at entry, NEVER future episode P&L.
// Recorded source episodes stay unchanged. A skipped episode does not invent
// alternative future signals, and none of these results is a native backtest.
public sealed record RiskEpisode(string Symbol, DateTime EntryUtc,DateTime ExitUtc,
 decimal Units,decimal MarginEur,decimal StopRiskEur,decimal EntryFeeEur,
 decimal ExitFeeEur,decimal GrossEur);
public sealed record ResearchPolicy(string Id, decimal MaxMarginToFreeFraction,
 decimal MinimumPostEntryFreeToEquityFraction,decimal MaxEntryStopAndFrictionToEquityFraction,
 decimal RoundTripFrictionReserveEur,decimal? MaximumTicketMarginEur=null,
 decimal? MinimumFreeMarginEur=null,decimal? MaximumTicketRiskEur=null);
public sealed record StudyRequest(string Schema,decimal InitialCapitalEur,
 List<RiskEpisode> Episodes,List<ResearchPolicy> Policies);
public sealed record StudyResult(string Policy,string Stress,int Accepted,int Skipped,
 string FinalCashEur,string MinimumClosedCashEur,string MaximumClosedDrawdownEur,
 string MinimumPostEntryFreeMarginEur,string MaximumUsedMarginEur,
 int InsolvencyBreaches, int ExposureReserveBreaches, int WeeksWithEntries,
 Dictionary<string,int> EntryCountsByIsoWeek);
public static class Program {
 static readonly JsonSerializerOptions Json=new() {
  PropertyNameCaseInsensitive=true,NumberHandling=JsonNumberHandling.AllowReadingFromString
 };
 static void Need(bool ok,string s){if(!ok)throw new ArgumentException("MXM_OFFLINE_RISK_"+s);}
 static bool ValidDecimal(decimal x)=>x>=0m;
 static string Str(decimal x)=>x.ToString(CultureInfo.InvariantCulture);
 static string Week(DateTime t)=>ISOWeek.GetYear(t).ToString(CultureInfo.InvariantCulture)+"-W"+
  ISOWeek.GetWeekOfYear(t).ToString("D2",CultureInfo.InvariantCulture);
 static bool Admit(decimal equity,RiskEpisode e,ResearchPolicy p){
  if(equity<=0m)return false;
  try {checked {
   decimal reserve=Math.Max(equity*p.MinimumPostEntryFreeToEquityFraction,p.MinimumFreeMarginEur??0m);
   decimal ticketCap=Math.Min(equity*p.MaxMarginToFreeFraction,p.MaximumTicketMarginEur??decimal.MaxValue);
   decimal stopFriction=e.StopRiskEur+p.RoundTripFrictionReserveEur;
   decimal riskCap=Math.Min(equity*p.MaxEntryStopAndFrictionToEquityFraction,p.MaximumTicketRiskEur??decimal.MaxValue);
   return e.MarginEur<=ticketCap && stopFriction<=riskCap &&
     equity-e.MarginEur-e.EntryFeeEur>=reserve &&
     equity-e.EntryFeeEur>0m;
  }}catch(OverflowException){return false;}
 }
 static StudyResult Evaluate(StudyRequest r, ResearchPolicy p,string mode) {
  decimal cash=r.InitialCapitalEur,peak=cash,min=cash,dd=0m,minPost=cash,maxMargin=0m;
  int accepted=0,skipped=0,insolvency=0,reserveBreaches=0;
  var weeks=new Dictionary<string,int>(StringComparer.Ordinal);
  foreach(var e in r.Episodes) {
   if(!Admit(cash,e,p)){skipped++;continue;}
   accepted++;
   decimal costFactor=mode is "DOUBLE_COMMISSION" or "ALL_STOP_GAP_2X" ? 2m:1m;
   decimal entryFee=e.EntryFeeEur*costFactor;
   decimal exitFee=e.ExitFeeEur*costFactor;
   decimal gross=mode switch {
    "RECORDED_CSHARP" or "DOUBLE_COMMISSION"=>e.GrossEur,
    "ALL_ESTIMATED_STOPS"=>-e.StopRiskEur,
    "ALL_STOP_GAP_2X"=>-2m*e.StopRiskEur,
    _=>throw new ArgumentException("UNKNOWN_STRESS")
   };
   // This is an adverse conditional mark-to-exit cash ledger. It does not
   // reconstruct intrabar equity, actual broker liquidation or missing signals.
   decimal postEntry=cash-entryFee-e.MarginEur;
   minPost=Math.Min(minPost,postEntry);
   maxMargin=Math.Max(maxMargin,e.MarginEur);
   decimal requiredReserve=Math.Max(cash*p.MinimumPostEntryFreeToEquityFraction,p.MinimumFreeMarginEur??0m);
   if(postEntry<requiredReserve)reserveBreaches++; // stressed entry commission can breach initial reserve
   cash=cash-entryFee+gross-exitFee;
   min=Math.Min(min,cash);peak=Math.Max(peak,cash);dd=Math.Max(dd,peak-cash);
   if(cash<=0m)insolvency++;
   string week=Week(e.EntryUtc);
   weeks[week]=weeks.GetValueOrDefault(week)+1;
  }
  return new(p.Id,mode,accepted,skipped,Str(cash),Str(min),Str(dd),
   Str(minPost),Str(maxMargin),insolvency,reserveBreaches,weeks.Count,weeks);
 }
 public static int Main(string[] args) {
  try {
   Need(args.Length==2,"ARGUMENTS");
   var data=File.ReadAllBytes(args[0]);
   Need(data.Length>0 && data.Length<=8000000,"INPUT_SIZE");
   var r=JsonSerializer.Deserialize<StudyRequest>(data,Json);
   Need(r!=null && r.Schema=="mxm.cold-risk-research.tape.v1" && r.InitialCapitalEur==200m &&
    r.Episodes!=null && r.Episodes.Count>0 && r.Episodes.Count<=100000 &&
    r.Policies!=null && r.Policies.Count==3,"SCHEMA_AND_CAPITAL");
   var validPolicies=r.Policies.All(p=>!string.IsNullOrWhiteSpace(p.Id) &&
    p.MaxMarginToFreeFraction>0m && p.MaxMarginToFreeFraction<=1m &&
    p.MinimumPostEntryFreeToEquityFraction>=0m && p.MinimumPostEntryFreeToEquityFraction<1m &&
    p.MaxEntryStopAndFrictionToEquityFraction>0m && p.MaxEntryStopAndFrictionToEquityFraction<=1m &&
    ValidDecimal(p.RoundTripFrictionReserveEur) &&
    (!p.MaximumTicketMarginEur.HasValue||p.MaximumTicketMarginEur>0) &&
    (!p.MinimumFreeMarginEur.HasValue||p.MinimumFreeMarginEur>=0) &&
    (!p.MaximumTicketRiskEur.HasValue||p.MaximumTicketRiskEur>0));
   Need(validPolicies && r.Policies.Select(p=>p.Id).Distinct(StringComparer.Ordinal).Count()==3 &&
    r.Policies.Select(p=>p.Id).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(
      new[]{"ADAPTIVE_EQUITY_BALANCED","ADAPTIVE_EQUITY_CONSERVATIVE","HISTORICAL_DIRECTOR_CONFIG"},
      StringComparer.Ordinal),"POLICY_ROSTER");
   DateTime prior=default;
   foreach(var e in r.Episodes) {
    Need(e.EntryUtc.Kind==DateTimeKind.Utc && e.ExitUtc.Kind==DateTimeKind.Utc &&
     e.EntryUtc>=prior && e.ExitUtc>e.EntryUtc && e.Units>0m &&
     e.MarginEur>0m && e.StopRiskEur>0m && e.EntryFeeEur>=0m &&
     e.ExitFeeEur>=0m && !string.IsNullOrWhiteSpace(e.Symbol),
     "CAUSAL_AND_COST_INPUT");
    prior=e.ExitUtc;
   }
   var output=new List<StudyResult>();
   foreach(var p in r.Policies)
    foreach(var mode in new[]{"RECORDED_CSHARP","DOUBLE_COMMISSION",
                               "ALL_ESTIMATED_STOPS","ALL_STOP_GAP_2X"})
     output.Add(Evaluate(r,p,mode));
   File.WriteAllText(args[1],JsonSerializer.Serialize(new {
     Schema="mxm.closed-portfolio-research-risk-surface.v1",
     InitialCapitalEur=200,EpisodeCount=r.Episodes.Count,Scenarios=output,
     HistoricalBrokerRiskCertified=false,HistoricalBrokerFillsCertified=false,
     AllStopStressIsProbabilityOfRuin=false,OriginalModelRerun=false,
     NewTradablePolicyQualified=false,OperationalProtectionChanged=false,
     CounterfactualEntryTapeOnly=true
   },Json));
   return 0;
  }catch(Exception e){Console.Error.WriteLine(e.GetType().Name+": "+e.Message);return 3;}
 }
}

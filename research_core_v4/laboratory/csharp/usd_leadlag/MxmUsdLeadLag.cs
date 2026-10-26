using System.Globalization;
using System.Security.Cryptography;
using System.Text;
namespace Mxm.Research;
public sealed record LeadLagEpisode(long Decision,long Entry,long Exit,int Direction,decimal EntryPrice,decimal ExitPrice,decimal GrossUsd,decimal NetUsd,decimal NetEur,int UnmarkedGroups);
public sealed record LeadLagResult(int Signals,int Complete,int Censored,string DecisionSha256,List<LeadLagEpisode> Episodes);
// Finite DEVELOPMENT screen only: unit-ticket economics, no capital/portfolio simulator.
public sealed class MxmUsdLeadLag {
 long minute=-1,blockedUntil=-1; AlignedUsdSnapshot? prior,pending,entry; int direction,signals,censored,unmarked;
 readonly List<LeadLagEpisode> episodes=new();
 readonly StringBuilder decisions=new();
 static decimal Mid(long? b,long? a)=>(b!.Value+a!.Value)/2m;
 static int Hour(long t)=>DateTimeOffset.FromUnixTimeMilliseconds(t).Hour;
 static bool Session(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t);return d.DayOfWeek>=DayOfWeek.Monday && d.DayOfWeek<=DayOfWeek.Friday && d.Hour>=6 && d.Hour<=19 && (d.Hour<19 || d.Minute<=57);}
 void Cancel(long t){censored++;blockedUntil=Math.Max(blockedUntil,pending!.T+80000);pending=null;entry=null;}
 public void Observe(AlignedUsdSnapshot s){
  if(s.Purpose!="GBP_QUOTE_GROUP")return;
  bool ready=s.Code=="READY_STRICT_PRIOR_FX";
  // Advance an existing episode before making any new decision at this quote.
  if(pending is not null){
   if(s.T>pending.T+80000 || !Session(s.T)){Cancel(s.T);}
   else if(entry is null){
    if(!ready || s.T>pending.T+10000)Cancel(s.T);
    else if(s.T>=pending.T+5000)entry=s;
   }else if(s.T>entry.T+65000){Cancel(s.T);}
   else if(!ready){unmarked++;}
   else if(s.T>=entry.T+60000){
    decimal ep=(direction>0?entry.GbpAskRaw!.Value:entry.GbpBidRaw!.Value)/100000m;
    decimal xp=(direction>0?s.GbpBidRaw!.Value:s.GbpAskRaw!.Value)/100000m;
    decimal gross=direction*(xp-ep)*1000m;
    // USD10/100k round trip plus0.1pip per side on1000 units; MODEL not certified terms.
    decimal net=gross-.10m-.02m;
    decimal eur=net/(net>=0?s.FxAskRaw!.Value/100000m:s.FxBidRaw!.Value/100000m);
    episodes.Add(new(pending.T,entry.T,s.T,direction,ep,xp,gross,net,eur,unmarked));pending=null;entry=null;
   }
  }
  long bucket=s.T/60000;
  if(bucket==minute)return;minute=bucket;
  // Exactly first GBP update of each UTC minute; invalid/late samples break history.
  var old=prior;prior=ready && s.T%60000<=5000 && Session(s.T)?s:null;
  int sig=0;
  if(prior is not null && old is not null && old.T/60000==bucket-1){
   decimal fx=Mid(s.FxBidRaw,s.FxAskRaw)/Mid(old.FxBidRaw,old.FxAskRaw)-1m;
   decimal gbp=Mid(s.GbpBidRaw,s.GbpAskRaw)/Mid(old.GbpBidRaw,old.GbpAskRaw)-1m;
   decimal spread=(s.GbpAskRaw!.Value-s.GbpBidRaw!.Value)/Mid(s.GbpBidRaw,s.GbpAskRaw);
   int sign=Math.Sign(fx);
   if(spread>0 && Math.Abs(fx)>=4m*spread && sign*(fx-gbp)>=2m*spread)sig=sign;
  }
  decisions.Append(s.T.ToString(CultureInfo.InvariantCulture)).Append(',').Append(sig).Append('\n');
  if(sig!=0 && pending is null && s.T>blockedUntil){pending=s;direction=sig;unmarked=0;signals++;}
 }
 public LeadLagResult Finish(){if(pending is not null)Cancel(pending.T);return new(signals,episodes.Count,censored,
  Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(decisions.ToString()))).ToLowerInvariant(),episodes);}
}

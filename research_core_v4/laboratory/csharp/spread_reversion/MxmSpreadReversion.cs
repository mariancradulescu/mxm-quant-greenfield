using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Mxm.Replay;
namespace Mxm.Research;
public sealed record SpreadEpisode(long Decision,long Entry,long Exit,int Direction,
 decimal EntryPrice,decimal ExitPrice,decimal GrossUsd,int UnmarkedGroups,long MaximumGroupGapMs);
public sealed record SpreadCensor(long Decision,int Direction,long? Entry,long ObservedThrough,string Reason,int UnmarkedGroups);
public sealed record SpreadResult(int Signals,int Complete,int Censored,string DecisionSha256,
 IReadOnlyList<SpreadEpisode> Episodes,IReadOnlyList<SpreadCensor> Unresolved);
/// <summary>One fixed DEVELOPMENT quote-headroom policy. Source timestamps are
/// model time, never historical receipt or fills. No cash, costs, risk or orders.</summary>
public sealed class MxmSpreadReversion : IDisposable {
 readonly IncrementalHash decisions=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
 readonly List<SpreadEpisode> episodes=new();readonly List<SpreadCensor> censored=new();
 AlignedUsdSnapshot? prior,entry;long? decision;long blocked=-1,last=-1;int direction,signals,unmarked;long maxGap;
 static bool Book(AlignedUsdSnapshot s,bool positive) {
  var shape=MxmBookShape.Classify(s.GbpBidRaw,s.GbpAskRaw);
  return (positive?MxmBookShape.StrictlyPositive(shape):MxmBookShape.NonCrossed(shape)) &&
   s.GbpBidMs.HasValue && s.GbpAskMs.HasValue && s.GbpBidMs<=s.T && s.GbpAskMs<=s.T &&
   s.T-s.GbpBidMs.Value<=5000 && s.T-s.GbpAskMs.Value<=5000;
 }
 static bool Session(long t)=>DateTimeOffset.FromUnixTimeMilliseconds(t).DayOfWeek is not (DayOfWeek.Saturday or DayOfWeek.Sunday);
 void Censor(long t,string reason){censored.Add(new(decision!.Value,direction,entry?.T,t,reason,unmarked));decision=null;entry=null;}
 public void Observe(AlignedUsdSnapshot s) {
  if(s.Purpose!="GBP_QUOTE_GROUP" || s.T<=last)throw new ArgumentException("SPREAD_SOURCE_ORDER_OR_ROLE");
  bool valid=Book(s,true);int issue=0;
  if(decision.HasValue) {
   if(entry==null) {
    if(s.T>decision.Value+1000)Censor(s.T,"ENTRY_TIMEOUT");
    else if(!valid)Censor(s.T,"ENTRY_UNAVAILABLE");
    else if(s.T>=decision.Value+250){entry=s;unmarked=0;maxGap=0;}
   }else {
    if(s.T>entry.T+1500)Censor(s.T,"EXIT_TIMEOUT");
    else {
     maxGap=Math.Max(maxGap,s.T-last);
     if(!Book(s,false))unmarked++;
     if(valid && s.T>=entry.T+1000) {
      decimal ep=(direction>0?entry.GbpAskRaw!.Value:entry.GbpBidRaw!.Value)/100000m;
      decimal xp=(direction>0?s.GbpBidRaw!.Value:s.GbpAskRaw!.Value)/100000m;
      episodes.Add(new(decision.Value,entry.T,s.T,direction,ep,xp,direction*(xp-ep)*1000m,unmarked,maxGap));
      decision=null;entry=null;
     }
    }
   }
  }
  if(!decision.HasValue && s.T>=blocked && valid && prior!=null && Book(prior,true) && s.T-prior.T<=1000 && Session(s.T)) {
   bool bidOnly=s.GbpBidMs==s.T && s.GbpAskMs!=s.T;
   bool askOnly=s.GbpAskMs==s.T && s.GbpBidMs!=s.T;
   long spread=prior.GbpAskRaw!.Value-prior.GbpBidRaw!.Value;
   if(bidOnly && prior.GbpBidRaw!.Value-s.GbpBidRaw!.Value>=spread)issue=1;
   else if(askOnly && s.GbpAskRaw!.Value-prior.GbpAskRaw!.Value>=spread)issue=-1;
   if(issue!=0){decision=s.T;direction=issue;entry=null;signals++;unmarked=0;maxGap=0;blocked=checked(s.T+3000);}
  }
  decisions.AppendData(Encoding.UTF8.GetBytes(s.T.ToString(CultureInfo.InvariantCulture)+","+issue.ToString(CultureInfo.InvariantCulture)+"\n"));
  prior=s;last=s.T;
 }
 public SpreadResult Finish(){if(decision.HasValue)Censor(last,"TERMINAL_UNSETTLED");return new(signals,episodes.Count,censored.Count,Convert.ToHexString(decisions.GetHashAndReset()).ToLowerInvariant(),episodes,censored);}
 public void Dispose()=>decisions.Dispose();
}

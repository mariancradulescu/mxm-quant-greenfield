using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
/// <summary>Unqualified DEVELOPMENT learner. Completed-bar returns in basis points.
/// Fixed bounded rolling ridge AR(1); no fitted configuration or future data.</summary>
internal sealed record MxmAr1ReplayPair(decimal X,decimal Y);
internal sealed record MxmOnlineAr1ReplayState(int CompletedBars,decimal? LastClose,decimal? LastReturn,
 MxmAr1ReplayPair[] Pairs,decimal Sx,decimal Sy,decimal Sxx,decimal Sxy,decimal Forecast,decimal Beta);
internal sealed record MxmDecisionReplayState(int CompletedBars,decimal[] LegacyTail,MxmOnlineAr1ReplayState? Online);
public sealed class MxmOnlineAr1Kernel {
 public const int Window=256,MinimumPairs=128;
 public const decimal Ridge=64m,ThresholdBps=2m,ShockBps=100m;
 readonly Queue<(decimal X,decimal Y)> pairs=new();
 decimal? lastClose,lastReturn;
 decimal sx,sy,sxx,sxy;
 public int CompletedBars {get;private set;}
 public int TrainingPairs=>pairs.Count;
 public decimal ForecastBps {get;private set;}
 public decimal Beta {get;private set;}
 internal MxmOnlineAr1ReplayState CaptureReplayState()=>new(CompletedBars,lastClose,lastReturn,
  pairs.Select(p=>new MxmAr1ReplayPair(p.X,p.Y)).ToArray(),sx,sy,sxx,sxy,ForecastBps,Beta);
 internal void RestoreReplayState(MxmOnlineAr1ReplayState s){
  if(s.CompletedBars<0 || s.Pairs==null || s.Pairs.Length>Window ||
     s.CompletedBars<s.Pairs.Length || (s.LastClose.HasValue && s.LastClose<=0) ||
     (s.LastReturn.HasValue && Math.Abs(s.LastReturn.Value)>ShockBps) ||
     s.Pairs.Any(p=>Math.Abs(p.X)>ShockBps || Math.Abs(p.Y)>ShockBps) || Math.Abs(s.Beta)>.95m)
   throw new ArgumentException("INVALID_ONLINE_REPLAY_STATE");
  Reset();CompletedBars=s.CompletedBars;lastClose=s.LastClose;lastReturn=s.LastReturn;
  foreach(var p in s.Pairs)pairs.Enqueue((p.X,p.Y));
  // Preserve exact decimal accumulation, including its rounding history.
  sx=s.Sx;sy=s.Sy;sxx=s.Sxx;sxy=s.Sxy;ForecastBps=s.Forecast;Beta=s.Beta;
 }
 public void Reset(){
  pairs.Clear();lastClose=lastReturn=null;sx=sy=sxx=sxy=0;
  CompletedBars=0;ForecastBps=Beta=0;
 }
 public int OnCompletedBar(decimal close){
  if(close<=0)throw new ArgumentOutOfRangeException(nameof(close));
  CompletedBars++;
  if(lastClose==null){lastClose=close;return 0;}
  decimal r=10000m*(close/lastClose.Value-1m);lastClose=close;
  if(Math.Abs(r)>ShockBps){Reset();lastClose=close;CompletedBars=1;return 0;}
  if(lastReturn.HasValue){
   var p=(X:lastReturn.Value,Y:r);pairs.Enqueue(p);
   sx+=p.X;sy+=p.Y;sxx+=p.X*p.X;sxy+=p.X*p.Y;
   if(pairs.Count>Window){var old=pairs.Dequeue();sx-=old.X;sy-=old.Y;sxx-=old.X*old.X;sxy-=old.X*old.Y;}
  }
  lastReturn=r;
  if(pairs.Count<MinimumPairs){ForecastBps=Beta=0;return 0;}
  decimal n=pairs.Count,mx=sx/n,my=sy/n;
  decimal variance=Math.Max(0m,sxx-sx*sx/n);
  Beta=Math.Max(-.95m,Math.Min(.95m,(sxy-sx*sy/n)/(variance+Ridge)));
  // All y observations end at this completed close; forecast is for NEXT bar.
  ForecastBps=my+Beta*(r-mx);
  return ForecastBps>ThresholdBps?1:ForecastBps<-ThresholdBps?-1:0;
 }
}
/// <summary>Explicit opt-in preserves every legacy kernel byte and default.</summary>
public sealed class MxmDecisionSource {
 readonly MxmDecisionKernel legacy;
 readonly MxmOnlineAr1Kernel? online;
 readonly Queue<decimal> legacyTail=new();
 int legacyCompleted;
 public MxmDecisionSource(MxmDecisionKernel kernel,bool onlineAr1=false){
  legacy=kernel;online=onlineAr1?new MxmOnlineAr1Kernel():null;
 }
 public int CompletedBars=>online?.CompletedBars??legacyCompleted;
 public void Reset(){if(online!=null)online.Reset();else legacy.Reset();legacyTail.Clear();legacyCompleted=0;}
 public int OnCompletedBar(decimal close){
  if(online!=null)return online.OnCompletedBar(close);
  int result=legacy.OnCompletedBar(close);legacyCompleted++;
  legacyTail.Enqueue(close);if(legacyTail.Count>6)legacyTail.Dequeue();return result;
 }
 internal MxmDecisionReplayState CaptureReplayState()=>new(CompletedBars,legacyTail.ToArray(),online?.CaptureReplayState());
 internal void RestoreReplayState(MxmDecisionReplayState s){
  if(s.CompletedBars<0 || s.LegacyTail==null || s.LegacyTail.Length>6 ||
     s.LegacyTail.Any(x=>x<=0) || (online!=null)!=(s.Online!=null) ||
     (online==null && s.LegacyTail.Length!=Math.Min(6,s.CompletedBars)))
   throw new ArgumentException("INVALID_DECISION_REPLAY_STATE");
  Reset();
  if(online!=null){online.RestoreReplayState(s.Online!);
   if(online.CompletedBars!=s.CompletedBars)throw new ArgumentException("ONLINE_REPLAY_COUNT");}
  else {foreach(var close in s.LegacyTail){legacy.OnCompletedBar(close);legacyTail.Enqueue(close);}
   legacyCompleted=s.CompletedBars;}
 }
}
}

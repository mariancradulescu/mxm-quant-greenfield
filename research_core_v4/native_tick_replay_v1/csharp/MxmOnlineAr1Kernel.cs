using System;
using System.Collections.Generic;
namespace Mxm.Replay {
/// <summary>Unqualified DEVELOPMENT learner. Completed-bar returns in basis points.
/// Fixed bounded rolling ridge AR(1); no fitted configuration or future data.</summary>
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
 public MxmDecisionSource(MxmDecisionKernel kernel,bool onlineAr1=false){
  legacy=kernel;online=onlineAr1?new MxmOnlineAr1Kernel():null;
 }
 public int CompletedBars=>online?.CompletedBars??legacy.CompletedBars;
 public void Reset(){if(online!=null)online.Reset();else legacy.Reset();}
 public int OnCompletedBar(decimal close)=>online!=null?online.OnCompletedBar(close):legacy.OnCompletedBar(close);
}
}

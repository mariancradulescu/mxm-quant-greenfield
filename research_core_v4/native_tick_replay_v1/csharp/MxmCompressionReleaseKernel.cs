using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
/// <summary>Unqualified DEVELOPMENT hypothesis. Prior-range compression, then a completed-close
/// channel release. No future bars, clock/session inference, fit, account or broker call.</summary>
public sealed class MxmCompressionReleaseKernel {
 public const int BaselineBars=48,FastBars=6,ChannelBars=12;
 public const decimal CompressionRatio=.6m;
 sealed record Bar(decimal High,decimal Low,decimal Close,decimal TrueRange);
 readonly Queue<Bar> bars=new();
 decimal? priorClose;
 public void Reset(){bars.Clear();priorClose=null;}
 public int OnCompletedBar(decimal high,decimal low,decimal close){
  if(low<=0 || high<low || close<low || close>high)throw new ArgumentException("COMPRESSION_OHLC");
  int direction=0;
  if(bars.Count==BaselineBars){
   var previous=bars.ToArray();decimal baseline=previous.Sum(x=>x.TrueRange);
   decimal fast=previous.Skip(BaselineBars-FastBars).Sum(x=>x.TrueRange);
   if(baseline>0 && fast*BaselineBars<=CompressionRatio*baseline*FastBars){
    var channel=previous.Skip(BaselineBars-ChannelBars);
    if(close>channel.Max(x=>x.High))direction=1;
    else if(close<channel.Min(x=>x.Low))direction=-1;
   }
  }
  decimal range=priorClose.HasValue?Math.Max(high-low,Math.Max(Math.Abs(high-priorClose.Value),Math.Abs(low-priorClose.Value))):high-low;
  bars.Enqueue(new(high,low,close,range));if(bars.Count>BaselineBars)bars.Dequeue();priorClose=close;
  return direction;
 }
}
}

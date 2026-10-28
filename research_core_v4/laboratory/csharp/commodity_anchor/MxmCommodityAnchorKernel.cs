using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Research {
// One unhedged target, not a paired arbitrage. Only completed co-observed bars.
public sealed record MxmAnchorSample(long Time,decimal Basis);
public sealed record MxmAnchorDecision(long Time,int Count,decimal Basis,decimal Mean,decimal Variance,int Direction);
public sealed class MxmCommodityAnchorKernel {
 readonly Queue<MxmAnchorSample> samples=new();long previous=-1;
 public MxmAnchorSample[] Capture()=>samples.ToArray();
 public MxmCommodityAnchorKernel(MxmAnchorSample[]? state=null) {
  foreach(var s in state??Array.Empty<MxmAnchorSample>()) {
   if(s.Time<=previous || s.Time%3600000!=0 || samples.Count>=48)throw new ArgumentException("ANCHOR_STATE");
   samples.Enqueue(s);previous=s.Time;
  }
 }
 public MxmAnchorDecision Completed(long time,decimal target,decimal anchor) {
  if(time%3600000!=0 || time<=previous || target<=0 || anchor<=0)throw new ArgumentException("ANCHOR_COMPLETED_SOURCE");
  while(samples.Count>0 && time-samples.Peek().Time>7*86400000L)samples.Dequeue();
  decimal basis=target/anchor,mean=0,variance=0;int direction=0;
  if(samples.Count==48) {
   mean=samples.Average(s=>s.Basis);variance=samples.Average(s=>(s.Basis-mean)*(s.Basis-mean));
   decimal deviation=basis-mean;
   if(Math.Abs(deviation*anchor)>.30m && deviation*deviation>variance)direction=deviation>0?-1:1;
  }
  var result=new MxmAnchorDecision(time,samples.Count,basis,mean,variance,direction);
  samples.Enqueue(new(time,basis));if(samples.Count>48)samples.Dequeue();previous=time;return result;
 }
}

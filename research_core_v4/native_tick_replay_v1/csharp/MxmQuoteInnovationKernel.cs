using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Research {
// Quote-change counts are not traded volume, orders, depth or a liquidity claim.
// This is a prospective DEVELOPMENT forecaster, not an admitted trading model.
public sealed record MxmInnovationSample(decimal X,decimal Y);
public sealed record MxmInnovationForecast(long Bucket,int Samples,decimal X,decimal PredictionBps);
public sealed record MxmInnovationState(MxmInnovationSample[] Samples,long? Bucket,decimal LastX,decimal LastMid);
public sealed class MxmQuoteInnovationKernel {
 readonly Queue<MxmInnovationSample> samples=new();
 long? lastBucket;decimal lastX,lastMid;
 public MxmQuoteInnovationKernel(MxmInnovationState? state=null) {
  if(state==null)return;
  if(state.Samples==null || state.Samples.Length>256 || state.LastMid<0 ||
     state.Samples.Any(x=>Math.Abs(x.X)>1) || Math.Abs(state.LastX)>1)
   throw new ArgumentException("INNOVATION_INVALID_STATE");
  foreach(var s in state.Samples)samples.Enqueue(s);
  lastBucket=state.Bucket;lastX=state.LastX;lastMid=state.LastMid;
 }
 public MxmInnovationState Capture()=>new(samples.ToArray(),lastBucket,lastX,lastMid);
 // Exactly one COMPLETED UTC minute, not a live partial bar. Noncontiguous
 // minutes discard the immature target, retaining only already-matured pairs.
 public MxmInnovationForecast? Completed(long bucket,decimal x,decimal midpoint) {
  if(bucket%60000!=0 || midpoint<=0 || Math.Abs(x)>1 ||
    (lastBucket.HasValue && bucket<=lastBucket.Value))
   throw new ArgumentException("INNOVATION_INVALID_COMPLETED_MINUTE");
  if(lastBucket.HasValue && bucket==lastBucket.Value+60000 && lastMid>0) {
   samples.Enqueue(new(lastX,10000m*(midpoint-lastMid)/lastMid));
   if(samples.Count>256)samples.Dequeue();
  }
  lastBucket=bucket;lastX=x;lastMid=midpoint;
  if(samples.Count<64)return null;
  decimal mx=samples.Average(s=>s.X),my=samples.Average(s=>s.Y);
  decimal xx=1m,xy=0m; // fixed unit ridge, never outcome-selected
  foreach(var s in samples){xx+=(s.X-mx)*(s.X-mx);xy+=(s.X-mx)*(s.Y-my);}
  decimal beta=xy/xx;
  return new(bucket,samples.Count,x,my+beta*(x-mx));
 }
}
}

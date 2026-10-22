using System;
using System.Collections.Generic;
namespace Mxm.Replay {
/// <summary>The same bar-close decision state can be called by the offline harness and a cTrader Robot.
/// No data acquisition, account calls, or trade execution is hidden in this kernel.</summary>
public sealed class MxmDecisionKernel {
 readonly Queue<decimal> fast=new(),slow=new();
 decimal fastSum,slowSum;
 public int CompletedBars {get;private set;}
 public void Reset(){fast.Clear();slow.Clear();fastSum=slowSum=0;CompletedBars=0;}
 public int OnCompletedBar(decimal close) {
  if(close<=0)throw new ArgumentOutOfRangeException(nameof(close));
  fast.Enqueue(close);fastSum+=close;if(fast.Count>3)fastSum-=fast.Dequeue();
  slow.Enqueue(close);slowSum+=close;if(slow.Count>6)slowSum-=slow.Dequeue();
  CompletedBars++;
  if(slow.Count<6)return 0;
  decimal delta=fastSum/3-slowSum/6;
  return delta>0.00005m?1:delta< -0.00005m?-1:0;
 }
}
}
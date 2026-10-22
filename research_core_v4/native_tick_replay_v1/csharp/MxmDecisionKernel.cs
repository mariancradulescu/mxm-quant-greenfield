using System;
using System.Collections.Generic;
namespace Mxm.Replay {
/// <summary>Single C# causal regime decision source shared by CLI harness and cTrader cBot.
/// Regime classification uses ONLY six already completed bars. No retrospective fitting,
/// external data, Python signal authority, platform calls or mutable cloud resources.</summary>
public enum StrategyMode { Adaptive, TrendOnly, RangeFade, Breakout }
public sealed class MxmDecisionKernel {
 readonly StrategyMode family;
 public MxmDecisionKernel(StrategyMode mode=StrategyMode.Adaptive){family=mode;}
 readonly Queue<decimal> closes=new();
 public int CompletedBars {get;private set;}
 public string LastRegime {get;private set;}="WARMUP";
 public void Reset(){closes.Clear();CompletedBars=0;LastRegime="WARMUP";}
 public int OnCompletedBar(decimal close) {
  if(close<=0)throw new ArgumentOutOfRangeException(nameof(close));
  closes.Enqueue(close);if(closes.Count>6)closes.Dequeue();
  CompletedBars++;
  if(closes.Count<6){LastRegime="WARMUP";return 0;}
  var a=closes.ToArray();
  decimal fast=(a[3]+a[4]+a[5])/3m;
  decimal slow=(a[0]+a[1]+a[2]+a[3]+a[4]+a[5])/6m;
  decimal impulse=(fast-slow)/close;
  int sign=impulse>0.000045m?1:impulse< -0.000045m?-1:0;
  decimal path=0;
  for(int i=1;i<a.Length;i++)path+=Math.Abs(a[i]-a[i-1]);
  if(path==0){LastRegime="FLAT";return 0;}
  decimal efficiency=Math.Abs(a[5]-a[0])/path;
  decimal relativeVolatility=path/(5m*close);
  if(relativeVolatility>0.007m){LastRegime="SHOCK_HOLD";return 0;}
  if(family==StrategyMode.TrendOnly){LastRegime="TREND_ONLY";return sign;}
  if(family==StrategyMode.RangeFade){LastRegime="RANGE_FADE";return efficiency<=0.60m?-sign:0;}
  if(family==StrategyMode.Breakout){
   decimal hi=a[0],lo=a[0];for(int i=1;i<5;i++){hi=Math.Max(hi,a[i]);lo=Math.Min(lo,a[i]);}
   LastRegime="CAUSAL_CHANNEL_BREAKOUT";
   return a[5]>hi+close*0.00005m?1:a[5]<lo-close*0.00005m?-1:0;
  }
  if(efficiency>=0.60m){LastRegime="TREND";return sign;}
  if(efficiency<=0.30m){LastRegime="RANGE_REVERSION";return -sign;}
  LastRegime="TRANSITION_HOLD";return 0;
 }
}
}
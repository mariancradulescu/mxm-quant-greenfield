using System;
namespace Mxm.Native {
public static class RoundKernel {
 public static (int Direction,double Level,double Distance,double Headroom,double StopDistance,string Reason) Feature(double bid,double ask,int digits) {
  if(!(0<bid && bid<ask) || !double.IsFinite(bid) || !double.IsFinite(ask) || digits<0 || digits>8) return (0,0,0,0,0,"INVALID");
  double mid=(bid+ask)/2,q=Math.Pow(10,3-digits),level=Math.Floor(mid/q+0.5)*q,delta=mid-level,dist=Math.Abs(delta);
  string reason=dist<=q*1e-10 ? "ON_LEVEL" : dist>q/4 ? "OUTSIDE_BARRIER_ZONE" : "SIGNAL";
  return (reason=="SIGNAL" ? (delta>0 ? 1:-1):0,level,dist,10000*(q/2-dist)/mid,dist+2*(ask-bid),reason);
 }
}}

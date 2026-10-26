using System;
namespace Mxm.Replay {
/// <summary>
/// Bounded search on a broker-supplied min + step volume grid.
/// Requested units are an upper cap; NEVER round upward above that cap.
/// Predicate must be monotone; selected candidate still faces all authoritative
/// post-durable checks. Unpriceable/no candidate => no new order.
/// </summary>
public static class MxmNativeVolumeSearch {
 public static decimal? LargestAffordable(decimal minimum,decimal maximum,
  decimal step,decimal requested,Func<decimal,bool> admitted) {
  if(admitted==null || minimum<=0m || maximum<minimum || step<=0m ||
     requested<minimum)return null;
  try {checked {
   decimal cap=Math.Min(maximum,requested);
   decimal slots=decimal.Floor((cap-minimum)/step);
   if(slots<0m || slots>long.MaxValue)return null;
   long hi=(long)slots;
   decimal Candidate(long n)=>minimum+step*n;
   if(!admitted(Candidate(0)))return null;
   if(hi==0 || admitted(Candidate(hi)))return Candidate(hi);
   long lo=0;
   while(hi-lo>1) {
    long mid=lo+(hi-lo)/2;
    if(admitted(Candidate(mid)))lo=mid;else hi=mid;
   }
   return Candidate(lo);
  }}catch(OverflowException){return null;}
 }
}
}

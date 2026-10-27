using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
public sealed record MxmNativeRiskQuote(string Source,decimal Bid,decimal Ask);
/// <summary>Finite local observation lifetime for every mark consumed by native
/// stop-risk admission. Not a loss conversion, broker quote or maximum-loss proof.
/// Equal-price refreshes cannot renew a captured admission lease.</summary>
public sealed class MxmNativeRiskObservationLease {
 readonly MxmObservedFxBook[] captured;
 readonly long capturedAt;
 public long ExpiresAtMs {get;}
 public int Sources=>captured.Length;
 public bool ExecutabilityProven=>false;
 public bool LossConversionProven=>false;
 MxmNativeRiskObservationLease(MxmObservedFxBook[] books,long now,long expires){
  captured=books;capturedAt=now;ExpiresAtMs=expires;
 }
 public static MxmNativeRiskObservationLease Capture(IEnumerable<MxmNativeRiskQuote> expected,
  long now,Func<string,MxmObservedFxBook?> read){
  if(expected==null || read==null || now<0)throw new ArgumentException("RISK_OBSERVATION_INPUT");
  var quotes=expected.Take(34).ToArray();
  if(quotes.Length==0 || quotes.Length>33 || quotes.Any(x=>x==null ||
   string.IsNullOrWhiteSpace(x.Source) || x.Source.Length>128))throw new ArgumentException("RISK_OBSERVATION_ROSTER");
  var books=new List<MxmObservedFxBook>();long expiry=long.MaxValue;
  foreach(var group in quotes.GroupBy(x=>x.Source,StringComparer.Ordinal)) {
   var q=group.First();
   if(group.Any(x=>x.Bid!=q.Bid || x.Ask!=q.Ask))throw new ArgumentException("RISK_OBSERVATION_CONFLICT");
   var book=read(q.Source);
   long age=MxmObservedCostFx.RequireObservedBookAge(book,q.Source,now);
   if(book!.Bid!=q.Bid || book.Ask!=q.Ask)throw new ArgumentException("RISK_OBSERVATION_NATIVE_PRICE_MISMATCH");
   // Compute from the oldest observed side rather than now+remaining-age,
   // avoiding overflow in a long-running process near Int64.MaxValue.
   long oldest=now-age;
   long end=oldest>long.MaxValue-MxmObservedCostFx.MaximumSideAgeMs?long.MaxValue:
    oldest+MxmObservedCostFx.MaximumSideAgeMs;
   expiry=Math.Min(expiry,end);books.Add(book);
  }
  return new(books.ToArray(),now,expiry);
 }
 public void Verify(long now,Func<string,MxmObservedFxBook?> read){
  if(read==null || now<capturedAt || now>ExpiresAtMs)throw new ArgumentException("RISK_OBSERVATION_LEASE_EXPIRED_OR_CLOCK_REGRESSED");
  foreach(var prior in captured) {
   var current=read(prior.Source);
   MxmObservedCostFx.RequireObservedBookAge(current,prior.Source,now);
   if(current!.Observation.Epoch!=prior.Observation.Epoch ||
    current.Observation.Origin!=prior.Observation.Origin ||
    current.Bid!=prior.Bid || current.Ask!=prior.Ask ||
    current.Observation.BidObservedMs<prior.Observation.BidObservedMs ||
    current.Observation.AskObservedMs<prior.Observation.AskObservedMs)
    throw new ArgumentException("RISK_OBSERVATION_CHANGED_OR_RESTARTED");
  }
 }
}
}

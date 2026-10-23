using System;

namespace Mxm.Replay {
/// <summary>In-memory decision, never a broker pending order or durable ACK.</summary>
public sealed record MxmDecisionIntent(int Desired, bool Contiguous, int CompletedBars,
 DateTime BoundaryUtc, DateTime ObservedUtc, DateTime ExpiresUtc);

/// <summary>
/// Shared by the product and replay: a closed-bar decision may be consumed
/// once, only on a strictly later symbol quote, before the next bar boundary.
/// Consume before invoking the broker, including on rejection/ambiguous ACK.
/// A cold instance has no intent to replay. This is not broker idempotency.
/// </summary>
public sealed class MxmCausalIntent {
 MxmDecisionIntent? pending;
 DateTime lastBoundary;
 DateTime blockedThroughBoundary;
 public bool CanPublish(DateTime boundaryUtc) {
  if(boundaryUtc.Kind!=DateTimeKind.Utc || boundaryUtc==default)
   throw new ArgumentException("INVALID_CAUSAL_BOUNDARY_UTC");
  return boundaryUtc>blockedThroughBoundary;
 }
 // A broker stop can precede BarClosed. Clear alone cannot prevent that
 // callback from publishing another decision for the already revoked bar.
 public void RevokeThroughBoundary(DateTime observedUtc,int barMinutes) {
  if(observedUtc.Kind!=DateTimeKind.Utc || observedUtc==default || barMinutes<1)
   throw new ArgumentException("INVALID_CAUSAL_REVOCATION_CLOCK");
  long width=checked(TimeSpan.TicksPerMinute*barMinutes);
  var boundary=new DateTime(observedUtc.Ticks/width*width,DateTimeKind.Utc);
  if(boundary>blockedThroughBoundary)blockedThroughBoundary=boundary;
  Clear();
 }
 public void Publish(int desired,bool contiguous,int completedBars,
                     DateTime boundaryUtc,DateTime observedUtc,int barMinutes) {
  if(desired < -1 || desired > 1 || completedBars<0 || barMinutes<1 ||
     boundaryUtc.Kind!=DateTimeKind.Utc || observedUtc.Kind!=DateTimeKind.Utc ||
     boundaryUtc==default || boundaryUtc<=lastBoundary || observedUtc<boundaryUtc ||
     observedUtc>=boundaryUtc.AddMinutes(barMinutes))
   throw new ArgumentException("INVALID_CAUSAL_INTENT_CLOCK_OR_DECISION");
  lastBoundary=boundaryUtc;
  if(!CanPublish(boundaryUtc)){Clear();return;}
  pending=new MxmDecisionIntent(desired,contiguous,completedBars,boundaryUtc,
    observedUtc,boundaryUtc.AddMinutes(barMinutes));
 }
 public void Clear() {pending=null;}
 public bool TryConsume(DateTime quoteUtc,out MxmDecisionIntent? intent) {
  intent=null;
  if(quoteUtc.Kind!=DateTimeKind.Utc || quoteUtc==default)
   throw new ArgumentException("INVALID_CAUSAL_QUOTE_UTC");
  if(pending==null)return false;
  // Expiry is evaluated even if Tick precedes BarClosed on the next boundary.
  if(quoteUtc>=pending.ExpiresUtc){pending=null;return false;}
  if(quoteUtc<=pending.ObservedUtc)return false;
  intent=pending;
  pending=null;
  return true;
 }
}
}

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
internal sealed record MxmIntentReplayState(MxmDecisionIntent? Pending,DateTime LastBoundary,DateTime BlockedThroughBoundary);
public sealed class MxmCausalIntent {
 MxmDecisionIntent? pending;
 DateTime lastBoundary;
 DateTime blockedThroughBoundary;
 // Offline account replay only. Native cTrader cold starts never restore an intent.
 internal MxmIntentReplayState CaptureReplayState()=>new(pending,lastBoundary,blockedThroughBoundary);
 internal void RestoreReplayState(MxmIntentReplayState s,int barMinutes){
  if((s.LastBoundary!=default && s.LastBoundary.Kind!=DateTimeKind.Utc) ||
     (s.BlockedThroughBoundary!=default && s.BlockedThroughBoundary.Kind!=DateTimeKind.Utc))
   throw new ArgumentException("INVALID_REPLAY_INTENT_CLOCK");
  if(s.Pending is MxmDecisionIntent p &&
     (p.Desired < -1 || p.Desired>1 || p.CompletedBars<0 ||
      p.BoundaryUtc.Kind!=DateTimeKind.Utc || p.ObservedUtc.Kind!=DateTimeKind.Utc ||
      p.BoundaryUtc!=s.LastBoundary || p.BoundaryUtc<=s.BlockedThroughBoundary ||
      p.ObservedUtc<p.BoundaryUtc || p.ObservedUtc>=p.ExpiresUtc ||
      p.ExpiresUtc!=p.BoundaryUtc.AddMinutes(barMinutes)))
   throw new ArgumentException("INVALID_REPLAY_PENDING_INTENT");
  pending=s.Pending;lastBoundary=s.LastBoundary;blockedThroughBoundary=s.BlockedThroughBoundary;
 }
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

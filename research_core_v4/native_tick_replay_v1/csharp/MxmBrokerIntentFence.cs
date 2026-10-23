using System;

namespace Mxm.Replay {
public sealed record MxmBrokerDecisionLease(long Revision,long? PositionId);

/// <summary>
/// Per-symbol in-memory fence between a bar intent and the observed broker book.
/// A broker notification or unexplained identity change invalidates consumed as
/// well as queued decisions. Not a broker transaction, persistent lease or fill proof.
/// </summary>
public sealed class MxmBrokerIntentFence {
 readonly MxmCausalIntent queue;
 readonly int barMinutes;
 long revision;
 long? positionId;
 DateTime blockedThroughBoundary;
 long? requestedReversalId;
 bool requestedCloseObserved;
 public MxmBrokerIntentFence(MxmCausalIntent queue,int barMinutes,long? initialPositionId) {
  if(queue==null || barMinutes<1 || initialPositionId<=0)
   throw new ArgumentException("INVALID_BROKER_INTENT_FENCE");
  this.queue=queue;this.barMinutes=barMinutes;positionId=initialPositionId;
 }
 static void Clock(DateTime utc) {
  if(utc.Kind!=DateTimeKind.Utc || utc==default)
   throw new ArgumentException("INVALID_BROKER_FENCE_UTC");
 }
 void Invalidate(DateTime observedUtc) {
  Clock(observedUtc);
  checked {revision++;}
  queue.Clear();requestedReversalId=null;requestedCloseObserved=false;
  long width=TimeSpan.TicksPerMinute*barMinutes;
  var boundary=new DateTime(observedUtc.Ticks/width*width,DateTimeKind.Utc);
  if(boundary>blockedThroughBoundary)blockedThroughBoundary=boundary;
 }
 public void Observe(long? actualPositionId,DateTime observedUtc) {
  Clock(observedUtc);
  if(actualPositionId<=0)throw new ArgumentException("INVALID_BROKER_POSITION_ID");
  if(actualPositionId==positionId)return;
  Invalidate(observedUtc);positionId=actualPositionId;
 }
 public bool CanPublish(DateTime boundaryUtc) {
  Clock(boundaryUtc);
  return boundaryUtc>blockedThroughBoundary;
 }
 public MxmBrokerDecisionLease Capture()=>new(revision,positionId);
 public bool IsCurrent(MxmBrokerDecisionLease lease,long? actualPositionId,DateTime observedUtc) {
  Observe(actualPositionId,observedUtc);
  return lease.Revision==revision && lease.PositionId==positionId;
 }
 // Called only after the adapter has checked label AND configured symbol.
 // Only a matching, explicitly requested reversal with reason Closed can
 // acknowledge a local close. StopLoss/StopOut/TakeProfit/unknown always revoke.
 public void Closed(long closedId,bool reasonIsClosed,DateTime observedUtc) {
  Clock(observedUtc);
  if(closedId<=0)throw new ArgumentException("INVALID_CLOSED_POSITION_ID");
  if(requestedReversalId==closedId && positionId==closedId && reasonIsClosed) {
   requestedCloseObserved=true;positionId=null;queue.Clear();return;
  }
  Invalidate(observedUtc);
  if(positionId==closedId)positionId=null;
 }
 public bool BeginReversal(MxmBrokerDecisionLease lease,long id,long? actualPositionId,DateTime observedUtc) {
  if(!IsCurrent(lease,actualPositionId,observedUtc) || lease.PositionId!=id || id<=0 ||
     requestedReversalId!=null)return false;
  requestedReversalId=id;requestedCloseObserved=false;return true;
 }
 public bool FinishReversal(MxmBrokerDecisionLease lease,long id,bool successful,long? resultId,
  long? actualPositionId,DateTime observedUtc,out MxmBrokerDecisionLease? continuation) {
  Clock(observedUtc);continuation=null;
  bool acknowledged=requestedReversalId==id && requestedCloseObserved &&
   lease.Revision==revision && lease.PositionId==id && successful && resultId==id &&
   actualPositionId==null && positionId==null;
  requestedReversalId=null;requestedCloseObserved=false;
  if(!acknowledged) {
   Invalidate(observedUtc);positionId=actualPositionId;return false;
  }
  continuation=Capture();return true;
 }
 public void Reset() {
  queue.Clear();checked {revision++;}
  requestedReversalId=null;requestedCloseObserved=false;
 }
}
}

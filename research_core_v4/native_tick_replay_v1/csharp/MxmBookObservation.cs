using System;
using System.Collections.Generic;
namespace Mxm.Replay {
public enum MxmObservationOrigin { RawPartialFields, NativeCallbackSnapshot }
public enum MxmReportedTransport { Unknown, Up, Down }
/// <summary>Descriptive state only. An open local subscription, carried price,
/// repeated field, heartbeat or elapsed clock never certifies executable liquidity.
/// Native callback sides are snapshots, not claims of underlying wire-field presence.</summary>
public static class MxmBookObservations {
 public static MxmBookObservation<decimal> RawFields()=>new(MxmObservationOrigin.RawPartialFields,MxmBookShape.Classify);
 public static MxmBookObservation<double> NativeSnapshots()=>new(MxmObservationOrigin.NativeCallbackSnapshot,
  (bid,ask)=>!bid.HasValue||!ask.HasValue?MxmBookShapeKind.Missing:MxmBookShape.ClassifyNative(bid.Value,ask.Value));
}
public sealed record MxmBookObservationView(long Epoch,bool SessionOpen,bool Faulted,
 MxmObservationOrigin Origin,MxmReportedTransport ReportedTransport,MxmBookShapeKind Shape,
 long Events,long BidFields,long AskFields,long BidChanges,long AskChanges,
 long? LastEventMs,long? BidObservedMs,long? AskObservedMs,long? BidChangedMs,long? AskChangedMs,
 long? BidServerMs,long? AskServerMs,long? LastReceivedUtcMs,long? EventAgeMs,long? BidAgeMs,long? AskAgeMs) {
 public bool ExecutabilityProven=>false;
 public bool ContinuousObservationProven=>false;
}
public sealed record MxmBookObservationValues<T>(T? Bid,T? Ask,MxmBookObservationView Observation) where T:struct;
public sealed class MxmBookObservation<T> where T:struct {
 readonly Func<T?,T?,MxmBookShapeKind> classify;
 readonly MxmObservationOrigin origin;
 T? bid,ask;
 long epoch,events,bidFields,askFields,bidChanges,askChanges;
 long? lastAction,lastEvent,bidObserved,askObserved,bidChanged,askChanged,bidServer,askServer,lastUtc;
 bool open,faulted;
 MxmReportedTransport transport=MxmReportedTransport.Unknown;
 internal MxmBookObservation(MxmObservationOrigin origin,Func<T?,T?,MxmBookShapeKind> classify){this.origin=origin;this.classify=classify;}
 void ClearBook(){bid=ask=null;bidObserved=askObserved=bidChanged=askChanged=bidServer=askServer=lastEvent=lastUtc=null;}
 void Clock(long now) {
  if(faulted)throw new InvalidOperationException("OBSERVATION_FAULT_LATCHED");
  if(now<0 || (lastAction.HasValue && now<lastAction.Value)) {
   faulted=true;open=false;ClearBook();throw new InvalidOperationException("OBSERVATION_MONOTONIC_REGRESSION");
  }
  lastAction=now;
 }
 public void BeginEpoch(long now){Clock(now);epoch=checked(epoch+1);ClearBook();transport=MxmReportedTransport.Unknown;open=true;}
 public void EndEpoch(long now){Clock(now);open=false;ClearBook();transport=MxmReportedTransport.Unknown;}
 // A reported UP never resurrects a closed epoch or a carried book. The caller
 // owns provenance of this report. Native Tick callbacks do not call this API.
 public void ReportTransport(MxmReportedTransport status,long now) {
  if(!Enum.IsDefined(typeof(MxmReportedTransport),status))throw new ArgumentException("OBSERVATION_TRANSPORT_STATUS");
  Clock(now);transport=status;
  if(status==MxmReportedTransport.Down){open=false;ClearBook();}
 }
 public void Observe(T? bidField,T? askField,long now,long receivedUtcMs,long? serverMs) {
  Clock(now);
  if(!open)throw new InvalidOperationException("OBSERVATION_EPOCH_CLOSED");
  if(origin==MxmObservationOrigin.NativeCallbackSnapshot && (!bidField.HasValue||!askField.HasValue))
   throw new ArgumentException("NATIVE_SNAPSHOT_REQUIRES_BOTH_FIELDS");
  events=checked(events+1);lastEvent=now;lastUtc=receivedUtcMs;
  if(bidField.HasValue) {
   bidFields=checked(bidFields+1);
   if(bid.HasValue && !EqualityComparer<T>.Default.Equals(bid.Value,bidField.Value)){bidChanges=checked(bidChanges+1);bidChanged=now;}
   bid=bidField;bidObserved=now;bidServer=serverMs;
  }
  if(askField.HasValue) {
   askFields=checked(askFields+1);
   if(ask.HasValue && !EqualityComparer<T>.Default.Equals(ask.Value,askField.Value)){askChanges=checked(askChanges+1);askChanged=now;}
   ask=askField;askObserved=now;askServer=serverMs;
  }
 }
 public MxmBookObservationValues<T> ReadBook(long now)=>new(bid,ask,Snapshot(now));
 public MxmBookObservationView Snapshot(long now) {
  Clock(now);
  long? Age(long? stamp)=>stamp.HasValue?checked(now-stamp.Value):null;
  return new(epoch,open,faulted,origin,transport,classify(bid,ask),events,bidFields,askFields,bidChanges,askChanges,
   lastEvent,bidObserved,askObserved,bidChanged,askChanged,bidServer,askServer,lastUtc,Age(lastEvent),Age(bidObserved),Age(askObserved));
 }
}
}

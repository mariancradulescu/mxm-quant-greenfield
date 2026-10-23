using System;
using System.Collections.Generic;
using System.Linq;

namespace Mxm.Replay {
// Broker book snapshots, not synthetic fills. No platform or network dependency.
public sealed record MxmProtectionPosition(long Id,string Label,string Symbol,int Direction,
 double Units,double Entry,double? Stop);
public sealed record MxmProtectionVerdict(bool Accepted,bool Halt,string Reason);

/// <summary>One synchronous order outcome. A fault latches account admission off.
/// Only the returned identity, absent from the pre-call book and still carrying
/// our exact label/symbol, is eligible for defensive closure. No inferred ownership.</summary>
public sealed class MxmOrderProtection {
 public bool Halted {get;private set;}
 long? returnedId;
 string label="",symbol="";
 bool mayFlatten;
 public MxmProtectionVerdict Reconcile(bool successful,long? resultId,
  string expectedLabel,string expectedSymbol,int direction,double units,
  double stopPips,double pipSize,double tickSize,IReadOnlyCollection<long> beforeIds,
  IReadOnlyCollection<MxmProtectionPosition> book) {
  if(Halted)return new(false,true,"ALREADY_HALTED");
  var owned=book.Where(x=>x.Label==expectedLabel && x.Symbol==expectedSymbol).ToArray();
  returnedId=resultId;label=expectedLabel;symbol=expectedSymbol;
  mayFlatten=resultId>0 && !beforeIds.Contains(resultId.Value);
  string reason="";
  if(!successful && resultId==null && owned.Length==0)
   return new(false,false,"REJECTED_NO_OBSERVED_POSITION");
  if(!successful)reason="FAILED_CALL_WITH_OBSERVED_POSITION";
  else if(resultId==null || resultId<=0)reason="MISSING_RETURNED_IDENTITY";
  else if(beforeIds.Contains(resultId.Value))reason="PREEXISTING_RETURNED_IDENTITY";
  else if(owned.Length!=1 || owned[0].Id!=resultId)reason="BOOK_IDENTITY_MISMATCH";
  else {
   var actual=owned[0];
   if((direction!=1 && direction!=-1) || actual.Direction!=direction)
    reason="DIRECTION_MISMATCH";
   else if(!double.IsFinite(units) || units<=0 || !double.IsFinite(actual.Units) || actual.Units!=units)
    reason="VOLUME_MISMATCH";
   else if(!double.IsFinite(stopPips) || stopPips<=0 || !double.IsFinite(pipSize) || pipSize<=0 ||
    !double.IsFinite(tickSize) || tickSize<=0 || !double.IsFinite(actual.Entry) || actual.Entry<=0 ||
    !actual.Stop.HasValue || !double.IsFinite(actual.Stop.Value) || actual.Stop.Value<=0)
    reason="STOP_UNVERIFIED";
   else {
    double distance=direction*(actual.Entry-actual.Stop.Value);
    double limit=stopPips*pipSize+tickSize;
    if(!double.IsFinite(distance) || !double.IsFinite(limit) || distance<=0 || distance>limit)
     reason="STOP_GEOMETRY_OUTSIDE_REQUEST";
   }
  }
  if(reason.Length==0)return new(true,false,"BOOK_AND_STOP_RECONCILED");
  Halted=true;return new(false,true,reason);
 }
 public void HaltUnknown() {Halted=true;mayFlatten=false;returnedId=null;}
 public long? DefensiveCloseId(IReadOnlyCollection<MxmProtectionPosition> book) {
  if(!Halted || !mayFlatten)return null;
  // Recheck ownership on EVERY retry; a reused or foreign identity is never seized.
  var matches=book.Where(x=>x.Id==returnedId && x.Label==label && x.Symbol==symbol).ToArray();
  return matches.Length==1?returnedId:null;
 }
}
}

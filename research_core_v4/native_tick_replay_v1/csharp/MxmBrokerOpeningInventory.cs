using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace Mxm.Replay {
public sealed record MxmBrokerOpeningFill(long DealId,long OrderId,long PositionId,string Symbol,
 int Direction,decimal Units,decimal Price,DateTime ExecutionUtc,string Label,string Comment);
public sealed record MxmObservedOpeningOrder(long OrderId,long PositionId,string Symbol,int Direction,
 string Label,string Comment,decimal ObservedFilledUnits,DateTime FirstObservedFillUtc,
 DateTime LastObservedFillUtc,long[] DealIds);
public sealed record MxmPendingOpeningObservation(bool Correlated,bool RequestedUnitsObserved,
 long? OrderId,decimal ObservedUnits,string Reason) {
 public bool MayResubmit=>false;
 public bool MayClearPending=>false;
 public bool StopProtectionProven=>false;
}
/// <summary>Broker-confirmed positive fill facts only, independent of local storage.
/// Rebuilt from available observations after restart, never an assertion of complete
/// history, first original fill, account cash/anchor, ownership or order idempotency.</summary>
public sealed class MxmBrokerOpeningInventory {
 public string ScopeFingerprint {get;}
 public DateTime ObservedUtc {get;}
 readonly MxmBrokerOpeningFill[] fills;
 readonly MxmObservedOpeningOrder[] orders;
 public MxmBrokerOpeningFill[] Fills=>fills.ToArray();
 public MxmObservedOpeningOrder[] Orders=>orders.Select(x=>x with {DealIds=x.DealIds.ToArray()}).ToArray();
 public string FactsSha256 {get;}
 public bool HistoryCoverageProven=>false;
 public bool CapitalContinuityProven=>false;
 public bool Hard21Proven=>false;
 public bool MaySubmitOrClearPending=>false;
 static bool Utc(DateTime x)=>x.Kind==DateTimeKind.Utc && x!=default;
 static void Need(bool ok){if(!ok)throw new ArgumentException("BROKER_OPENING_FACTS_INVALID_OR_CONFLICTING");}
 static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
 public MxmBrokerOpeningInventory(string accountScope,DateTime observedUtc,IEnumerable<MxmBrokerOpeningFill> observations){
  Need(!string.IsNullOrWhiteSpace(accountScope) && accountScope.Length<=1024 && Utc(observedUtc) && observations!=null);
  ScopeFingerprint=Hash(accountScope);ObservedUtc=observedUtc;
  var unique=new Dictionary<long,MxmBrokerOpeningFill>();int count=0;
  foreach(var f in observations!) {
   if(f==null)throw new ArgumentException("NULL_BROKER_OPENING_FILL");
   Need(++count<=100000 && f.DealId>0 && f.OrderId>0 && f.PositionId>0 &&
    !string.IsNullOrWhiteSpace(f.Symbol) && f.Symbol.Length<=128 && (f.Direction==1 || f.Direction==-1) &&
    f.Units>0m && f.Price>0m && Utc(f.ExecutionUtc) && f.ExecutionUtc<=observedUtc &&
    f.Label!=null && f.Label.Length<=128 && f.Comment!=null && f.Comment.Length<=1024);
   if(unique.TryGetValue(f.DealId,out var prior))Need(prior==f);
   else unique.Add(f.DealId,f);
  }
  fills=unique.Values.OrderBy(x=>x.DealId).ToArray();
  var result=new List<MxmObservedOpeningOrder>();
  foreach(var group in fills.GroupBy(x=>x.OrderId).OrderBy(x=>x.Key)) {
   var first=group.First();decimal units=0;
   foreach(var f in group) {
    Need(f.PositionId==first.PositionId && f.Symbol==first.Symbol && f.Direction==first.Direction &&
     f.Label==first.Label && f.Comment==first.Comment);units=checked(units+f.Units);
   }
   result.Add(new(first.OrderId,first.PositionId,first.Symbol,first.Direction,first.Label,first.Comment,
    units,group.Min(x=>x.ExecutionUtc),group.Max(x=>x.ExecutionUtc),group.Select(x=>x.DealId).OrderBy(x=>x).ToArray()));
  }
  orders=result.ToArray();
  // Observation time is separate: equal broker facts have the same digest
  // across input order, overlapping partial-close history and cold instances.
  FactsSha256=Hash(JsonSerializer.Serialize(new {ScopeFingerprint,Fills=fills}));
 }
 public MxmPendingOpeningObservation ObservePending(MxmRecoverableEntry request) {
  var none=new MxmPendingOpeningObservation(false,false,null,0m,"NO_POSITIVE_CORRELATED_OPENING_ORDER");
  if(request==null || !MxmEntryRecovery.Valid(request,"MXM_ENTRY_CHECKPOINT_V1_READY_"+ScopeFingerprint) ||
     request.PreparedUtc>ObservedUtc)return none with {Reason="REQUEST_SCOPE_OR_CLOCK_INVALID"};
  var hits=orders.Where(x=>x.Comment==request.Comment).ToArray();
  if(hits.Length!=1)return none with {Reason=hits.Length==0?none.Reason:"MULTIPLE_CORRELATED_OPENING_ORDERS"};
  var o=hits[0];
  if(o.Label!=request.Label || o.Symbol!=request.Symbol || o.Direction!=request.Direction ||
     request.BeforeIds.Contains(o.PositionId) || o.FirstObservedFillUtc<request.PreparedUtc ||
     o.ObservedFilledUnits>(decimal)request.Units)
   return none with {Reason="CORRELATED_ORDER_IDENTITY_VOLUME_OR_TIME_MISMATCH"};
  return new(true,o.ObservedFilledUnits==(decimal)request.Units,o.OrderId,o.ObservedFilledUnits,
   "POSITIVE_OPENING_FILL_FACTS_ONLY_NOT_PERMISSION_TO_CLEAR_OR_RESUBMIT");
 }
}
}

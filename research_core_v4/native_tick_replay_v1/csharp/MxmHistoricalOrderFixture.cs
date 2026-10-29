using System;
using System.Linq;
using Mxm.Replay;
internal static class Program {
 static void Need(bool ok,string reason){if(!ok)throw new Exception(reason);}
 static void Reject(Action action,string reason){
  try{action();}catch(ArgumentException){return;}
  throw new Exception(reason);
 }
 static void Main(){
  var now=new DateTime(2026,10,29,12,0,0,DateTimeKind.Utc);
  var t=now.AddMinutes(-2);const string scope="Pepperstone:1001:LIVE";
  var h=new MxmHistoricalOrderFact(101,"EURUSD",1,"MXM_CSHARP_REFERENCE_V1",
    "MXM_ORIGINAL_REQUEST_1","Filled",t,1000m,1000m);
  var fill=new MxmBrokerOpeningFill(201,101,301,"EURUSD",1,1000m,1.1m,
    t.AddSeconds(1),h.Label,h.Comment);
  var open=new MxmBrokerOpeningInventory(scope,now,new[]{fill});
  var a=new MxmHistoricalOrderInventory(scope,now,new[]{h,h});
  var b=new MxmHistoricalOrderInventory(scope,now,new[]{h});
  Need(a.Orders.Length==1 && a.FactsSha256==b.FactsSha256,"Deduplication or canonicalization failed");
  var yes=a.ObserveOriginalIntent(h.Comment,h.Label,h.Symbol,1,open);
  Need(yes.HistoricalMatches==1 && yes.UniqueOrderId==101 &&
   yes.MatchedOpeningDeal && !yes.MayResubmit && !yes.MayClearUnknown &&
   !yes.AuthorizesCloudTrading,"Positive cross corroboration must not create order permission");
  var blank=new MxmHistoricalOrderInventory(scope,now,Array.Empty<MxmHistoricalOrderFact>());
  var no=blank.ObserveOriginalIntent(h.Comment,h.Label,h.Symbol,1,open);
  Need(no.HistoricalMatches==0 && !no.MayResubmit && !no.MayClearUnknown &&
   !blank.LateFillExcluded && !blank.HistoryCompleteProven,"Empty broker history cannot exclude late fill");
  var absent=a.ObserveOriginalIntent(null,h.Label,h.Symbol,1,open);
  Need(!absent.MayResubmit && !absent.MatchedOpeningDeal,"Lost original comment cannot be reconstructed from server");
  var other=new MxmHistoricalOrderInventory("Pepperstone:1002:LIVE",now,new[]{h});
  Need(!other.ObserveOriginalIntent(h.Comment,h.Label,h.Symbol,1,open).MatchedOpeningDeal &&
   other.FactsSha256!=a.FactsSha256,"Cross account evidence contamination");
  var wrong=a.ObserveOriginalIntent(h.Comment,h.Label,"GBPUSD",1,open);
  Need(wrong.Reason=="ORIGINAL_IDENTITY_MISMATCH","Symbol mismatch must fail closed");
  var errors=new MxmHistoricalOrderInventory(scope,now,new[]{h with {Status="Error",ObservedFilledUnits=0m}});
  Need(!errors.ObserveOriginalIntent(h.Comment,h.Label,h.Symbol,1,
     new MxmBrokerOpeningInventory(scope,now,Array.Empty<MxmBrokerOpeningFill>())).MayResubmit,
     "Error cannot certify an earlier request did not later fill");
  var multiple=new MxmHistoricalOrderInventory(scope,now,new[]{h,h with{OrderId=102}});
  Need(multiple.ObserveOriginalIntent(h.Comment,h.Label,h.Symbol,1,open).Status=="CONFLICT",
   "Duplicate client comment is not broker-enforced unique key");
  Reject(()=>new MxmHistoricalOrderInventory(scope,now,new[]{h,h with {Status="Cancelled"}}),
   "Same OrderId contradictory versions");
  Reject(()=>new MxmHistoricalOrderInventory(scope,now,new[]{h with {SubmittedUtc=now.AddMinutes(1)}}),
   "Future broker fact");
  Reject(()=>new MxmHistoricalOrderInventory(scope,now,new[]{h with {Status="Magic"}}),
   "Unknown broker status");
  Reject(()=>new MxmHistoricalOrderInventory(scope,now,new[]{h with {ObservedFilledUnits=1100m}}),
   "Overfilled order observation");
  // Indistinguishable restart prefixes:
  // A: no send occurred; B: request in transit, none of live/pending/history
  // objects has yet changed. Retrying in both duplicates B after delayed fill.
  // The only rule safe for both is no resubmission without authoritative
  // idempotency or durable pre-call uncertainty reconstruction.
  foreach(bool inTransit in new[]{false,true}) {
   var snapshot=new MxmHistoricalOrderInventory(scope,now,Array.Empty<MxmHistoricalOrderFact>());
   var decision=snapshot.ObserveOriginalIntent(null,h.Label,h.Symbol,1,
     new MxmBrokerOpeningInventory(scope,now,Array.Empty<MxmBrokerOpeningFill>()));
   Need(!decision.MayResubmit && !decision.MayClearUnknown,
    "Indistinguishable no-send and in-transit states must both block retry");
   _=inTransit; // hidden world fact is unavailable to the restarted bot
  }
  Console.WriteLine("MXM_HISTORICAL_UNKNOWN_ORDER_FRONTIER_PASS: 13+ positive/negative and indistinguishability cases; broker calls=0");
 }
}

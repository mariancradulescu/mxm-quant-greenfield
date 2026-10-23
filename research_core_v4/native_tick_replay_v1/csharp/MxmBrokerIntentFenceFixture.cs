using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mxm.Replay;

int checks=0;
void Require(bool value,string reason) {
 if(!value)throw new Exception("MXM_BROKER_INTENT_FENCE_FIXTURE_"+reason);
 checks++;
}
var utc=new DateTime(2026,10,23,10,0,0,DateTimeKind.Utc);
MxmCausalIntent Pending() {
 var queue=new MxmCausalIntent();queue.Publish(1,true,8,utc,utc,5);return queue;
}
// Concrete old product path: the position disappears, but TryConsume still
// returns the old direction; Apply then sees owned.Length == 0 and may enter.
var vulnerable=Pending();
Require(vulnerable.TryConsume(utc.AddSeconds(1),out var stale) && stale!.Desired==1,
 "OLD_QUEUE_ALONE_REPRODUCES_STALE_DIRECTION_AFTER_BROKER_STOP");

foreach(bool isLong in new[]{true,false}) {
 var queue=new MxmCausalIntent();var fence=new MxmBrokerIntentFence(queue,5,41);
 queue.Publish(isLong?1:-1,true,8,utc,utc,5);
 fence.Closed(41,false,utc.AddMilliseconds(1)); // StopLoss, not a local close.
 Require(!queue.TryConsume(utc.AddSeconds(1),out _),"BROKER_STOP_EVENT_REVOKES_BOTH_DIRECTIONS");
 Require(!fence.CanPublish(utc),"STOP_BEFORE_BAR_CALLBACK_SUPPRESSES_SAME_BOUNDARY");
 Require(fence.CanPublish(utc.AddMinutes(5)),"NEW_BAR_NOT_PERMANENTLY_BLOCKED");
 queue.Publish(isLong?1:-1,true,9,utc.AddMinutes(5),utc.AddMinutes(5),5);
 var recovered=fence.Capture();
 Require(queue.TryConsume(utc.AddMinutes(5).AddSeconds(1),out _) &&
  fence.IsCurrent(recovered,null,utc.AddMinutes(5).AddSeconds(1)),"FRESH_POST_STOP_BAR_MAY_ENTER");
}
// The queue itself now owns the revocation boundary. Consumers cannot
// accidentally resurrect an intent by omitting an adapter-side CanPublish.
{
 var queue=new MxmCausalIntent();
 queue.RevokeThroughBoundary(utc.AddSeconds(2),5);
 queue.Clear(); // Clear must not remove the stop barrier.
 queue.Publish(1,true,8,utc,utc.AddSeconds(3),5);
 Require(!queue.TryConsume(utc.AddSeconds(4),out _),"QUEUE_REJECTS_POST_STOP_SAME_BAR_PUBLICATION");
 queue.RevokeThroughBoundary(utc.AddMinutes(-5),5); // Late notification cannot move it backwards.
 Require(!queue.CanPublish(utc),"DELAYED_REVOCATION_CANNOT_LOWER_BARRIER");
 queue.Publish(-1,true,9,utc.AddMinutes(5),utc.AddMinutes(5),5);
 Require(queue.TryConsume(utc.AddMinutes(5).AddSeconds(1),out var next) && next!.Desired==-1,
 "QUEUE_ACCEPTS_NEXT_BOUNDARY_EXACTLY_ONCE");
 Require(!queue.TryConsume(utc.AddMinutes(5).AddSeconds(2),out _),"NEW_INTENT_STILL_SINGLE_CONSUMPTION");
}
// All causal permutations of publication, broker removal, close notification
// and tick consumption with removal preceding consumption. No chosen native
// ordering is assumed and none is certified by this mathematical enumeration.
string[] operations={"publish","remove","closed","consume"};
IEnumerable<string[]> Permute(string[] values) {
 if(values.Length==0){yield return Array.Empty<string>();yield break;}
 for(int i=0;i<values.Length;i++)foreach(var suffix in Permute(values.Where((_,j)=>j!=i).ToArray()))
  yield return new[]{values[i]}.Concat(suffix).ToArray();
}
int interleavings=0;
foreach(var order in Permute(operations)) {
 int Index(string op)=>Array.IndexOf(order,op);
 if(Index("publish")>Index("consume") || Index("remove")>Index("consume") ||
    Index("remove")>Index("closed"))continue;
 var queue=new MxmCausalIntent();var fence=new MxmBrokerIntentFence(queue,5,41);
 long? book=41;bool consumed=false;int step=0;
 foreach(string operation in order) {
  var now=utc.AddMilliseconds(++step);
  if(operation=="publish") {
   fence.Observe(book,now);queue.Publish(1,true,8,utc,now,5);
   if(!fence.CanPublish(utc))queue.Clear();
  } else if(operation=="remove")book=null;
  else if(operation=="closed")fence.Closed(41,false,now);
  else {fence.Observe(book,now);consumed=queue.TryConsume(now,out _);}
 }
 Require(!consumed,"NO_PRE_STOP_INTENT_WHEN_BOOK_REMOVED_BEFORE_TICK_"+string.Join('_',order));
 interleavings++;
}
Require(interleavings>0,"NONEMPTY_CAUSAL_ENUMERATION");
// Stop after consume: clearing only the queue is too late. The admission lease
// must be revoked too, before the final ExecuteMarketOrder call.
{
 var queue=Pending();var fence=new MxmBrokerIntentFence(queue,5,41);
 var lease=fence.Capture();Require(queue.TryConsume(utc.AddSeconds(1),out _),"PRE_STOP_CONSUMED");
 fence.Closed(41,false,utc.AddSeconds(2));
 Require(!fence.IsCurrent(lease,null,utc.AddSeconds(3)),"STOP_AFTER_CONSUMPTION_REVOKES_ADMISSION");
}
{
 var queue=Pending();var fence=new MxmBrokerIntentFence(queue,5,41);
 var lease=fence.Capture();Require(queue.TryConsume(utc.AddSeconds(1),out _),"PRE_DISAPPEARANCE_CONSUMED");
 Require(!fence.IsCurrent(lease,null,utc.AddSeconds(2)),"NO_EVENT_BUT_BOOK_DISAPPEARED_REVOKES_ADMISSION");
}
{
 var queue=Pending();var fence=new MxmBrokerIntentFence(queue,5,41);
 var lease=fence.Capture();fence.Observe(42,utc.AddSeconds(1));
 Require(!queue.TryConsume(utc.AddSeconds(2),out _) &&
  !fence.IsCurrent(lease,42,utc.AddSeconds(2)),"REPLACEMENT_SAME_SYMBOL_SAME_COUNT_NOT_SAME_POSITION");
}
// Expected local reversal: only the exact identity + reason Closed + successful
// matching result + empty book can create one flat continuation lease.
foreach(string variant in new[]{"matching","stop","wrong_id","no_event","failed","wrong_result","still_open"}) {
 var queue=Pending();var fence=new MxmBrokerIntentFence(queue,5,41);
 var lease=fence.Capture();Require(queue.TryConsume(utc.AddSeconds(1),out _),"REVERSAL_CONSUMED");
 Require(fence.BeginReversal(lease,41,41,utc.AddSeconds(1)),"REVERSAL_REQUEST_BOUND");
 if(variant!="no_event")fence.Closed(variant=="wrong_id"?42:41,variant!="stop",utc.AddSeconds(2));
 bool ok=fence.FinishReversal(lease,41,variant!="failed",variant=="wrong_result"?42:41,
  variant=="still_open"?41:null,utc.AddSeconds(3),out var next);
 Require(ok==(variant=="matching"),"REVERSAL_RECONCILIATION_"+variant);
 if(ok)Require(next!=null && next.PositionId==null && fence.IsCurrent(next,null,utc.AddSeconds(4)),
  "ONLY_MATCHING_CLOSE_AUTHORIZES_FLAT_CONTINUATION");
 Require(!fence.FinishReversal(lease,41,true,41,null,utc.AddSeconds(4),out _),"NO_SECOND_REVERSAL_CONTINUATION");
}
// Per-symbol isolation and cold restart: a stop on A cannot erase B; a newly
// constructed instance cannot resurrect a consumed or queued prior intent.
{
 var a=Pending();var b=Pending();var fenceA=new MxmBrokerIntentFence(a,5,41);
 var fenceB=new MxmBrokerIntentFence(b,5,51);fenceA.Closed(41,false,utc.AddSeconds(1));
 Require(!a.TryConsume(utc.AddSeconds(2),out _) && b.TryConsume(utc.AddSeconds(2),out _),"OTHER_SYMBOL_UNAFFECTED");
 var coldQueue=new MxmCausalIntent();var cold=new MxmBrokerIntentFence(coldQueue,5,41);
 Require(!coldQueue.TryConsume(utc.AddSeconds(2),out _),"COLD_RESTART_NO_OLD_INTENT");
 var lease=fenceB.Capture();fenceB.Reset();
 Require(!fenceB.IsCurrent(lease,51,utc.AddSeconds(3)),"STOP_RESET_REVOKES_CONSUMED_LEASE");
}
// Old product accepts IsSuccessful alone, even when no stop was attached.
var good=new MxmProtectionPosition(90,"OWNER","EURUSD",1,1000,1.1,1.0988);
MxmProtectionVerdict Check(MxmOrderProtection guard,bool ok=true,long? id=90,
 MxmProtectionPosition[]? book=null,long[]? before=null,int direction=1)=>
 guard.Reconcile(ok,id,"OWNER","EURUSD",direction,1000,12,.0001,.00001,
  before??Array.Empty<long>(),book??new[]{good});
Require(Check(new()).Accepted,"POSTFILL_VALID_LONG");
Require(Check(new(),book:new[]{good with {Direction=-1,Stop=1.1012}},direction:-1).Accepted,
 "POSTFILL_VALID_SHORT");
Require(Check(new(),book:new[]{good with {Stop=1.098795}}).Accepted,"ONE_TICK_ROUNDING_BOUND");
foreach(var bad in new[]{good with {Stop=null},good with {Stop=double.NaN},
 good with {Stop=1.101},good with {Stop=1.0987},good with {Units=999},
 good with {Units=double.PositiveInfinity},good with {Entry=0},good with {Direction=-1},
 good with {Id=91},good with {Label="FOREIGN"},good with {Symbol="GBPUSD"}}) {
 var guard=new MxmOrderProtection();
 var verdict=Check(guard,book:new[]{bad});
 Require(verdict.Halt && !verdict.Accepted,"POSTFILL_INVALID_BOOK_HALTS");
 Require(!Check(guard).Accepted && guard.Halted,"POSTFILL_LATCH_CANNOT_SELF_RESET");
 bool attributable=bad.Id==90 && bad.Label=="OWNER" && bad.Symbol=="EURUSD";
 Require(guard.DefensiveCloseId(new[]{bad})==(attributable?90L:(long?)null),
  "ONLY_ATTRIBUTABLE_ID_CAN_BE_CLOSED");
 Require(guard.DefensiveCloseId(new[]{bad with {Label="FOREIGN"}})==null,"RETRY_RECHECKS_OWNERSHIP");
 Require(guard.DefensiveCloseId(Array.Empty<MxmProtectionPosition>())==null,"DISAPPEARED_NO_CLOSE");
}
foreach(var scenario in new[]{"NO_ID","NO_BOOK","FAILED_WITH_POSITION","PREEXISTING","MULTIPLE"}) {
 var guard=new MxmOrderProtection();
 var verdict=Check(guard,ok:scenario!="FAILED_WITH_POSITION",id:scenario=="NO_ID"?null:90,
  book:scenario=="NO_BOOK"?Array.Empty<MxmProtectionPosition>():
   scenario=="MULTIPLE"?new[]{good,good with {Id=91}}:new[]{good},
  before:scenario=="PREEXISTING"?new long[]{90}:Array.Empty<long>());
 Require(verdict.Halt,"AMBIGUOUS_OUTCOME_HALTS_"+scenario);
 if(scenario=="NO_ID" || scenario=="PREEXISTING")
  Require(guard.DefensiveCloseId(new[]{good})==null,"NO_INFERRED_OWNERSHIP_"+scenario);
}
var unknown=new MxmOrderProtection();unknown.HaltUnknown();
Require(unknown.Halted && unknown.DefensiveCloseId(new[]{good})==null && !Check(unknown).Accepted,
 "EXCEPTION_WITHOUT_IDENTITY_HALTS_WITHOUT_SEIZING_BOOK");
var rejected=new MxmOrderProtection();
Require(!Check(rejected,ok:false,id:null,book:Array.Empty<MxmProtectionPosition>()).Halt,
 "CLEAN_REJECTION_NO_SYNTHETIC_FILL");
// Fake broker retry sequence: first close rejects, second book still contains ID;
// later absence suppresses another close but never reopens admission.
var retry=new MxmOrderProtection();Check(retry,book:new[]{good with {Stop=null}});
Require(retry.DefensiveCloseId(new[]{good})==90 && retry.DefensiveCloseId(new[]{good})==90,
 "DEFENSIVE_CLOSE_RETRY_SAME_ID");
Require(retry.DefensiveCloseId(Array.Empty<MxmProtectionPosition>())==null && retry.Halted,
 "FLATTENED_REMAINS_HALTED");
Console.WriteLine("MXM_POSTFILL_PROTECTION_IDENTITY_STOP_LATCH_RETRY_PASS_NOT_NATIVE_PROOF");
var output=Path.Combine("verification","broker-intent-fence","synthetic-contract.json");
Directory.CreateDirectory(Path.GetDirectoryName(output)!);
File.WriteAllText(output,JsonSerializer.Serialize(new {
 schema="mxm.broker-intent-fence.synthetic-contract.v1",checks,interleavings,
 old_product_counterexample_reproduced=true,postfill_protection_contract_passed=true,
 postfill_identity_stop_halt_defensive_retry_tested=true,native_ctrader_callbacks_observed=false,
 broker_orders=0,scientific_trials=0,hard21=false
},new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine("MXM_BROKER_CLOSE_FENCE_COUNTEREXAMPLE_AND_INTERLEAVINGS_PASS_NOT_NATIVE_CALLBACK_PROOF");

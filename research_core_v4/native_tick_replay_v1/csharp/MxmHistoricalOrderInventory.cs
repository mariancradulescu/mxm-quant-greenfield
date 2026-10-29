using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Replay {
/// <summary>
/// Observed broker historical-order facts, not complete broker history.
/// HistoricalOrder Id is broker-assigned AFTER submission; neither comment
/// nor label is a broker-enforced idempotency key.
/// </summary>
public sealed record MxmHistoricalOrderFact(long OrderId,string Symbol,int Direction,
 string Label,string Comment,string Status,DateTime SubmittedUtc,
 decimal SubmittedUnits,decimal? ObservedFilledUnits);

public sealed record MxmHistoricalIntentEvidence(int HistoricalMatches,
 long? UniqueOrderId,string Status,bool MatchedOpeningDeal,string Reason) {
 public bool MayResubmit=>false;
 public bool MayClearUnknown=>false;
 public bool AuthorizesCloudTrading=>false;
}

public sealed class MxmHistoricalOrderInventory {
 readonly MxmHistoricalOrderFact[] orders;
 public MxmHistoricalOrderFact[] Orders=>orders.ToArray();
 public string ScopeFingerprint {get;}
 public string FactsSha256 {get;}
 public DateTime ObservedUtc {get;}
 public bool HistoryCompleteProven=>false;
 public bool BrokerRequestIdempotencyProven=>false;
 public bool LateFillExcluded=>false;
 public bool MaySubmitNewOrder=>false;
 static bool Utc(DateTime x)=>x.Kind==DateTimeKind.Utc && x!=default;
 static void Need(bool ok) {
  if(!ok)throw new ArgumentException("HISTORICAL_ORDER_FACT_INVALID_OR_CONFLICTING");
 }
 static string Hash(string x)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(x))).ToLowerInvariant();
 public MxmHistoricalOrderInventory(string accountScope,DateTime observedUtc,
  IEnumerable<MxmHistoricalOrderFact> observations) {
  Need(!string.IsNullOrWhiteSpace(accountScope) && accountScope.Length<=1024 &&
   Utc(observedUtc) && observations!=null);
  ScopeFingerprint=Hash(accountScope);
  ObservedUtc=observedUtc;
  var unique=new Dictionary<long,MxmHistoricalOrderFact>();
  int seen=0;
  foreach(var o in observations) {
   Need(o!=null && ++seen<=100000 && o.OrderId>0 &&
    !string.IsNullOrWhiteSpace(o.Symbol) && o.Symbol.Length<=128 &&
    (o.Direction==1 || o.Direction==-1) &&
    o.Label!=null && o.Label.Length<=128 &&
    o.Comment!=null && o.Comment.Length<=1024 &&
    o.Status is ("Filled" or "Expired" or "Created" or "Accepted" or "Error" or "Cancelled") &&
    Utc(o.SubmittedUtc) && o.SubmittedUtc<=observedUtc &&
    o.SubmittedUnits>0m &&
    (!o.ObservedFilledUnits.HasValue ||
     o.ObservedFilledUnits.Value>=0m && o.ObservedFilledUnits.Value<=o.SubmittedUnits));
   if(unique.TryGetValue(o.OrderId,out var prior))Need(prior==o);
   else unique.Add(o.OrderId,o);
  }
  orders=unique.Values.OrderBy(o=>o.OrderId).ToArray();
  FactsSha256=Hash(JsonSerializer.Serialize(new {ScopeFingerprint,orders}));
 }
 /// <summary>
 /// Known pre-call intent + matching historical-order ID + independently
 /// observed opening deals are *positive* attribution only.
 /// Missing broker evidence (including rejected-looking statuses) is never
 /// a final negative acknowledgement nor a reason to resend.
 /// </summary>
 public MxmHistoricalIntentEvidence ObserveOriginalIntent(string? originalComment,
  string originalLabel,string originalSymbol,int originalDirection,
  MxmBrokerOpeningInventory opening) {
  if(string.IsNullOrWhiteSpace(originalComment) ||
    string.IsNullOrWhiteSpace(originalLabel) ||
    string.IsNullOrWhiteSpace(originalSymbol) ||
    originalDirection is not (1 or -1) || opening==null ||
    opening.ScopeFingerprint!=ScopeFingerprint)
   return new(0,null,"UNVERIFIED",false,"ORIGINAL_INTENT_OR_ACCOUNT_SCOPE_MISSING");
  var matches=orders.Where(o=>o.Comment==originalComment).ToArray();
  if(matches.Length==0)return new(0,null,"UNKNOWN",false,"ABSENCE_IS_NOT_A_NEGATIVE_ACK");
  if(matches.Length!=1)return new(matches.Length,null,"CONFLICT",false,"MULTIPLE_ORIGINAL_COMMENT_MATCHES");
  var match=matches[0];
  if(match.Label!=originalLabel || match.Symbol!=originalSymbol || match.Direction!=originalDirection)
   return new(1,match.OrderId,"CONFLICT",false,"ORIGINAL_IDENTITY_MISMATCH");
  // Only an opening deal with the broker-assigned SAME order ID, matching
  // original comment, label, symbol and side, can corroborate the opening.
  bool positive=opening.Orders.Any(o=>o.OrderId==match.OrderId &&
   o.Label==match.Label && o.Symbol==match.Symbol &&
   o.Direction==match.Direction && o.Comment==match.Comment);
  return new(1,match.OrderId,match.Status,positive,
   positive?"POSITIVE_HISTORICAL_ORDER_AND_OPENING_DEAL_NO_RETRY_PERMISSION":
    "HISTORICAL_ORDER_ONLY_NOT_A_COMPLETE_EXECUTION_OR_NO_FILL_PROOF");
 }
}
}

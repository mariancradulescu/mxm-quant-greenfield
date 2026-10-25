using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace Mxm.Replay {
public enum MxmEntryRecoveryInspection {Normal,Recoverable,Blocked}
public sealed record MxmRecoverableEntry(string Scope,string Attempt,string Label,string Symbol,int Direction,
 double Units,double StopPips,double PipSize,double TickSize,DateTime BoundaryUtc,DateTime PreparedUtc,
 DateTime DeadlineUtc,long[] BeforeIds) {
 public string Comment=>"MXM"+Attempt;
}
public sealed record MxmEntryRecoveryPosition(MxmProtectionPosition Position,string? Comment,DateTime EntryUtc,
 double PipSize,double TickSize);
public sealed record MxmEntryRecoveryVerdict(bool Accepted,string Reason,MxmEntryRecoveryPosition? Match);
/// <summary>Positive OPEN-position attribution only. A comment is correlation data,
/// not broker idempotency. No empty-book inference, order call, close or history heuristic.</summary>
public static class MxmEntryRecovery {
 sealed record Envelope(string Schema,string Body,string Sha256);
 static string Hash(string raw)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(raw))).ToLowerInvariant();
 static bool Utc(DateTime value)=>value.Kind==DateTimeKind.Utc && value!=default;
 public static bool Valid(MxmRecoverableEntry? r,string scope){
  try {
   return r!=null && r.Scope==scope && Guid.TryParseExact(r.Attempt,"N",out var id) && id!=Guid.Empty &&
    r.Attempt==id.ToString("N") && !string.IsNullOrWhiteSpace(r.Label) && r.Label.Length<=128 &&
    !string.IsNullOrWhiteSpace(r.Symbol) && r.Symbol.Length<=128 && (r.Direction==1 || r.Direction==-1) &&
    double.IsFinite(r.Units) && r.Units>0 && (decimal)r.Units>0 &&
    double.IsFinite(r.StopPips) && r.StopPips>0 && double.IsFinite(r.PipSize) && r.PipSize>0 &&
    double.IsFinite(r.TickSize) && r.TickSize>0 && Utc(r.BoundaryUtc) && Utc(r.PreparedUtc) && Utc(r.DeadlineUtc) &&
    r.BoundaryUtc<=r.PreparedUtc && r.PreparedUtc<r.DeadlineUtc &&
    (r.DeadlineUtc-r.BoundaryUtc).TotalMinutes is 1 or 5 or 15 && r.BeforeIds!=null && r.BeforeIds.Length<=10000 &&
    r.BeforeIds.All(x=>x>0) && r.BeforeIds.Distinct().Count()==r.BeforeIds.Length &&
    r.BeforeIds.SequenceEqual(r.BeforeIds.OrderBy(x=>x));
  }catch{return false;}
 }
 public static string Encode(MxmRecoverableEntry r){
  string body=JsonSerializer.Serialize(r);return JsonSerializer.Serialize(new Envelope("mxm.pending-entry.v2",body,Hash(body)));
 }
 public static MxmRecoverableEntry? Decode(string raw,string scope){
  try {
   var frame=JsonSerializer.Deserialize<Envelope>(raw);
   if(frame==null || frame.Schema!="mxm.pending-entry.v2" || frame.Body==null || frame.Sha256!=Hash(frame.Body))return null;
   var record=JsonSerializer.Deserialize<MxmRecoverableEntry>(frame.Body);
   return Valid(record,scope) && Encode(record!)==raw?record:null;
  }catch{return null;}
 }
 public static MxmEntryRecoveryVerdict Match(MxmRecoverableEntry r,IReadOnlyCollection<MxmEntryRecoveryPosition> book,
  int pendingOrders,DateTime now){
  MxmEntryRecoveryVerdict Refuse(string why)=>new(false,why,null);
  if(!Valid(r,r.Scope) || !Utc(now) || now<r.PreparedUtc)return Refuse("RECOVERY_REQUEST_OR_CLOCK_INVALID");
  if(pendingOrders!=0)return Refuse("BROKER_PENDING_ORDERS_UNRESOLVED");
  if(book==null || book.Any(x=>x==null || x.Position==null || x.Position.Id<=0) ||
     book.Select(x=>x.Position.Id).Distinct().Count()!=book.Count)return Refuse("BROKER_BOOK_IDENTITY_INVALID");
  var exact=book.Where(x=>x.Comment==r.Comment).ToArray();
  if(exact.Length!=1)return Refuse(exact.Length==0?"NO_POSITIVE_CORRELATED_OPEN_POSITION":"MULTIPLE_CORRELATED_POSITIONS");
  var match=exact[0];
  if(book.Any(x=>x.Position.Id!=match.Position.Id && !r.BeforeIds.Contains(x.Position.Id)))
   return Refuse("UNEXPECTED_OTHER_NEW_BROKER_POSITION");
  if(!Utc(match.EntryUtc) || match.EntryUtc<r.PreparedUtc || match.EntryUtc>now)
   return Refuse("BROKER_ENTRY_TIME_UNVERIFIED");
  if(match.PipSize!=r.PipSize || match.TickSize!=r.TickSize)return Refuse("BROKER_SYMBOL_GEOMETRY_CHANGED");
  var protection=new MxmOrderProtection().Reconcile(true,match.Position.Id,r.Label,r.Symbol,r.Direction,r.Units,
   r.StopPips,r.PipSize,r.TickSize,r.BeforeIds,book.Select(x=>x.Position).ToArray());
  return protection.Accepted?new(true,"EXACT_CORRELATED_OPEN_POSITION_AND_STOP",match):Refuse(protection.Reason);
 }
}
}

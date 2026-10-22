using System;
namespace Mxm.Replay {
/// <summary>
/// Single-broker-account admission inventory fence. The cBot may only open
/// a NEW entry when ALL existing broker positions use its managed MXM label
/// and there are no account pending orders. Such a read is still NOT an atomic
/// inter-robot lock: a second cBot can race after this snapshot.
/// This guard NEVER grants permission to manage other owners' positions.
/// </summary>
public static class MxmAccountIsolation {
 public const string Admit="ADMIT_ISOLATED_ACCOUNT_SNAPSHOT_ONLY";
 public static string Check(int allOpenAccountPositions,
                            int ownLabelAccountPositions,
                            int accountPendingOrders) {
  if(allOpenAccountPositions<0 || ownLabelAccountPositions<0 ||
     accountPendingOrders<0 || ownLabelAccountPositions>allOpenAccountPositions)
   return "REJECT_INCONSISTENT_ACCOUNT_BOOK";
  if(allOpenAccountPositions!=ownLabelAccountPositions)
   return "REJECT_FOREIGN_ACCOUNT_POSITION";
  if(accountPendingOrders!=0)
   return "REJECT_ACCOUNT_PENDING_ORDER";
  return Admit;
 }
}
}

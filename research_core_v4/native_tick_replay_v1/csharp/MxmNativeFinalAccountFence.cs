using System;
namespace Mxm.Replay {
/// <summary>
/// Last estimated account snapshot immediately before a potential broker order.
/// Conservative monotonic revalidation: after initial admission, equity/free
/// margin cannot have fallen, nor ticket margin/stop exposure increased.
/// Position/price/stop book identity is checked separately by the Robot.
/// Neither snapshot is atomic, nor a guarantee of broker fills/risk.
/// </summary>
public sealed record MxmNativeEntrySnapshot(decimal EquityEur,decimal FreeMarginEur,
 decimal TicketMarginEur,decimal ProposedStopRiskEur);
public static class MxmNativeFinalAccountFence {
 public const string Admit="FINAL_NATIVE_ACCOUNT_SNAPSHOT_ESTIMATE_ONLY";
 public static string Check(MxmNativeEntrySnapshot initial,MxmNativeEntrySnapshot final) {
  if(initial==null || final==null || initial.EquityEur<=0m || final.EquityEur<=0m ||
    initial.FreeMarginEur<=0m || final.FreeMarginEur<=0m ||
    initial.FreeMarginEur>initial.EquityEur || final.FreeMarginEur>final.EquityEur ||
    initial.TicketMarginEur<=0m || final.TicketMarginEur<=0m ||
    initial.ProposedStopRiskEur<=0m || final.ProposedStopRiskEur<=0m)
   return "REJECT_INVALID_OR_UNVERIFIED_FINAL_ACCOUNT_SNAPSHOT";
  if(final.EquityEur<initial.EquityEur)
   return "REJECT_ACCOUNT_EQUITY_DECLINED_BEFORE_ORDER";
  if(final.FreeMarginEur<initial.FreeMarginEur)
   return "REJECT_ACCOUNT_FREE_MARGIN_DECLINED_BEFORE_ORDER";
  if(final.TicketMarginEur>initial.TicketMarginEur)
   return "REJECT_TICKET_MARGIN_INCREASED_BEFORE_ORDER";
  if(final.ProposedStopRiskEur>initial.ProposedStopRiskEur)
   return "REJECT_PROPOSED_STOP_RISK_INCREASED_BEFORE_ORDER";
  return Admit;
 }
}

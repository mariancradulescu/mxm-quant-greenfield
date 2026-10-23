using System;

namespace Mxm.Replay {
/// <summary>Distance from CURRENT liquidation-side mark to broker stop.
/// Equity includes floating PnL, so entry-to-stop loss is not equity-at-risk.
/// The distance is an estimate, never guaranteed execution at the stop.</summary>
public static class MxmStopRiskGeometry {
 public const string Valid="VALID_MARK_TO_STOP_DISTANCE_ONLY";
 public static string TryDistance(int direction,decimal bid,decimal ask,
  decimal stop,decimal pipSize,out decimal distancePips) {
  distancePips=0;
  if((direction!=1 && direction!=-1) || bid<=0 || ask<bid || stop<=0 || pipSize<=0)
   return "REJECT_UNVERIFIED_MARK_TO_STOP_GEOMETRY";
  decimal distance=direction==1?bid-stop:stop-ask;
  // A stop already touched/passed is unresolved execution, not zero risk.
  // Never invent a fill, adjust the stop, or cancel a broker order here.
  if(distance<=0)return "REJECT_STOP_TOUCHED_OR_PASSED_ACK_UNRESOLVED";
  distancePips=distance/pipSize;
  return Valid;
 }
}
}

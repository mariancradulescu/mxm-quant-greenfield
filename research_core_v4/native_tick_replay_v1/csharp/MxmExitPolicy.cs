using System;
namespace Mxm.Replay {
/// <summary>Pure product/replay discretionary exit policy. Broker stop routing is separate.</summary>
public static class MxmExitPolicy {
 public static string? Reason(ExitMode mode,int desired,int currentDirection,
  bool contiguous,int completedBars,DateTime boundaryUtc,DateTime entryUtc,int barMinutes) {
  if(!Enum.IsDefined(typeof(ExitMode),mode) || desired < -1 || desired > 1 ||
   (currentDirection!=1 && currentDirection!=-1) || completedBars<0 || barMinutes<1 ||
   boundaryUtc.Kind!=DateTimeKind.Utc || entryUtc.Kind!=DateTimeKind.Utc || entryUtc==default)
   throw new ArgumentException("INVALID_EXIT_POLICY_STATE");
  if(contiguous && completedBars>=6 && mode==ExitMode.NeutralFlat && desired==0)
   return "NEUTRAL_FLAT";
  if(mode==ExitMode.Horizon12 && (boundaryUtc-entryUtc).TotalMinutes>=12*barMinutes)
   return "HORIZON12";
  return desired!=0 && desired!=currentDirection ? "REVERSAL" : null;
 }
}
}

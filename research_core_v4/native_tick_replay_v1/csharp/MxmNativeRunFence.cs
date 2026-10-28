using System;
namespace Mxm.Replay {
public enum MxmNativeRunMode { New, ExistingPath, ObservationOnly, Stopped }
/// <summary>Immutable run-purpose boundary, not a broker permission or mutex.
/// An observation instance cannot escalate, even after stop/parameter changes.
/// ExistingPath still requires EVERY original native permission/risk/storage check.
/// </summary>
public sealed class MxmNativeRunFence {
 public MxmNativeRunMode Mode {get;private set;}=MxmNativeRunMode.New;
 public bool ObservationLatched {get;private set;}
 public bool IsObserving=>Mode==MxmNativeRunMode.ObservationOnly;
 public bool BlocksAccountMutation=>Mode!=MxmNativeRunMode.ExistingPath;
 public bool Begin(bool observationOnly,bool demoTrading,bool simulation,string environment,out string reason) {
  if(Mode!=MxmNativeRunMode.New){Stop();reason="RUN_MODE_ALREADY_BOUND";return false;}
  ObservationLatched=observationOnly;
  if(environment is not ("Desktop" or "CLI" or "Cloud")) {Stop();reason="UNKNOWN_NATIVE_ENVIRONMENT";return false;}
  if(observationOnly) {
   if(demoTrading || simulation){Stop();reason="OBSERVATION_MODE_CONFLICT_OR_SIMULATION";return false;}
   Mode=MxmNativeRunMode.ObservationOnly;reason="OBSERVATION_ONLY_NO_ACCOUNT_MUTATION";return true;
  }
  if(!simulation && environment!="Desktop") {Stop();reason="ENTRY_PERSISTENCE_ENVIRONMENT_UNQUALIFIED_SAFE_STOP";return false;}
  Mode=MxmNativeRunMode.ExistingPath;reason="EXISTING_PATH_REQUIRES_ALL_ORIGINAL_GATES";return true;
 }
 public void DemandAccountMutationPath() {
  if(BlocksAccountMutation)throw new InvalidOperationException("OBSERVATION_OR_UNINITIALIZED_ACCOUNT_MUTATION_DENIED");
 }
 public void Stop()=>Mode=MxmNativeRunMode.Stopped;
}
}

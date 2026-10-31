using System;
using Mxm.Replay;
static void Check(bool yes,string label){if(!yes)throw new InvalidOperationException(label);}
decimal? F(decimal configured,decimal buy,decimal sell,decimal spread,decimal slip)
 => MxmNativeEstimatedFrictionGuard.FloorEur(configured,buy,sell,spread,slip);
Check(F(.20m,.05m,.06m,.27m,.10m)==.49m,"BOTH_FEES_SPREAD_SLIPPAGE");
Check(F(.20m,.05m,.06m,0m,0m)==.20m,"NEVER_WEAKEN_FIXED_RESERVE");
Check(F(.20m,.05m,.06m,.27m,.10m)>.20m,"NATIVE_SPREAD_NEVER_DISCARDED");
Check(F(.20m,.05m,.06m,.27m,.10m)+1.60m>2m,"MODELLED_STOP_PLUS_COST_REJECT");
Check(F(.20m,.05m,.06m,.27m,.10m)+1.40m<=2m,"ESTIMATED_STOP_PLUS_COST_ALLOW_BOUND");
Check(!F(.20m,.05m,.06m,-.01m,.10m).HasValue,"NO_UNKNOWN_NEGATIVE_SPREAD");
Check(!F(.20m,-.01m,.06m,.27m,.10m).HasValue,"NO_NEGATIVE_FEE");
Check(!F(.20m,.05m,.06m,.27m,-.01m).HasValue,"NO_NEGATIVE_SLIP");
Check(!F(.20m,.05m,.06m,decimal.MaxValue,.10m).HasValue,"COST_OVERFLOW_SAFE_HOLD");
Check(!F(decimal.MaxValue,decimal.MaxValue,0m,0m,0m).HasValue,"COMMISSION_OVERFLOW_SAFE_HOLD");
Console.WriteLine("MXM_NATIVE_OBSERVED_SPREAD_PLUS_BOTH_FEES_EUR_STOP_RISK_GUARD_PASS_NO_ORDERS");
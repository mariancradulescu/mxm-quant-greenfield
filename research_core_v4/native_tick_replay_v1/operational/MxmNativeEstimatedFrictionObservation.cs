using System;
using cAlgo.API;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>Operational native-only estimate, not an independent bot.</summary>
public sealed partial class MxmReferenceProductBot {
 [Parameter("Additional Slippage Cushion EUR", DefaultValue=0.10, MinValue=0.0)]
 public double ExtraSlippageCushionEur {get;set;}=0.10;
 decimal? NativeObservedRoundTripRiskReserve(Symbol symbol,double units,
  MxmNativeCommissionEstimate fee,double bid,double ask) {
  if(fee==null || symbol==null ||
     !double.IsFinite(units) || units<=0 ||
     !double.IsFinite(bid) || !double.IsFinite(ask) || bid<=0 || ask<bid ||
     !double.IsFinite(symbol.PipSize) || symbol.PipSize<=0 ||
     !double.IsFinite(ExtraSlippageCushionEur) || ExtraSlippageCushionEur<0 ||
     !double.IsFinite(EstimatedRoundTripFrictionReserveEur) ||
     EstimatedRoundTripFrictionReserveEur<0)return null;
  try {checked {
   double spreadPips=(ask-bid)/symbol.PipSize;
   if(!double.IsFinite(spreadPips) || spreadPips<0)return null;
   double cash=symbol.AmountRisked(units,spreadPips);
   if(!double.IsFinite(cash) || cash<0)return null;
   return MxmNativeEstimatedFrictionGuard.FloorEur(
    (decimal)EstimatedRoundTripFrictionReserveEur,
    fee.BuyEur,fee.SellEur,(decimal)cash,(decimal)ExtraSlippageCushionEur);
  }}catch(Exception){return null;}
 }
}
}

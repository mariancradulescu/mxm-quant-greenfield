using System;
namespace Mxm.Replay {
/// <summary>Descriptive price geometry only: no freshness, liquidity or fill claim.</summary>
public enum MxmBookShapeKind { Missing,Invalid,Crossed,Locked,Positive }
public static class MxmBookShape {
 public static MxmBookShapeKind Classify(decimal? bid,decimal? ask) {
  if(!bid.HasValue || !ask.HasValue)return MxmBookShapeKind.Missing;
  if(bid<=0m || ask<=0m)return MxmBookShapeKind.Invalid;
  return ask<bid?MxmBookShapeKind.Crossed:ask==bid?MxmBookShapeKind.Locked:MxmBookShapeKind.Positive;
 }
 public static MxmBookShapeKind ClassifyNative(double bid,double ask) {
  if(!double.IsFinite(bid)||!double.IsFinite(ask)||bid<=0d||ask<=0d)return MxmBookShapeKind.Invalid;
  return ask<bid?MxmBookShapeKind.Crossed:ask==bid?MxmBookShapeKind.Locked:MxmBookShapeKind.Positive;
 }
 // Caller policy is explicit. Neither predicate alone admits any broker order.
 public static bool NonCrossed(MxmBookShapeKind shape)=>shape is MxmBookShapeKind.Locked or MxmBookShapeKind.Positive;
 public static bool StrictlyPositive(MxmBookShapeKind shape)=>shape==MxmBookShapeKind.Positive;
}
}

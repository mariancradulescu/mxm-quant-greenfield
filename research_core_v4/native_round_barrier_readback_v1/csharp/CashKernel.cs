using System;
namespace Mxm.Native {
public static class CashKernel {
 public static double Scenario(int direction,double quantity,double entryBid,double entryAsk,double exitBid,double exitAsk,double fxBid,double fxAsk,double feeBps,string quote){
  if((direction!=1 && direction!=-1)||quantity<=0||!(0<entryBid && entryBid<entryAsk && 0<exitBid && exitBid<exitAsk)||feeBps<0)throw new ArgumentException("INVALID");
  double gross=quantity*(direction>0 ? exitBid-entryAsk:entryBid-exitAsk);
  double value=gross-quantity*(entryBid+entryAsk)/2*feeBps/10000;
  if(quote=="EUR")return value;if(quote!="USD"||!(0<fxBid && fxBid<fxAsk))throw new ArgumentException("FX_ROUTE");
  return value/(value>=0 ? fxAsk:fxBid);
 }
}}

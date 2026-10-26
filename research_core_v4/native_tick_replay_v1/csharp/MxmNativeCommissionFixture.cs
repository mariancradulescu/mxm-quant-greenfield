using System;
using System.Collections.Generic;
using Mxm.Replay;
int checks=0;
void Need(bool ok,string reason) {if(!ok)throw new Exception("NATIVE_COMMISSION_FIXTURE_"+reason);checks++;}
var types=new[]{0,1,2,3};
foreach(var kind in types)foreach(var minType in new[]{0,1}) {
 // Independent artificial cTrader API-style fees and equivalent captured-terms
 // wire fee calculator, at both modeled fill sides. NO actual Pepperstone fees.
 decimal units=1000m,bid=1.20m,ask=1.2002m;
 decimal commission=kind==2?0.1m:3.5m;
 decimal minimum=0.2m;
 var t=new MxmNativeCommissionTerms(kind,minType,"USD",minType==0?"EUR":"USD",
  commission,minimum,100000m);
 var z=MxmNativeCommission.Price(t,units,bid,ask,1m,0.9m,0.9m,1m);
 int capturedKind=kind+1;
 long rawRate=kind==2?10000:350000000;
 var historic=new MxmCommissionTerms(17,"USD",capturedKind,rawRate,
  minType==0?1:2,20000000,minType==0?"EUR":"USD",100000,1000000000,100000,10000000);
 var rates=new Dictionary<string,decimal>{{"EUR",1m},{"USD",0.9m}};
 var buy=MxmInstrumentCommission.Price(historic,100000,ask,1m,rates).UnroundedFeeEur;
 var sell=MxmInstrumentCommission.Price(historic,100000,bid,1m,rates).UnroundedFeeEur;
 Need(z.BuyEur==buy && z.SellEur==sell && z.PerSideCeilingEur==Math.Max(buy,sell),
  "EXACT_SIDE_PARITY_KIND_"+kind+"_MIN_"+minType);
 Need(z.RoundTripReserveEur==2m*z.PerSideCeilingEur &&
  z.Classification.Contains("NOT_BROKER_CHARGE"),"TWO_SIDE_RESERVE_NO_PROMOTION");
 Need(MxmOwnerEntryEnvelope.Check(200m,80m,z.PerSideCeilingEur,
   0.01m,0m)=="REJECT_OWNER_POST_ENTRY_RESERVE_LT_120",
   "OWNER_FEE_REDUCES_FREE_RESERVE");
}
// Final pre-order recheck with independent hypothetical changed conversion.
var boundTerms=new MxmNativeCommissionTerms(0,0,"USD","EUR",350m,.01m,100000m);
var early=MxmNativeCommission.Price(boundTerms,1000m,1.2m,1.2002m,1m,.9m,.9m,1m);
var costlierFx=MxmNativeCommission.Price(boundTerms,1000m,1.2m,1.2002m,1m,1.1m,.9m,1m);
var cheaperFx=MxmNativeCommission.Price(boundTerms,1000m,1.2m,1.2002m,1m,.8m,.9m,1m);
Need(MxmNativeCommission.StillCovered(early,early),"REPRICE_IDENTICAL_ALLOWED");
Need(!MxmNativeCommission.StillCovered(early,costlierFx),"REPRICE_INCREASE_REJECTED");
Need(MxmNativeCommission.StillCovered(early,cheaperFx),"REPRICE_DECREASE_KEEPS_EARLIER_RESERVE");
Need(!MxmNativeCommission.StillCovered(early,
 early with {RoundTripReserveEur=0m}),"REPRICE_FALSE_BROKER_RESERVE_REJECTED");
Need(!MxmNativeCommission.StillCovered(early,
 early with {Classification="EXACT_BROKER_CHARGE"}),"REPRICE_FALSE_CLAIM_REJECTED");
Need(MxmOwnerEntryEnvelope.RoundTripFeeReserveCovers(early.RoundTripReserveEur,early.BuyEur,early.SellEur),
 "NATIVE_QUOTED_BOTH_SIDES_RESERVE_RECONCILIATION");
Need(!MxmOwnerEntryEnvelope.RoundTripFeeReserveCovers(early.PerSideCeilingEur,early.BuyEur,early.SellEur),
 "ONE_FEE_NOT_TWO_SIDE_RESERVE");
void Reject(MxmNativeCommissionTerms t,decimal qUsd=1m,decimal usdEur=.9m,
 decimal quoteEur=.9m,decimal minEur=1m,decimal volume=1000m,
 decimal bid=1.2m,decimal ask=1.2002m) {
 bool threw=false;
 try {MxmNativeCommission.Price(t,volume,bid,ask,qUsd,usdEur,quoteEur,minEur);}
 catch(ArgumentException){threw=true;}
 Need(threw,"INVALID_MUST_FAIL");
}
var normal=new MxmNativeCommissionTerms(0,0,"USD","EUR",3.5m,.2m,100000m);
Reject(normal,qUsd:0);Reject(normal,usdEur:0);
Reject(normal,minEur:0);Reject(normal,bid:1.3m,ask:1.2m);
Reject(normal,volume:0);
Reject(normal with {Type=4});Reject(normal with {MinimumType=2});
Reject(normal with {LotSize=0});Reject(normal with {Commission=-1m});
Reject(normal with {Minimum=-1m});Reject(normal with {QuoteAsset=""});
Reject(normal with {MinimumAsset=""});
Reject(normal with {Commission=decimal.MaxValue,Minimum=decimal.MaxValue});
var percent=normal with {Type=2};
Reject(percent,quoteEur:0);
var quoteMin=normal with {MinimumType=1};
Reject(quoteMin,quoteEur:0);
var free=new MxmNativeCommissionTerms(1,0,"USD","EUR",0m,0m,100000m);
var zero=MxmNativeCommission.Price(free,1000m,1.2m,1.3m,0m,0m,0m,0m);
Need(zero.RoundTripReserveEur==0m,"EXPLICIT_ZERO_TERMS_NOT_MISSING_SOURCE");
Console.WriteLine("MXM_NATIVE_FEE_ESTIMATE_ARTIFICIAL_KIND_MINIMUM_PARITY_AND_INVALIDS "+checks);
Console.WriteLine("NATIVE_SYMBOL_AND_CONVERTER_VALUES_ARE_ESTIMATES_NOT_BROKER_CHARGES_NO_ORDERS");

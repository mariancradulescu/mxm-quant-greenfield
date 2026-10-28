using System;
using System.Globalization;
using System.Numerics;
namespace Mxm.Replay;
// Constant displayed-rate component only. No charging calendar, effective-term
// history, contract multiplier, executable FX or actual broker charge is inferred.
public sealed record MxmDisplayedFinancing(long SymbolId,string Asset,int CalculationType,
 string SignedRate,long VolumeCents,int Direction,int PriceExponent,int ExplicitMultiplier,string SourceSha256);
public sealed record MxmFinancingComponent(long SymbolId,string Asset,long VolumeCents,int Direction,decimal AmountQuote,
 string SourceSha256,bool ActualBrokerCharge=false,bool HistoricalApplicability=false);
public static class MxmDisplayedFinancingCalculator {
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("DISPLAYED_FINANCING_"+why);}
 public static bool Digest(string v)=>v!=null && v.Length==64 && System.Linq.Enumerable.All(v,c=>c>='0'&&c<='9'||c>='a'&&c<='f');
 // Parse the exact supplied decimal representation, including exponents. Do not
 // allow Decimal.TryParse to silently turn a nonzero sub-quantum debit into zero.
 static (BigInteger N,BigInteger D) Ratio(string value){
  Need(value!=null && value.Length is >0 and <=80,"RATE_FORMAT");
  string text=value!;int sign=1;if(text.StartsWith("-",StringComparison.Ordinal)){sign=-1;text=text[1..];}
  else if(text.StartsWith("+",StringComparison.Ordinal))text=text[1..];
  string[] exp=text.Split('e','E');Need(exp.Length<=2,"RATE_EXPONENT");
  int power=exp.Length==1?0:int.Parse(exp[1],NumberStyles.AllowLeadingSign,CultureInfo.InvariantCulture);
  Need(power is >=-400 and <=400,"RATE_EXPONENT_BOUND");
  string[] dot=exp[0].Split('.');Need(dot.Length<=2,"RATE_DECIMAL");string digits=string.Concat(dot);
  Need(digits.Length is >0 and <=64 && System.Linq.Enumerable.All(digits,c=>c>='0'&&c<='9'),"RATE_DIGITS");
  int scale=(dot.Length==2?dot[1].Length:0)-power;
  BigInteger n=sign*BigInteger.Parse(digits,CultureInfo.InvariantCulture),d=BigInteger.One;
  if(scale>=0)d=BigInteger.Pow(10,scale);else n*=BigInteger.Pow(10,-scale);return(n,d);
 }
 public static decimal Floor18(BigInteger n,BigInteger d){
  Need(d>0,"DENOMINATOR");BigInteger q=BigInteger.DivRem(n*BigInteger.Pow(10,18),d,out var rem);
  if(rem<0)q--;BigInteger abs=BigInteger.Abs(q),whole=BigInteger.DivRem(abs,BigInteger.Pow(10,18),out var fraction);
  string rendered=(q<0?"-":"")+whole.ToString(CultureInfo.InvariantCulture)+"."+fraction.ToString("D18",CultureInfo.InvariantCulture);
  Need(decimal.TryParse(rendered,NumberStyles.AllowLeadingSign|NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out decimal result),"AMOUNT_RANGE");
  // Decimal parsing can round when integer and fractional digits exceed28.
  var actual=Ratio(result.ToString(CultureInfo.InvariantCulture));
  Need(actual.N*BigInteger.Pow(10,18)==q*actual.D,"OUTPUT_QUANTUM_EXACT");return result;
 }
 public static MxmFinancingComponent Estimate(MxmDisplayedFinancing x){
  Need(x.SymbolId>0 && !string.IsNullOrWhiteSpace(x.Asset) && x.Asset.Length<=64 && Digest(x.SourceSha256),"IDENTITY");
  Need(x.CalculationType is 0 or 2,"PERCENTAGE_OR_UNKNOWN_CASH_BASIS_UNRESOLVED");
  Need(x.VolumeCents>0 && (x.Direction==1 || x.Direction==-1) && x.PriceExponent is >=0 and <=18 && x.ExplicitMultiplier is >=1 and <=7,"EXPLICIT_UNITS");
  var rate=Ratio(x.SignedRate);decimal amount=Floor18(rate.N*x.VolumeCents*x.ExplicitMultiplier,rate.D*100*BigInteger.Pow(10,x.PriceExponent));
  return new(x.SymbolId,x.Asset,x.VolumeCents,x.Direction,amount,x.SourceSha256);
 }
 // Scenario conversion: floor signed values, use the adverse side for debits.
 public static decimal ConvertScenario(MxmFinancingComponent component,decimal creditEurPerAsset,decimal debitEurPerAsset){
  Need(creditEurPerAsset>0 && debitEurPerAsset>=creditEurPerAsset,"TWO_SIDED_SCENARIO_FX");
  if(component.Asset=="EUR")Need(creditEurPerAsset==1m && debitEurPerAsset==1m,"EUR_IDENTITY");
  var a=Ratio(component.AmountQuote.ToString(CultureInfo.InvariantCulture));var r=Ratio((component.AmountQuote<0?debitEurPerAsset:creditEurPerAsset).ToString(CultureInfo.InvariantCulture));
  return Floor18(a.N*r.N,a.D*r.D);
 }
}

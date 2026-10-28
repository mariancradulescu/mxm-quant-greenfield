"""Exact independent rational source-cost oracle. No prices, forecast or cash posting."""
from fractions import Fraction
from decimal import Decimal
import re
SHA=re.compile('^[0-9a-f]{64}$')
def floor18(value):
 units=value.numerator*10**18//value.denominator
 # C# Decimal must preserve the complete fixed-18 output exactly.
 rendered=('-' if units<0 else '')+str(abs(units)//10**18)+'.'+str(abs(units)%10**18).zfill(18)
 result=Decimal(rendered)
 coefficient=abs(units);scale=18
 while coefficient and coefficient%10==0 and scale>0:coefficient//=10;scale-=1
 if coefficient>79228162514264337593543950335:raise ValueError('DISPLAYED_FINANCING_OUTPUT_QUANTUM_EXACT')
 return result

def reference(rows):
 output=[]
 for r in rows:
  estimates=[]
  for direction in (1,-1):
   reason=None
   try:
    f=r['full'];asset=r['quote_asset']
    if asset is None:raise ValueError('QUOTE_ASSET_UNRESOLVED')
    lo,step,hi=[int(f[k]) for k in ('minVolume','stepVolume','maxVolume')]
    if lo<=0 or step<=0 or hi<lo or lo%step:raise ValueError('VOLUME_LATTICE_UNRESOLVED')
    kind=int(f['swapCalculationType'])
    if kind not in (0,2):raise ValueError('PERCENTAGE_OR_UNKNOWN_CASH_BASIS_UNRESOLVED')
    exponent=int(f['pipPosition' if kind==0 else 'digits']);rate=f['swapLong' if direction==1 else 'swapShort']
    if not r['symbol_id']>0 or not asset.strip() or len(asset)>64 or not SHA.fullmatch(r['source_sha256']):raise ValueError('DISPLAYED_FINANCING_IDENTITY')
    if not 0<=exponent<=18:raise ValueError('DISPLAYED_FINANCING_EXPLICIT_UNITS')
    try:raw_rate=Fraction(rate)
    except (ValueError,ZeroDivisionError):raise ValueError('DISPLAYED_FINANCING_RATE_DIGITS')
    amount=floor18(raw_rate*lo/Fraction(100*10**exponent))
    estimates.append({'direction':direction,'status':'DISPLAYED_RATE_UNIT_COMPONENT_ONLY','component':{'SymbolId':r['symbol_id'],'Asset':asset,'VolumeCents':lo,'Direction':direction,'AmountQuote':amount,'SourceSha256':r['source_sha256'],'ActualBrokerCharge':False,'HistoricalApplicability':False}})
   except KeyError:reason='EXPLICIT_FIELD_UNRESOLVED'
   except ValueError as e:reason=str(e)
   if reason is not None:estimates.append({'direction':direction,'status':'UNRESOLVED','reason':reason})
  output.append({'symbol_id':r['symbol_id'],'estimates':estimates})
 return output

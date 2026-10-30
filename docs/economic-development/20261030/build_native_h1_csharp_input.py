"""Generate the exact existing .NET portfolio_policy Program.cs input from authenticated
M5-derived complete-hour closes plus separate next-open outcome observations.
Plaintext is PRIVATE: never Git/upload public; GitHub receives ciphertext only.
"""
import datetime as dt,hashlib,json,io,zipfile
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parent
SIDS=(3,7,9,10,11,12,13,14)
START=dt.datetime(2025,9,28,tzinfo=dt.timezone.utc)
END=dt.datetime(2026,6,1,tzinfo=dt.timezone.utc)
ZFILES=['MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip','MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip']
EXPECTED=['09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259','37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e']


def main():
    archives={}
    for filename,expected in zip(ZFILES,EXPECTED):
        raw=(P/filename).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==expected
        archives[filename]=zipfile.ZipFile(io.BytesIO(raw))
    events=[];prices={};custody={}
    for sid in SIDS:
        matches=[(name,z) for name,z in archives.items() if f'raw/{sid}_M5.csv' in z.namelist()]
        assert len(matches)==1
        fname,z=matches[0]
        raw=z.read(f'raw/{sid}_M5.csv'); df=pd.read_csv(io.BytesIO(raw),parse_dates=['time_utc']).set_index('time_utc').sort_index()
        unique=df.index.is_unique;assert unique and (df.index.tz is not None)
        # Use the immutable broker identity mapping from original source receipt.
        original=json.load(open(P/'PRIMARY145_AUTHENTICATED_SOURCE_CLOCKS_PRIVATE.json'))
        record=next(x for x in original['actual_series_clock_receipts'] if x['symbol_id']==sid)
        assert record['csv_sha256']==hashlib.sha256(raw).hexdigest()
        symbol=record['symbol']
        h=df.resample('1h',label='left',closed='left').agg({'close':['count','last']})
        h.columns=['n','close'];h=h[h['n']==12]
        for start,rec in h.iterrows():
            end=start.to_pydatetime()+dt.timedelta(hours=1)
            if START<=end<END:
                events.append({'symbol':symbol,'end':end.isoformat().replace('+00:00','Z'),
                  'close':str(rec['close']),'available':(end+dt.timedelta(minutes=5)).isoformat().replace('+00:00','Z')})
        # The outcome lookups are deliberately disjoint from native policy input bars.
        # The native C# code never reads this additional root field.
        for t in pd.date_range(START,END,freq='1h',inclusive='left'):
            d=t.to_pydatetime()
            if d.weekday()>=5 or not 7<=d.hour<=15:continue
            a=df['open'].get(pd.Timestamp(d+dt.timedelta(minutes=5)))
            b=df['open'].get(pd.Timestamp(d+dt.timedelta(minutes=60)))
            if a is not None and b is not None:
                prices[f'{symbol}|{d.isoformat().replace("+00:00","Z")}']={'entry':str(a),'exit':str(b)}
        custody[symbol]={'sid':sid,'raw_csv_sha256':record['csv_sha256'],'archive_sha256':EXPECTED[ZFILES.index(fname)],'hour_events':sum(e['symbol']==symbol for e in events)}
    events.sort(key=lambda x:(x['end'],x['symbol']))
    symbols=sorted(custody)
    data={'symbols':symbols,'bars':events,'outcome_lookup_PRIVATE_NOT_NATIVE_INPUT':prices,
      'source_clock_rules':'12 genuine M5 observations, no interpolation; next-open t+5 to t+60 for outcome only',
      'source_original_verified':custody}
    dst=P/'PRIMARY145_NATIVE_H1_CSHARP_INPUT_PRIVATE.json'
    dst.write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({'symbols':symbols,'bars':len(events),'outcome_quote_pairs':len(prices),
          'source_tape_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'private_bytes':dst.stat().st_size},indent=2))
if __name__=='__main__':main()

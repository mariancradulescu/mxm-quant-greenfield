"""Prospective pure extraction only. No files, broker, forecasts or responses."""
import math
WEEK=7*86400

def weekly_activity_surprise(cutoff,bars):
    """bars: timestamp -> {timestamp,available_at,tick_volume}; close-time availability.
    Caller must separately verify original receipts or classify as conditional lag.
    No stale-hour search, gap fill, session compression or nearest-week substitute.
    """
    if type(cutoff) is not int or cutoff%300: raise ValueError('M5_GRID')
    hour=cutoff//3600*3600-3600
    totals=[]
    for w in range(5):
        total=0
        for ts in range(hour-w*WEEK,hour-w*WEEK+3600,300):
            b=bars.get(ts)
            if b is None:return None,'WEEKLY_MATCHED_HOUR_INCOMPLETE'
            a=b.get('available_at');v=b.get('tick_volume')
            if b.get('timestamp')!=ts or type(a) is not int or not ts+300<=a<=cutoff:return None,'LATE_OR_INVALID_RECORD'
            if type(v) is not int or v<0:return None,'INVALID_ACTIVITY'
            total+=v
        totals.append(total)
    return math.log1p(totals[0])-sum(math.log1p(v) for v in totals[1:])/4,'SUPPORTED'

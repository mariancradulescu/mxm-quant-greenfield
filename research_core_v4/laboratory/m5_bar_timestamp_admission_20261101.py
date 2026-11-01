"""Auxiliary prospective M5 historical/open-time admission contract.

DOES NOT edit SHA-frozen historic envelopes, models, signals, C# cBot, or the
source custody. cTrader historical ProtoOATrendbar stamps its OPEN, and
BarClosed is delivered when a NEW bar opens, not at bar-open of old candle.
No original market or future return data is accessed here.
"""
from __future__ import annotations
from datetime import datetime,timezone

M5_MS=300_000

def nominal_completed_m5_bar(bar_open_ms:int,next_open_ms:int,decision_ms:int)->bool:
    """Historical source *nominal* closure; never certifies live arrival."""
    for n in (bar_open_ms,next_open_ms,decision_ms):
        if type(n) is not int or n<0:
            raise ValueError("M5_OPEN_TIME_NONNEGATIVE_INT_REQUIRED")
    if bar_open_ms % M5_MS or next_open_ms % M5_MS:
        raise ValueError("M5_SOURCE_OPEN_CLOCK_NOT_ALIGNED")
    return next_open_ms==bar_open_ms+M5_MS and decision_ms>=next_open_ms

def native_closed_m5_bar_received(bar_open_ms:int,next_open_ms:int,
                                  next_bar_first_receipt_ms:int|None,decision_ms:int)->bool:
    """Requires a REAL next-bar first receipt; no synthetic clock substitution."""
    if not nominal_completed_m5_bar(bar_open_ms,next_open_ms,decision_ms):
        return False
    if next_bar_first_receipt_ms is None:return False
    if type(next_bar_first_receipt_ms) is not int or next_bar_first_receipt_ms<0:
        raise ValueError("M5_NATIVE_RECEIPT_NONNEGATIVE_INT_REQUIRED")
    return next_bar_first_receipt_ms>=next_open_ms and decision_ms>=next_bar_first_receipt_ms

def selftest():
    t=int(datetime(2026,9,8,10,25,tzinfo=timezone.utc).timestamp()*1000)
    assert not nominal_completed_m5_bar(t,t+M5_MS,t)
    assert not nominal_completed_m5_bar(t,t+M5_MS,t+M5_MS-1)
    assert nominal_completed_m5_bar(t,t+M5_MS,t+M5_MS)
    assert not nominal_completed_m5_bar(t,t+2*M5_MS,t+M5_MS)
    assert not native_closed_m5_bar_received(t,t+M5_MS,None,t+M5_MS)
    assert not native_closed_m5_bar_received(t,t+M5_MS,t+M5_MS+750,t+M5_MS)
    assert native_closed_m5_bar_received(t,t+M5_MS,t+M5_MS+750,t+M5_MS+900)
    assert not native_closed_m5_bar_received(t,t+2*M5_MS,t+M5_MS+750,t+M5_MS+900)
    try:nominal_completed_m5_bar(t,t+M5_MS,"2026-09-08T10:30Z")
    except ValueError:pass
    else:raise AssertionError("BAD_TIME_TYPE_ACCEPTED")
    print("MXM_PROSPECTIVE_M5_OPEN_TIME_RECEIPT_FENCE_SELFTEST_SUCCESS")
if __name__=="__main__":selftest()

"""Current-metadata-only localization. No quotes, historical data or orders.

Credentials are injected into localize(), never read from repository or written.
Protocol/transport imports occur only after credential checks. The transport-facing
allowlist is narrower than the legacy generic read-only collector allowlist.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

ALLOWED = frozenset({'ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq',
 'ProtoOAAccountAuthReq','ProtoOATraderReq','ProtoOAAssetListReq',
 'ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAExpectedMarginReq'})
FINGERPRINT = 'b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636'


def checked_request(transport, message):
    if type(message).__name__ not in ALLOWED:
        raise PermissionError('request outside current-metadata allowlist')
    response = transport.request(message)
    if type(response).__name__ in {'ProtoOAErrorRes','ProtoCHErrorRes'}:
        raise RuntimeError('broker rejected current metadata request')
    return response


def classify(identity, light, full, margin, deposit='EUR'):
    """No strategy outcomes, signal support or ranking inputs are accepted."""
    base = {'symbol':identity['symbol'], 'symbol_id':identity['symbol_id'],
            'asset_class':identity['asset_class'], 'historical_quote_support':'UNKNOWN'}
    def out(status, reason):
        return dict(base, status=status, reason=reason)
    if not light or not full or deposit != 'EUR':
        return out('METADATA_INSUFFICIENT','missing full/light metadata or EUR deposit proof')
    if str(light.get('symbolName')) != identity['symbol'] or int(full.get('symbolId',-1)) != identity['symbol_id']:
        return out('METADATA_INSUFFICIENT','broker identity mismatch')
    if light.get('enabled') is False or full.get('tradingMode') in (1,2,3) or full.get('enableShortSelling') is False:
        return out('STRUCTURALLY_INELIGIBLE','disabled entry mode or short selling disabled')
    required = ['minVolume','stepVolume','lotSize','maxVolume','tradingMode',
                'enableShortSelling','commissionType','scheduleTimeZone','schedule',
                'pnlConversionFeeRate','minCommissionType','minCommissionAsset']
    if any(k not in full for k in required) or any(k not in light for k in ['baseAssetId','quoteAssetId']) or full.get('tradingMode') != 0:
        return out('METADATA_INSUFFICIENT','required explicit execution/schedule/conversion semantics absent')
    try:
        lo, step, lot, hi = (int(full[k]) for k in ['minVolume','stepVolume','lotSize','maxVolume'])
        if min(lo,step,lot) <= 0 or hi < lo:
            return out('STRUCTURALLY_INELIGIBLE','invalid min/step/lot/max volume')
        if lo % step:
            return out('METADATA_INSUFFICIENT','minimum/step alignment requires explicit broker volume-lattice resolution')
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(full['scheduleTimeZone'])
            if any(not (0 <= int(v['startSecond']) < int(v['endSecond']) <= 604800) for v in full['schedule']):
                return out('METADATA_INSUFFICIENT','weekly schedule boundaries require resolution')
        except (ZoneInfoNotFoundError,KeyError,ValueError,TypeError):
            return out('METADATA_INSUFFICIENT','schedule/timezone malformed')
        if int(full['commissionType']) not in (1,2,3,4):
            return out('METADATA_INSUFFICIENT','unknown commission unit')
        if 'minCommission' not in full and 'preciseMinCommission' not in full:
            return out('METADATA_INSUFFICIENT','minimum commission absent; zero not inferred')
        if 'commission' not in full and 'preciseTradingCommissionRate' not in full:
            return out('METADATA_INSUFFICIENT','commission rate missing; zero not inferred')
        if int(full.get('commission',0)) != 0 and 'preciseTradingCommissionRate' not in full:
            return out('METADATA_INSUFFICIENT','nonzero legacy commission requires precise rate')
        if not full['schedule'] or not isinstance(full['scheduleTimeZone'],str):
            return out('METADATA_INSUFFICIENT','empty schedule or timezone')
        if not margin or int(margin['requested_volume']) != lo:
            return out('METADATA_INSUFFICIENT','expected margin not bound to exact minimum volume')
        digits = int(margin['moneyDigits'])
        if not 0 <= digits <= 18:
            raise ValueError()
        buy,sell = (Decimal(str(margin[k])) / Decimal(10)**digits for k in ['buyMargin','sellMargin'])
        if not buy.is_finite() or not sell.is_finite() or min(buy,sell) < 0:
            raise ValueError()
        base.update(buy_min_margin_eur=str(buy),sell_min_margin_eur=str(sell),
                    min_volume=lo,step_volume=step,lot_size=lot)
        if max(buy,sell) >= Decimal(200):
            return out('ECONOMICALLY_UNEXECUTABLE_FOR_EUR200','one or both minimum margins >= EUR200')
    except (KeyError,ValueError,TypeError,InvalidOperation):
        return out('METADATA_INSUFFICIENT','malformed execution or margin units')
    return out('STRUCTURALLY_ELIGIBLE','explicit current bidirectional entry/min-volume margin and metadata gates pass; no profitability certification')


def localize(frontier, *, client_id, client_secret, access_token, transport=None):
    if not all(isinstance(x,str) and x for x in [client_id,client_secret,access_token]):
        raise PermissionError('Secure cTrader read-only application/token credential injection required')
    if len(frontier)!=1576 or len({x['symbol_id'] for x in frontier})!=1576:
        raise ValueError('exact authoritative frontier required')
    from google.protobuf.json_format import MessageToDict
    from m6.ctrader_proto import OpenApiMessages_pb2 as oa
    from m6.ctrader_transport import StdlibCTraderTransport
    from m6.ctrader_capture import account_fingerprint
    plain = lambda x: MessageToDict(x,preserving_proto_field_name=False,use_integers_for_enums=True)
    tr = transport or StdlibCTraderTransport()
    send = lambda name,**kw: checked_request(tr,getattr(oa,name)(**kw))
    started = datetime.now(timezone.utc).isoformat()
    try:
        tr.connect()
        send('ProtoOAApplicationAuthReq',clientId=client_id,clientSecret=client_secret)
        acc = send('ProtoOAGetAccountListByAccessTokenReq',accessToken=access_token)
        if not acc.HasField('permissionScope') or int(acc.permissionScope)!=0:
            raise PermissionError('explicit SCOPE_VIEW access token required')
        candidates = [x for x in acc.ctidTraderAccount if x.isLive and account_fingerprint(int(x.ctidTraderAccountId))==FINGERPRINT]
        if len(candidates)!=1: raise PermissionError('authorized LIVE account fingerprint mismatch')
        aid=int(candidates[0].ctidTraderAccountId)
        send('ProtoOAAccountAuthReq',ctidTraderAccountId=aid,accessToken=access_token)
        trader=plain(send('ProtoOATraderReq',ctidTraderAccountId=aid).trader)
        if 'pepperstone' not in str(trader.get('brokerName','')).lower():
            raise PermissionError('Pepperstone broker identity unresolved')
        assets={int(x.assetId):plain(x) for x in send('ProtoOAAssetListReq',ctidTraderAccountId=aid).asset}
        deposit=assets.get(int(trader.get('depositAssetId',-1)),{}).get('name')
        if deposit!='EUR': raise PermissionError('EUR deposit not proved')
        lights={int(x.symbolId):plain(x) for x in send('ProtoOASymbolsListReq',ctidTraderAccountId=aid,includeArchivedSymbols=False).symbol}
        rows=[]
        # One symbol per full-metadata request bounds response sizes; no symbol
        # skipped because another failed, no retries that mask missing metadata.
        for identity in sorted(frontier,key=lambda x:x['symbol_id']):
            sid=identity['symbol_id']; light=lights.get(sid); full=None; margin=None
            if light is not None:
                q=oa.ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.append(sid)
                res=checked_request(tr,q)
                found=[x for x in res.symbol if int(x.symbolId)==sid]
                if len(found)==1:
                    full=plain(found[0])
                    # Explicitly materialize proto defaults without inventing
                    # absent optional monetary/conversion/shortability fields.
                    if int(full.get('minVolume',0))>0:
                        q=oa.ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,symbolId=sid)
                        q.volume.append(int(full['minVolume']))
                        m=plain(checked_request(tr,q))
                        vals=m.get('margin',[])
                        if len(vals)==1 and int(vals[0].get('volume',-1))==int(full['minVolume']):
                            margin=dict(vals[0],moneyDigits=m.get('moneyDigits'),requested_volume=int(full['minVolume']))
            rows.append(dict(classify(identity,light,full,margin,deposit),
                             current_light_metadata=light,current_full_metadata=full,expected_margin=margin))
        result={'schema':'mxm.v4.quote-scope-current-metadata.v1','started_utc':started,
          'completed_utc':datetime.now(timezone.utc).isoformat(),'account_fingerprint_sha256':FINGERPRINT,
          'source_environment':'Pepperstone - Europe LIVE','deposit_asset':'EUR','rows':rows,
          'historical_requests_sent':0,'orders_sent':0,'features_computed':False,'responses_computed':False}
        # Do not return auth responses, account ID, trader balances or credentials.
        import json
        raw=json.dumps(result)
        if any(s in raw for s in [client_secret,access_token]):
            raise PermissionError('secret leakage rejected')
        return result
    except Exception:
        # Suppress transport exception details that might contain auth fields.
        raise RuntimeError('current metadata localization failed closed; no historical requests') from None
    finally:
        tr.close()

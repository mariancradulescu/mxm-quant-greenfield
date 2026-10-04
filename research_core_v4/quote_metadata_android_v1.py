"""Device-only current metadata collection and sanitized single-ZIP publication.

The frozen localizer is unchanged. This facade enforces protocol identity, rate
limits, private account selection, read-only reconnection and output allowlists.
No scientific modules are imported. No private file is copied into the ZIP.
"""
from __future__ import annotations
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.parse
import zipfile

EXPECTED_LOCALIZER_SHA = 'd3aba0cfe36d85465ed9c384ccc1979887b82e5229793f359ea5d1652efbd48c'
EXPECTED_IDENTITY_SHA = '2287445f9b8dbd61ef40a1d81756e1848c2b623a846bc968c4e214d9b2a874e1'
FRONTIER_REL = 'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json'
CONTRACT_REL = 'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_CONTRACT_V1.json'
STATUSES = frozenset({'STRUCTURALLY_ELIGIBLE','STRUCTURALLY_INELIGIBLE',
 'METADATA_INSUFFICIENT','ECONOMICALLY_UNEXECUTABLE_FOR_EUR200'})
OUTPUT_NAME = 'MXM_V4_CURRENT_METADATA_1576_RETURN_V1.zip'
SENSITIVE_KEYS = frozenset({'clientid','clientsecret','accesstoken','refreshtoken',
 'authorizationcode','ctidtraderaccountid','accountid','balance','balanceeur',
 'traderlogin','password','equity','usedmargin','freemargin'})
LIGHT_FIELDS = frozenset({'symbolId','symbolName','enabled','baseAssetId','quoteAssetId','symbolCategoryId'})
FULL_FIELDS = frozenset({'symbolId','digits','pipPosition','enableShortSelling',
 'minVolume','stepVolume','maxVolume','lotSize','tradingMode','commission',
 'commissionType','preciseTradingCommissionRate','minCommission','preciseMinCommission',
 'minCommissionType','minCommissionAsset','pnlConversionFeeRate','leverageId',
 'scheduleTimeZone','schedule','holiday','measurementUnits'})
MARGIN_FIELDS = frozenset({'volume','buyMargin','sellMargin','moneyDigits','requested_volume'})


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_frontier(root):
    raw=(Path(root)/FRONTIER_REL).read_bytes();data=json.loads(raw)
    if not isinstance(data,list) or len(data)!=1576:
        raise ValueError('frontier must have exactly1576 identities')
    if any(set(x)!={'symbol','symbol_id','asset_class'} or type(x['symbol_id']) is not int
           or x['symbol_id']<=0 or not isinstance(x['symbol'],str) or not x['symbol']
           or not isinstance(x['asset_class'],str) or not x['asset_class'] for x in data):
        raise ValueError('frontier shape invalid')
    if len({x['symbol_id'] for x in data})!=1576 or len({x['symbol'] for x in data})!=1576:
        raise ValueError('frontier duplicates')
    if data!=sorted(data,key=lambda x:x['symbol_id']) or sha(canonical(data))!=EXPECTED_IDENTITY_SHA:
        raise ValueError('authoritative identity hash mismatch')
    return data


def verify_package(root):
    root=Path(root);manifest=json.loads((root/'PACKAGE_MANIFEST.json').read_bytes())
    if manifest.get('schema')!='mxm.v4.android-current-metadata-source-package.v1':
        raise ValueError('package manifest schema')
    files=manifest.get('file_sha256',{})
    if not files or FRONTIER_REL not in files or CONTRACT_REL not in files:
        raise ValueError('package file inventory incomplete')
    for rel,h in files.items():
        target=root/rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or target.is_symlink():
            raise ValueError('unsafe package path')
        if sha(target.read_bytes())!=h:raise ValueError('package checksum mismatch')
    if sha((root/'research_core_v4/quote_scope_metadata_v1.py').read_bytes())!=EXPECTED_LOCALIZER_SHA:
        raise ValueError('frozen localizer hash mismatch')
    contract=json.loads((root/CONTRACT_REL).read_bytes())
    if contract['frontier_identity_sha256']!=EXPECTED_IDENTITY_SHA or contract['historical_requests_authorized'] is not False:
        raise ValueError('wrong metadata-only contract')
    load_frontier(root) # before OAuth imports, browser or network
    return manifest


def verify_runtime(root):
    """Reject cached/site modules from another deployment before private OAuth."""
    import importlib
    root=Path(root).resolve()
    expected={'google.protobuf':('5.29.5',root/'vendor'),
              'tzdata':('2026.5',root/'vendor')}
    for name,(version,prefix) in expected.items():
        module=importlib.import_module(name)
        if module.__version__!=version or not Path(module.__file__).resolve().is_relative_to(prefix):
            raise PermissionError('loaded dependency differs from bound deployment')
    for name in ['research_core_v4.quote_scope_metadata_v1','m6.pydroid_oauth',
                 'm6.ctrader_transport','m6.ctrader_proto.OpenApiMessages_pb2',
                 'm6.ctrader_proto.OpenApiModelMessages_pb2']:
        module=importlib.import_module(name)
        expected_path=root/(name.replace('.','/')+'.py')
        if Path(module.__file__).resolve()!=expected_path:
            raise PermissionError('loaded source module differs from bound deployment')


class Secrets:
    """Private memory only; never printable or included in manifests."""
    def __init__(self):self._values=set()
    def __repr__(self):return '<private values withheld>'
    def add(self,value):
        if value is not None and str(value):self._values.add(str(value))
    def capture(self,oauth):
        # The paths come from the unchanged device-local infrastructure.
        for path in [oauth.APP_CONFIG_PATH,oauth.TOKEN_STATE_PATH,oauth.ACCOUNT_SELECTION_PATH]:
            data=oauth._load_json(path) or {}
            for key in ['client_id','client_secret','access_token','refresh_token','ctid_trader_account_id']:
                self.add(data.get(key))
    def scan(self,raw):
        text=raw.decode('utf-8')
        for value in self._values:
            forms={value,json.dumps(value,ensure_ascii=False)[1:-1],json.dumps(value)[1:-1],urllib.parse.quote(value,safe=''),urllib.parse.quote_plus(value,safe='')}
            if any(x and x in text for x in forms):
                raise PermissionError('private-value output scan rejected package')


class MetadataTransport:
    """Only eight metadata messages; canonical protobuf type and payload checks."""
    def __init__(self,inner,oauth,secrets,progress=print,clock=time.monotonic,sleep=time.sleep):
        from m6.ctrader_proto import OpenApiMessages_pb2 as oa
        from research_core_v4.quote_scope_metadata_v1 import ALLOWED
        self._oa=oa;self._types={name:getattr(oa,name) for name in ALLOWED}
        self._inner=inner;self._oauth=oauth;self._secrets=secrets
        self._progress=progress;self._clock=clock;self._sleep=sleep;self._last=None
        self.request_counts=collections.Counter();self._app=None;self._account=None
        self._completed_symbol_ids=set();self.authorization_needs_refresh=False
        self._selected=False;self.asset_metadata=[]
        self.scope_view_verified=False;self.account_auth_verified=False
    def __repr__(self):return '<metadata-only transport; private state withheld>'
    def connect(self):self._inner.connect()
    def close(self):self._inner.close()
    def _validate(self,msg):
        name=type(msg).__name__
        if name not in self._types or type(msg) is not self._types[name]:
            raise PermissionError('unexpected protocol request')
        if not msg.IsInitialized() or int(msg.payloadType)!=int(self._types[name]().payloadType):
            raise PermissionError('malformed metadata request/payload override')
        return name
    def _send(self,msg):
        name=self._validate(msg)
        now=self._clock()
        if self._last is not None:
            delay=.05-(now-self._last) # <=20 metadata requests/sec; published ceiling50
            if delay>0:self._sleep(delay)
        self._last=self._clock();self.request_counts[name]+=1
        res=self._inner.request(msg)
        if type(res).__name__ not in {'ProtoOAErrorRes','ProtoCHErrorRes'}:
            expected=name[:-3]+'Res'
            if type(res) is not getattr(self._oa,expected) or not res.IsInitialized():
                raise PermissionError('unexpected metadata response type')
            if 'ctidTraderAccountId' in res.DESCRIPTOR.fields_by_name and res.HasField('ctidTraderAccountId') and 'ctidTraderAccountId' in msg.DESCRIPTOR.fields_by_name and int(res.ctidTraderAccountId)!=int(msg.ctidTraderAccountId):
                raise PermissionError('metadata response account mismatch')
        return res
    def _restore(self):
        self._inner.close();self._inner.connect()
        for auth in [self._app,self._account]:
            if auth is not None:
                res=self._send(auth)
                if type(res).__name__ in {'ProtoOAErrorRes','ProtoCHErrorRes'}:
                    raise RuntimeError('read-only reconnect auth rejected')
    def request(self,msg):
        name=self._validate(msg)
        from m6.ctrader_transport import TransportError
        for attempt in range(3):
            try:
                res=self._send(msg);break
            except PermissionError:
                raise
            except (TransportError,OSError,TimeoutError):
                if attempt==2:raise RuntimeError('current metadata transport failed closed') from None
                self._sleep(float(attempt+1));self._restore()
        if type(res).__name__ in {'ProtoOAErrorRes','ProtoCHErrorRes'}:
            code=str(getattr(res,'errorCode','')).upper()
            if any(x in code for x in ['TOKEN_INVALID','INVALID_TOKEN','TOKEN_EXPIRED','ACCESS_TOKEN_INVALID']):
                self.authorization_needs_refresh=True
                raise RuntimeError('read-only authorization expired or rejected')
            if 'AUTH' in code or 'PERMISSION' in code or 'SCOPE' in code:
                raise RuntimeError('read-only authorization rejected')
            # Broker-declared per-symbol unavailable metadata becomes an explicit
            # unresolved row; raw error descriptions never leave the facade.
            if name=='ProtoOASymbolByIdReq':
                return self._oa.ProtoOASymbolByIdRes(ctidTraderAccountId=msg.ctidTraderAccountId)
            if name=='ProtoOAExpectedMarginReq':
                return self._oa.ProtoOAExpectedMarginRes(ctidTraderAccountId=msg.ctidTraderAccountId)
            raise RuntimeError('broker rejected current metadata authorization')
        if name=='ProtoOAApplicationAuthReq':self._app=msg
        if name=='ProtoOAAccountAuthReq':self._account=msg;self.account_auth_verified=True
        if name=='ProtoOAGetAccountListByAccessTokenReq':
            if not res.HasField('permissionScope') or int(res.permissionScope)!=0:
                raise PermissionError('SCOPE_VIEW required')
            self.scope_view_verified=True
            from m6.ctrader_capture import account_fingerprint
            from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT
            live=[x for x in res.ctidTraderAccount if x.isLive]
            bound=[x for x in live if account_fingerprint(int(x.ctidTraderAccountId))==FINGERPRINT]
            if len(bound)!=1:
                self.authorization_needs_refresh=True
                raise PermissionError('bound LIVE account not authorized')
            if not self._selected:
                saved=self._oauth.load_saved_account_id()
                valid_saved=saved is not None and int(saved)==int(bound[0].ctidTraderAccountId)
                if len(live)>1 and not valid_saved:
                    from google.protobuf.json_format import MessageToDict
                    choices=[MessageToDict(x,preserving_proto_field_name=False) for x in live]
                    chosen=self._oauth.choose_live_account_locally(choices)
                    if int(chosen)!=int(bound[0].ctidTraderAccountId):
                        raise PermissionError('selected account differs from frozen fingerprint')
                self._secrets.add(int(bound[0].ctidTraderAccountId));self._selected=True
        if name=='ProtoOAAssetListReq':
            from google.protobuf.json_format import MessageToDict
            self.asset_metadata=[{k:v for k,v in MessageToDict(x,preserving_proto_field_name=False).items() if k in {'assetId','name','displayName','digits'}} for x in res.asset]
        if name=='ProtoOASymbolByIdReq':
            self._completed_symbol_ids.update(int(x) for x in msg.symbolId)
            n=len(self._completed_symbol_ids)
            if n%50==0 or n==1576:self._progress(f'[METADATE] {n}/1576 ({n*100/1576:.1f}%)')
        return res


def reject_sensitive_keys(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if re.sub(r'[^a-z0-9]','',str(k).lower()) in SENSITIVE_KEYS:
                raise PermissionError('private output field rejected')
            reject_sensitive_keys(v)
    elif isinstance(value,list):
        for v in value:reject_sensitive_keys(v)
    elif isinstance(value,str) and re.search(r'https?://[^\s]*[?&](?:code|access_token|refresh_token|client_secret|client_id)=',value,re.I):
        raise PermissionError('authentication URL output rejected')


def sanitize(result,frontier):
    from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT
    reject_sensitive_keys(result)
    if result.get('account_fingerprint_sha256')!=FINGERPRINT or result.get('deposit_asset')!='EUR' or result.get('source_environment')!='Pepperstone - Europe LIVE':
        raise ValueError('environment proof mismatch')
    if result.get('historical_requests_sent')!=0 or result.get('orders_sent')!=0 or result.get('features_computed') is not False or result.get('responses_computed') is not False:
        raise PermissionError('nonmetadata execution state')
    rows=result.get('rows',[]);expected={x['symbol_id']:x for x in frontier}
    if len(rows)!=1576 or len({x['symbol_id'] for x in rows})!=1576 or {x['symbol_id'] for x in rows}!=set(expected):
        raise ValueError('output identity completeness failed')
    out=[]
    fields={'symbol','symbol_id','asset_class','historical_quote_support','status','reason',
            'buy_min_margin_eur','sell_min_margin_eur','min_volume','step_volume','lot_size'}
    for row in sorted(rows,key=lambda x:x['symbol_id']):
        ident=expected[row['symbol_id']]
        if any(row[k]!=ident[k] for k in ident) or row.get('status') not in STATUSES:
            raise ValueError('output identity/classification mismatch')
        new={k:v for k,v in row.items() if k in fields}
        for key,allowed in [('current_light_metadata',LIGHT_FIELDS),('current_full_metadata',FULL_FIELDS),('expected_margin',MARGIN_FIELDS)]:
            data=row.get(key)
            if data is not None and not isinstance(data,dict):raise ValueError('metadata object invalid')
            new[key]={k:v for k,v in (data or {}).items() if k in allowed} if data is not None else None
        # Nested schedule/holiday fields are also allowlisted; retain exactly
        # the materialization semantics, without unrelated server fields.
        full=new['current_full_metadata']
        if full:
            for key,allowed in [('schedule',{'startSecond','endSecond'}),('holiday',{'holidayId','name','description','holidayDate','isRecurring','startSecond','endSecond','scheduleTimeZone'})]:
                if key in full:
                    if not isinstance(full[key],list):raise ValueError('schedule shape invalid')
                    full[key]=[{k:v for k,v in x.items() if k in allowed} for x in full[key]]
        out.append(new)
    clean={k:result[k] for k in ['schema','started_utc','completed_utc','account_fingerprint_sha256','source_environment','deposit_asset','historical_requests_sent','orders_sent','features_computed','responses_computed']}
    clean['rows']=out
    clean['asset_metadata']=[{k:v for k,v in x.items() if k in {'assetId','name','displayName','digits'}} for x in result.get('asset_metadata',[])]
    clean['frontier_identity_sha256']=EXPECTED_IDENTITY_SHA
    clean['summary_counts']={k:sum(r['status']==k for r in out) for k in sorted(STATUSES)}
    clean['asset_class_composition']=dict(sorted(collections.Counter(r['asset_class'] for r in out).items()))
    clean['eligible_asset_class_composition']=dict(sorted(collections.Counter(r['asset_class'] for r in out if r['status']=='STRUCTURALLY_ELIGIBLE').items()))
    reject_sensitive_keys(clean);canonical(clean)
    return clean


def publish_return(result,frontier,root,output_dir,secrets,transports,package_manifest):
    clean=sanitize(result,frontier)
    counts=collections.Counter()
    for tr in transports:counts.update(tr.request_counts)
    from research_core_v4.quote_scope_metadata_v1 import ALLOWED
    if set(counts)-ALLOWED:raise PermissionError('unexpected protocol trace')
    if not transports or not transports[-1].scope_view_verified or not transports[-1].account_auth_verified:
        raise PermissionError('verified read-only account trace required')
    manifest={'schema':'mxm.v4.android-current-metadata-execution-manifest.v1',
       'status':'COMPLETED_CURRENT_METADATA_ONLY','source_head':package_manifest['source_head'],
       'frontier_count':1576,'frontier_identity_sha256':EXPECTED_IDENTITY_SHA,
       'source_file_sha256':{k:v for k,v in package_manifest['file_sha256'].items() if k in [
         'V4_CURRENT_METADATA_RUN.py','research_core_v4/pydroid_quote_metadata_launcher_v1.py',
         'research_core_v4/quote_metadata_android_v1.py','research_core_v4/quote_scope_metadata_v1.py',FRONTIER_REL,CONTRACT_REL]},
       'started_utc':clean['started_utc'],'completed_utc':clean['completed_utc'],
       'current_metadata_request_attempt_counts':dict(sorted(counts.items())),
       'historical_requests_sent':0,'orders_sent':0,'features_computed':False,'responses_computed':False,
       'permission_scope_verified':0,'bound_account_auth_verified':True,
       'known_private_value_scan_passed':True,'OAuth_state_exported':False,
       'summary_counts':clean['summary_counts'],'all1576_identity_rows_verified':True,
       'future_historical_capture_authorized':False,'scientific_execution_authorized':False}
    files={'CURRENT_METADATA_LOCALIZATION.json':canonical(clean)+b'\n',
           'EXECUTION_MANIFEST.json':canonical(manifest)+b'\n',
           'FRONTIER_IDENTITIES.json':canonical(frontier)+b'\n'}
    files['CHECKSUMS.sha256']=''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    for data in files.values():reject_sensitive_keys(json.loads(data) if data[:1] in (b'{',b'[') else None);secrets.scan(data)
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    # Only one caller-owned fixed return file. Never add OAuth cache/root trees.
    final=output_dir/OUTPUT_NAME;tmp=output_dir/(OUTPUT_NAME+'.partial')
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o600<<16;z.writestr(info,data)
        with zipfile.ZipFile(tmp) as z:
            if set(z.namelist())!=set(files) or z.testzip() is not None:raise ValueError('ZIP integrity')
            for name in z.namelist():
                data=z.read(name);secrets.scan(data)
                if data!=files[name]:raise ValueError('ZIP content mismatch')
        os.replace(tmp,final)
    finally:tmp.unlink(missing_ok=True)
    return final

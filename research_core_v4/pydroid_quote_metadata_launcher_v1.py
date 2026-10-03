"""One Pydroid run: existing device OAuth -> metadata-only -> one sanitized ZIP."""
from pathlib import Path
from research_core_v4.quote_metadata_android_v1 import (
    verify_package,verify_runtime,load_frontier,Secrets,MetadataTransport,publish_return,
)


def run_device(root,*,oauth=None,transport_factory=None,progress=print,output_dir=None):
    root=Path(root)
    package=verify_package(root) # exact frontier/source hashes BEFORE OAuth/network
    frontier=load_frontier(root)
    if oauth is None:
        verify_runtime(root)
        from m6 import pydroid_oauth as oauth
    if transport_factory is None:
        from m6.ctrader_transport import StdlibCTraderTransport
        transport_factory=StdlibCTraderTransport
    from research_core_v4.quote_scope_metadata_v1 import localize
    secrets=Secrets();secrets.capture(oauth);transports=[]
    token_request=oauth._token_request
    def private_token_request(params):
        # Capture transient authorization code for export scanning only; no logs.
        for k in ['client_id','client_secret','refresh_token','code']:secrets.add(params.get(k))
        value=token_request(params)
        for k in ['accessToken','refreshToken']:secrets.add(value.get(k))
        return value
    oauth._token_request=private_token_request
    try:
        progress('[PREFLIGHT OK] 1576 identități exacte; numai metadate curente; fără istoric sau ordine.')
        app,access,mode=oauth.ensure_v2_authorization()
        secrets.capture(oauth)
        for key in ['client_id','client_secret']:secrets.add(app.get(key))
        secrets.add(access)
        if str(app.get('scope','')).lower()!='accounts':raise PermissionError('read-only OAuth app scope required')
        progress('[OAUTH OK] Autorizare privată pe dispozitiv; verificare SCOPE_VIEW la broker.')
        for attempt in range(2):
            transport=MetadataTransport(transport_factory(),oauth,secrets,progress=progress)
            transports.append(transport)
            try:
                result=localize(frontier,client_id=app['client_id'],client_secret=app['client_secret'],access_token=access,transport=transport)
                break
            except Exception:
                if attempt==0 and mode!='FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION' and transport.authorization_needs_refresh:
                    progress('[OAUTH] Autorizarea salvată trebuie reînnoită pentru contul exact; continuă în browser, fără un al doilea RUN.')
                    app,access,mode=oauth.force_fresh_v2_authorization()
                    secrets.capture(oauth)
                    for key in ['client_id','client_secret']:secrets.add(app.get(key))
                    secrets.add(access)
                    if str(app.get('scope','')).lower()!='accounts':raise PermissionError('read-only OAuth app scope required')
                    continue
                raise
        secrets.capture(oauth)
        result['asset_metadata']=transports[-1].asset_metadata
        return publish_return(result,frontier,root,output_dir or root/'RETURN_TO_CHATGPT',secrets,transports,package)
    finally:
        oauth._token_request=token_request


def main(root):
    try:
        path=run_device(root)
        print('[FINALIZAT] Metadate curente pentru toate cele1576 identități; fără istoric, ordine sau răspunsuri științifice.')
        print('TRIMITE ÎNAPOI DOAR ACEST ZIP:')
        print(path.resolve())
        return 0
    except KeyboardInterrupt:
        print('[OPRIT] Nu s-a finalizat un nou ZIP de rezultate. Nu trimite un ZIP vechi.')
        return 130
    except Exception:
        # Never print transport/OAuth exceptions, request objects, URLs or paths
        # to private caches. Preserve all working private authorization state.
        print('[BLOCAT ÎN SIGURANȚĂ] Nu s-a finalizat un nou ZIP. Autorizarea privată rămâne pe telefon; nu trimite un ZIP vechi.')
        return 1

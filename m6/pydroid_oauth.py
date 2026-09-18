"""Pydroid browser-first OAuth state for the M6 read-only cTrader capture.

First V2 run obtains a fresh account grant. Legacy phone state may supply only the
Open API application's client_id/client_secret; legacy access/refresh tokens and old
DEMO/LIVE grants are never imported. Later V2 runs reuse or refresh the V2 token.
"""
from __future__ import annotations

import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from .ctrader_capture import (
    READ_ONLY_SCOPE,
    TOKEN_URL,
    OAuthError,
    atomic_write_json,
    build_authorization_url,
)

REDIRECT_URI = "http://127.0.0.1:8765/callback"
LOCAL_SETUP_URI = "http://127.0.0.1:8765/setup"

PRIVATE_ROOT = Path.home() / ".mxm_quant" / "m6_ctrader_capture_v2"
PRIVATE_STATE_PATH = PRIVATE_ROOT / "credentials.json"
LEGACY_APP_STATE_PATH = (
    Path.home() / ".mxm_quant" / "a118_c02_openapi_v1" / "credentials.json"
)
TOKEN_EXPIRY_SAFETY_SECONDS = 60


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _normalize_app_credentials(raw):
    if not isinstance(raw, dict):
        return None
    scope = raw.get("scope")
    if scope not in (None, "", READ_ONLY_SCOPE):
        return None
    client_id = str(raw.get("client_id") or raw.get("clientId") or "").replace("\\x00", "").strip()
    client_secret = str(raw.get("client_secret") or raw.get("clientSecret") or "").replace("\\x00", "").strip()
    if not client_id or not client_secret:
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "scope": READ_ONLY_SCOPE,
    }


def _secure_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, value)
    try:
        os.chmod(path.parent, 0o700)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _v2_state():
    raw = _load_json(PRIVATE_STATE_PATH)
    if raw is None or raw.get("scope") != READ_ONLY_SCOPE:
        return None
    app = _normalize_app_credentials(raw)
    if app is None:
        return None
    result = dict(raw)
    result.update(app)
    return result


def _app_credentials_for_fresh_auth():
    current = _normalize_app_credentials(_load_json(PRIVATE_STATE_PATH))
    if current is not None:
        return current, "V2_PRIVATE_APP_CREDENTIALS"

    legacy = _normalize_app_credentials(_load_json(LEGACY_APP_STATE_PATH))
    if legacy is not None:
        return legacy, "LEGACY_APP_CREDENTIALS_ONLY"
    return None, None


def _token_request(params: dict) -> dict:
    try:
        response = requests.get(TOKEN_URL, params=params, timeout=30)
    except requests.RequestException:
        raise OAuthError("cTrader token endpoint transport failure") from None
    if response.status_code != 200:
        raise OAuthError(f"cTrader token endpoint HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        raise OAuthError("cTrader token endpoint returned malformed JSON") from None
    if not isinstance(data, dict) or not data.get("accessToken"):
        detail = data.get("description") if isinstance(data, dict) else None
        raise OAuthError(
            f"cTrader token endpoint rejected authorization: {detail or 'no access token'}"
        )
    return data


def _save_v2_state(app: dict, token: dict, *, authorization_source: str):
    now = int(time.time())
    expires_in = int(token.get("expiresIn") or 0)
    state = {
        "client_id": app["client_id"],
        "client_secret": app["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "scope": READ_ONLY_SCOPE,
        "access_token": token["accessToken"],
        "refresh_token": token.get("refreshToken"),
        "expires_at_unix": now + expires_in if expires_in > 0 else 0,
        "saved_at_unix": now,
        "authorization_source": authorization_source,
        "target_environment": "Pepperstone - Europe LIVE",
        "legacy_account_grants_imported": False,
        "legacy_access_refresh_tokens_imported": False,
    }
    _secure_write_json(PRIVATE_STATE_PATH, state)
    return state


def _refresh_v2_state(state):
    refresh = state.get("refresh_token")
    if not refresh:
        return None
    try:
        token = _token_request({
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": state["client_id"],
            "client_secret": state["client_secret"],
        })
    except OAuthError:
        return None
    app = _normalize_app_credentials(state)
    if app is None:
        return None
    return _save_v2_state(app, token, authorization_source="V2_REFRESH_TOKEN")


def _remembered_v2_authorization():
    state = _v2_state()
    if state is None:
        return None
    expires_at = int(state.get("expires_at_unix") or 0)
    access_token = str(state.get("access_token") or "")
    if access_token and expires_at > int(time.time()) + TOKEN_EXPIRY_SAFETY_SECONDS:
        app = _normalize_app_credentials(state)
        if app is not None:
            return app, access_token
    refreshed = _refresh_v2_state(state)
    if refreshed is None:
        return None
    app = _normalize_app_credentials(refreshed)
    if app is None:
        return None
    return app, str(refreshed["access_token"])


def _setup_html():
    return """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM cTrader Setup</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px">
<h2>MXM cTrader Open API setup</h2>
<p>This is a <b>local page on 127.0.0.1</b>. These are Open API application
credentials, not your cTID username/password. They stay on this phone and never
enter the capture ZIP or ChatGPT.</p>
<form method="post" action="/setup" autocomplete="off">
<label>Open API Client ID</label><br>
<input name="client_id" style="width:100%;padding:10px" required><br><br>
<label>Open API Client Secret</label><br>
<input name="client_secret" type="password" style="width:100%;padding:10px" required><br><br>
<button type="submit" style="padding:12px 18px">Continue to cTrader authorization</button>
</form></body></html>"""


def _callback_html():
    return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM authorization received</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px">
<h2>Authorization received.</h2>
<p>Pydroid is continuing automatically. You can return to Pydroid now.</p>
<script>setTimeout(function(){try{window.close();}catch(e){}},500);</script>
</body></html>"""


class BrowserOAuthHandler(BaseHTTPRequestHandler):
    server_version = "MXMM6OAuth/3.0"

    def _send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/setup":
            self._send_html(_setup_html())
            return
        if parsed.path == "/callback":
            query = parse_qs(parsed.query, keep_blank_values=True)
            self.server.oauth_code = (query.get("code") or [None])[0]
            self.server.oauth_error = (query.get("error") or [None])[0]
            self._send_html(_callback_html())
            return
        self._send_html("<html><body>Not found</body></html>", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/setup":
            self._send_html("<html><body>Not found</body></html>", 404)
            return
        try:
            length = min(max(int(self.headers.get("Content-Length", "0")), 0), 65536)
        except ValueError:
            length = 0
        raw = self.rfile.read(length).decode("utf-8", "replace")
        form = parse_qs(raw, keep_blank_values=True)
        app = _normalize_app_credentials({
            "client_id": (form.get("client_id") or [""])[0],
            "client_secret": (form.get("client_secret") or [""])[0],
            "scope": READ_ONLY_SCOPE,
        })
        if app is None:
            self._send_html(
                "<html><body><h3>Client ID and Client Secret are required.</h3>"
                "<a href='/setup'>Try again</a></body></html>",
                400,
            )
            return
        self.server.app_credentials = app
        auth_url = build_authorization_url(
            app["client_id"], REDIRECT_URI, scope=READ_ONLY_SCOPE
        )
        self.send_response(303)
        self.send_header("Location", auth_url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def _open_browser(url: str) -> None:
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:
        raise OAuthError(
            f"Android browser could not be opened: {type(exc).__name__}"
        ) from None
    if opened is False:
        raise OAuthError(
            "Android browser refused the OAuth launch; set a default browser and RUN again"
        )


def _fresh_browser_authorization(timeout_seconds=300):
    server = HTTPServer(("127.0.0.1", 8765), BrowserOAuthHandler)
    server.timeout = 1
    server.oauth_code = None
    server.oauth_error = None

    app, app_source = _app_credentials_for_fresh_auth()
    server.app_credentials = app

    try:
        if app is None:
            print("[OAUTH] Opening browser. Open API app setup is required once on this phone.")
            _open_browser(LOCAL_SETUP_URI)
        else:
            if app_source == "LEGACY_APP_CREDENTIALS_ONLY":
                print("[OAUTH] Reusing ONLY the existing Open API APPLICATION credentials.")
                print("[OAUTH] Old DEMO/LIVE grants and old access/refresh tokens are NOT reused.")
            print("[OAUTH] Opening official cTrader authorization page...")
            print("[OAUTH] Select ONLY the intended Pepperstone LIVE account, then Allow access.")
            _open_browser(
                build_authorization_url(
                    app["client_id"], REDIRECT_URI, scope=READ_ONLY_SCOPE
                )
            )

        deadline = time.monotonic() + timeout_seconds
        while (
            time.monotonic() < deadline
            and not server.oauth_code
            and not server.oauth_error
        ):
            server.handle_request()

        if server.oauth_error:
            raise OAuthError(f"cTrader authorization denied: {server.oauth_error}")
        if not server.oauth_code:
            raise OAuthError(
                "OAuth callback timed out. Keep Pydroid running during authorization and "
                "verify redirect URI is exactly http://127.0.0.1:8765/callback"
            )
        app = server.app_credentials
        if app is None:
            raise OAuthError("Open API application credentials were not established")

        token = _token_request({
            "grant_type": "authorization_code",
            "code": server.oauth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": app["client_id"],
            "client_secret": app["client_secret"],
        })
        state = _save_v2_state(
            app, token, authorization_source="FRESH_V2_BROWSER_GRANT"
        )
        return app, str(state["access_token"])
    finally:
        server.oauth_code = None
        server.server_close()


def ensure_v2_authorization():
    """One fresh V2 browser grant, then remember/refresh it on later runs."""
    remembered = _remembered_v2_authorization()
    if remembered is not None:
        app, access_token = remembered
        return app, access_token, "REMEMBERED_V2_AUTHORIZATION"
    app, access_token = _fresh_browser_authorization()
    return app, access_token, "FRESH_BROWSER_AUTHORIZATION"

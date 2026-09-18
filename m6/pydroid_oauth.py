"""Clean browser-first OAuth for the M6 read-only cTrader capture.

No legacy credentials, grants, tokens, or account selections are imported.
On the first run this module opens a local browser setup page for the approved
Open API application's Client ID/Secret, stores them only in a new private local
directory, then redirects to the official cTrader OAuth page. Every run performs
a fresh user-visible cTrader authorization with scope=accounts.
"""
from __future__ import annotations

import json
import os
import subprocess
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

# Deliberately new clean state. Nothing from prior MXM/cTrader auth folders is read.
PRIVATE_ROOT = Path.home() / ".mxm_quant" / "m6_ctrader_capture_clean_v1"
APP_CONFIG_PATH = PRIVATE_ROOT / "app_credentials.json"
TOKEN_STATE_PATH = PRIVATE_ROOT / "oauth_state.json"


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _secure_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, value)
    try:
        os.chmod(path.parent, 0o700)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _normalize_app_credentials(raw):
    if not isinstance(raw, dict):
        return None
    client_id = str(raw.get("client_id") or "").replace("\\x00", "").strip()
    client_secret = str(raw.get("client_secret") or "").replace("\\x00", "").strip()
    redirect_uri = str(raw.get("redirect_uri") or REDIRECT_URI).strip()
    scope = str(raw.get("scope") or READ_ONLY_SCOPE).strip().lower()
    if not client_id or not client_secret:
        return None
    if redirect_uri != REDIRECT_URI:
        return None
    if scope != READ_ONLY_SCOPE:
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "scope": READ_ONLY_SCOPE,
    }


def _load_app_credentials():
    return _normalize_app_credentials(_load_json(APP_CONFIG_PATH))


def _save_app_credentials(app: dict) -> None:
    clean = _normalize_app_credentials(app)
    if clean is None:
        raise OAuthError("Open API application credentials are incomplete")
    _secure_write_json(APP_CONFIG_PATH, clean)


def _save_token_state(token: dict) -> None:
    now = int(time.time())
    expires_in = int(token.get("expiresIn") or 0)
    state = {
        "scope": READ_ONLY_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "target_environment": "Pepperstone - Europe LIVE",
        "access_token": token["accessToken"],
        "refresh_token": token.get("refreshToken"),
        "expires_at_unix": now + expires_in if expires_in > 0 else 0,
        "saved_at_unix": now,
        "authorization_source": "FRESH_BROWSER_AUTHORIZATION",
    }
    _secure_write_json(TOKEN_STATE_PATH, state)


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


def _setup_html():
    return """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM cTrader setup</title>
</head>
<body style="font-family:sans-serif;max-width:680px;margin:24px auto;padding:0 16px">
<h2>MXM cTrader Open API — first setup</h2>
<p>This page is local on <b>127.0.0.1</b>. Start from the Credentials page of your
approved cTrader Open API application.</p>
<p>Enter the <b>Open API Client ID</b> and <b>Open API Client Secret</b> below.
These are application credentials, not your cTID password. They are saved only on
this phone under a private MXM folder and are never included in the capture ZIP.</p>
<p>Registered redirect must be exactly:
<code>http://127.0.0.1:8765/callback</code></p>
<form method="post" action="/setup" autocomplete="off">
<label>Open API Client ID</label><br>
<input name="client_id" style="width:100%;padding:12px" required><br><br>
<label>Open API Client Secret</label><br>
<input name="client_secret" type="password" style="width:100%;padding:12px" required><br><br>
<button type="submit" style="padding:13px 18px">Save locally and continue to cTrader</button>
</form>
<p>Next, the official cTrader page opens. Sign in there, select the intended
<b>Pepperstone LIVE</b> account, keep view-only/account access, then Allow access.</p>
</body></html>"""


def _callback_html():
    return """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM authorization received</title>
</head>
<body style="font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px">
<h2>Authorization received.</h2>
<p>Pydroid is continuing automatically with the Pepperstone LIVE read-only capture.</p>
<p><a href="intent://#Intent;package=ru.iiec.pydroid3;end">Return to Pydroid</a></p>
<script>
setTimeout(function(){
  try { window.location.href = "intent://#Intent;package=ru.iiec.pydroid3;end"; }
  catch(e) { try { window.close(); } catch(_e) {} }
}, 350);
</script>
</body></html>"""


class BrowserOAuthHandler(BaseHTTPRequestHandler):
    server_version = "MXMM6CleanOAuth/1.0"

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
            "redirect_uri": REDIRECT_URI,
            "scope": READ_ONLY_SCOPE,
        })
        if app is None:
            self._send_html(
                "<html><body><h3>Client ID and Client Secret are required.</h3>"
                "<a href='/setup'>Try again</a></body></html>",
                400,
            )
            return

        # Save application credentials immediately, before leaving the local page.
        _save_app_credentials(app)
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


def _best_effort_return_to_pydroid() -> bool:
    try:
        subprocess.Popen(
            ["am", "start", "-n", "ru.iiec.pydroid3/ru.iiec.pydroid.MainActivity"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, ValueError):
        return False


def _fresh_browser_authorization(timeout_seconds=300):
    server = HTTPServer(("127.0.0.1", 8765), BrowserOAuthHandler)
    server.timeout = 1
    server.oauth_code = None
    server.oauth_error = None

    app = _load_app_credentials()
    server.app_credentials = app

    try:
        if app is None:
            print("[OAUTH] First clean setup: opening the browser now...")
            print("[OAUTH] Enter Open API Client ID/Secret on the LOCAL setup page.")
            _open_browser(LOCAL_SETUP_URI)
        else:
            print("[OAUTH] Local Open API application credentials found.")
            print("[OAUTH] Opening the official cTrader authorization page...")
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
                "OAuth callback timed out. Keep Pydroid running while authorizing and "
                "verify the registered redirect URI is exactly "
                "http://127.0.0.1:8765/callback"
            )

        app = server.app_credentials
        if app is None:
            raise OAuthError("Open API application credentials were not established")

        code = server.oauth_code
        try:
            token = _token_request({
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": app["client_id"],
                "client_secret": app["client_secret"],
            })
        finally:
            code = None
            server.oauth_code = None

        _save_token_state(token)
        _best_effort_return_to_pydroid()
        return app, str(token["accessToken"])
    finally:
        server.oauth_code = None
        server.server_close()


def ensure_v2_authorization():
    """Perform a fresh browser authorization on every run, using only clean local state."""
    app, access_token = _fresh_browser_authorization()
    return app, access_token, "FRESH_CLEAN_BROWSER_AUTHORIZATION"

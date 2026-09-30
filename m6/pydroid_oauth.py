"""Robust browser-first OAuth for the M6 read-only cTrader capture.

Android/Pydroid rules:
- local callback server owns 127.0.0.1:8765 for the entire OAuth exchange;
- no browser browser deep-link deep link is used;
- no Play Store routing is used;
- best-effort return to the already-installed Pydroid app uses Android's local activity
  manager only after the authorization code has been received and exchanged;
- if Android blocks foreground switching, the browser page tells the user to return via
  Recents and explicitly not to press RUN again.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ctrader_capture import (
    READ_ONLY_SCOPE,
    TOKEN_URL,
    OAuthError,
    atomic_write_json,
    build_authorization_url,
)

REDIRECT_URI = "http://127.0.0.1:8765/callback"
LOCAL_SETUP_URI = "http://127.0.0.1:8765/setup"

PRIVATE_ROOT = Path.home() / ".mxm_quant" / "m6_ctrader_capture_clean_v3"
APP_CONFIG_PATH = PRIVATE_ROOT / "app_credentials.json"
TOKEN_STATE_PATH = PRIVATE_ROOT / "oauth_state.json"
ACCOUNT_SELECTION_PATH = PRIVATE_ROOT / "account_selection.json"
TOKEN_REUSE_SAFETY_SECONDS = 300


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
    if redirect_uri != REDIRECT_URI or scope != READ_ONLY_SCOPE:
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


def _load_token_state():
    state = _load_json(TOKEN_STATE_PATH)
    if not isinstance(state, dict):
        return None
    if str(state.get("scope") or "").strip().lower() != READ_ONLY_SCOPE:
        return None
    access_token = str(state.get("access_token") or "").strip()
    refresh_token = str(state.get("refresh_token") or "").strip()
    if not access_token:
        return None
    return {
        "access_token": access_token,
        "refresh_token": refresh_token or None,
        "expires_at_unix": int(state.get("expires_at_unix") or 0),
        "scope": READ_ONLY_SCOPE,
        "redirect_uri": REDIRECT_URI,
    }


def load_saved_account_id():
    state = _load_json(ACCOUNT_SELECTION_PATH)
    if not isinstance(state, dict):
        return None
    try:
        account_id = int(state.get("ctid_trader_account_id"))
    except (TypeError, ValueError):
        return None
    if account_id <= 0:
        return None
    if str(state.get("environment") or "").upper() != "LIVE":
        return None
    return account_id


def save_saved_account_id(account_id: int) -> None:
    account_id = int(account_id)
    if account_id <= 0:
        raise OAuthError("invalid LIVE account id")
    _secure_write_json(ACCOUNT_SELECTION_PATH, {
        "schema": "mxm.greenfield.v2.local-ctrader-account-selection.v1",
        "environment": "LIVE",
        "broker": "Pepperstone",
        "ctid_trader_account_id": account_id,
        "saved_at_unix": int(time.time()),
        "transferable": False,
    })


def _save_token_state(token: dict) -> None:
    now = int(time.time())
    expires_in = int(token.get("expiresIn") or 0)
    _secure_write_json(TOKEN_STATE_PATH, {
        "scope": READ_ONLY_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "target_environment": "Pepperstone - Europe LIVE",
        "access_token": token["accessToken"],
        "refresh_token": token.get("refreshToken"),
        "expires_at_unix": now + expires_in if expires_in > 0 else 0,
        "saved_at_unix": now,
        "authorization_source": "FRESH_BROWSER_AUTHORIZATION",
    })


def _token_request(params: dict) -> dict:
    url = TOKEN_URL + "?" + urllib.parse.urlencode(params)
    method = "POST" if params.get("grant_type") == "refresh_token" else "GET"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MXM-M6-Pydroid-Capture/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise OAuthError(f"cTrader token endpoint HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise OAuthError("cTrader token endpoint transport failure") from None

    if status != 200:
        raise OAuthError(f"cTrader token endpoint HTTP {status}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OAuthError("cTrader token endpoint returned malformed JSON") from None
    if not isinstance(data, dict) or not data.get("accessToken"):
        detail = data.get("description") if isinstance(data, dict) else None
        raise OAuthError(
            f"cTrader token endpoint rejected authorization: {detail or 'no access token'}"
        )
    return data


def _setup_html():
    return """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM cTrader setup</title></head>
<body style="font-family:sans-serif;max-width:680px;margin:24px auto;padding:0 16px">
<h2>MXM cTrader Open API — first setup</h2>
<p>This page is local on <b>127.0.0.1</b>.</p>
<p>Enter your approved Open API application's <b>Client ID</b> and
<b>Client Secret</b>. They are saved only on this phone and never enter the capture ZIP.</p>
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
<b>Pepperstone LIVE</b> account, keep account/view access, then Allow access.</p>
<p><b>Important:</b> keep this Pydroid run alive while the browser is open.
Do not press RUN a second time.</p>
</body></html>"""


def _callback_html():
    return """<!doctype html><html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MXM authorization received</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px">
<h2>Authorization received.</h2>
<p>The local callback reached the running Pydroid script successfully.</p>
<p>The script is exchanging the authorization code and will continue automatically.</p>
<p><b>Return to Pydroid using Android Recents if it does not come to the foreground automatically.</b></p>
<p><b>Do not press RUN again.</b></p>
</body></html>"""


class OAuthHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class BrowserOAuthHandler(BaseHTTPRequestHandler):
    server_version = "MXMM6CleanOAuth/3.0"

    def _send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        try:
            self.wfile.flush()
        except OSError:
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/setup":
            self._send_html(_setup_html())
            return
        if parsed.path == "/callback":
            query = parse_qs(parsed.query, keep_blank_values=True)
            code = (query.get("code") or [None])[0]
            error = (query.get("error") or [None])[0]
            self.server.oauth_code = code
            self.server.oauth_error = error
            self._send_html(_callback_html())
            self.server.oauth_event.set()
            return
        if parsed.path == "/health":
            self._send_html("<html><body>MXM OAuth callback server: OK</body></html>")
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


PYDROID_PACKAGE = "ru.iiec.pydroid3"
PYDROID_MAIN_COMPONENT = "ru.iiec.pydroid3/ru.iiec.pydroid.MainActivity"


def _pydroid_foreground_commands() -> tuple[tuple[str, ...], ...]:
    """Safe local Android activity-manager paths; no browser/deep-link routing."""
    return (
        ("am", "start", "-n", PYDROID_MAIN_COMPONENT),
        (
            "am", "start",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            "-p", PYDROID_PACKAGE,
        ),
    )


def _best_effort_return_to_pydroid() -> bool:
    """Try the earlier proven explicit activity, then launcher; Recents remains fallback."""
    for command in _pydroid_foreground_commands():
        try:
            completed = subprocess.run(
                list(command),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            return True
    return False


def _start_callback_server(host="127.0.0.1", port=8765):
    server = OAuthHTTPServer((host, port), BrowserOAuthHandler)
    server.oauth_code = None
    server.oauth_error = None
    server.app_credentials = None
    server.oauth_event = threading.Event()
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.1},
        name="mxm-oauth-callback",
        daemon=True,
    )
    thread.start()
    return server, thread


def _stop_callback_server(server, thread):
    try:
        server.shutdown()
    finally:
        server.server_close()
        thread.join(timeout=3)


def _fresh_browser_authorization(timeout_seconds=300):
    try:
        server, thread = _start_callback_server()
    except OSError as exc:
        raise OAuthError(
            "OAuth callback server could not bind 127.0.0.1:8765. "
            "Close any older MXM/Pydroid run and RUN once."
        ) from exc

    app = _load_app_credentials()
    server.app_credentials = app

    try:
        if app is None:
            print("[OAUTH] First clean setup: opening the local browser form...")
            _open_browser(LOCAL_SETUP_URI)
        else:
            print("[OAUTH] Local Open API application credentials found.")
            print("[OAUTH] Opening official cTrader authorization...")
            _open_browser(
                build_authorization_url(
                    app["client_id"], REDIRECT_URI, scope=READ_ONLY_SCOPE
                )
            )

        if not server.oauth_event.wait(timeout_seconds):
            raise OAuthError(
                "OAuth callback timed out. Keep the original Pydroid RUN alive while "
                "authorizing and verify redirect URI is exactly "
                "http://127.0.0.1:8765/callback"
            )

        if server.oauth_error:
            raise OAuthError(f"cTrader authorization denied: {server.oauth_error}")
        if not server.oauth_code:
            raise OAuthError("OAuth callback arrived without an authorization code")

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

        if _best_effort_return_to_pydroid():
            print(
                "[OAUTH] Authorization received. Pydroid foreground return requested "
                "through Android's local activity manager."
            )
        else:
            print(
                "[OAUTH] Authorization received. Automatic foreground return was unavailable. "
                "Return to the SAME Pydroid run via Android Recents. Do NOT press RUN again."
            )

        # Keep localhost alive briefly after successful code exchange so Chrome cannot
        # immediately hit a closed callback socket while finishing navigation.
        time.sleep(2.0)
        return app, str(token["accessToken"])
    finally:
        server.oauth_code = None
        _stop_callback_server(server, thread)


def _reuse_or_refresh_authorization():
    app = _load_app_credentials()
    state = _load_token_state()
    if app is None or state is None:
        return None

    now = int(time.time())
    if state["expires_at_unix"] > now + TOKEN_REUSE_SAFETY_SECONDS:
        return app, state["access_token"], "REUSED_SAVED_ACCESS_TOKEN"

    refresh_token = state.get("refresh_token")
    if not refresh_token:
        return None

    try:
        token = _token_request({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": app["client_id"],
            "client_secret": app["client_secret"],
        })
    except OAuthError:
        return None

    _save_token_state(token)
    return app, str(token["accessToken"]), "REFRESHED_SAVED_ACCESS_TOKEN"


def _account_choice_html(candidates):
    rows = []
    for item in candidates:
        aid = int(item["ctidTraderAccountId"])
        title = str(item.get("brokerTitleShort") or "LIVE account")
        login = str(item.get("traderLogin") or "")
        label = f"{title} — LIVE"
        if login:
            label += f" — login {login}"
        rows.append(
            f'<label style="display:block;padding:12px 0">'
            f'<input type="radio" name="account_id" value="{aid}" required> '
            f'{label}</label>'
        )
    return f"""<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Select Pepperstone LIVE account</title></head>
<body style="font-family:sans-serif;max-width:680px;margin:24px auto;padding:0 16px">
<h2>Select the Pepperstone LIVE account</h2>
<p>This is a one-time local choice. Future runs reuse it automatically.</p>
<form method="post" action="/account">{''.join(rows)}
<button type="submit" style="padding:13px 18px">Use this LIVE account</button>
</form></body></html>"""


class AccountSelectionHandler(BaseHTTPRequestHandler):
    server_version = "MXMM6AccountSelect/1.0"

    def _send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path != "/account":
            self._send_html("<html><body>Not found</body></html>", 404)
            return
        self._send_html(_account_choice_html(self.server.candidates))

    def do_POST(self):
        if urlparse(self.path).path != "/account":
            self._send_html("<html><body>Not found</body></html>", 404)
            return
        try:
            length = min(max(int(self.headers.get("Content-Length", "0")), 0), 65536)
        except ValueError:
            length = 0
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        try:
            selected = int((form.get("account_id") or [""])[0])
        except ValueError:
            selected = 0
        allowed = {int(x["ctidTraderAccountId"]) for x in self.server.candidates}
        if selected not in allowed:
            self._send_html("<html><body>Invalid LIVE account selection.</body></html>", 400)
            return
        self.server.selected_account_id = selected
        self._send_html(
            "<html><body><h2>LIVE account saved.</h2>"
            "<p>Return to Pydroid. Future runs reuse this account automatically.</p>"
            "</body></html>"
        )
        self.server.selection_event.set()

    def log_message(self, fmt, *args):
        return


def choose_live_account_locally(candidates, timeout_seconds=180):
    cleaned = []
    seen = set()
    for account in candidates:
        aid = int(account.get("ctidTraderAccountId") or 0)
        if aid <= 0 or aid in seen:
            continue
        seen.add(aid)
        cleaned.append({
            "ctidTraderAccountId": aid,
            "brokerTitleShort": account.get("brokerTitleShort"),
            "traderLogin": account.get("traderLogin"),
            "isLive": True,
        })

    if len(cleaned) == 1:
        selected = cleaned[0]["ctidTraderAccountId"]
        save_saved_account_id(selected)
        return selected
    if not cleaned:
        raise OAuthError("no authorized LIVE accounts were returned by cTrader")

    server = OAuthHTTPServer(("127.0.0.1", 8765), AccountSelectionHandler)
    server.candidates = cleaned
    server.selected_account_id = None
    server.selection_event = threading.Event()
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.1},
        daemon=True,
        name="mxm-live-account-selector",
    )
    thread.start()
    try:
        print("[ACCOUNT] Multiple LIVE accounts are authorized; opening one-time selector.")
        _open_browser("http://127.0.0.1:8765/account")
        if not server.selection_event.wait(timeout_seconds):
            raise OAuthError("local LIVE account selection timed out")
        selected = int(server.selected_account_id)
        save_saved_account_id(selected)
        _best_effort_return_to_pydroid()
        return selected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def ensure_v2_authorization():
    remembered = _reuse_or_refresh_authorization()
    if remembered is not None:
        return remembered
    app, access_token = _fresh_browser_authorization()
    return app, access_token, "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION"


def force_fresh_v2_authorization():
    """Force one browser OAuth round without deleting the previous local token first."""
    app, access_token = _fresh_browser_authorization()
    return app, access_token, "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION_FORCED"

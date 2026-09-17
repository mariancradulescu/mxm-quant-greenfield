#!/usr/bin/env python3
"""One-button Android/Pydroid launcher for MXM PRIMARY_WAVE_02 cTrader capture."""
from __future__ import annotations

import getpass
import json
import os
import queue
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "m6_capture_local.json"
TOKEN_PATH = ROOT / ".m6_secrets" / "token_cache.json"
PLAN_PATH = ROOT / "data" / "PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"

try:
    import requests
    from m6.ctrader_capture import (
        READ_ONLY_SCOPE,
        TOKEN_URL,
        OAuthError,
        atomic_write_json,
        build_authorization_url,
        is_loopback_redirect,
        parse_oauth_redirect,
        redact_text,
    )
except ImportError as exc:
    print("Missing packages. In Pydroid Pip install: ctrader-open-api==0.9.2 requests==2.32.3 service_identity>=24.1.0,<25")
    raise SystemExit(2) from exc


def _secure_write_json(path: Path, value):
    atomic_write_json(path, value)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_or_create_config():
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        print("\nFirst run: local cTrader Open API application configuration.")
        print("Use the Client ID / Client Secret / Redirect URI of your approved cTrader Open API app.")
        print("Do NOT enter your cTrader username/password here.")
        client_id = input("Open API Client ID: ").strip()
        client_secret = getpass.getpass("Open API Client Secret (hidden): ").strip()
        redirect_uri = input(
            "Redirect URI [http://127.0.0.1:8765/callback]: "
        ).strip() or "http://127.0.0.1:8765/callback"
        config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "ctid_trader_account_id": None,
            "symbol_overrides": {},
        }
        _secure_write_json(CONFIG_PATH, config)
        print(f"Saved locally only: {CONFIG_PATH.name}")
    for key in ("client_id", "client_secret", "redirect_uri"):
        if not config.get(key):
            raise SystemExit(f"Local config is missing {key}. Delete {CONFIG_PATH.name} and RUN again.")
    return config


def _token_request(params):
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
        raise OAuthError("cTrader token endpoint did not return an access token")
    return data


def _try_refresh(config):
    if not TOKEN_PATH.exists():
        return None
    try:
        cached = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        refresh = cached.get("refreshToken")
        if not refresh:
            return None
        return _token_request({
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
        })
    except Exception:
        return None


def _loopback_authorization(config, auth_url):
    parsed = urlparse(config["redirect_uri"])
    returned = queue.Queue(maxsize=1)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] != parsed.path:
                self.send_response(404)
                self.end_headers()
                return
            full = f"{parsed.scheme}://{parsed.netloc}{self.path}"
            if returned.empty():
                returned.put(full)
            body = (
                "<html><body><h2>MXM cTrader authorization received.</h2>"
                "<p>You may return to Pydroid. The capture continues automatically.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = HTTPServer((parsed.hostname, parsed.port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        print("\nOpening the official cTrader authorization page...")
        print("In the browser: log in to cTrader there, verify VIEW/ACCOUNTS access, then tap Allow access.")
        webbrowser.open(auth_url, new=2)
        callback_url = returned.get(timeout=180)
        return parse_oauth_redirect(callback_url, config["redirect_uri"])
    finally:
        server.shutdown()
        server.server_close()


def _authorize(config):
    auth_url = build_authorization_url(
        config["client_id"], config["redirect_uri"], scope=READ_ONLY_SCOPE
    )
    if is_loopback_redirect(config["redirect_uri"]):
        code = _loopback_authorization(config, auth_url)
    else:
        print("\nOpening official cTrader authorization page...")
        webbrowser.open(auth_url, new=2)
        print("Your registered redirect URI is not a local loopback callback.")
        print("After cTrader redirects, paste the FULL final redirect URL here. The code is not stored.")
        callback_url = getpass.getpass("Final redirect URL (hidden): ").strip()
        code = parse_oauth_redirect(callback_url, config["redirect_uri"])
    try:
        return _token_request({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
        })
    finally:
        code = None


def _access_token(config):
    token = _try_refresh(config)
    if token is None:
        token = _authorize(config)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _secure_write_json(TOKEN_PATH, token)
    return token["accessToken"]


def main():
    print("MXM Quant Greenfield V2 — M6 read-only cTrader DEVELOPMENT capture")
    print("Contract: scope=accounts | LIVE orders=NO | account mutation=NO | economics=NO")
    config = _load_or_create_config()
    if not PLAN_PATH.is_file():
        raise SystemExit(f"Missing frozen plan: {PLAN_PATH}")
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    try:
        access_token = _access_token(config)
    except Exception as exc:
        print("OAuth BLOCKED safely:", redact_text(str(exc)))
        raise SystemExit(1) from None

    try:
        from m6.ctrader_openapi import OpenApiCaptureRunner
    except ImportError as exc:
        print("cTrader SDK import failed. Reinstall the exact packages from docs/M6_PYDROID_CTRADER_CAPTURE.md")
        raise SystemExit(2) from exc

    runner = OpenApiCaptureRunner(
        plan=plan,
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        access_token=access_token,
        config=config,
        repo_root=ROOT,
    )
    try:
        zip_path = runner.run()
    except Exception as exc:
        print("\nCapture BLOCKED safely:", redact_text(str(exc)))
        print("No order was placed. No M6 economics were run.")
        print("If a partial ZIP exists in capture_output, return it for diagnosis.")
        raise SystemExit(1) from None
    finally:
        access_token = None

    print("\nCAPTURE COMPLETE.")
    print("Return this ZIP to ChatGPT:")
    print(zip_path)
    print("Do not send m6_capture_local.json or anything under .m6_secrets/.")


if __name__ == "__main__":
    main()

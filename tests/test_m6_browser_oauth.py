import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import m6.pydroid_oauth as oauth
from m6.ctrader_capture import PYDROID_PACKAGE_FILES


class M6BrowserOAuthTests(unittest.TestCase):
    def test_01_clean_private_state_has_no_legacy_import(self):
        source = Path(oauth.__file__).read_text(encoding="utf-8")
        self.assertIn("m6_ctrader_capture_clean_v3", source)
        self.assertNotIn("a118_c02_openapi_v1", source)
        self.assertNotIn("LEGACY_APP_STATE_PATH", source)
        self.assertNotIn("SCOPE_VIEW", source)

    def test_02_app_credentials_round_trip_only_clean_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "app_credentials.json"
            with patch.object(oauth, "APP_CONFIG_PATH", path):
                oauth._save_app_credentials({
                    "client_id": "APP",
                    "client_secret": "SECRET",
                    "redirect_uri": oauth.REDIRECT_URI,
                    "scope": "accounts",
                    "access_token": "MUST_NOT_SAVE",
                    "refresh_token": "MUST_NOT_SAVE",
                })
                stored = json.loads(path.read_text(encoding="utf-8"))
                loaded = oauth._load_app_credentials()
        self.assertEqual(loaded["client_id"], "APP")
        self.assertEqual(loaded["client_secret"], "SECRET")
        self.assertEqual(stored["scope"], "accounts")
        self.assertNotIn("access_token", stored)
        self.assertNotIn("refresh_token", stored)

    def test_03_valid_saved_access_token_skips_browser(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_path = root / "app.json"
            token_path = root / "token.json"
            with patch.object(oauth, "APP_CONFIG_PATH", app_path), patch.object(
                oauth, "TOKEN_STATE_PATH", token_path
            ):
                oauth._save_app_credentials({
                    "client_id": "APP",
                    "client_secret": "SECRET",
                    "redirect_uri": oauth.REDIRECT_URI,
                    "scope": "accounts",
                })
                oauth._secure_write_json(token_path, {
                    "scope": "accounts",
                    "redirect_uri": oauth.REDIRECT_URI,
                    "access_token": "ACCESS",
                    "refresh_token": "REFRESH",
                    "expires_at_unix": int(time.time()) + 3600,
                })
                with patch.object(oauth, "_fresh_browser_authorization") as fresh:
                    app, token, mode = oauth.ensure_v2_authorization()
        fresh.assert_not_called()
        self.assertEqual(app["client_id"], "APP")
        self.assertEqual(token, "ACCESS")
        self.assertEqual(mode, "REUSED_SAVED_ACCESS_TOKEN")

    def test_04_expired_saved_token_refreshes_without_browser(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_path = root / "app.json"
            token_path = root / "token.json"
            with patch.object(oauth, "APP_CONFIG_PATH", app_path), patch.object(
                oauth, "TOKEN_STATE_PATH", token_path
            ):
                oauth._save_app_credentials({
                    "client_id": "APP",
                    "client_secret": "SECRET",
                    "redirect_uri": oauth.REDIRECT_URI,
                    "scope": "accounts",
                })
                oauth._secure_write_json(token_path, {
                    "scope": "accounts",
                    "redirect_uri": oauth.REDIRECT_URI,
                    "access_token": "OLD",
                    "refresh_token": "REFRESH",
                    "expires_at_unix": int(time.time()) - 1,
                })
                with patch.object(
                    oauth,
                    "_token_request",
                    return_value={
                        "accessToken": "NEW_ACCESS",
                        "refreshToken": "NEW_REFRESH",
                        "expiresIn": 3600,
                    },
                ) as refresh, patch.object(
                    oauth, "_fresh_browser_authorization"
                ) as fresh:
                    app, token, mode = oauth.ensure_v2_authorization()
                    saved = json.loads(token_path.read_text(encoding="utf-8"))
        fresh.assert_not_called()
        params = refresh.call_args.args[0]
        self.assertEqual(params["grant_type"], "refresh_token")
        self.assertEqual(params["refresh_token"], "REFRESH")
        self.assertEqual(token, "NEW_ACCESS")
        self.assertEqual(saved["refresh_token"], "NEW_REFRESH")
        self.assertEqual(mode, "REFRESHED_SAVED_ACCESS_TOKEN")

    def test_05_missing_or_unrefreshable_state_falls_back_to_browser(self):
        fresh_value = (
            {"client_id": "APP", "client_secret": "SECRET", "scope": "accounts"},
            "ACCESS",
        )
        with patch.object(oauth, "_reuse_or_refresh_authorization", return_value=None), patch.object(
            oauth, "_fresh_browser_authorization", return_value=fresh_value
        ) as fresh:
            app, token, mode = oauth.ensure_v2_authorization()
        fresh.assert_called_once()
        self.assertEqual(token, "ACCESS")
        self.assertEqual(mode, "FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION")

    def test_06_account_selection_persists_locally(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_selection.json"
            with patch.object(oauth, "ACCOUNT_SELECTION_PATH", path):
                oauth.save_saved_account_id(12345)
                self.assertEqual(oauth.load_saved_account_id(), 12345)
                stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["environment"], "LIVE")
        self.assertEqual(stored["broker"], "Pepperstone")
        self.assertFalse(stored["transferable"])

    def test_07_single_live_candidate_is_selected_without_browser(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_selection.json"
            candidates = [{
                "ctidTraderAccountId": 7,
                "isLive": True,
                "brokerTitleShort": "Pepperstone - Europe",
                "traderLogin": 99,
            }]
            with patch.object(oauth, "ACCOUNT_SELECTION_PATH", path), patch.object(
                oauth, "_open_browser"
            ) as browser:
                selected = oauth.choose_live_account_locally(candidates)
        browser.assert_not_called()
        self.assertEqual(selected, 7)

    def test_08_browser_flow_accounts_only_and_no_terminal_credentials(self):
        root = Path(__file__).resolve().parents[1]
        entry = (root / "M6_CAPTURE_RUN.py").read_text(encoding="utf-8")
        launcher = (root / "m6/pydroid_launcher.py").read_text(encoding="utf-8")
        module = (root / "m6/pydroid_oauth.py").read_text(encoding="utf-8")
        self.assertNotIn("input(", entry)
        self.assertNotIn("getpass", entry)
        self.assertNotIn("m6_capture_local.json", launcher)
        self.assertIn("READ_ONLY_SCOPE", module)
        self.assertNotIn('scope="trading"', module)
        self.assertNotIn("import requests", module)
        self.assertIn("urllib.request", module)
        self.assertNotIn("intent://", module)
        self.assertNotIn("play.google.com", module)

    def test_09_callback_server_receives_code_and_remains_alive_until_shutdown(self):
        import urllib.request

        server, thread = oauth._start_callback_server(host="127.0.0.1", port=0)
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/callback?code=TEST_CODE", timeout=2
            ) as response:
                body = response.read().decode("utf-8")
            self.assertIn("Authorization received", body)
            self.assertTrue(server.oauth_event.wait(1))
            self.assertEqual(server.oauth_code, "TEST_CODE")
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=2
            ) as response:
                self.assertIn("callback server: OK", response.read().decode("utf-8"))
        finally:
            oauth._stop_callback_server(server, thread)

    def test_10_deployment_package_contains_active_oauth_modules(self):
        self.assertIn("m6/pydroid_oauth.py", PYDROID_PACKAGE_FILES)
        self.assertIn("m6/pydroid_launcher.py", PYDROID_PACKAGE_FILES)
        self.assertNotIn("M6_CAPTURE_RUN_BASE.py", PYDROID_PACKAGE_FILES)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import m6.pydroid_oauth as oauth
from m6.ctrader_capture import PYDROID_PACKAGE_FILES


class M6BrowserOAuthTests(unittest.TestCase):
    def test_01_legacy_state_contributes_app_credentials_only(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = Path(td) / "legacy.json"
            legacy.write_text(json.dumps({
                "client_id": "APP",
                "client_secret": "SECRET",
                "scope": "accounts",
                "access_token": "OLD_ACCESS",
                "refresh_token": "OLD_REFRESH",
                "ctidTraderAccountId": 123,
            }), encoding="utf-8")
            missing = Path(td) / "missing.json"
            with patch.object(oauth, "LEGACY_APP_STATE_PATH", legacy), patch.object(
                oauth, "PRIVATE_STATE_PATH", missing
            ):
                app, source = oauth._app_credentials_for_fresh_auth()
            self.assertEqual(source, "LEGACY_APP_CREDENTIALS_ONLY")
            self.assertEqual(app["client_id"], "APP")
            self.assertEqual(app["client_secret"], "SECRET")
            self.assertEqual(app["scope"], "accounts")
            self.assertNotIn("access_token", app)
            self.assertNotIn("refresh_token", app)
            self.assertNotIn("ctidTraderAccountId", app)

    def test_02_valid_v2_token_is_remembered_without_refresh(self):
        now = int(time.time())
        state = {
            "client_id": "APP",
            "client_secret": "SECRET",
            "scope": "accounts",
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "expires_at_unix": now + 3600,
        }
        with patch.object(oauth, "_v2_state", return_value=state), patch.object(
            oauth, "_refresh_v2_state"
        ) as refresh:
            app, token = oauth._remembered_v2_authorization()
        refresh.assert_not_called()
        self.assertEqual(token, "ACCESS")
        self.assertEqual(app["scope"], "accounts")

    def test_03_expired_v2_token_refreshes(self):
        now = int(time.time())
        old = {
            "client_id": "APP",
            "client_secret": "SECRET",
            "scope": "accounts",
            "access_token": "OLD",
            "refresh_token": "REFRESH",
            "expires_at_unix": now - 1,
        }
        new = {
            "client_id": "APP",
            "client_secret": "SECRET",
            "scope": "accounts",
            "access_token": "NEW",
            "refresh_token": "NEW_REFRESH",
            "expires_at_unix": now + 3600,
        }
        with patch.object(oauth, "_v2_state", return_value=old), patch.object(
            oauth, "_refresh_v2_state", return_value=new
        ):
            app, token = oauth._remembered_v2_authorization()
        self.assertEqual(token, "NEW")
        self.assertEqual(app["client_id"], "APP")

    def test_04_remembered_authorization_skips_fresh_browser(self):
        remembered = (
            {"client_id": "APP", "client_secret": "SECRET", "scope": "accounts"},
            "ACCESS",
        )
        with patch.object(
            oauth, "_remembered_v2_authorization", return_value=remembered
        ), patch.object(oauth, "_fresh_browser_authorization") as fresh:
            app, token, mode = oauth.ensure_v2_authorization()
        fresh.assert_not_called()
        self.assertEqual(token, "ACCESS")
        self.assertEqual(mode, "REMEMBERED_V2_AUTHORIZATION")

    def test_05_first_v2_run_forces_fresh_browser_grant(self):
        fresh_value = (
            {"client_id": "APP", "client_secret": "SECRET", "scope": "accounts"},
            "ACCESS",
        )
        with patch.object(
            oauth, "_remembered_v2_authorization", return_value=None
        ), patch.object(
            oauth, "_fresh_browser_authorization", return_value=fresh_value
        ) as fresh:
            app, token, mode = oauth.ensure_v2_authorization()
        fresh.assert_called_once()
        self.assertEqual(mode, "FRESH_BROWSER_AUTHORIZATION")
        self.assertEqual(token, "ACCESS")

    def test_06_browser_flow_is_live_read_only_and_no_terminal_credentials(self):
        root = Path(__file__).resolve().parents[1]
        entry = (root / "M6_CAPTURE_RUN.py").read_text(encoding="utf-8")
        launcher = (root / "m6/pydroid_launcher.py").read_text(encoding="utf-8")
        module = (root / "m6/pydroid_oauth.py").read_text(encoding="utf-8")
        self.assertNotIn("input(", entry)
        self.assertNotIn("getpass", entry)
        self.assertNotIn("m6_capture_local.json", launcher)
        self.assertIn("Pepperstone LIVE", module)
        self.assertIn("READ_ONLY_SCOPE", module)
        self.assertNotIn('scope="trading"', module)
        self.assertNotIn("OLD_ACCESS", module)
        self.assertNotIn("OLD_REFRESH", module)

    def test_07_deployment_package_excludes_old_terminal_launcher(self):
        self.assertIn("m6/pydroid_oauth.py", PYDROID_PACKAGE_FILES)
        self.assertIn("m6/pydroid_launcher.py", PYDROID_PACKAGE_FILES)
        self.assertNotIn("M6_CAPTURE_RUN_BASE.py", PYDROID_PACKAGE_FILES)


if __name__ == "__main__":
    unittest.main(verbosity=2)

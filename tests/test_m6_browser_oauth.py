import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import m6.pydroid_oauth as oauth
from m6.ctrader_capture import PYDROID_PACKAGE_FILES


class M6BrowserOAuthTests(unittest.TestCase):
    def test_01_clean_state_uses_new_private_root_and_no_legacy_path(self):
        source = Path(oauth.__file__).read_text(encoding="utf-8")
        self.assertIn("m6_ctrader_capture_clean_v1", source)
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

    def test_03_setup_post_saves_app_credentials_before_ctrader_redirect(self):
        source = Path(oauth.__file__).read_text(encoding="utf-8")
        post = source[source.index("    def do_POST(self):"):source.index("    def log_message", source.index("    def do_POST(self):"))]
        self.assertLess(post.index("_save_app_credentials(app)"), post.index("build_authorization_url("))
        self.assertIn("303", post)
        self.assertIn("Location", post)

    def test_04_every_run_forces_fresh_clean_browser_authorization(self):
        fresh_value = (
            {"client_id": "APP", "client_secret": "SECRET", "scope": "accounts"},
            "ACCESS",
        )
        with patch.object(
            oauth, "_fresh_browser_authorization", return_value=fresh_value
        ) as fresh:
            app, token, mode = oauth.ensure_v2_authorization()
        fresh.assert_called_once()
        self.assertEqual(token, "ACCESS")
        self.assertEqual(mode, "FRESH_CLEAN_BROWSER_AUTHORIZATION")

    def test_05_browser_flow_is_accounts_only_and_no_terminal_credentials(self):
        root = Path(__file__).resolve().parents[1]
        entry = (root / "M6_CAPTURE_RUN.py").read_text(encoding="utf-8")
        launcher = (root / "m6/pydroid_launcher.py").read_text(encoding="utf-8")
        module = (root / "m6/pydroid_oauth.py").read_text(encoding="utf-8")
        self.assertNotIn("input(", entry)
        self.assertNotIn("getpass", entry)
        self.assertNotIn("m6_capture_local.json", launcher)
        self.assertIn("Pepperstone - Europe LIVE", module)
        self.assertIn("READ_ONLY_SCOPE", module)
        self.assertNotIn('scope="trading"', module)
        self.assertNotIn("legacy", module.lower())

    def test_06_deployment_package_contains_clean_oauth_and_excludes_old_terminal_launcher(self):
        self.assertIn("m6/pydroid_oauth.py", PYDROID_PACKAGE_FILES)
        self.assertIn("m6/pydroid_launcher.py", PYDROID_PACKAGE_FILES)
        self.assertNotIn("M6_CAPTURE_RUN_BASE.py", PYDROID_PACKAGE_FILES)

    def test_07_token_state_is_separate_from_app_secret(self):
        with tempfile.TemporaryDirectory() as td:
            token_path = Path(td) / "oauth_state.json"
            with patch.object(oauth, "TOKEN_STATE_PATH", token_path):
                oauth._save_token_state({
                    "accessToken": "ACCESS",
                    "refreshToken": "REFRESH",
                    "expiresIn": 3600,
                })
                stored = json.loads(token_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["access_token"], "ACCESS")
        self.assertEqual(stored["refresh_token"], "REFRESH")
        self.assertNotIn("client_secret", stored)
        self.assertEqual(stored["scope"], "accounts")


if __name__ == "__main__":
    unittest.main(verbosity=2)

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENTRY_PATH = ROOT / "M6_CAPTURE_RUN.py"

_spec = importlib.util.spec_from_file_location("m6_capture_bootstrap_entry", ENTRY_PATH)
entry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entry)


class M6PydroidBootstrapTests(unittest.TestCase):
    def test_01_entry_defers_m6_runtime_import_until_after_bootstrap(self):
        source = ENTRY_PATH.read_text(encoding="utf-8")
        main = source[source.index("def main()") :]
        self.assertLess(
            main.index("_ensure_runtime_dependencies()"),
            main.index("from m6.pydroid_launcher import main as launcher_main"),
        )

    def test_02_missing_sdk_triggers_same_interpreter_pip_install(self):
        not_ready = {
            "ready": False,
            "packages": {
                "ctrader-open-api": None,
                "requests": "2.32.3",
                "service-identity": "24.2.0",
            },
            "problems": ["ctrader-open-api: installed=missing required=0.9.2"],
        }
        ready = {
            "ready": True,
            "packages": {
                "ctrader-open-api": "0.9.2",
                "requests": "2.32.3",
                "service-identity": "24.2.0",
            },
            "problems": [],
        }
        with tempfile.TemporaryDirectory() as td:
            req = Path(td) / "requirements.txt"
            req.write_text("ctrader-open-api==0.9.2\n", encoding="utf-8")
            with patch.object(entry, "REQUIREMENTS_PATH", req), patch.object(
                entry, "runtime_dependency_status", side_effect=[not_ready, ready]
            ), patch.object(
                entry.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["pip"], 0),
            ) as run:
                entry._ensure_runtime_dependencies()
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[0], entry.sys.executable)
        self.assertEqual(command[1:4], ["-m", "pip", "install"])
        self.assertIn("-r", command)

    def test_03_failed_auto_install_stops_before_runtime_import(self):
        not_ready = {
            "ready": False,
            "packages": {},
            "problems": ["ctrader-open-api missing"],
        }
        with tempfile.TemporaryDirectory() as td:
            req = Path(td) / "requirements.txt"
            req.write_text("ctrader-open-api==0.9.2\n", encoding="utf-8")
            with patch.object(entry, "REQUIREMENTS_PATH", req), patch.object(
                entry, "runtime_dependency_status", return_value=not_ready
            ), patch.object(
                entry.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["pip"], 1),
            ):
                with self.assertRaises(SystemExit):
                    entry._ensure_runtime_dependencies()

    def test_04_service_identity_range(self):
        self.assertTrue(entry._service_identity_compatible("24.1.0"))
        self.assertTrue(entry._service_identity_compatible("24.9.1"))
        self.assertFalse(entry._service_identity_compatible("23.9.0"))
        self.assertFalse(entry._service_identity_compatible("25.0.0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

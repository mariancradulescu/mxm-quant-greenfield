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

    def test_02_missing_protobuf_installs_binary_only_no_deps(self):
        not_ready = {
            "ready": False,
            "packages": {"protobuf": None},
            "problems": ["protobuf missing"],
            "rust_required": False,
            "cryptography_required": False,
        }
        ready = {
            "ready": True,
            "packages": {"protobuf": "3.20.1"},
            "problems": [],
            "rust_required": False,
            "cryptography_required": False,
        }
        with tempfile.TemporaryDirectory() as td:
            req = Path(td) / "requirements.txt"
            req.write_text("protobuf==3.20.1\n", encoding="utf-8")
            with patch.object(entry, "REQUIREMENTS_PATH", req), patch.object(
                entry, "runtime_dependency_status", side_effect=[not_ready, ready]
            ), patch.object(
                entry.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["pip"], 0),
            ) as run:
                entry._ensure_runtime_dependencies()
        command = run.call_args.args[0]
        self.assertEqual(command[0], entry.sys.executable)
        self.assertEqual(command[1:4], ["-m", "pip", "install"])
        self.assertIn("--only-binary=:all:", command)
        self.assertIn("--no-deps", command)
        self.assertIn("-r", command)

    def test_03_failed_wheel_install_stops_before_runtime_import(self):
        not_ready = {
            "ready": False,
            "packages": {"protobuf": None},
            "problems": ["protobuf missing"],
            "rust_required": False,
            "cryptography_required": False,
        }
        with tempfile.TemporaryDirectory() as td:
            req = Path(td) / "requirements.txt"
            req.write_text("protobuf==3.20.1\n", encoding="utf-8")
            with patch.object(entry, "REQUIREMENTS_PATH", req), patch.object(
                entry, "runtime_dependency_status", return_value=not_ready
            ), patch.object(
                entry.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["pip"], 1),
            ):
                with self.assertRaises(SystemExit):
                    entry._ensure_runtime_dependencies()

    def test_04_bootstrap_source_forbids_rust_crypto_stack(self):
        source = ENTRY_PATH.read_text(encoding="utf-8")
        self.assertIn('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python"', source)
        self.assertIn("--only-binary=:all:", source)
        self.assertIn("--no-deps", source)
        for forbidden in (
            "ctrader-open-api==",
            "Twisted==",
            "pyOpenSSL==",
            "service_identity>=",
            "cryptography==",
            "import twisted",
            "from twisted",
            "import OpenSSL",
            "from OpenSSL",
            "import cryptography",
            "from cryptography",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

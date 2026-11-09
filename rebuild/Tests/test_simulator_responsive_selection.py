"""Regression coverage for Xcode 27 CoreSimulator hung-service recovery.

No macOS hardware or simulator is used in these tests. Production capture
still requires real simctl boot/launchd/screenshot success before claiming PASS.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

FILE = Path(__file__).resolve().parents[1] / "scripts/boot_preview_simulator.py"
SPEC = importlib.util.spec_from_file_location("scarlet_simulator_selector", FILE)
SIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SIM)

MOCK_DEVICES = {
    "com.apple.CoreSimulator.SimRuntime.iOS-27-0": [
        {"udid": "old", "name": "iPhone 17", "state": "Shutdown",
         "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17",
         "isAvailable": True},
    ],
    "com.apple.CoreSimulator.SimRuntime.iOS-27-2": [
        {"udid": "booted", "name": "iPhone 17", "state": "Booted",
         "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17",
         "isAvailable": True},
        {"udid": "new", "name": "iPhone 17 Pro", "state": "Shutdown",
         "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro",
         "isAvailable": True},
    ],
}


class ResponsiveSimulatorSelection(unittest.TestCase):
    def test_runtime_pairing_never_mixes_iphone_device_and_runtime(self):
        borrowed, disposable = SIM.candidates(MOCK_DEVICES)
        self.assertEqual(borrowed[0]["udid"], "booted")
        self.assertEqual(disposable[0]["udid"], "new")
        self.assertEqual(disposable[0]["runtime"].split(".")[-1], "iOS-27-2")

    def test_borrowed_simulator_must_pass_launchd_and_screenshot_probes(self):
        commands = []
        def fake_call(*args, **kwargs):
            commands.append(args)
            if args[:4] == ("xcrun", "simctl", "list", "devices"):
                return subprocess.CompletedProcess(args, 0,
                    stdout=json.dumps({"devices": MOCK_DEVICES}), stderr="")
            if len(args) > 4 and args[:3] == ("xcrun", "simctl", "io"):
                Path(args[-1]).write_bytes(b"PNG" * 1000)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with mock.patch.object(SIM, "call", side_effect=fake_call):
                self.assertTrue(SIM.select(td, td / "id", td / "owned"))
            self.assertEqual((td / "id").read_text().strip(), "booted")
            self.assertEqual((td / "owned").read_text().strip(), "0")
            self.assertEqual(json.loads((td / "simulator-selection.json").read_text())["status"], "ready")
            self.assertTrue(any(x[:3] == ("xcrun", "simctl", "spawn") for x in commands))
            self.assertTrue(any(x[:3] == ("xcrun", "simctl", "io") for x in commands))
            self.assertFalse(any("killall" in x for x in commands))

    def test_unresponsive_booted_device_falls_back_to_preconfigured_template(self):
        commands = []
        def fake_call(*args, **kwargs):
            commands.append(args)
            if args[:4] == ("xcrun", "simctl", "list", "devices"):
                return subprocess.CompletedProcess(args, 0,
                    stdout=json.dumps({"devices": MOCK_DEVICES}), stderr="")
            if args[:3] == ("xcrun", "simctl", "spawn") and args[3] == "booted":
                raise subprocess.TimeoutExpired(args, 18)
            if args[:3] == ("xcrun", "simctl", "create"):
                return subprocess.CompletedProcess(args, 0, stdout="disposable-id\n", stderr="")
            if args[:3] == ("xcrun", "simctl", "io"):
                Path(args[-1]).write_bytes(b"PNG" * 1000)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with mock.patch.object(SIM, "call", side_effect=fake_call):
                self.assertTrue(SIM.select(td, td / "id", td / "owned"))
            self.assertEqual((td / "id").read_text().strip(), "new")
            self.assertEqual((td / "owned").read_text().strip(), "2")
            report = json.loads((td / "simulator-selection.json").read_text())
            self.assertEqual(report["runtime"].split(".")[-1], "iOS-27-2")
            self.assertEqual(report["mode"], "preconfigured_booted_verified")
            self.assertTrue(any(x[:3] == ("xcrun", "simctl", "boot") for x in commands))
            self.assertFalse(any(x[:3] == ("xcrun", "simctl", "create") for x in commands))

    def test_hung_simulator_is_infrastructure_failure_not_fake_success(self):
        def fake_call(*args, **kwargs):
            if args[:4] == ("xcrun", "simctl", "list", "devices"):
                return subprocess.CompletedProcess(args, 0,
                    stdout=json.dumps({"devices": MOCK_DEVICES}), stderr="")
            raise subprocess.TimeoutExpired(args, 5)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with mock.patch.object(SIM, "call", side_effect=fake_call):
                self.assertFalse(SIM.select(td, td / "id", td / "owned"))
            self.assertFalse((td / "id").exists())
            self.assertEqual(
                json.loads((td / "simulator-selection.json").read_text())["status"],
                "infra_unavailable")
            self.assertFalse((td / "home.png").exists())

    def test_capture_script_only_deletes_an_owned_device(self):
        text = (FILE.parent / "capture_simulator_ui.sh").read_text()
        self.assertIn('mode="$(cat "$SIM_OWNED_FILE")"', text)
        self.assertIn('if [[ "$mode" == "0" ]]', text)
        self.assertIn('actions=("shutdown", "delete") if sys.argv[2]=="1" else ("shutdown",)', text)
        self.assertNotIn('killall', text)
        self.assertIn("boot_preview_simulator.py", text)
        self.assertIn('[[ -s "$OUT/$screen.png" ]]', text)


if __name__ == "__main__":
    unittest.main()

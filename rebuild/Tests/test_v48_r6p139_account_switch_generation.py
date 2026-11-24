"""Account-switch priority survives transient preflight and newer switch events."""
from pathlib import Path
import re
import importlib.util
import json
import plistlib
import zipfile
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUTO = (ROOT / "HostApp/ScarletAutomaticRenewal.swift").read_text()

class AccountSwitchGeneration(unittest.TestCase):
    def test_no_early_consumption_and_generation_fence(self):
        body = AUTO.split("private func refreshIfDue(origin:", 1)[1]
        start = body.index("running = true")
        dispatch = body.index("ScarletNativeRefreshExecutor.execute()")
        preflight = body[start:dispatch]
        self.assertNotIn("pendingVerifiedAccountSwitch = false", preflight)
        self.assertIn("let switchGeneration = accountSwitchRequest.generation", preflight)
        self.assertIn("guard accountSwitchRequest.generation == switchGeneration", preflight)
        self.assertLess(preflight.index("ScarletInstalledProfileReadback.beginRequest"),
                        preflight.index("accountSwitchRequest.consume(switchGeneration)", preflight.index("ScarletInstalledProfileReadback.beginRequest")))
        self.assertIn("accountSwitchRequest.restore(switchGeneration)", body[dispatch:])

    def test_transient_preflight_does_not_consume_priority(self):
        body = AUTO.split("private func refreshIfDue(origin:", 1)[1]
        for marker, end in [
            ("if case .unavailable(let reason) = authState", "guard authState.isAuthenticated"),
            ("guard !Task.isCancelled else", "let (paired, pairingReason)"),
            ('if nativeState.reason == "team_operation_in_progress"', "guard nativeState.canRefreshSelectedTeam"),
        ]:
            section = body.split(marker, 1)[1].split(end, 1)[0]
            self.assertNotIn("consume(", section)
        self.assertIn("if !transient {", body)
        self.assertIn("if origin == \"verified_account_switch\" { accountSwitchRequest.consume(switchGeneration) }", body)

    def test_cumulative_archive_rejects_missing_generation_fence(self):
        spec = importlib.util.spec_from_file_location(
            "gate139", ROOT / "integration/verify_integrated_release.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        sha = "d" * 40
        host = "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI"
        worker = "Frameworks/SideStoreApp.framework/SideStore"
        actions = {k: {} for k in ("RefreshAllIntent", "RefreshAllAppsWidgetIntent", "InstallIPAIntent")}
        actions["ScarletSelfUpdateIntent"] = {"fullyQualifiedTypeName": "LiveContainerSwiftUI.ScarletSelfUpdateIntent"}
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "candidate.ipa"
            for include in (False, True):
                with zipfile.ZipFile(ipa, "w") as z:
                    z.writestr(gate.PREFIX + "Info.plist", plistlib.dumps({
                        "CFBundleIdentifier": "com.kdt.livecontainer.P8EZT3U5N4",
                        "CFBundleShortVersionString": "3.8.11",
                        "CFBundleVersion": "3.8.139", "CFBundleExecutable": "LiveContainer"}))
                    for path, markers in gate.REQUIRED_MARKERS.items():
                        data = list(markers)
                        if path == host:
                            data.extend([("scarlet-source-commit:" + sha).encode(),
                                         b"ScarletSelfUpdateIntent", b"shortcut_update_installed_build_verified",
                                         b"classic_handoff_drained", b"classic_handoff_blocked",
                                         b"selected_team_partial_refresh_results", b"selected_team_refresh_result_mismatch",
                                         b"profile_readback_request_busy", b"Scarlet.Refresh.InstalledProfileReceipt.V138"])
                            if include:
                                data.append(b"automatic_deferred_account_generation_changed")
                        if path == worker:
                            data.extend([b"self_update_identity_unverified", b"Scarlet self-update signed identity or version mismatch",
                                         b"self_update_archive_unverified", b"Scarlet self-update archive digest mismatch",
                                         b"Scarlet self-update source topology mismatch", b"Scarlet self-update provisioning Team mismatch",
                                         b"SideSign.DeveloperPortalError", b"selected_team_partial_refresh_results",
                                         b"selected_team_refresh_result_mismatch"])
                        z.writestr(gate.PREFIX + path, b"\0".join(data))
                    for path in ("Metadata.appintents/extract.actionsdata",
                                 "Frameworks/LiveContainerSwiftUI.framework/Metadata.appintents/extract.actionsdata"):
                        z.writestr(gate.PREFIX + path, json.dumps({"actions": actions}))
                if include:
                    self.assertFalse(gate.verify(ipa, "3.8.139", sha)["deviceVerified"])
                else:
                    with self.assertRaisesRegex(ValueError, "R139"):
                        gate.verify(ipa, "3.8.139", sha)

    def test_build_identity_not_publicly_published(self):
        workflow = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()
        branch = "fix/scarlet-r6p139-switch-generation-20261124"
        self.assertIn(branch, next(x for x in workflow.splitlines() if x.startswith("    branches:")))
        self.assertIn("--host-build-version 3.8.139", workflow)
        self.assertNotIn(branch, workflow.split("  publish-unsigned-github-release:", 1)[1])

    def test_actual_swift_generation_state(self):
        swiftc = shutil.which("swiftc")
        if not swiftc:
            self.skipTest("Swift compiler unavailable")
        match = re.search(r"struct ScarletVerifiedAccountRefreshRequest: Sendable \{.*?\n\}", AUTO, re.S)
        self.assertIsNotNone(match)
        fixture = "import Foundation\n" + match.group(0) + """
var state = ScarletVerifiedAccountRefreshRequest()
precondition(!state.isPending)
state.enqueue()
let a = state.generation
precondition(state.isPending)
state.enqueue()
let b = state.generation
precondition(a != b && state.isPending)
state.consume(a)
precondition(state.isPending)
state.restore(a)
precondition(state.generation == b && state.isPending)
state.consume(b)
precondition(!state.isPending)
state.restore(b)
precondition(state.isPending)
state.consume(b)
state.enqueue()
let c = state.generation
state.restore(b)
precondition(c != b && state.generation == c && state.isPending)
print("R139_SWITCH_GENERATION_PASS")
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "main.swift"
            src.write_text(fixture)
            exe = Path(tmp) / "test"
            p = subprocess.run([swiftc, "-swift-version", "6", "-strict-concurrency=complete", "-warnings-as-errors", str(src), "-o", str(exe)], capture_output=True, text=True, timeout=90)
            self.assertEqual(p.returncode, 0, p.stderr)
            p = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("R139_SWITCH_GENERATION_PASS", p.stdout)

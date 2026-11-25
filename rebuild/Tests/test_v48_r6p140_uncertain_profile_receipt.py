"""R140: preserve readback evidence when native failure does not rule out install."""
import re
import importlib.util
import json
import plistlib
import zipfile
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]
A = (R / "HostApp/ScarletAutomaticRenewal.swift").read_text()
P = (R / "HostApp/ScarletSigningReadinessPanel.swift").read_text()

class UncertainProfileReceipt(unittest.TestCase):
    def test_all_three_callers_use_stage_aware_resolution(self):
        for source, body in (("automatic", A), ("manual", P), ("selected_p12_rotation", P)):
            start = body.index(f'beginRequest(source: "{source}")')
            catch = body.split("ScarletNativeRefreshExecutor.execute(", 1)[1] if source == "automatic" else body[start:].split("ScarletNativeRefreshExecutor.execute(", 1)[1]
            catch = catch.split("} catch {", 1)[1].split("recordError", 1)[0]
            self.assertIn("ScarletInstalledProfileReadback.resolveFailedRequest(", catch, source)
            self.assertIn("nativeEvidence?.stage", catch, source)
            self.assertNotIn("ScarletInstalledProfileReadback.discardFailedRequest()", catch, source)

    def test_definite_rejection_vs_possible_mutation(self):
        body = A.split("static func resolveFailedRequest(", 1)[1].split("static func finishRequest", 1)[0]
        for reason in ("worker_unresponsive", "selected_team_partial_refresh_results",
                       "host_not_in_refresh_results", "native_host_reinstall_owner_unverified"):
            self.assertIn(f'"{reason}"', body)
        self.assertIn('stage == "refresh"', body)
        self.assertIn("discardFailedRequest()", body)
        self.assertIn('"installation_verified": "false"', body)
        self.assertIn("profile_readback_retained_uncertain_native_failure", body)

    def test_cumulative_archive_rejects_missing_uncertain_receipt(self):
        spec = importlib.util.spec_from_file_location(
            "gate139", R / "integration/verify_integrated_release.py")
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
                        "CFBundleVersion": "3.8.140", "CFBundleExecutable": "LiveContainer"}))
                    for path, markers in gate.REQUIRED_MARKERS.items():
                        data = list(markers)
                        if path == host:
                            data.extend([("scarlet-source-commit:" + sha).encode(),
                                         b"ScarletSelfUpdateIntent", b"shortcut_update_installed_build_verified",
                                         b"classic_handoff_drained", b"classic_handoff_blocked",
                                         b"selected_team_partial_refresh_results", b"selected_team_refresh_result_mismatch",
                                         b"profile_readback_request_busy", b"Scarlet.Refresh.InstalledProfileReceipt.V138", b"automatic_deferred_account_generation_changed"])
                            if include:
                                data.append(b"profile_readback_retained_uncertain_native_failure")
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
                    self.assertFalse(gate.verify(ipa, "3.8.140", sha)["deviceVerified"])
                else:
                    with self.assertRaisesRegex(ValueError, "R140"):
                        gate.verify(ipa, "3.8.140", sha)

    def test_actual_swift_receipt_resolution(self):
        swiftc = shutil.which("swiftc")
        if not swiftc:
            self.skipTest("Swift compiler unavailable on NAS")
        body = "enum ScarletInstalledProfileReadback {" + A.split("enum ScarletInstalledProfileReadback {", 1)[1]
        body = re.sub(r"    private static func installedDigest\(\) -> String\? \{.*?\n    \}",
                      '    static var fixtureDigest: String? = "new"\n    private static func installedDigest() -> String? { fixtureDigest }',
                      body, count=1, flags=re.S)
        fixture = """
import Foundation
@MainActor final class ScarletDiagnosticRecorder {
    static let shared = ScarletDiagnosticRecorder()
    var events: [String] = []
    func record(_ a: String, _ b: String, status: String = "info", fields: [String: String] = [:]) {
        if b == "profile_readback_retained_uncertain_native_failure" {
            precondition(fields["installation_verified"] == "false")
            events.append(b)
        }
    }
}
""" + "@MainActor\n" + body + """
let prefs = UserDefaults.standard
let key = "Scarlet.Refresh.InstalledProfileReceipt.V138"
let digest = "Scarlet.Refresh.PreviousInstalledProfileSHA.V37"
let owner = "Scarlet.Refresh.ProfileRequestProcess.V37"
let source = "Scarlet.Refresh.ProfileRequestSource.V37"
let date = "Scarlet.Refresh.ProfileRequestDate.V37"
let prior: [String: Any] = [digest: "old", owner: "prior", source: "manual", date: Date(timeIntervalSince1970: 100)]
defer { prefs.removeObject(forKey: key) }
@MainActor func run(_ reason: String, _ stage: String?, _ retain: Bool) {
    prefs.set(prior, forKey: key)
    precondition(ScarletInstalledProfileReadback.beginRequest(source: "automatic"))
    ScarletInstalledProfileReadback.resolveFailedRequest(reason: reason, stage: stage)
    precondition(!ScarletInstalledProfileReadback.beginRequest(source: "manual"))
    ScarletInstalledProfileReadback.finishRequest()
    let current = prefs.dictionary(forKey: key)!
    precondition(current[digest] as? String == (retain ? "new" : "old"))
    precondition(current[source] as? String == (retain ? "automatic" : "manual"))
    if !retain { precondition(current[owner] as? String == "prior") }
}
run("team_operation_in_progress", nil, false)
run("host_selected_team_mismatch", nil, false)
run("transport_unavailable", "transport", false)
run("signing_failed", "team", false)
run("installation_failed", "refresh", true)
run("selected_team_partial_refresh_results", nil, true)
run("host_not_in_refresh_results", nil, true)
run("native_host_reinstall_owner_unverified", nil, true)
run("worker_unresponsive", nil, true)
run("selected_team_refresh_result_mismatch", nil, true)
run("sidestore_native_operation_failed", nil, true)
run("sidestore_native_operation_failed", "team", false)
precondition(ScarletDiagnosticRecorder.shared.events.count == 7)
prefs.removeObject(forKey: key)
ScarletInstalledProfileReadback.fixtureDigest = nil
precondition(ScarletInstalledProfileReadback.beginRequest(source: "manual"))
ScarletInstalledProfileReadback.resolveFailedRequest(reason: "worker_unresponsive", stage: nil)
ScarletInstalledProfileReadback.finishRequest()
precondition(ScarletDiagnosticRecorder.shared.events.count == 7)
precondition(prefs.object(forKey: key) == nil)
print("R140_PROFILE_UNCERTAIN_PASS")
"""
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "main.swift"
            f.write_text(fixture)
            exe = Path(tmp) / "test"
            p = subprocess.run([swiftc, "-swift-version", "6", "-strict-concurrency=complete", "-warnings-as-errors", str(f), "-o", str(exe)], capture_output=True, text=True, timeout=90)
            self.assertEqual(p.returncode, 0, p.stderr)
            p = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("R140_PROFILE_UNCERTAIN_PASS", p.stdout)

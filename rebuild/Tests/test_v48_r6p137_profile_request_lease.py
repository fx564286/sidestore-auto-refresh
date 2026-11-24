"""R137: host-wide refresh readback lease and rollback semantics."""
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

class ProfileRequestLease(unittest.TestCase):
    def test_every_native_request_acquires_and_releases_the_same_lease(self):
        for source, body in (
            ("automatic", A), ("manual", P), ("selected_p12_rotation", P)
        ):
            with self.subTest(source=source):
                start = body.index(f'ScarletInstalledProfileReadback.beginRequest(source: "{source}")')
                self.assertIn("guard ", body[start-12:start])
                dispatch = body.index("ScarletNativeRefreshExecutor.execute(", start)
                self.assertIn("defer { ScarletInstalledProfileReadback.finishRequest() }", body[start:dispatch])
                self.assertIn("ScarletInstalledProfileReadback.discardFailedRequest()", body[dispatch:])
        self.assertLess(A.index('guard ScarletInstalledProfileReadback.beginRequest(source: "automatic")'),
                        A.index("prefs.set(Date(), forKey: attemptKey)"))

    def test_transaction_preserves_previous_receipt_and_refuses_overlap(self):
        body = A.split("enum ScarletInstalledProfileReadback {", 1)[1]
        begin = body.split("static func beginRequest", 1)[1].split("static func discardFailedRequest", 1)[0]
        self.assertIn("guard previousRequest == nil else { return false }", begin)
        self.assertLess(begin.index("previousRequest ="), begin.index("storeReceipt(Receipt("))
        rollback = body.split("static func discardFailedRequest", 1)[1].split("static func finishRequest", 1)[0]
        self.assertIn("guard let previousRequest else { return }", rollback)
        self.assertIn("storeReceipt(previousRequest.previousReceipt", rollback)
        self.assertIn("previousRequest = nil", body.split("static func finishRequest",1)[1])
        self.assertIn("guard previousRequest == nil else { return }", body.split("static func verifyNewProcess",1)[1])

    def test_rotation_busy_does_not_report_started(self):
        start = P.index('guard ScarletInstalledProfileReadback.beginRequest(source: "selected_p12_rotation")')
        self.assertGreater(P.index('"selected_p12_host_resign_started"', start), start)

    def test_archive_requires_r137_marker_and_no_new_public_release(self):
        spec = importlib.util.spec_from_file_location("gate137", R / "integration/verify_integrated_release.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        sha = "c" * 40
        host = "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI"
        worker = "Frameworks/SideStoreApp.framework/SideStore"
        branch = "fix/scarlet-r6p137-profile-lease-20261124"
        workflow = (R.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()
        self.assertIn(branch, next(line for line in workflow.splitlines() if line.startswith("    branches:")))
        self.assertIn("--host-build-version 3.8.137", workflow)
        self.assertNotIn(branch, workflow.split("  publish-unsigned-github-release:", 1)[1])
        actions = {k: {} for k in ("RefreshAllIntent", "RefreshAllAppsWidgetIntent", "InstallIPAIntent")}
        actions["ScarletSelfUpdateIntent"] = {"fullyQualifiedTypeName": "LiveContainerSwiftUI.ScarletSelfUpdateIntent"}
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "test.ipa"
            for include in (False, True):
                with zipfile.ZipFile(ipa, "w") as z:
                    z.writestr(gate.PREFIX + "Info.plist", plistlib.dumps({
                        "CFBundleIdentifier": "com.kdt.livecontainer.P8EZT3U5N4",
                        "CFBundleShortVersionString": "3.8.11",
                        "CFBundleVersion": "3.8.137", "CFBundleExecutable": "LiveContainer"}))
                    for path, markers in gate.REQUIRED_MARKERS.items():
                        data = list(markers)
                        if path == host:
                            data.extend([("scarlet-source-commit:" + sha).encode(), b"ScarletSelfUpdateIntent",
                                         b"shortcut_update_installed_build_verified", b"classic_handoff_drained",
                                         b"classic_handoff_blocked", b"selected_team_partial_refresh_results",
                                         b"selected_team_refresh_result_mismatch"])
                            if include:
                                data.append(b"profile_readback_request_busy")
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
                    self.assertEqual(gate.verify(ipa, "3.8.137", sha)["version"], "3.8.137")
                else:
                    with self.assertRaisesRegex(ValueError, "R137"):
                        gate.verify(ipa, "3.8.137", sha)

    def test_actual_swift_transaction(self):
        swift = shutil.which("swift")
        if not swift:
            self.skipTest("Swift unavailable on this host; Xcode CI required")
        body = "enum ScarletInstalledProfileReadback {" + A.split("enum ScarletInstalledProfileReadback {",1)[1]
        # Replace only the platform-specific profile reader. All lease,
        # persistence, rollback and verify code is the production implementation.
        body = re.sub(r"    private static func installedDigest\(\) -> String\? \{.*?\n    \}",
                      "    static var fixtureDigest: String? = \"new\"\n    private static func installedDigest() -> String? { fixtureDigest }",
                      body, count=1, flags=re.S)
        fixture = """
import Foundation
@MainActor final class ScarletDiagnosticRecorder {
    static let shared = ScarletDiagnosticRecorder()
    func record(_ a: String, _ b: String, status: String = "info", fields: [String: String] = [:]) {}
}
""" + "@MainActor\n" + body + """
let prefs = UserDefaults.standard
let before = "Scarlet.Refresh.PreviousInstalledProfileSHA.V37"
let owner = "Scarlet.Refresh.ProfileRequestProcess.V37"
let source = "Scarlet.Refresh.ProfileRequestSource.V37"
let date = "Scarlet.Refresh.ProfileRequestDate.V37"
let record = "Scarlet.Refresh.InstalledProfileReceipt.V138"
let keys = [before, owner, source, date, record]
@MainActor func receipt() -> [String: Any] { prefs.dictionary(forKey: record) ?? [:] }
for key in keys { prefs.removeObject(forKey: key) }
defer { for key in keys { prefs.removeObject(forKey: key) } }
prefs.set("old", forKey: before)
prefs.set("prior-process", forKey: owner)
prefs.set("prior-source", forKey: source)
let priorDate = Date(timeIntervalSince1970: 1000)
prefs.set(priorDate, forKey: date)
precondition(ScarletInstalledProfileReadback.beginRequest(source: "manual"))
precondition(!ScarletInstalledProfileReadback.beginRequest(source: "automatic"))
precondition(receipt()[source] as? String == "manual")
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(receipt()[before] as? String == "new")
ScarletInstalledProfileReadback.discardFailedRequest()
ScarletInstalledProfileReadback.finishRequest()
precondition(receipt()[before] as? String == "old")
precondition(receipt()[owner] as? String == "prior-process")
precondition(receipt()[source] as? String == "prior-source")
precondition(receipt()[date] as? Date == priorDate)
precondition(ScarletInstalledProfileReadback.beginRequest(source: "automatic"))
ScarletInstalledProfileReadback.finishRequest()
precondition(receipt()[before] as? String == "new")
precondition(receipt()[source] as? String == "automatic")
ScarletInstalledProfileReadback.fixtureDigest = nil
precondition(ScarletInstalledProfileReadback.beginRequest(source: "selected_p12_rotation"))
precondition(!ScarletInstalledProfileReadback.beginRequest(source: "manual"))
ScarletInstalledProfileReadback.discardFailedRequest()
ScarletInstalledProfileReadback.finishRequest()
precondition(receipt()[source] as? String == "automatic")
print("R137_PROFILE_LEASE_PASS")
"""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "main.swift"
            f.write_text(fixture)
            p = subprocess.run([swift, "-swift-version", "6", str(f)], capture_output=True,
                               text=True, timeout=120, cwd=d)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("R137_PROFILE_LEASE_PASS", p.stdout)

if __name__ == "__main__":
    unittest.main()

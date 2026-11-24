"""R138 receipt persistence: single record, migration, tombstone and rollback."""
import os
import importlib.util
import json
import plistlib
import zipfile
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

R = Path(os.environ.get("SCARLET_TEST_ROOT", Path(__file__).resolve().parents[1]))
A = (R / "HostApp/ScarletAutomaticRenewal.swift").read_text()

class ProfileReceiptRecord(unittest.TestCase):
    def test_single_value_replaces_independent_writes(self):
        body = A.split("enum ScarletInstalledProfileReadback {", 1)[1]
        begin = body.split("static func beginRequest", 1)[1].split("static func discardFailedRequest", 1)[0]
        self.assertIn('Scarlet.Refresh.InstalledProfileReceipt.V138', body)
        self.assertIn('storeReceipt(Receipt(', begin)
        for old in ('prefs.set(digest, forKey: beforeKey)', 'prefs.set(processMarker, forKey: ownerKey)',
                    'prefs.set(source, forKey: sourceKey)', 'prefs.set(Date(), forKey: requestTimeKey)'):
            self.assertNotIn(old, begin)
        self.assertIn('prefs.set(receipt?.values ?? [:], forKey: receiptKey)', body)

    def test_migration_requires_complete_record_and_canonical_tombstone(self):
        body = A.split("enum ScarletInstalledProfileReadback {", 1)[1]
        self.assertIn('if prefs.object(forKey: receiptKey) != nil', body)
        self.assertIn('let date = values[requestTimeKey] as? Date else { return nil }', body)
        read = body.split('private static func readReceipt', 1)[1].split('private static func installedDigest', 1)[0]
        self.assertLess(read.index('storeReceipt(legacy, in: prefs)'), read.index('prefs.removeObject(forKey: key)'))
        verify = body.split('static func verifyNewProcess', 1)[1]
        self.assertIn('storeReceipt(nil, in: prefs)', verify)
        self.assertIn('"installation_verified": "false"', verify)

    def test_version_and_marker(self):
        workflow = (R.parent / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
        branch = 'fix/scarlet-r6p138-profile-receipt-record-20261124'
        self.assertIn(branch, next(x for x in workflow.splitlines() if x.startswith('    branches:')))
        self.assertIn('--host-build-version 3.8.138', workflow)
        self.assertNotIn(branch, workflow.split('  publish-unsigned-github-release:', 1)[1])
        gate = (R / 'integration/verify_integrated_release.py').read_text()
        self.assertIn('R138 single-value profile receipt marker missing', gate)

    def test_archive_requires_compiled_r138_receipt_marker(self):
        spec = importlib.util.spec_from_file_location("gate138", R / "integration/verify_integrated_release.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        sha = "c" * 40
        host = "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI"
        worker = "Frameworks/SideStoreApp.framework/SideStore"
        actions = {k: {} for k in ("RefreshAllIntent", "RefreshAllAppsWidgetIntent", "InstallIPAIntent")}
        actions["ScarletSelfUpdateIntent"] = {"fullyQualifiedTypeName": "LiveContainerSwiftUI.ScarletSelfUpdateIntent"}
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "test.ipa"
            for include in (False, True):
                with zipfile.ZipFile(ipa, "w") as z:
                    z.writestr(gate.PREFIX + "Info.plist", plistlib.dumps({
                        "CFBundleIdentifier": "com.kdt.livecontainer.P8EZT3U5N4",
                        "CFBundleShortVersionString": "3.8.11",
                        "CFBundleVersion": "3.8.138", "CFBundleExecutable": "LiveContainer"}))
                    for path, markers in gate.REQUIRED_MARKERS.items():
                        data = list(markers)
                        if path == host:
                            data.extend([("scarlet-source-commit:" + sha).encode(), b"ScarletSelfUpdateIntent",
                                         b"shortcut_update_installed_build_verified", b"classic_handoff_drained",
                                         b"classic_handoff_blocked", b"selected_team_partial_refresh_results",
                                         b"selected_team_refresh_result_mismatch", b"profile_readback_request_busy"])
                            if include:
                                data.append(b"Scarlet.Refresh.InstalledProfileReceipt.V138")
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
                    self.assertEqual(gate.verify(ipa, "3.8.138", sha)["version"], "3.8.138")
                else:
                    with self.assertRaisesRegex(ValueError, "R138"):
                        gate.verify(ipa, "3.8.138", sha)

    def test_actual_swift_receipt(self):
        swiftc = shutil.which('swiftc')
        if not swiftc:
            self.skipTest('Swift compiler unavailable; native Xcode CI required')
        body = 'enum ScarletInstalledProfileReadback {' + A.split('enum ScarletInstalledProfileReadback {',1)[1]
        body = re.sub(r'    private static func installedDigest\(\) -> String\? \{.*?\n    \}',
                      '    static var fixtureDigest: String? = "new"\n    private static func installedDigest() -> String? { fixtureDigest }',
                      body, count=1, flags=re.S)
        fixture = '''
import Foundation
@MainActor final class ScarletDiagnosticRecorder {
    static let shared = ScarletDiagnosticRecorder()
    var events: [String] = []
    func record(_ a: String, _ b: String, status: String = "info", fields: [String: String] = [:]) { events.append(b) }
}
''' + '@MainActor\n' + body + '''
let prefs = UserDefaults.standard
let before = "Scarlet.Refresh.PreviousInstalledProfileSHA.V37"
let owner = "Scarlet.Refresh.ProfileRequestProcess.V37"
let source = "Scarlet.Refresh.ProfileRequestSource.V37"
let date = "Scarlet.Refresh.ProfileRequestDate.V37"
let record = "Scarlet.Refresh.InstalledProfileReceipt.V138"
let keys = [before, owner, source, date, record]
@MainActor func reset() { for key in keys { prefs.removeObject(forKey: key) }; ScarletDiagnosticRecorder.shared.events = [] }
@MainActor func changed() -> Bool { ScarletDiagnosticRecorder.shared.events.contains("installed_profile_changed_after_request") }
@MainActor func seedLegacy(_ complete: Bool) {
    prefs.set("old", forKey: before); prefs.set("prior-process", forKey: owner)
    if complete { prefs.set("manual", forKey: source); prefs.set(Date(timeIntervalSince1970: 1000), forKey: date) }
}
@MainActor func canonical() -> [String: Any] { prefs.dictionary(forKey: record) ?? [:] }
reset()
// R137 used only digest+owner, and falsely treated a partial legacy record as evidence.
seedLegacy(false)
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(!changed(), "incomplete legacy receipt emitted changed evidence")
precondition(prefs.object(forKey: record) != nil && canonical().isEmpty)
reset()
seedLegacy(true)
ScarletInstalledProfileReadback.fixtureDigest = "old"
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(canonical()[source] as? String == "manual")
precondition(prefs.object(forKey: before) == nil)
ScarletInstalledProfileReadback.fixtureDigest = "new"
precondition(ScarletInstalledProfileReadback.beginRequest(source: "automatic"))
precondition(!ScarletInstalledProfileReadback.beginRequest(source: "manual"))
precondition(canonical()[before] as? String == "new")
ScarletInstalledProfileReadback.discardFailedRequest()
ScarletInstalledProfileReadback.finishRequest()
precondition(canonical()[before] as? String == "old")
precondition(canonical()[date] as? Date == Date(timeIntervalSince1970: 1000))
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(changed() && canonical().isEmpty)
// A legacy key resurrected by older interrupted migration must never override a tombstone.
seedLegacy(true)
ScarletDiagnosticRecorder.shared.events = []
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(!changed())
reset()
seedLegacy(true)
prefs.set([before: "old", owner: "prior-process"], forKey: record)
ScarletInstalledProfileReadback.verifyNewProcess()
precondition(!changed(), "malformed canonical record fell back to stale legacy")
reset()
ScarletInstalledProfileReadback.fixtureDigest = nil
precondition(ScarletInstalledProfileReadback.beginRequest(source: "manual"))
ScarletInstalledProfileReadback.discardFailedRequest()
ScarletInstalledProfileReadback.finishRequest()
precondition(canonical().isEmpty)
reset()
print("R138_PROFILE_RECEIPT_PASS")
'''
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'main.swift'; f.write_text(fixture)
            binary = Path(d) / 'test'
            p = subprocess.run([swiftc, '-swift-version', '6', '-strict-concurrency=complete', '-warnings-as-errors', str(f), '-o', str(binary)], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('R138_PROFILE_RECEIPT_PASS', p.stdout)

if __name__ == '__main__': unittest.main()

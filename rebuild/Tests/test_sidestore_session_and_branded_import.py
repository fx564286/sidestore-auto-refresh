"""Integration guard: authenticated SideStore Keychain != available LC signer.

User-observed 2026-11-09 screenshots and 1,101-line diagnostic:
- auth host_session_restored + stored_session_restored
- guest certificate_bridge_skipped(reason=missing)
- sources guest_download_started without terminal event in report
- floating download overlay obscuring multiple app tabs

Static assertions guard wiring; real iPhone runtime and download are separate.
"""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
WORKER=(ROOT/"integration/ScarletGuestSignInAgent.swift.txt").read_text()
XPC=(ROOT/"integration/wire_scarlet_auth.py").read_text()
MAP=json.loads((ROOT/"design/figma-current-screen-map.json").read_text())

class AuthAndImportUIRegression(unittest.TestCase):
    def test_side_store_auth_verification_is_guest_keychain_not_badge(self):
        self.assertIn("storedAuthenticated()", HOST)
        self.assertIn("scarletAuthStored", XPC)
        self.assertIn("persistedState", XPC)
        self.assertIn("host_session_restored", HOST)
        self.assertIn("내장 SideStore · 인증 세션 복원됨", PATCH)
        self.assertIn("scarletSigningCertAvailable", PATCH)
        self.assertIn("서명 인증서 · 없음 (로그인과 별도)", PATCH)
        self.assertIn("certificate_bridge_skipped", HOST)
        self.assertIn("same_team_verified_readback", HOST)
        self.assertIn("인증서 발급 또는 동기화가 필요합니다", PATCH)

    def test_global_source_toast_was_removed(self):
        self.assertNotIn('.overlay(alignment: .top) {\n            if sourceIsDownloading', HOST)
        self.assertIn("SCARLET_BRANDED_SOURCE_DOWNLOAD_SHEET", HOST)
        self.assertIn("SCARLET_SOURCE_DOWNLOAD_STAGE", HOST)
        self.assertIn("SCARLET_SOURCE_DOWNLOAD_CANCEL", HOST)
        self.assertIn("showSourceDownloadSheet = true", HOST)

    def test_download_bounded_cancelable_and_does_not_false_claim_install(self):
        self.assertIn("config.timeoutIntervalForRequest = 45", HOST)
        self.assertIn("config.timeoutIntervalForResource = 900", HOST)
        self.assertIn("sourceDownloadTask?.cancel()", HOST)
        self.assertIn("try Task.checkCancellation()", HOST)
        self.assertIn("guest_download_cancelled", HOST)
        self.assertIn("guest_download_failed", HOST)
        self.assertIn("sourceDownloadedIPA = staged", HOST)
        self.assertIn("stageGuestIPAFromFiles(staged)", HOST)
        self.assertIn('"stage": "download_only"', HOST)
        self.assertIn("showSourceDownloadSheet = false", HOST)

    def test_branded_original_lc_guest_importer_still_owns_actual_install(self):
        self.assertIn("LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,", HOST)
        self.assertIn("await startInstallApp(queuedIPA)", PATCH)
        self.assertIn('SCARLET_BRANDED_GUEST_IMPORT_CARD', PATCH)
        self.assertIn('SCARLET_GUEST_IMPORT_ACTUAL_PROGRESS', PATCH)
        self.assertIn('ProgressView(value: Double(installProgressPercentage), total: 1.0)', PATCH)
        self.assertIn('if #available(iOS 26.0, *)', PATCH)
        self.assertIn('.glassEffect()', PATCH)
        self.assertIn('.disabled(!scarletQueuedImportFinished || installprogressVisible)', PATCH)

    def test_figma_tracks_both_install_steps(self):
        self.assertEqual(MAP["screens"]["sourceDownloadInProgress"], "133:2")
        self.assertEqual(MAP["screens"]["guestImportInProgress"], "133:43")
        self.assertIn("SideStore",MAP["authSemantics"])

if __name__=="__main__":
    unittest.main()

"""November five-point Scarlet clean-rebuild integration guard.

These source checks validate wiring and cannot replace iPhone runtime/optical
or signing verification.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()

class FivePointNovemberAccept(unittest.TestCase):
    def test_1_verified_auth_session_drives_account_state(self):
        self.assertIn("scarletLoginVerified: Bool? = nil", PATCH)
        self.assertIn('Label("Apple ID 로그인",', PATCH)
        self.assertIn('로그인됨 · 내장 SideStore 세션 복원', PATCH)
        self.assertIn('ScarletConnectedSideSignEngine().storedAuthenticated()', PATCH)
        self.assertIn("서명 인증서 · 없음 (로그인과 별도)", PATCH)
        self.assertIn("onDismiss:", PATCH)

    def test_2_real_independent_four_column_guest_launcher(self):
        home=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
        self.assertIn("SCARLET_APPS_FOUR_COLUMN_LAUNCHER",home)
        self.assertIn("count: 4",home)
        self.assertIn("ForEach(visibleGuests)",home)
        self.assertNotIn("ScarletGuestListCard(",home)
        self.assertIn("Image(uiImage: image)",UI)
        self.assertIn("iconIsDarkIcon(false)?.pngData()",HOST)
        self.assertIn(".tabBarMinimizeBehavior(.onScrollDown)",UI)
        self.assertIn("onSystemGlassMounted",UI)

    def test_3_original_lc_bootstrap_and_previous_launch_error_visible(self):
        self.assertIn("ensureOriginalLCGuestBootstrap()",HOST)
        self.assertIn('"LCLaunchExtensionPrivateDocBookmark"',HOST)
        self.assertIn('"LCCertificateTeamId"',HOST)
        self.assertIn("reportPreviousGuestLaunchFailure()",HOST)
        self.assertIn('"previous_launch_error_detected"',HOST)
        self.assertIn('"jit_delegate_unavailable"',HOST)
        self.assertIn("try await app.runApp()",HOST)
        self.assertNotIn("forceJIT: false",HOST)

    def test_4_source_add_entry_goes_to_actual_url_sheet(self):
        self.assertIn("showSourceURLInput = true",HOST)
        self.assertIn("SCARLET_DIRECT_SOURCE_URL_FIELD",HOST)
        self.assertIn("originalSources.addSource(from: newSourceURL)",HOST)
        self.assertIn('showSourceURLInput = false',HOST)
        self.assertIn("onAddSource: {",HOST)
        self.assertNotIn("showNativeSources = true\\n            },",HOST)

    def test_5_source_app_download_reaches_original_guest_importer(self):
        self.assertIn("ScarletSourceAppPresentation",UI)
        self.assertIn("source.apps",UI)
        self.assertIn("SCARLET_SOURCE_APP_INSTALL",UI)
        self.assertIn("onInstallSourceApp(app.id)",UI)
        self.assertIn("onInstallSourceApp: installSourceGuestApp",HOST)
        self.assertIn("session.download(from: url)",HOST)
        self.assertIn("stageGuestIPAFromFiles(staged, presentProgress: !installProgressMinimized)",HOST)
        self.assertIn("LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,",HOST)
        self.assertIn("guest_download_started",HOST)
        self.assertIn("guest_download_completed",HOST)
        self.assertIn("transport_unverified",HOST)
        self.assertNotIn('NSNotification.InstallAppNotification',HOST)

if __name__=="__main__":
    unittest.main()

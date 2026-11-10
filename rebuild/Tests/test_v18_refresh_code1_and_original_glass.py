"""V18: user-requested glass rollback + SideStore code-1 refresh diagnostics.

2026-11-09 on-device SourceCommit 08b010bb5916 proves V17 code installed.
The automatic refresh logs show SideStore code 1 and no verified renewal.
Source contracts alone do not prove a newly re-signed iPhone install.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GLASS = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
AUTO = (ROOT / "HostApp/ScarletAutomaticRenewal.swift").read_text()
PANEL = (ROOT / "HostApp/ScarletSigningReadinessPanel.swift").read_text()
JOURNAL = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

class V18RefreshAndGlass(unittest.TestCase):
    def test_original_liquid_glass_untouched(self):
        start = GLASS.index("private func glassPlate(radius: CGFloat)")
        stop = GLASS.index("private var currentAppName", start)
        code = GLASS[start:stop]
        self.assertIn("SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)", code)
        self.assertIn(".clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))", code)
        self.assertNotIn("systemBackground", code)
        self.assertNotIn(".opacity(0.88)", code)

    def test_code_1_is_diagnosed_without_secret_error_payloads(self):
        for fragment in (
            "enum ScarletRefreshFailureDiagnosis",
            "refresh_already_running", "liveprocess_missing",
            "liveprocess_start_failed", "embedded_sidestore_exited",
            "embedded_sidestore_start_timeout", "sidestore_internal_failure",
            'ScarletRefreshFailureDiagnosis.category(error)',
            '"automatic_failure_categorized"', '"LastFailureReason"',
        ):
            if fragment == '"LastFailureReason"':
                self.assertIn("Scarlet.Refresh.LastFailureReason", AUTO)
            else:
                self.assertIn(fragment, AUTO)
        self.assertIn('static func category(_ error: Error) -> String', AUTO)
        self.assertNotIn('fields: ["message": error.localizedDescription]', AUTO)
        self.assertIn('func recordError(_ category: String', JOURNAL)

    def test_bg_failure_is_not_reported_as_success(self):
        self.assertIn('let requestReturned = await refreshIfDue(origin: "background")', AUTO)
        self.assertIn('let taskSucceeded = requestReturned && !Task.isCancelled', AUTO)
        self.assertIn('bg.setTaskCompleted(success: taskSucceeded)', AUTO)
        self.assertIn('return false', AUTO)
        self.assertIn('return true', AUTO)
        self.assertIn('installation_verified": "false"', AUTO)

    def test_manual_refresh_does_not_recommend_new_p12_for_xpc_crash(self):
        self.assertIn('ScarletRefreshFailureDiagnosis.category(error)', PANEL)
        self.assertIn('ScarletRefreshFailureDiagnosis.nativeGuidance(failure)', PANEL)
        self.assertIn('certificateRecoveryStatus = nil', PANEL)
        self.assertIn('SCARLET_REFRESH_FAILURE_CATEGORY', PANEL)
        self.assertIn('Scarlet.Refresh.LastFailureReason', PANEL)
        self.assertIn('manual_request_underlying_error', PANEL)
        self.assertIn('ScarletNativeRefreshExecutor.execute()', PANEL)
        self.assertIn('요청 반환 · 재설치 확인 안 됨', PANEL)

if __name__ == "__main__":
    unittest.main()

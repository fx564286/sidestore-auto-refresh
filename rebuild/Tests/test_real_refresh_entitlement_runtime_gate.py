"""Scarlet native entitlement readback and non-misleading 7-day refresh.
Source wiring gate only. Signed device entitlement/renewal must be verified on iPhone.
"""
from pathlib import Path
import unittest

R = Path(__file__).resolve().parents[1]
CAP = (R/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST = (R/"HostApp/ScarletIntegratedHostView.swift").read_text()
PATCH = (R/"integration/apply_scarlet_host.py").read_text()
POLICY = (R/"Sources/ScarletCleanCore/ScarletRefreshPolicy.swift").read_text()

class SignedRuntimeCapabilityGate(unittest.TestCase):
    def test_1_manual_refresh_invokes_original_sidestore_engine(self):
        self.assertIn("import SideStoreSupport", CAP)
        self.assertIn("RefreshAllAppsIntent().perform()", CAP)
        self.assertNotIn('Label("SideStore 수동 새로고침"', CAP)
        self.assertIn("storedAuthenticated()", CAP)
        self.assertNotIn("SCARLET_MANUAL_SIDESTORE_REFRESH", CAP)
        self.assertIn("installation_verified", CAP)
        self.assertIn('"false"', CAP)

    def test_2_automatic_refresh_not_falsely_reported(self):
        self.assertIn('LabeledContent("자동 갱신", value: "미연결 · 실행 안 됨")', CAP)
        self.assertIn("자동 7일 갱신은 아직 연결되지 않았습니다", CAP)
        self.assertIn("recommendedLeadTime: TimeInterval = 72 * 3600", POLICY)

    def test_3_actual_entitlement_and_container_both_required(self):
        self.assertIn('com.apple.security.application-groups', CAP)
        self.assertIn('com.apple.developer.team-identifier', CAP)
        self.assertIn('FileManager.default.containerURL(', CAP)
        self.assertIn("developerTeamEntitled && sideStoreAppGroupEntitled &&", CAP)
        self.assertIn("sideStoreAppGroupAccessible", CAP)
        self.assertIn("signedApplicationIdentifierMatches", CAP)
        self.assertIn('group.com.SideStore.SideStore.', CAP)
        self.assertIn('P8EZT3U5N4', CAP)
        self.assertIn("safeBlockCategory", CAP)
        self.assertNotIn("SCARLET_REFRESH_ENTITLEMENT_READBACK", CAP)

    def test_3b_signer_app_id_variants_are_not_automatically_entitled(self):
        # Screenshot shows a suffix-duplicated host bundle. Both observed
        # spellings are eligible only if Apple's signed app ID matches exactly.
        self.assertIn('baseBundleID + ".P8EZT3U5N4"', CAP)
        self.assertIn('"application-identifier" as CFString', CAP)
        self.assertIn('applicationID == (team! + "." + bundleID!)', CAP)
        self.assertIn("signedApplicationIdentifierMatches: signedIDMatches", CAP)
        self.assertIn("actualHostIdentity && signedApplicationIdentifierMatches", CAP)
        self.assertIn("signed_application_identifier_mismatch", CAP)
        self.assertIn('"실제 서명과 일치"', CAP)
        self.assertIn("FileManager.default.containerURL(", CAP)
        self.assertNotIn("SecTaskCopyValueForEntitlement = ", CAP)

    def test_4_fail_closed_existing_signer_bridge(self):
        first = HOST.index("private func bridgeExistingSideStoreCertificateIfSafe()")
        body = HOST[first: HOST.index("private func ensureOriginalLCGuestBootstrap()", first)]
        self.assertLess(body.index("guard permissions.canRequestNativeRefresh else"),
                        body.index('LCUtils.appGroupUserDefault.set(certData'))
        self.assertIn("certificate_bridge_skipped", body)
        self.assertNotIn("SecItemDelete(", body)
        self.assertNotIn("SecItemAdd(", body)

    def test_5_native_settings_has_real_panel_not_dummy_toggle(self):
        self.assertIn("ScarletSigningReadinessPanel.swift", PATCH)
        self.assertIn("ScarletSigningReadinessPanel()", PATCH)
        self.assertIn("SCARLET_CERTIFICATE_SEPARATE_FROM_LOGIN", PATCH)
        self.assertIn("canRequestNativeRefresh", CAP)
        self.assertIn(".disabled(isIssuingNativeCertificate ||", CAP)

if __name__ == "__main__":
    unittest.main()

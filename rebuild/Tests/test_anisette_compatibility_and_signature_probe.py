"""Regression contract for real-device 2026-11-07 -80045 and post-sign invalid signature.

Cannot prove Apple accepts a compatibility profile or that iOS approves
guest signatures; those require account-owner on-device validation.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def read(path: str) -> str:
    return (ROOT / path).read_text()

UI = read("HostApp/ScarletAppleIDLoginSheet.swift")
BRIDGE = read("HostApp/ScarletSideStoreAuthenticationBridge.swift")
TRANSPORT = read("HostApp/ScarletAuthXPCSupport.swift")
WIRING = read("integration/wire_scarlet_auth.py")
GUEST = read("integration/ScarletGuestSignInAgent.swift.txt")
HOST = read("HostApp/ScarletIntegratedHostView.swift")
INSTRUMENTATION = read("integration/apply_scarlet_host.py")

class OwnerDeviceFailures(unittest.TestCase):
    def test_profile_requires_user_selection_after_apple_80045(self):
        self.assertIn('error.localizedDescription.contains("-80045")', UI)
        self.assertIn("showAnisetteCompatibility = true", UI)
        self.assertIn('Text("기존 설정").tag("default")', UI)
        self.assertIn('Text("Windows iTunes (원격)").tag("windows")', UI)
        self.assertIn('Text("Mac AuthKit (원격)").tag("mac")', UI)
        self.assertIn("anisetteProfile: anisetteProfile", UI)
        self.assertNotIn("try await engine.signIn(appleID: account, password: secret) {", UI)

    def test_profile_passes_single_xpc_boundary_without_persistence(self):
        for source in (UI, BRIDGE, TRANSPORT):
            self.assertIn("anisetteProfile", source)
        self.assertIn("profile:(NSString*)profile", WIRING)
        self.assertIn('@"profile": profile ?: @"default"', WIRING)
        self.assertIn('payload["profile"] as? String', GUEST)
        self.assertIn('["windows", "mac", "sidestore_new_mac"].contains(profile)', GUEST)
        self.assertIn('Text("SideStore New (Mac 서버)").tag("sidestore_new_mac")', UI)
        self.assertNotIn("AnisetteConfigManager.shared.saveConfig", GUEST)
        self.assertNotIn("resetToDefaults", GUEST)
        self.assertNotIn("clearCache", GUEST)
        self.assertNotIn("signOut(", GUEST)

    def test_new_anisette_provider_avoids_stale_header_cache(self):
        self.assertIn("https://new.ani.sidestore.io", GUEST)
        self.assertIn("let dedicatedMacServer = profile == \"sidestore_new_mac\"", GUEST)
        self.assertIn("let existingBlob: Data? = sameStoredIdentity ?", GUEST)
        self.assertIn("headers.clientInfo = nil", GUEST)
        self.assertIn("headers.userAgent = nil", GUEST)
        self.assertIn("SideSign.AnisetteDataManager()", GUEST)
        self.assertIn("fetchAnisetteDataWithFailover(", GUEST)
        self.assertIn('headers.clientInfo = "<PC> ', GUEST)
        self.assertIn('headers.clientInfo = "<MacBookPro13,3> ', GUEST)
        self.assertIn("compatible.clientInfo = headers.clientInfo ?? result.clientInfo", GUEST)
        self.assertIn("compatible.userAgent = headers.userAgent ?? result.userAgent", GUEST)
        self.assertIn('servers = urls.compactMap(URL.init(string:)).filter { $0.scheme == "https" }', GUEST)
        self.assertIn("if let pendingAdiBlob {", GUEST)
        self.assertIn("AuthManager.shared.currentAppleID = email", GUEST)
        self.assertLess(GUEST.index("guard !cancelled else"), GUEST.index("if let pendingAdiBlob {"))
        self.assertIn('return (try await AnisetteProvider.fetch(), nil)', GUEST)

    def test_jitless_failure_uses_original_non_destructive_check(self):
        self.assertIn("DispatchQueue.global(qos: .utility).async", HOST)
        self.assertIn("LCUtils.validateJITLessSetup { verified, _ in", HOST)
        self.assertIn('"jitless_probe_finished"', HOST)
        self.assertIn("ScarletGuestCertificateInvalid", HOST)
        self.assertIn('"certificate_invalid"', INSTRUMENTATION)
        self.assertNotIn("SecItemDelete", HOST)
        self.assertNotIn("revokeCertificate", HOST)

if __name__ == "__main__":
    unittest.main()

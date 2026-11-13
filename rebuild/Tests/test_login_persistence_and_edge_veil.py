"""Regressions for 2026-11-07 screenshot + real 2FA success log.

The Apple challenge succeeded once, but only in-memory UI state was shown.
This checks a SideStore-worker Keychain roundtrip and cross-scene refresh.
System TabView minimize behavior must be retained while hiding edge veils.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def source(path):
    return (ROOT/path).read_text()

GUEST = source("integration/ScarletGuestSignInAgent.swift.txt")
WIRING = source("integration/wire_scarlet_auth.py")
SUPPORT = source("HostApp/ScarletAuthXPCSupport.swift")
BRIDGE = source("HostApp/ScarletSideStoreAuthenticationBridge.swift")
LOGIN = source("HostApp/ScarletAppleIDLoginSheet.swift")
HOST = source("HostApp/ScarletIntegratedHostView.swift")
SHELL = source("Sources/ScarletIndependentUI/ScarletIndependentShell.swift")
GLASS = source("HostApp/ScarletNativeGlass.swift")

class PersistedSideStoreLogin(unittest.TestCase):
    def test_success_requires_worker_keychain_roundtrip(self):
        self.assertIn("@objc(persistedState)", GUEST)
        self.assertIn("auth.isAuthenticated &&", GUEST)
        for field in ("auth.currentAppleID != nil", "auth.adsid != nil", "auth.xcodeToken != nil"):
            self.assertIn(field, GUEST)
        self.assertLess(GUEST.index("guard persistedState() else"),
                        GUEST.index('finish(id, code: 0, domain: "success")'))
        self.assertIn("scarlet.auth.keychain_roundtrip_failed", GUEST)

    def test_original_sidestore_saved_token_session_uses_successful_profile(self):
        self.assertIn("scarlet.auth.lastSuccessfulAnisetteProfile", GUEST)
        self.assertIn("static func restoreAnisetteForSavedSession()", GUEST)
        self.assertIn("let sameStoredIdentity = !dedicatedMacServer", GUEST)
        self.assertIn("source.count(original) == 1", WIRING)
        self.assertIn("ScarletGuestSignInAgent.restoreAnisetteForSavedSession()", WIRING)
        for source_code in (GUEST, WIRING, HOST):
            self.assertNotIn("SecItemDelete", source_code)
            self.assertNotIn("signOut(", source_code)

    def test_xpc_checks_real_guest_keychain_on_resume(self):
        self.assertIn("scarletAuthStored:", WIRING)
        self.assertIn("@selector(persistedState)", WIRING)
        self.assertIn("remote.scarletAuthStored", SUPPORT)
        self.assertIn("public func storedAuthenticated() async -> Bool", SUPPORT)
        self.assertIn("func storedAuthenticated() async -> Bool", BRIDGE)
        self.assertIn("func storedAuthenticated() async -> Bool", LOGIN)
        self.assertIn("guard await engine.storedAuthenticated() else", LOGIN)
        self.assertIn("stored_session_restored", LOGIN)
        self.assertIn("SCARLET_STORED_LOGIN_VISIBLE", LOGIN)
        self.assertIn("refreshStoredLoginState()", HOST)
        self.assertIn("host_session_restored", HOST)
        self.assertIn("if phase == .active && !showScarletAppleIDLogin", HOST)
        self.assertNotIn("appleAuthVerified = true", HOST)

    def test_foreground_login_checks_discard_stale_xpc_readbacks(self):
        self.assertIn("authStateReadGeneration &+= 1", HOST)
        self.assertIn("requestGeneration == authStateReadGeneration", HOST)
        self.assertIn("!showScarletAppleIDLogin", HOST)
        self.assertLess(HOST.index("requestGeneration == authStateReadGeneration"),
                        HOST.index("appleAuthVerified = verified"))
        self.assertIn("host_session_read_discarded", HOST)

    def test_system_glass_minimize_remains_but_all_edge_veils_removed(self):
        self.assertIn("TabView(selection: $selected)", SHELL)
        self.assertIn(".tabBarMinimizeBehavior(.onScrollDown)", SHELL)
        self.assertIn("SCARLET_IOS26_NATIVE_SYSTEM_GLASS_TABS", SHELL)
        self.assertIn(".scrollEdgeEffectHidden(true, for: .all)", SHELL)
        self.assertIn(".scrollEdgeEffectHidden(true, for: .all)", GLASS)
        self.assertNotIn(".scrollEdgeEffectStyle(.hard", GLASS)
        self.assertNotIn(".scrollEdgeEffectStyle(.hard", SHELL)
        self.assertIn("scarletDiagnosticScrollMargins", GLASS)
        self.assertIn("nativeSettings()\n                    .scarletIndependentScrollEdge()", SHELL)
        self.assertIn("nativeTweaks()\n                    .scarletIndependentScrollEdge()", SHELL)

if __name__ == "__main__":
    unittest.main()

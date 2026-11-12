"""R6P20: reuse 2FA-confirmed Apple portal session and signed-ID BG tasks."""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
AUTH=(R/'integration/ScarletGuestSignInAgent.swift.txt').read_text()
AUTO=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
PAIR=(R/'HostApp/ScarletNativeDevicePairing.swift').read_text()
GEN=(R/'integration/apply_scarlet_host.py').read_text()

class RealSignInSessionAndSignedIdentifierTests(unittest.TestCase):
    def test_verified_apple_session_reused_after_2fa_before_team_portal(self):
        self.assertIn('let (_, session) = try await AuthManager.shared.signIn(',AUTH)
        verified=AUTH.index('guard persistedState() else {',AUTH.index('@objc(begin:)'))
        cached=AUTH.index('AuthManager.shared.session = session',verified)
        active=AUTH.index('let teamState = await ensureActiveTeamForRefresh()',cached)
        self.assertLess(verified,cached)
        self.assertLess(cached,active)
        self.assertIn('finish(id, code: -3401',AUTH[verified:cached])
        self.assertIn('finish(id, code: -3402',AUTH[active:])
    def test_engine_get_authenticated_session_may_need_anisette_without_cache(self):
        self.assertIn('DeveloperPortalProxy.shared.fetchTeams(',AUTH)
        self.assertIn('AuthManager.shared.session = session',AUTH)
        self.assertNotIn('AuthManager.shared.signOut()',AUTH)
        self.assertNotIn('clearActiveCertificate()',AUTH)
    def test_bg_task_id_tracks_exact_installed_signed_bundle(self):
        for src,ending in [(AUTO,'.refresh'),(PAIR,'.pairing')]:
            self.assertIn('Bundle.main.bundleIdentifier ?? original',src)
            self.assertIn('actual == original + ".P8EZT3U5N4"',src)
            self.assertIn('return actual + "'+ending+'"',src)
            self.assertIn('return original + "'+ending+'"',src)
    def test_both_known_permitted_bundle_id_variants_declared(self):
        self.assertIn('BGTaskSchedulerPermittedIdentifiers',GEN)
        self.assertIn('observedBundle="com.kdt.livecontainer.P8EZT3U5N4.P8EZT3U5N4"',GEN)
        self.assertIn('for suffix in ("refresh", "pairing")',GEN)
        self.assertIn('if allowedID not in identifiers: identifiers.append(allowedID)',GEN)
        self.assertIn('identifier="com.kdt.livecontainer.P8EZT3U5N4.refresh"',GEN)
    def test_no_signed_entitlement_or_guest_screen_modified(self):
        self.assertNotIn('SecTaskCopyValueForEntitlement =',AUTH)
        self.assertNotIn('window.frame =',AUTH)
        self.assertNotIn('SecItemDelete',AUTH)
if __name__=='__main__':unittest.main()

"""V118 network session isolation regression tests; no live Apple requests."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v118', ROOT / 'scripts/patch_v118_gsa_isolation.py')
v118 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v118)
FIXTURE = '''import GSACryptoKit
// NRG_GSA_HTTP_STATUS_V2
// NRG_GSA_RECOVERY_V1
// SCARLET_V116_SIDEINSTALLER_PARITY
// NRG_GSA_CLIENT_IDENTITY_V3
public extension DeveloperPortal {
    func authenticate(appleID unsanitizedAppleID: String, password: String, anisetteData: AnisetteData, xcodeVersion: String, machinePassword: String? = nil, accountRepairHandler: AccountRepairHandler, verificationHandler: VerificationHandler? = nil) async throws -> AuthSession {
        let sanitizedAppleID = unsanitizedAppleID.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return AuthSession()
    }
    func sendAuthenticationRequest() {
        let headers = ["X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo)]
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
    }
    func makeTwoFactorAuthRequest() {
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
    }
    func f1() { session.data(for: request) }
    func f2() { session.data(for: request) }
    func f3() { session.data(for: request) }
    func f4() { session.data(for: request) }
    func f5() { session.data(for: request) }
}
'''

class V118Tests(unittest.TestCase):
    def test_session_is_shared_across_auth_and_five_sites(self):
        updated = v118.transform(FIXTURE)
        self.assertEqual(updated.count(v118.AFTER), 5)
        self.assertNotIn(v118.BEFORE, updated)
        self.assertIn('URLSessionConfiguration.ephemeral', updated)
        self.assertIn('ScarletV118AuthTransport.$current.withValue(isolated)', updated)
        self.assertIn('defer { isolated.invalidateAndCancel() }', updated)
        self.assertEqual(v118.transform(updated), updated)

    def test_diagnostics_are_privacy_bounded(self):
        self.assertIn('fields_complete=', v118.DIAG)
        self.assertIn('profile_coherent=', v118.DIAG)
        self.assertIn('time=', v118.DIAG)
        for forbidden in ('print(anisetteData', 'password =', 'SecItemDelete(', 'authToken ='):
            self.assertNotIn(forbidden, v118.DIAG + v118.ENTRY)

    def test_prerequisites_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'prerequisite'):
            v118.transform(FIXTURE.replace('SCARLET_V116_SIDEINSTALLER_PARITY', 'MISSING'))
        with self.assertRaisesRegex(ValueError, 'anchor drifted'):
            v118.transform(FIXTURE.replace('session.data(for:', 'session.data(with:', 1))
        after = v118.transform(FIXTURE)
        with self.assertRaisesRegex(ValueError, 'partial or drifted'):
            v118.transform(after.replace('session=isolated', 'session=shared'))

    def test_does_not_generate_fake_2fa(self):
        for prohibited in ('verificationHandler(.trustedDevice', 'verificationHandler(.sms',
                           'signOut()', 'resetAnisette', 'SecItemDelete'):
            self.assertNotIn(prohibited, v118.ENTRY + v118.DIAG)

if __name__ == '__main__':
    unittest.main()

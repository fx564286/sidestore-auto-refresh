import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nrg_v3", ROOT / "scripts/patch_nrg_gsa_client_v3.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

FIXTURE = '''NRG_GSA_RECOVERY_V1 NRG_GSA_HTTP_STATUS_V2
public extension DeveloperPortal {
    private func nrgGrandSlamClientInfo(_ source: String) -> String { source }
    func sendAuthenticationRequest() {
        let headers = ["X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)]
    }
    private func makeTwoFactorAuthRequest() {
        let headers = [
            "Content-Type": "application/x-plist",
            "User-Agent": h.developerServices.userAgent,
            "X-MMe-Client-Info": a.clientInfo,
            "X-Apple-I-MD": a.oneTimePassword,
            "X-Mme-Device-Id": a.deviceID
        ]
    }
}
'''

class NRGClientConsistencyTests(unittest.TestCase):
    def test_2fa_matches_srp_without_migrating_anisette(self):
        after = patch.transform(FIXTURE)
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)', after)
        self.assertEqual(after.count('"X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)'), 2)
        self.assertIn('"X-Apple-I-MD": a.oneTimePassword', after)
        self.assertIn('"X-Mme-Device-Id": a.deviceID', after)
        self.assertNotIn('ani.jkcoxson.com', after)

    def test_idempotent(self):
        once = patch.transform(FIXTURE)
        self.assertEqual(patch.transform(once), once)

    def test_pin_guard(self):
        with self.assertRaises(ValueError):
            patch.transform(FIXTURE.replace('NRG_GSA_HTTP_STATUS_V2', 'UNKNOWN'))

    def test_drift_guard(self):
        with self.assertRaises(ValueError):
            patch.transform(FIXTURE.replace('"X-MMe-Client-Info": a.clientInfo,', '"X-MMe-Client-Info": other,'))

    def test_partial_guard(self):
        with self.assertRaises(ValueError):
            patch.transform(FIXTURE + '// NRG_GSA_CLIENT_IDENTITY_V3')

if __name__ == '__main__':
    unittest.main()

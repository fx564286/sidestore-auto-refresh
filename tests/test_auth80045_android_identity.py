import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Auth80045IdentityTest(unittest.TestCase):
    def test_grandslam_and_2fa_share_android_identity(self):
        text = (ROOT / "scripts/patch_nrg_gsa_auth.py").read_text()
        other = (ROOT / "scripts/patch_nrg_gsa_client_v3.py").read_text()
        android = "<Pixel 7> <Android;14;UQ1A.240205.002> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
        self.assertIn(android, text)
        self.assertNotIn("<PC> <Windows;6.2(0,0);9200>", text)
        self.assertNotIn("return original",text)
        self.assertIn("NRG_GSA_80045_IDENTITY_V2",text)
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo)', text)
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)', other)
        self.assertIn("NRG_GSA_CLIENT_IDENTITY_V3", other)


if __name__ == "__main__":
    unittest.main()

import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"scripts/scarlet_v188_apple_profile_reconcile.py"
spec=importlib.util.spec_from_file_location("scarlet_apple_reconcile",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def profile(group=True,apple=True,local=True,live=True):
    return {"group_ok":group,"live":live,"bundle_ok":True,"device":True,
            "apple_matches":["existing-P12"] if apple else [],
            "profile_matches":["existing-P12"] if local else []}

class AppGroupTest(unittest.TestCase):
    def test_all_four_authorized(self):
        s=module.authorization_identities(profile())
        self.assertEqual(s,{"existing-P12"})
        self.assertTrue(module.common_signing_identity([s]*4))
    def test_missing_group_blocks(self):
        self.assertFalse(module.authorization_identities(profile(group=False)))
    def test_missing_server_cert_blocks(self):
        self.assertFalse(module.authorization_identities(profile(apple=False)))
    def test_missing_profile_cert_blocks(self):
        self.assertFalse(module.authorization_identities(profile(local=False)))
    def test_expired_blocks(self):
        self.assertFalse(module.authorization_identities(profile(live=False)))
    def test_mixed_certificates_block(self):
        self.assertFalse(module.common_signing_identity([
            {"existing-P12"},{"existing-P12"},{"existing-P12"},{"renewed-PEM-keypair"}]))
    def test_incomplete_profiles_block(self):
        self.assertFalse(module.common_signing_identity([{"existing-P12"}]*3))

if __name__=="__main__":
    unittest.main()

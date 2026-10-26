"""V122: explicit server-scoped one-shot V3 ADI recovery, no destructive legacy edits."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v122",ROOT/"scripts/patch_v122_scoped_adi_reprovision.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class Tests(unittest.TestCase):
    def test_provider_transform_idempotent(self):
        sample="import Foundation\n// SCARLET_V120_ANISETTE_ROUTE\n"+p.ANCHOR
        once=p.transform_provider(sample)
        self.assertEqual(p.transform_provider(once),once)
        self.assertIn("action=one_shot_in_memory_provision",once)
        self.assertIn("original_preserved=true",once)
        self.assertIn("return freshHeaders",once)
    def test_keychain_transform_idempotent(self):
        s="import Foundation\n"+p.KEYCHAIN_ANCHOR
        once=p.transform_keychain(s)
        self.assertEqual(p.transform_keychain(once),once)
        self.assertIn('key: "scarletV122SideStoreAdiPb"',once)
        self.assertIn('key: "scarletV122MacAdiPb"',once)
        self.assertEqual(once.count('key: "adiPb"'),1)
    def test_strict_recovery_only_for_verified_v121_failure(self):
        s=p.ADDITION
        self.assertIn("UserDefaults.standard.disableAnisetteRotation",s)
        self.assertIn("v122Host == \"new.ani.sidestore.io\"",s)
        self.assertIn("v122Host == \"mac-ani.jkcoxson.com\"",s)
        self.assertIn('case .badServerResponse(let http, let payload)',s)
        self.assertIn('http == 200',s)
        self.assertIn('payload.hasPrefix("V3 get_headers rejected")',s)
        self.assertIn("existingAdiBlob: nil",s)
        self.assertIn("legacy_preserved=true",s)
        self.assertIn("Keychain.shared.scarletV122SideStoreAdiPb == encoded",s)
        self.assertNotIn("Keychain.shared.adiPb =",s)
        self.assertNotIn("AnisetteConfigManager.shared.anisetteAdiBlob =",s)
        self.assertNotIn("SecItemDelete",s)
    def test_anchor_drift_rejected(self):
        with self.assertRaisesRegex(ValueError,"unexpected"):
            p.transform_provider("broken")
        with self.assertRaisesRegex(ValueError,"unexpected"):
            p.transform_keychain("broken")
if __name__=="__main__":
    unittest.main()

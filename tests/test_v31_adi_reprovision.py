"""V31: verified one-time recovery for native ADI -45061.

This suite runs against the exact pinned SideStore source, then applies the
patch twice in-memory. No credential material is needed to exercise it.
"""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/patch_v31_adi_45061.py"
SOURCE=Path(os.environ.get("SIDESTORE_TEST_SOURCE", str(ROOT/"work/EmbeddedSideStore")))
TARGET=SOURCE/"SideStore/Core/Anisette/OnDeviceAnisetteManager.swift"

spec=importlib.util.spec_from_file_location("v31_adi_patch", SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class V31ADIRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not TARGET.is_file():
            raise AssertionError(f"Pinned SideStore source not found: {TARGET}")
        cls.source=TARGET.read_text()

    def test_exact_pinned_source_patch_is_idempotent(self):
        first=module.patch(self.source)
        second=module.patch(first)
        self.assertEqual(first,second)
        self.assertEqual(first.count(module.MARKER),1)
        self.assertNotEqual(first,self.source)
        self.assertIn("import AnisetteKit",first)

    def test_recovery_requires_typed_native_minus45061_and_old_blob(self):
        s=module.patch(self.source)
        self.assertIn("catch let originalError as AnisetteKit.AnisetteError",s)
        self.assertIn("case .adiError(let errorCode, _) = originalError",s)
        self.assertIn("errorCode == -45061",s)
        self.assertIn("let oldAdiPbData = existingAdiPbData, !oldAdiPbData.isEmpty",s)
        self.assertNotIn("if (originalError as NSError).code == -45061",s)

    def test_at_most_one_reprovision_with_same_identifier(self):
        s=module.patch(self.source)
        start=s.index("NRG_V31_ADI_45061_REPROVISION_V1")
        stop=s.index('return recoveredData',start)
        recovery=s[start:stop]
        self.assertEqual(recovery.count('existingAdiBlob: nil'),1)
        self.assertGreaterEqual(recovery.count('identifier: identifierUUID'),2)
        self.assertEqual(recovery.count('state=committed'),1)
        self.assertIn('guard let recoveredBlob, !recoveredBlob.isEmpty else {',recovery)

    def test_no_destructive_credential_certificate_or_pairing_changes(self):
        s=module.patch(self.source)
        start=s.index("NRG_V31_ADI_45061_REPROVISION_V1")
        stop=s.index('return recoveredData',start)
        recovery=s[start:stop]
        for forbidden in ("signOut()", "clearSignInInfo", "clearActiveCertificate",
                          "removeItem(", "SecItemDelete", "resetToDefaults()",
                          "resetAdi", "idevicepair", "UserDefaults.standard.remove"):
            self.assertNotIn(forbidden,recovery,forbidden)
        self.assertIn('AnisetteConfigManager.shared.anisetteAdiBlob = newValue',recovery)
        self.assertIn('AnisetteConfigManager.shared.anisetteAdiBlob == newValue',recovery)
        self.assertIn('AnisetteConfigManager.shared.anisetteAdiBlob = oldAdiPbData.base64EncodedString()',recovery)
        self.assertIn("previousBlob=preserved",recovery)
        self.assertNotIn('String(describing: originalError)',recovery)

    def test_unexpected_source_fails_closed(self):
        with self.assertRaises(ValueError):
            module.patch(self.source.replace('existingAdiBlob: existingAdiPbData,','existingAdiBlob: nil,'))

if __name__=="__main__":
    unittest.main()

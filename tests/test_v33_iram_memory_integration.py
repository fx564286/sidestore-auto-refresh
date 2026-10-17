"""V33 integrates the *feature* of iRAM+ without bundling its app or credentials.

Apple's signed profile is the authority, not the success of a portal request.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("SIDESTORE_TEST_SOURCE", ROOT/"work/EmbeddedSideStore"))
SIDESIGN = ROOT/"scripts/patch_v33_sidesign_memory.py"
SIDESTORE = ROOT/"scripts/patch_v33_sidestore_memory.py"

def load(path):
    spec=importlib.util.spec_from_file_location(path.stem,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class V33MemoryIntegrationTests(unittest.TestCase):
    def test_exact_pinned_sidesign_capability_patch(self):
        patcher=load(SIDESIGN)
        self.assertTrue(patcher.PATCH.is_file())
        patch=patcher.PATCH.read_text()
        self.assertIn('INCREASED_MEMORY_LIMIT',patch)
        self.assertIn('bundleIdCapabilities',patch)
        self.assertIn('request.httpMethod = "PATCH"',patch)
        self.assertIn('sendServicesBodyRequest',patch)
        self.assertIn('.increasedMemoryLimit',patch)
        self.assertNotIn('Password=',patch)
        self.assertNotIn('SecItemDelete',patch)

        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in patcher.EXPECTED:
                target=root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(subprocess.check_output(
                    ['git','-C',str(SOURCE/'Dependencies/SideSign'),
                     'show',patcher.PIN+':'+name]))
                self.assertEqual(patcher.sha(target),patcher.EXPECTED[name][0])
            subprocess.run(['git','apply','--check',str(patcher.PATCH)],
                           cwd=root,check=True)
            subprocess.run(['git','apply',str(patcher.PATCH)],
                           cwd=root,check=True)
            patcher.verify(root)
            for name,(_,after) in patcher.EXPECTED.items():
                self.assertEqual(patcher.sha(root/name),after)

    def test_default_memory_and_signed_profile_are_distinct(self):
        patcher=load(SIDESTORE)
        original=subprocess.check_output(
            ['git','-C',str(SOURCE),
             'show','ff25922e5c13ccfafd83bda5092910d848ebd409:'+str(patcher.TARGET)],
            text=True)
        generated=patcher.patch(original)
        self.assertNotEqual(original,generated)
        self.assertEqual(generated,patcher.patch(generated))
        self.assertEqual(generated.count(patcher.MARKER),1)
        self.assertIn('entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] == nil',generated)
        self.assertIn('entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] = true',generated)
        self.assertIn('let memoryGranted = profile.entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] as? Bool == true',generated)
        self.assertIn('[NRG_MEMORY_PROFILE] increasedMemoryGranted=',generated)
        self.assertNotIn('entitlements[ALTEntitlement.extendedVirtualAddressing.rawValue] = true',generated)

    def test_no_second_apple_account_login_or_credential_wipe(self):
        source=SIDESTORE.read_text()+SIDESIGN.read_text()
        for forbidden in ['signOut()', 'clearKeychain()', 'SecItemDelete(', 'revokeCertificate(',
                          'appleAccountPassword =', 'clearSignInInfo(']:
            self.assertNotIn(forbidden,source)

if __name__ == "__main__":
    unittest.main()

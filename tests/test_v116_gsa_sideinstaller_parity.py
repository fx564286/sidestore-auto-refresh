"""V116 offline regression: SideInstaller Mac identity / header compatibility."""
import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
patch = load('patch_v116_sideinstaller_gsa')
gsa = (ROOT / 'scripts/patch_nrg_gsa_auth.py').read_text(encoding='utf8')

def v115_helper():
    tree = ast.parse(gsa)
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'patch_side_sign')
    return next(n.value.value for n in ast.walk(func)
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'helper' for t in n.targets)
                and isinstance(n.value, ast.Constant))

def patched_fixture():
    return ('''NRG_GSA_RECOVERY_V1
NRG_GSA_HTTP_STATUS_V2
NRG_GSA_CLIENT_IDENTITY_V3
public extension DeveloperPortal {
''' + v115_helper() +
    '''    func sendAuthenticationRequest() {
        let headers: [String: String] = [
            "X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo),
''' + patch.OLD_GSA_ACCEPT + '''
        ]
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
''' + patch.OLD_GSA_EXTRA + '''
    }
    private func makeTwoFactorAuthRequest() {
        let headers: [String: String] = [
''' + patch.OLD_2FA_UA + '\n' + patch.OLD_2FA_XCODE + '''
            "X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo),
        ]
    }
}
''')

class V116ParityTests(unittest.TestCase):
    def test_transform_is_idempotent_and_fail_closed(self):
        old = patched_fixture()
        changed = patch.transform(old)
        self.assertEqual(patch.transform(changed), changed)
        self.assertEqual(changed.count(patch.MARKER), 2)
        self.assertIn('nrgGSAIsLegacyMac(original)', changed)
        self.assertIn('"Accept": "text/x-xml-plist"', changed)
        self.assertIn('nrgGrandSlamUserAgent(a.clientInfo', changed)
        self.assertIn('"X-Xcode-Version": "14.2 (14C18)"', changed)
        self.assertNotIn(patch.OLD_GSA_EXTRA, changed)
        self.assertNotIn(patch.OLD_2FA_XCODE, changed)
        with self.assertRaisesRegex(ValueError, 'pinned source mismatch'):
            patch.transform(old.replace(patch.OLD_GSA_UA, 'unrelatedUserAgent', 1))
        with self.assertRaisesRegex(ValueError, 'corrupted marker'):
            patch.transform(changed.replace('"text/x-xml-plist"', '"*/*"', 1))

    def test_legacy_mac_is_normalized_but_modern_mac_and_windows_preserved(self):
        compiler = shutil.which('swiftc')
        if not compiler:
            self.skipTest('swiftc not available')
        changed = patch.transform(patched_fixture())
        before = changed.index('    private func nrgGrandSlamClientInfo(')
        after = changed.index('    func sendAuthenticationRequest()')
        helper = changed[before:after]
        swift = '''import Foundation
struct V116 {
''' + helper + '''
func validate() {
    let old = "<MacBookPro13,3> <Mac OS X;10.12.6;16G29> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    let modern = "<MacBookPro18,3> <macOS;26.6;25F84> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    let win = "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"
    let android = "<Pixel 7> <Android;14> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    let malformedMac = "<MacBookPro13,3> <Mac OS X;10.12.6;16G29> <not-authkit>"
    precondition(nrgGSAIsLegacyMac(old))
    precondition(nrgGSAIsLegacyMac(malformedMac))
    precondition(nrgGrandSlamUsesWindowsCompatibility(malformedMac))
    precondition(nrgGrandSlamUserAgent(malformedMac,fallback:"Xcode") == "akd/1.0 CFNetwork/808.1.4")
    precondition(nrgGrandSlamClientInfo(old) == modern)
    precondition(nrgGrandSlamClientInfo(modern) == modern)
    precondition(nrgGrandSlamClientInfo(win) == win)
    precondition(nrgGrandSlamClientInfo(android) == android)
    precondition(!nrgGSAIsLegacyMac(modern))
    precondition(nrgGrandSlamUsesWindowsCompatibility(win))
    precondition(!nrgGrandSlamUsesWindowsCompatibility(old))
    precondition(nrgGrandSlamUserAgent(old,fallback:"Xcode") == "AuthKit/1 (Macintosh; OS X 26.6) (com.apple.akd/1.0)")
    precondition(nrgGrandSlamUserAgent(win,fallback:"Xcode") == "akd/1.0 CFNetwork/808.1.4")
    precondition(nrgGrandSlamUserAgent(modern,fallback:"Xcode") == "Xcode")
}
}
V116().validate()
'''
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'main.swift'
            binary = Path(folder)/'check-v116'
            source.write_text(swift,encoding='utf8')
            subprocess.run([compiler, str(source), '-o', str(binary)], capture_output=True, text=True, check=True, timeout=60)
            subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=15)

    def test_no_account_or_adi_state_mutation(self):
        body = (ROOT / 'scripts/patch_v116_sideinstaller_gsa.py').read_text()
        self.assertIn('SideInstaller', body)
        self.assertNotIn('SecItemDelete(', patch.NEW_GSA_EXTRA + patch.LEGACY_MAC_HELPER)
        self.assertNotIn('AuthManager.shared.signOut()', patch.NEW_GSA_EXTRA + patch.LEGACY_MAC_HELPER)
        self.assertNotIn('adiPb =', patch.NEW_GSA_EXTRA + patch.LEGACY_MAC_HELPER)
        self.assertNotIn('anisetteProvider =', patch.NEW_GSA_EXTRA + patch.LEGACY_MAC_HELPER)

if __name__ == '__main__':
    unittest.main()

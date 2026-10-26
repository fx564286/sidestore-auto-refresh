"""V118 2FA gateway tests: require real Apple challenge, never synthesize one."""
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

v116 = load("patch_v116_sideinstaller_gsa")
v118 = load("patch_v118_2fa_gateway")

def v116_fixture():
    # Use the exact pinned V116 test fixture, with the original 2FA
    # Content-Type header that the source patch fixture omitted.
    from test_v116_gsa_sideinstaller_parity import patched_fixture
    source = patched_fixture().replace(v116.OLD_2FA_UA,
        '            "Content-Type": "application/x-plist",\n' + v116.OLD_2FA_UA, 1)
    return v116.transform(source)

class V118GatewayTests(unittest.TestCase):
    def test_non_destructive_idempotence(self):
        old = v116_fixture()
        new = v118.transform(old)
        self.assertEqual(new, v118.transform(new))
        self.assertEqual(new.count(v118.MARK), 1)
        self.assertIn('<Mac15,7> <macOS;27.0;26A5378j>', new)
        self.assertIn('"Connection": "close"', new)
        self.assertEqual(new.count('"Connection": "close"'), 1)
        for forbidden in ("AuthManager.shared.signOut()", "SecItemDelete(", "resetAnisette",
                          "adiPb =", "verificationHandler(.verificationCode", "autoSubmitCode"):
            self.assertNotIn(forbidden, v118.NEW_MAC + v118.NEW_UA + v118.NEW_ACCEPT)
        self.assertNotIn("SCARLET_V118_2FA_GATEWAY", old)
        with self.assertRaisesRegex(ValueError, "expected exactly one"):
            v118.transform(old.replace(v118.OLD_ACCEPT, '"Accept": "anything",'))
        with self.assertRaisesRegex(ValueError, "partial overlay"):
            v118.transform(new.replace(v118.NEW_ACCEPT, v118.OLD_ACCEPT))

    def test_mac_and_windows_profiles_match_auth_and_2fa(self):
        swiftc = shutil.which("swiftc")
        if not swiftc:
            self.skipTest("Swift unavailable on non-macOS developer runner")
        patched = v118.transform(v116_fixture())
        a = patched.index("    private func nrgGrandSlamClientInfo(")
        b = patched.index("    func sendAuthenticationRequest()", a)
        helper = patched[a:b]
        program = '''import Foundation
struct Probe {
''' + helper + '''
func run() {
 let original = "<MacBookPro18,3> <macOS;13.1;22C65> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
 let old = "<MacBookPro13,3> <Mac OS X;10.12.6;16G29> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
 let win = "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"
 let current = "<Mac15,7> <macOS;27.0;26A5378j> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
 precondition(nrgGrandSlamClientInfo(original) == current)
 precondition(nrgGrandSlamClientInfo(old) == current)
 precondition(nrgGrandSlamClientInfo(current) == current)
 precondition(nrgGrandSlamClientInfo(win) == win)
 precondition(nrgGrandSlamUserAgent(original, fallback:"Xcode") == "akd/1.0 CFNetwork/808.1.4")
 precondition(nrgGrandSlamUserAgent(win, fallback:"Xcode") == "akd/1.0 CFNetwork/808.1.4")
}
}
Probe().run()
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "main.swift"
            exe = Path(folder) / "gateway-check"
            path.write_text(program)
            subprocess.run([swiftc, str(path), "-o", str(exe)], text=True,
                capture_output=True, check=True, timeout=60)
            subprocess.run([str(exe)], text=True, capture_output=True, check=True, timeout=10)

if __name__ == "__main__":
    unittest.main()

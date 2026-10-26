"""Scarlet V115: GrandSlam/2FA headers must follow the same effective profile.

Offline tests only. Never perform Apple auth, read credentials, or alter ADI.
"""
import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GSA = (ROOT / "scripts/patch_nrg_gsa_auth.py").read_text(encoding="utf-8")
V3_PATH = ROOT / "scripts/patch_nrg_gsa_client_v3.py"
V3 = V3_PATH.read_text(encoding="utf-8")


class ProfileCoherence(unittest.TestCase):
    def test_gsa_uses_native_headers_unless_effective_profile_windows(self):
        self.assertIn("SCARLET_V115_GSA_PROFILE_COHERENCE", GSA)
        self.assertIn('"User-Agent": nrgGrandSlamUsesWindowsCompatibility(anisetteData.clientInfo)', GSA)
        self.assertIn("if nrgGrandSlamUsesWindowsCompatibility(anisetteData.clientInfo) {", GSA)
        self.assertIn('request.setValue("14.2 (14C18)", forHTTPHeaderField: "X-Xcode-Version")', GSA)
        self.assertIn('request.setValue("com.apple.gs.xcode.auth", forHTTPHeaderField: "X-Apple-App-Info")', GSA)
        self.assertNotIn('            "User-Agent": "akd/1.0 CFNetwork/808.1.4",', GSA)
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo)', GSA)
        self.assertNotIn("AuthManager.shared.signOut()", GSA.split("def patch_signin")[0])

    def test_2fa_transform_is_conditional_and_idempotent(self):
        self.assertIn('"User-Agent": nrgGrandSlamUsesWindowsCompatibility(a.clientInfo)', V3)
        self.assertIn('"X-Xcode-Version": nrgGrandSlamUsesWindowsCompatibility(a.clientInfo)', V3)
        spec = importlib.util.spec_from_file_location("v115_2fa", V3_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fixture = (
            "NRG_GSA_RECOVERY_V1 NRG_GSA_HTTP_STATUS_V2 nrgGrandSlamClientInfo\n"
            "    private func makeTwoFactorAuthRequest(\n"
            '            "User-Agent": h.developerServices.userAgent,\n'
            '            "X-Xcode-Version": context.xcodeVersion,\n'
            '            "X-MMe-Client-Info": a.clientInfo,\n'
        )
        applied = mod.transform(fixture)
        self.assertEqual(mod.transform(applied), applied)
        self.assertIn("SCARLET_V115_GSA_PROFILE_COHERENCE", applied)
        self.assertNotIn('"User-Agent": h.developerServices.userAgent,', applied)

    def test_swift_profile_family_selection(self):
        compiler = shutil.which("swiftc")
        if compiler is None:
            self.skipTest("swiftc unavailable")
        tree = ast.parse(GSA)
        patch = next(n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == "patch_side_sign")
        helper = next(n.value.value for n in ast.walk(patch)
                      if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "helper" for t in n.targets)
                      and isinstance(n.value, ast.Constant))
        swift = '''import Foundation
struct Test {
''' + helper + '''
func verify() {
    let mac = "<MacBookPro> <Mac OS X;10.14.6> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    let win = "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"
    let android = "<Pixel 7> <Android;14> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    precondition(nrgGrandSlamClientInfo(mac) == mac)
    precondition(!nrgGrandSlamUsesWindowsCompatibility(mac))
    precondition(nrgGrandSlamUsesWindowsCompatibility(win))
    precondition(nrgGrandSlamClientInfo(android) == android)
    precondition(!nrgGrandSlamUsesWindowsCompatibility(android))
    precondition(nrgGrandSlamUsesWindowsCompatibility("unknown"))
}
}
Test().verify()
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"main.swift"
            binary = Path(tmp)/"v115"
            src.write_text(swift, encoding="utf-8")
            subprocess.run([compiler, str(src), "-o", str(binary)],
                           capture_output=True, text=True, check=True, timeout=60)
            subprocess.run([str(binary)], capture_output=True,
                           text=True, check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()

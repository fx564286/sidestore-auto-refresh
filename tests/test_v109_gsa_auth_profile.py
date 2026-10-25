"""V109 source integrity: Android profile + scoped -80045 UI."""
import importlib.util
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
guidance=load("patch_v109_gsa_auth_guidance")
GSA=(ROOT/"scripts/patch_nrg_gsa_auth.py").read_text()

class ProfileTests(unittest.TestCase):
    def test_profile_families_preserved(self):
        self.assertIn("SCARLET_V109_GSA_PROFILE_PRESERVATION",GSA)
        self.assertIn('original.contains("<Android;")',GSA)
        self.assertIn('original.contains("<Windows;")',GSA)
        self.assertIn('original.contains("<macOS;")',GSA)
        self.assertIn('original.contains("<Mac OS X;")',GSA)
        self.assertIn('hasAuthKit && original.contains("<Android;")',GSA)
        self.assertIn("com.apple.iTunes/12.12.4.1",GSA)
        self.assertNotIn("anisetteAdiBlob =",GSA)

    def test_profile_helper_executes_on_macos_swift(self):
        compiler=shutil.which("swiftc")
        if not compiler:
            return
        tree=ast.parse(GSA)
        func=next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name=="patch_side_sign")
        helper=next(n.value.value for n in ast.walk(func)
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=="helper" for t in n.targets)
                    and isinstance(n.value,ast.Constant))
        profiles=[
            "<Pixel 7> <Android;14;build> <com.apple.AuthKit/1 (com.apple.akd/1.0)>",
            "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>",
            "<MacBookPro> <macOS;13.1> <com.apple.AuthKit/1 (com.apple.akd/1.0)>",
            "<MacBookPro> <Mac OS X;10.14.6> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
        ]
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"main.swift"
            exe=Path(temp)/"profile-check"
            body="import Foundation\\nstruct ProfileCheck {\\n"+helper+"\\nfunc run() {\\n"
            for line in profiles:
                body+='precondition(nrgGrandSlamClientInfo("'+line+'") == "'+line+'")\\n'
            body+='precondition(nrgGrandSlamClientInfo("invalid").contains("<Windows;"))\\n'
            body+='print("V109_PROFILE_SWIFT_PASS")\\n}\\n}\\nProfileCheck().run()\\n'
            p.write_text(body)
            subprocess.run([compiler,str(p),"-o",str(exe)],capture_output=True,
                           text=True,check=True,timeout=60)
            result=subprocess.run([str(exe)],capture_output=True,
                                  text=True,check=True,timeout=10)
            self.assertIn("V109_PROFILE_SWIFT_PASS",result.stdout)

    def test_guidance_handler_and_non_destructive_policy(self):
        before=("import SideSign\n"
                "            case .failure(let error):\n"
                "                completionHandler(.failure(error))\n")
        after=guidance.patch(before)
        self.assertEqual(guidance.patch(after),after)
        self.assertIn('code == -80045',after)
        self.assertIn("NSLocalizedDescriptionKey",after)
        self.assertIn("User Customizations",after)
        for forbidden in ("AuthManager.shared.signOut()", "adiPb =",
                          "session.data(for:", "verificationCode("):
            self.assertNotIn(forbidden,after)
        with self.assertRaisesRegex(ValueError,"pinned"):
            guidance.patch("wrong target")
        with self.assertRaisesRegex(ValueError,"partial"):
            guidance.patch(after.replace("code == -80045","code == 0"))

    def test_same_policy_srp_and_2fa(self):
        other=(ROOT/"scripts/patch_nrg_gsa_client_v3.py").read_text()
        self.assertIn('nrgGrandSlamClientInfo(anisetteData.clientInfo)',GSA)
        self.assertIn('nrgGrandSlamClientInfo(a.clientInfo)',other)

if __name__=="__main__":
    unittest.main()

"""V121: strict V3 diagnostics must preserve provisioning and distinguish failures."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v121",ROOT/"scripts/patch_v121_anisette_v3_trace.py")
v121=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v121)

class V121Tests(unittest.TestCase):
    def test_strict_pinned_source_insertion_idempotent(self):
        base="import Foundation\n"+v121.ANCHOR+"        // legacy path remains unchanged\n"
        patched=v121.transform(base)
        self.assertEqual(patched,v121.transform(patched))
        self.assertEqual(patched.count(v121.ANCHOR),1)
        self.assertIn("let v121KnownV3Hosts: Set<String>",patched)
        self.assertIn("return v121Headers",patched)
        self.assertIn("// legacy path remains unchanged",patched)
    def test_error_status_and_v1_fallback_gates(self):
        s=v121.INJECT
        self.assertIn("if !adiPb.isEmpty && v121KnownV3Hosts.contains",s)
        self.assertIn("stage=v3_get_headers http=",s)
        self.assertIn("stage=transport failed=true code=",s)
        self.assertIn("stage=get_headers result=rejected",s)
        self.assertIn("throw AnisetteError.badServerResponse",s)
        self.assertIn("throw AnisetteError.invalidAnisetteData",s)
        self.assertIn("new.ani.sidestore.io",s)
        self.assertIn("mac-ani.jkcoxson.com",s)
    def test_do_not_log_secrets_or_modify_adi(self):
        s=v121.INJECT
        for forbidden in ('print(cleanIdentifier)','print(v121JSON)','print(adiPb)','print(v121Data)','SecItemDelete','removeObject(forKey: "adiPb")','anisetteAdiBlob =','"password"'):
            self.assertNotIn(forbidden,s)
        self.assertIn("body intentionally not logged",s)
    def test_unexpected_source_or_partial_refused(self):
        with self.assertRaisesRegex(ValueError,"unexpected pinned"):
            v121.transform("import Foundation\n")
        with self.assertRaisesRegex(ValueError,"partial"):
            v121.transform(v121.MARK+"\n")
    def test_cert_screen_message_does_not_imply_keychain_loss(self):
        s=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text(encoding="utf-8")
        self.assertIn("USB import bundle is not staged",s)
        self.assertIn("does not prove a signing identity is absent from Keychain",s)
        self.assertNotIn("USB signing files not found in NRG Documents. Run the USB bootstrap again.",s)

if __name__=="__main__":
    unittest.main()

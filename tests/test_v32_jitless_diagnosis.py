"""V32 JIT-Less: separate trusted local X509 metadata from online OCSP."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PIN = "12377cf3b91d51739a33f14a302e5f522b238593"
SOURCE = Path(os.environ.get("LIVE_CONTAINER_TEST_SOURCE", ROOT / "work/LiveContainer"))
SCRIPT = ROOT / "scripts/patch_v32_jitless_diagnosis.py"

spec=importlib.util.spec_from_file_location("v32_jitless", SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class V32JITLessDiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=subprocess.check_output(
            ["git","-C",str(SOURCE),"show",f"{PIN}:{mod.TARGET.as_posix()}"],
            text=True)
        cls.code=mod.patch(cls.original)

    def test_pinned_patch_idempotent(self):
        self.assertNotEqual(self.original,self.code)
        self.assertEqual(mod.patch(self.code),self.code)
        self.assertEqual(self.code.count(mod.MARKER),1)

    def test_local_facts_do_not_claim_online_revocation_status(self):
        s=self.code
        self.assertIn("LCUtils.certificateFacts(withKeyData: data, password: password)",s)
        self.assertIn('certTeamId = facts["teamIdentifier"]',s)
        self.assertIn('offlineCertificateExpiration = facts["notAfter"]',s)
        self.assertIn('certificateValidateUntil = offlineCertificateExpiration',s)
        self.assertIn('LCUtils.validateCertificate { status, date, ou, error in',s)
        self.assertIn("certificateStatus = 2",s)
        self.assertIn('certificateValidationIssue = Self.safeOCSPFailure(error)',s)
        self.assertNotIn("certificateStatus = certificateLocalParsed ? 0",s)
        self.assertNotIn('certificateStatus = 0\n',s)
        self.assertIn("DispatchQueue.main.async",s)

    def test_diagnostic_not_secrets_and_uses_safe_fixed_explanations(self):
        s=self.code
        self.assertIn('Text("PKCS#12 Parsing")',s)
        self.assertIn('Text("OCSP Verification")',s)
        self.assertIn("private static func safeOCSPFailure",s)
        self.assertNotIn('Text(nativeError)',s)
        self.assertNotIn('errorInfo = error.loc',s)
        self.assertNotIn("SecPKCS12Import",s)
        self.assertNotIn("SecItemDelete",s)
        self.assertNotIn("clearSignInInfo",s)

    def test_unexpected_source_fails_closed(self):
        with self.assertRaises(ValueError):
            mod.patch(self.original.replace('@State var certTeamId : String?', '@State var teamId : String?'))

if __name__=="__main__":
    unittest.main()

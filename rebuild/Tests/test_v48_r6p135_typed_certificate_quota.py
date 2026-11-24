"""R135 exact typed SideSign quota classification, no certificate mutation."""
from pathlib import Path
import unittest

R = Path(__file__).resolve().parents[1]
S = (R / "integration/ScarletGuestSavedAccounts.swift.txt").read_text()

class TypedCertificateQuota(unittest.TestCase):
    def test_typed_sidesign_case_precedes_legacy_domain_code(self):
        self.assertIn("private static func isCertificateQuotaError", S)
        helper = S.split("private static func isCertificateQuotaError", 1)[1].split(
            "private static func portalFailure", 1)[0]
        self.assertIn("error as? DeveloperPortalError", helper)
        self.assertIn("case .tooManyCertificates = portalError", helper)
        self.assertIn('native.domain == "ALTAppleAPIErrorDomain"', helper)
        self.assertIn("native.code == 35 || native.code == 7460", helper)

    def test_actual_create_catch_and_wire_receipt_use_typed_helper(self):
        self.assertIn("let fallback = isCertificateQuotaError(error)", S)
        self.assertIn("isCertificateQuotaError(error) || isCertificateQuotaError(deepest)", S)
        self.assertIn('"SideSign.DeveloperPortalError": return "appleapi"', S)
        self.assertNotIn("original.code == 7460 || deepest.code == 7460", S)
        self.assertNotIn("revokeCertificate(", S)
        self.assertIn("if forceNew && previouslyRegistered.contains(", S)

if __name__ == "__main__":
    unittest.main()

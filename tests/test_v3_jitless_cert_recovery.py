from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts/patch_v3_unified_shell.py"
SERVICE = ROOT / "scripts/templates/v3_sidestore_service.swift"

class AutoImportTests(unittest.TestCase):
    def test_automatic_action_never_opens_file_picker(self):
        source = PATCH.read_text()
        section = source.split("        replacement = ",1)[1].split("        text = text[:start]",1)[0]
        self.assertIn('operation: "certExportActive"',section)
        self.assertIn('operation: "healthSnapshot"',section)
        self.assertNotIn("v3RecoverSideStoreCertificateFromP12",section)
        self.assertNotIn("certificateImportFileAlert.open",section)
        self.assertNotIn("certificateImportPasswordAlert.open",section)

    def test_portal_team_not_required_for_local_active_cert(self):
        source = SERVICE.read_text()
        section = source.split('case "certExportActive":',1)[1].split('case "certImport":',1)[0]
        self.assertIn("V3_JITLESS_AUTO_IMPORT_V17",section)
        self.assertNotIn("authSnapshot?.isAuthenticated",section)
        self.assertNotIn("teamRecord.account?",section)
        self.assertIn("CertificateManager.shared.activeCertificate",section)
        self.assertNotIn("createCertificate(",section)
        self.assertNotIn("revokeCertificate(",section)

    def test_lost_active_identity_self_heals_only_with_one_valid_local_cert(self):
        source = SERVICE.read_text()
        block = source.split('case "certExportActive":', 1)[1].split('case "certImport":', 1)[0]
        self.assertIn("V18_LOCAL_CERT_SELF_HEAL", block)
        self.assertIn("manager.loadActiveCertificate()", block)
        self.assertIn("manager.getAllLocalCertificates()", block)
        self.assertIn("usable.count == 1", block)
        self.assertIn("manager.setActiveCertificate(usable[0])", block)
        self.assertNotIn("createCertificate(", block)
        self.assertNotIn("revokeCertificate(", block)
        self.assertNotIn("usable.first", block)

    def test_one_time_usb_recovery_for_empty_keystore(self):
        service = SERVICE.read_text()
        block = service.split('case "certExportActive":', 1)[1].split('case "certImport":', 1)[0]
        for required in ("V19_USB_ONCE_BOOTSTRAP", "NRG-OneTimeCertificate.p12",
                         "NRG-OneTimeCertificate.password",
                         "CertificateManager.parse(", "manager.setActiveCertificate(candidate)",
                         "manager.loadActiveCertificate()", "try? fm.removeItem(at: certURL)",
                         "try? fm.removeItem(at: passURL)",
                         "candidate.x509.expiryDate > Date()"):
            self.assertIn(required, block)
        self.assertLess(block.index("V18_LOCAL_CERT_SELF_HEAL"), block.index("V19_USB_ONCE_BOOTSTRAP"))
        self.assertNotIn("createCertificate(", block)
        self.assertNotIn("revokeCertificate(", block)

    def test_manual_still_separate(self):
        source = PATCH.read_text()
        self.assertIn('func importCertificate() async {',source)
        self.assertIn('func importCertificateFromSideStore() async {',source)

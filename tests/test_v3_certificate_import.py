"""Regression checks for NRG SideStore P12 import (no signing secrets in IPA)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "scripts" / "templates"

class SideStoreCertificateImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wire = (ROOT / "v3_wire_contract.swift").read_text()
        cls.service = (ROOT / "v3_sidestore_service.swift").read_text()
        cls.ui = (ROOT / "v3_unified_shell.swift").read_text()

    def test_wire_whitelist_and_one_shot_secret(self):
        self.assertIn('"certImport"', self.wire)
        self.assertIn('"certImport"', self.wire.split('private static let credentialAnswerOperations', 1)[1].split(']', 1)[0])
        self.assertIn('case "certImport":', self.wire)
        self.assertIn('Set(answer.keys) == Set(["password"])', self.wire)

    def test_import_updates_real_signing_keychain(self):
        self.assertIn('case "certImport":', self.service)
        self.assertIn('purpose: "certImport"', self.service)
        self.assertIn('CertificateManager.parse(', self.service)
        self.assertIn('CertificateManager.shared.setActiveCertificate(certificate)', self.service)
        self.assertIn('CertificateManager.shared.loadActiveCertificate()', self.service)
        block = self.service.split('        case "certImport":', 1)[1].split('        case "certSetActive":', 1)[0]
        self.assertNotIn('createCertificate(', block)
        self.assertNotIn('revokeCertificate(', block)
        self.assertNotIn('UserDefaults.standard', block)

    def test_ui_import_is_explicit_and_not_bundled(self):
        self.assertIn('Import SideStore Signing Certificate (.p12 / .pfx)', self.ui)
        self.assertIn('.fileImporter(isPresented: $selectingSigningP12', self.ui)
        self.assertIn('SecureField("P12 password', self.ui)
        self.assertIn('stageSharedFile(data, purpose: "certImport")', self.ui)
        self.assertIn('operation: "certImport"', self.ui)
        self.assertIn('status.discardSharedFile(token)', self.ui)

if __name__ == "__main__":
    unittest.main()

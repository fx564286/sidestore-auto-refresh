"""Regression contract: JIT-Less must recover an absent SideStore signing identity."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts" / "patch_v3_unified_shell.py"
SERVICE = ROOT / "scripts" / "templates" / "v3_sidestore_service.swift"
WIRE = ROOT / "scripts" / "templates" / "v3_wire_contract.swift"
SHARED = ROOT / "scripts" / "templates" / "v3_secret_handoff.swift"


class JITLessCertificateRecoveryTests(unittest.TestCase):
    def test_export_failure_enters_explicit_p12_fallback(self):
        text = PATCH.read_text()
        self.assertIn("V3_JITLESS_P12_RECOVERY_V1", text)
        self.assertIn('if importStage == "certExportActive"', text)
        self.assertIn("await v3RecoverSideStoreCertificateFromP12(requestID: requestID)", text)
        self.assertIn("await certificateImportFileAlert.open()", text)
        self.assertIn("await certificateImportPasswordAlert.open()", text)

    def test_recovery_updates_both_stores_only_after_readback(self):
        text = PATCH.read_text()
        chunk = text.split("private func v3RecoverSideStoreCertificateFromP12", 1)[1].split("\n\n'''", 1)[0]
        for anchor in ('purpose: "certImport"', 'operation: "certImport"',
                       'operation: "healthSnapshot"', 'certificateIdentitySHA256',
                       'V3CertificateImportOwnership.isActive(requestID)',
                       "v3CompleteSideStoreCertificateImport("):
            self.assertIn(anchor, chunk)
        self.assertLess(chunk.index('operation: "certImport"'), chunk.index('operation: "healthSnapshot"'))
        self.assertLess(chunk.index('operation: "healthSnapshot"'), chunk.index('v3CompleteSideStoreCertificateImport('))
        for forbidden in ("revokeCertificate(", "createCertificate(", 'print(password)', "debugLog(password)"):
            self.assertNotIn(forbidden, chunk)

    def test_side_store_import_is_enabled_and_bounded(self):
        service = SERVICE.read_text()
        wire = WIRE.read_text()
        staging = SHARED.read_text()
        self.assertIn('case "certImport":', service)
        self.assertIn("CertificateManager.shared.setActiveCertificate(certificate)", service)
        self.assertIn('case "certImport":', wire)
        self.assertIn('"certImport"', staging)
        self.assertIn("V3SharedFileRecord.discard(token, containerRoot: containerRoot)", PATCH.read_text())


if __name__ == "__main__":
    unittest.main()

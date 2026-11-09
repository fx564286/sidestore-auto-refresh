"""Safe SideStore -> SideInstaller P12 recovery pipeline regression."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PANEL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
class CertificateRecoveryContract(unittest.TestCase):
    def test_sidestore_first_and_explicit_external_fallback(self):
        for s in ("SCARLET_P12_FROM_SIDESTORE",
                  "SCARLET_P12_SIDEINSTALLER_FALLBACK",
                  "SCARLET_P12_IMPORT_FROM_FILES",
                  "sideinstaller://",
                  "ScarletCertificateAutoBridgeRequested",
                  "ScarletCertificateAutoBridgeFinished"):
            self.assertIn(s,PANEL if s!="ScarletCertificateAutoBridgeRequested" else HOST)
        self.assertIn("bridgeExistingSideStoreCertificateIfSafe()",HOST)
        self.assertIn("certificate_bridge_skipped",HOST)

    def test_import_checks_identity_before_mutation_and_reads_back(self):
        for s in ("readiness.canRequestNativeRefresh",
                  "LCSharedUtils.teamIdentifier()",
                  "LCUtils.getCertTeamId(",
                  "actualTeam == archiveTeam",
                  "LCUtils.certificateData() == nil",
                  'LCUtils.appGroupUserDefault.set(archive, forKey: "LCCertificateData")',
                  'LCUtils.certificateData() == archive',
                  'LCSharedUtils.certificatePassword() == password',
                  'UTType(filenameExtension: "p12")',
                  "startAccessingSecurityScopedResource",
                  "pendingP12 = nil",
                  "p12Password = \"\""):
            self.assertIn(s,PANEL)

    def test_no_silent_revoke_or_p12_exfiltration(self):
        for forbidden in ("revokeCertificate", "revokeDevelopmentCert",
                          "URLSession.shared.upload", "base64EncodedString()",
                          'print(p12Password)', "UIPasteboard.general"):
            self.assertNotIn(forbidden,PANEL)
        self.assertNotIn('SCARLET_P12_SIDEINSTALLER_FALLBACK',HOST)
if __name__=="__main__":unittest.main()

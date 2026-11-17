"""P101 regression: expired/mismatched host signer cannot block guest bridge."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / 'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()
BRIDGE = SRC.split('private func bridgeExistingSideStoreCertificateIfSafe()', 1)[1].split(
    'private func ensureOriginalLCGuestBootstrap()', 1)[0]

class ExpiredSignerNeverPreferred(unittest.TestCase):
    def test_p101_distinct_build_and_compiled_marker_gate(self):
        workflow = (ROOT / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
        for marker in ('--host-build-version 3.8.101', 'version="3.8.101"',
                       'Scarlet-Crystal-V48-R6P101-VALID-HOST-SIGNER-UNSIGNED.ipa',
                       'scarlet-v48-r6p101-valid-host-signer-unsigned-20261117',
                       'b"certificate_bridge_replacing_stale_signer"'):
            self.assertIn(marker, workflow)

    def test_existing_stale_signer_does_not_early_return(self):
        self.assertNotIn('guard LCUtils.certificateData() == nil else { return }', BRIDGE)
        self.assertIn('certificate_bridge_replacing_stale_signer', BRIDGE)
        self.assertIn('expired_or_foreign_team_signer', BRIDGE)
        self.assertIn('certificate_bridge_not_persisted', BRIDGE)

    def test_existing_valid_signer_uses_real_installed_host_team(self):
        self.assertIn('verifiedInstalledHostTeam()', BRIDGE)
        self.assertIn('let installedHostTeam = identity.team', BRIDGE)
        self.assertIn('if let existing = LCUtils.certificateData()', BRIDGE)
        self.assertIn('ScarletHostTeamSignerVault.signerIsUsable(', BRIDGE)
        self.assertIn('ScarletHostProvisioningSigner.check(', BRIDGE)
        self.assertIn('== .matched', BRIDGE)

    def test_cert_candidate_must_be_same_host_team_unexpired_and_provisioned(self):
        self.assertIn('certificate_team_mismatch', BRIDGE)
        self.assertIn('certificate_expired', BRIDGE)
        self.assertIn('candidate_not_in_host_profile', BRIDGE)
        self.assertLess(BRIDGE.index('lastReason = "certificate_expired"'),
                        BRIDGE.index('verifiedCertificate = candidate'))

    def test_stale_signer_write_failure_restores_prior_preferences(self):
        for token in ('let priorCert = LCUtils.certificateData()',
                      'let priorPassword = LCSharedUtils.certificatePassword()',
                      'let priorDate = prefs.object(',
                      'prefs.set(priorCert, forKey: "LCCertificateData")',
                      'prefs.set(priorPassword, forKey: "LCCertificatePassword")',
                      'prefs.set(priorDate, forKey: "LCCertificateUpdateDate")'):
            self.assertIn(token, BRIDGE)
        self.assertNotIn('SecItemDelete(', BRIDGE)

    def test_usable_checks_validity_not_cache_timestamp(self):
        VAULT = SRC.split('enum ScarletHostTeamSignerVault {', 1)[1].split(
            '// P93: The signed HOST provisioning profile', 1)[0]
        self.assertIn('LCUtils.getCertTeamId(withKeyData:', VAULT)
        self.assertIn('LCUtils.scarletCertificateDER(', VAULT)
        self.assertIn('ScarletX509Validity.interval(der: der)', VAULT)
        self.assertIn('window.start <= now && window.end > now', VAULT)
        self.assertNotIn('LCCertificateUpdateDate', VAULT)

    def test_der_parser_locates_exact_tbs_validity_and_rejects_truncation(self):
        PARSER = SRC.split('enum ScarletX509Validity {', 1)[1].split(
            'enum ScarletHostTeamSignerVault {', 1)[0]
        for token in ('let tbs = tlv(', 'serial.tag == 0x02',
                      'sig.tag == 0x30', 'issuer.tag == 0x30',
                      'validity.tag == 0x30', 'node.tag == 0x17 || node.tag == 0x18',
                      'cert.end == b.count', 'len <= limit - i',
                      'before.end', 'after.end == validity.content.upperBound',
                      'static func notAfter(der: Data) -> Date?'):
            if token == 'before.end':
                self.assertIn(token, PARSER)
            else:
                self.assertIn(token, PARSER)
        self.assertNotIn('SecCertificateCopyValues', PARSER)

if __name__=='__main__': unittest.main()

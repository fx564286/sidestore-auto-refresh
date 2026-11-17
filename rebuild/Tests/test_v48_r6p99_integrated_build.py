"""P99 source contract and CI binary-gate for the forked P98 remedies."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()
ISSUER=(ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
BUTTON=(ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
WORKFLOW=(ROOT/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class IntegratedP99(unittest.TestCase):
    def test_both_independent_p98_paths_in_one_source(self):
        self.assertIn('issueFreshInstallCertificate(owner.teamID)',BUTTON)
        self.assertIn('if !forceNew {',ISSUER)
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',ISSUER)
        self.assertIn('verifiedInstalledHostTeam() -> (team: String, source: String)?',HOST)
        self.assertIn('native_host_team_identity_source',HOST)
        self.assertIn('signer_host_team_identity_source',HOST)
        self.assertIn('LCUtils.validateJITLessSetup { valid, _ in',HOST)
    def test_one_distinct_install_version_with_both_compiled_binary_proofs(self):
        for term in ('fix/scarlet-v48-r6p99-merged-fresh-cert-host-recovery-20261117',
                     '--host-build-version 3.8.99','version="3.8.99"',
                     'Scarlet-Crystal-V48-R6P99-MERGED-CERT-HOST-UNSIGNED.ipa',
                     'scarlet-v48-r6p99-merged-cert-host-unsigned-20261117',
                     'P99 both P98 remedies compiled into the ONE released IPA'):
            self.assertIn(term,WORKFLOW)
        for marker in ('b"issueFreshInstallCertificate"','b"installed_host_team_unverified"',
                       'b"native_host_team_identity_source"',
                       'b"issueFreshInstallTeamCertificate:reply:"'):
            self.assertIn(marker,WORKFLOW)

if __name__=='__main__':unittest.main()

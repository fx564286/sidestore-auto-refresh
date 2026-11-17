"""P98: no silent host-team SecTask return; strict development-profile fallback."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SRC=(ROOT/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()

class HostTeamRecovery(unittest.TestCase):
    def test_missing_sectask_does_not_silently_terminate_recovery(self):
        self.assertIn('static func verifiedInstalledHostTeam() -> (team: String, source: String)?', SRC)
        self.assertIn('"installed_host_team_unverified"', SRC)
        self.assertIn('"native_host_team_identity_source"', SRC)
        self.assertIn('"signer_host_team_identity_source"', SRC)
        self.assertEqual(SRC.count('.verifiedInstalledHostTeam() else {'), 3) # P101: bridge adds installed-host signer check
        self.assertNotIn('let signedHostTeam = signedValue.takeRetainedValue()', SRC)
    def test_profile_fallback_has_strict_bundle_and_expiry(self):
        section=SRC.split('static func verifiedInstalledHostTeam()',1)[1].split('static func check(archive:',1)[0]
        for condition in ['profile["TeamIdentifier"] as? [String]', 'teams.count == 1',
                          'profile["ExpirationDate"] as? Date', 'expiry > Date()',
                          'profile["DeveloperCertificates"] as? [Data]',
                          'rights["get-task-allow"] as? Bool == true',
                          'rights["com.apple.developer.team-identifier"] as? String == team',
                          'rights["application-identifier"] as? String == team + "." + bundleID',
                          'return (team, "installed_profile")']:
            self.assertIn(condition,section)
    def test_signed_device_still_requires_exact_der_and_kernel_check(self):
        self.assertIn('allowed.contains(candidateDER) ? .matched : .different',SRC)
        self.assertIn('LCUtils.validateJITLessSetup { valid, _ in',SRC)
        self.assertGreaterEqual(SRC.count('guard profile == .matched else {'),2)
        self.assertIn('restoreOriginal(prefs)',SRC)

if __name__ == '__main__': unittest.main()

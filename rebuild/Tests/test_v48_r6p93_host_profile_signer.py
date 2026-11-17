"""P93 signed-host certificate trust anchor, not another P78/P91 retry."""
from pathlib import Path
import unittest
import plistlib

R = Path(__file__).resolve().parents[1]
G = (R/'HostApp/ScarletIntegratedHostView.swift').read_text()
W = (R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P93SignedHostProfile(unittest.TestCase):
    def test_signed_host_actual_developer_cert_der_required(self):
        self.assertIn('embedded.mobileprovision', G)
        self.assertIn('profile["DeveloperCertificates"] as? [Data]', G)
        self.assertIn('SecPKCS12Import(archive as CFData', G)
        self.assertIn('SecIdentityCopyCertificate(identity, &cert)', G)
        self.assertIn('SecCertificateCopyData(cert) as Data', G)
        self.assertIn('allowed.contains(candidateDER) ? .matched : .different', G)
        self.assertIn('entitlements["get-task-allow"] as? Bool == true', G)
        self.assertNotIn('Unmanaged.passRetained', G)

    def test_only_matching_host_p12_can_enter_original_rollback_trial(self):
        self.assertIn('let profile = ScarletHostProvisioningSigner.check(', G)
        self.assertGreaterEqual(G.count('guard profile == .matched else {'),2)
        self.assertIn('signer_recovery_trial_started',G)
        self.assertIn('restoreOriginal(prefs)',G)
        self.assertIn('LCUtils.validateJITLessSetup { valid, _ in',G)
        self.assertIn('candidate_not_in_host_profile',G)
        self.assertIn('jitless_host_profile_signer_readback',G)

    def test_same_team_multiple_saved_apple_ids_not_ambiguously_rejected(self):
        self.assertIn('before.filter({ $0.active }).count == 1',G)
        self.assertIn('after.filter({ $0.active }).count == 1',G)
        self.assertIn('$0.active && $0.id == owner.id && $0.teamID == hostTeam',G)
        self.assertNotIn('before.filter({ $0.teamID == hostTeam }).count == 1',G)
        self.assertNotIn('after.filter({ $0.teamID == hostTeam }).count == 1',G)
        self.assertIn('ScarletHostProvisioningSigner.check(\n                archive: archive, password: password)',G)

    def test_signed_profile_xml_extraction_round_trip_matches_ios_plist(self):
        cert=b'\x30\x82\x01\x00fake-test-der'
        profile={'DeveloperCertificates':[cert], 'Entitlements':{'get-task-allow':True}}
        cms=b'HEADER\0\x01'+plistlib.dumps(profile,fmt=plistlib.FMT_XML)+b'TRAILER'
        content=cms[cms.index(b'<plist'):cms.index(b'</plist>')+len(b'</plist>')]
        parsed=plistlib.loads(content)
        self.assertEqual(parsed['DeveloperCertificates'][0],cert)
        self.assertTrue(parsed['Entitlements']['get-task-allow'])

    def test_native_ci_independent_p93_and_unchanged_bundle_id(self):
        self.assertIn('fix/scarlet-v48-r6p93-host-profile-signer-anchor-20261117',W)
        self.assertIn('--host-build-version 3.8.93',W)
        self.assertIn('Scarlet-Crystal-V48-R6P93-HOST-PROFILE-SIGNER-UNSIGNED.ipa',W)
        self.assertIn('scarlet-v48-r6p93-host-profile-signer-unsigned-20261117',W)
        self.assertIn('"CFBundleIdentifier"]=="com.kdt.livecontainer.P8EZT3U5N4"',W)

if __name__=='__main__': unittest.main()

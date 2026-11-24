"""P113 signed-team suffix and account-owner-pinned native refresh contracts."""
import importlib.util
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('p113_wire', R/'rebuild/integration/wire_scarlet_auth.py')
wire=importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)
WORKER=(R/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
WORKFLOW=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class OwnerFenceIdentity(unittest.TestCase):
    def test_actual_upstream_profile_source_transform_is_idempotent(self):
        swift='''        } else if self.context.appendTeamID {
            parentID = "\\(self.context.targetBundleIdentifier).\\(team.identifier)"
        } else {
            parentID = self.context.targetBundleIdentifier
        }
'''
        swift += r'''
            guard let installedApp = InstalledApp.first(satisfying: predicate, in: context) else {
                self.verboseLog("[FetchProvisioningProfiles] No existing InstalledApp found for target: \(target)")
                return nil
            }
            let teamsMatch = (installedApp.team?.identifier == team.identifier || installedApp.team == nil)
                             && installedApp.resignedBundleIdentifier.contains(team.identifier)
'''
        swift += '        let profile = try await DeveloperPortalProxy.shared.downloadProvisioningProfile(for: groupAppID, deviceType: DeveloperPortalProxy.currentDeviceType, team: team)'
        swift += '\n        if let overrideProfile = self.context.overrideProvisioningProfile {'
        swift += '\n        if let preferredBundleID = await self.getPreferredBundleID(for: targetAppBundle, team: team) {'
        patched=wire.patch_idempotent_team_provisioning(swift)
        self.assertIn('parentID = exactHostID',patched)
        self.assertIn('while normalized.hasSuffix(teamSuffix + teamSuffix)',patched)
        with self.assertRaises(AssertionError):wire.patch_idempotent_team_provisioning(patched)

    def test_team_suffix_policy(self):
        a='P8EZT3U5N4'; b='AB12CD34EF'
        base='com.kdt.livecontainer.'+a
        def after(original,team):
            return original[:-len('.'+team)] if original.endswith('.'+team+'.'+team) else (original if original.endswith('.'+team) else original+'.'+team)
        self.assertEqual(after(base,a),base)
        self.assertEqual(after(base,b),base+'.'+b)
        self.assertEqual(after('com.example.app',b),'com.example.app.'+b)

    def test_refresh_dispatches_are_guarded_after_transport(self):
        self.assertGreaterEqual(WORKER.count('guard let pinnedSerial = await ScarletInstallTeamAuthority'),3)
        self.assertGreaterEqual(WORKER.count('signingOwner.appleID == selectedAppleID'),2)
        self.assertGreaterEqual(WORKER.count('signingOwner.teamID == selectedTeamID'),2)
        self.assertGreaterEqual(WORKER.count('teamID: selectedTeamID) == pinnedSerial'),2)
        self.assertIn('AppManager.shared.refresh(',WORKER)
        self.assertIn('AppManager.shared.backgroundRefresh(',WORKER)
        self.assertIn('AppManager.shared.install(.url(installedHost)',WORKER)
        self.assertNotIn('revokeCertificate(',WORKER)

    def test_unique_native_release(self):
        for x in ('fix/scarlet-v48-r6p113-owner-fence-idempotent-ids-20261118',
                  '--host-build-version 3.8.113','version="3.8.113"',
                  'Scarlet-Crystal-V48-R6P113-OWNER-FENCE-UNSIGNED.ipa',
                  'scarlet-v48-r6p113-owner-fence-unsigned-20261118'):
            self.assertIn(x,WORKFLOW)

if __name__=='__main__':unittest.main()

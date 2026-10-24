"""V92: source/typed error provenance regression for repeated refresh failure.

The test intentionally does not simulate an Apple portal success: it verifies
that the installed error chain and independent phase probes cannot disappear
without failing the build. Neither signing IDs nor certificates are modified.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


startup=load('v92_combined_startup','patch_combined_service_startup.py')
v77=load('v92_portal_8220','patch_v77_profile_8220_device_registration.py')

FIXTURE='''import Foundation
private func provisionAndFetchProfile(for targetAppBundle: ALTApplication, parentAppBundle: ALTApplication?, team: ALTTeam) async throws -> ALTProvisioningProfile {
        let preferredBundleID = await self.getPreferredBundleID(for: targetAppBundle, team: team)
        let preferredName: String
        let appID = try await self.registerAppID(for: targetAppBundle, name: preferredName, bundleIdentifier: bundleID, team: team)
        let updatedAppID = try await self.updateFeatures(for: appID, targetAppBundle: targetAppBundle, team: team)
        let groupAppID = try await self.updateAppGroups(for: updatedAppID, targetAppBundle: targetAppBundle, team: team)
        verboseLog(targetAppBundle.dumpMachOInfo())
        self.debugLog("[FetchProvisioningProfiles] Fetching provisioning profile from Apple for App ID \\(groupAppID.bundleIdentifier)...")
        let profile = try await DeveloperPortalProxy.shared.downloadProvisioningProfile(for: groupAppID, deviceType: DeveloperPortalProxy.currentDeviceType, team: team)
        return profile
    }
}
'''

class ProfileTraceTests(unittest.TestCase):
    def test_canonical_helper_preserves_all_non_cancelled_errors(self):
        source=startup.SIGNING_CAUSE_HELPER
        self.assertIn('SCARLET_V92_PROFILE_CAUSE_PROPAGATION',source)
        self.assertIn('if error is CancellationError { throw error }',source)
        self.assertNotIn('(error as? ServerError) != nil ||',source)
        self.assertIn('lcStructuredSigningFailure(error, stage: stage, sourceStep: sourceStep',source)
        self.assertIn('NSUnderlyingErrorKey: native',source)
        self.assertNotIn('print(error.localizedDescription)',source)

    def test_upstream_refresh_profile_trace_and_v77_8220_compat(self):
        transformed=startup.patch_provisioning_profile_requests(FIXTURE)
        self.assertEqual(transformed.count('LC_PROVISIONING_PARENT_ID_UPSTREAM_V1'),1)
        for phase in ['register_app_id','update_capabilities','assign_app_groups']:
            self.assertEqual(transformed.count('phase='+phase+' state=entered'),1)
            self.assertEqual(transformed.count('phase='+phase+' state=passed'),1)
        self.assertEqual(transformed.count('phase=profile_download state=entered'),1)
        self.assertEqual(transformed.count('return try await lcProvisioningBundleRequest'),1)
        self.assertIn(v77.ANCHOR,transformed)
        patched=v77.patch(transformed)
        self.assertEqual(v77.patch(patched),patched)
        self.assertEqual(patched.count('serverCode == 8220'),1)
        self.assertIn('fetchDevices(for: team, types: .all)',patched)

    def test_idempotent_fail_closed_on_upstream_drift(self):
        with self.assertRaises((ValueError,SystemExit)):
            startup.patch_provisioning_profile_requests('missing pinned operation')
        with self.assertRaises(ValueError):
            v77.patch('missing provisioning anchors')

if __name__=="__main__":
    unittest.main()

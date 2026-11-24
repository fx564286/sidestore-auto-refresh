"""R6P118: report installed-host signer mismatch before an impossible native refresh.

Static contract tests; Apple owner records and physical device state are not
mutated in this test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "integration/ScarletGuestRefreshAgent.swift.txt").read_text()
UI = (ROOT / "HostApp/ScarletSigningReadinessPanel.swift").read_text()
FIXTURE = (ROOT / "Tests/fixtures/resident_scene_settings.m").read_text()


class HostTeamMismatchPropagation(unittest.TestCase):
    def test_zero_target_host_mismatch_wins_over_inventory_alias(self):
        start = SRC.index("let reason: String")
        end = SRC.index("reply(count, managesHost, signingReady, reason)", start)
        segment = SRC[start:end]
        self.assertIn('if targets.isEmpty && hostBootstrap == "host_selected_team_mismatch"', segment)
        self.assertIn('reason = "host_selected_team_mismatch"', segment)
        self.assertLess(segment.index('reason = "host_selected_team_mismatch"'),
                        segment.index("else if let inventoryReason"))
        self.assertNotIn('hostBootstrap == "host_selected_team_mismatch"\n                        ? "no_managed_apps_for_selected_team"', segment)

    def test_manual_onboarding_requires_true_zero_inventory_not_wrong_host_owner(self):
        self.assertIn('nativeState.reason == "no_managed_apps_for_selected_team"', UI)
        self.assertNotIn('nativeState.reason == "host_selected_team_mismatch"', UI)
        self.assertIn('hostBootstrap == "host_selected_team_mismatch"', SRC)

    def test_release_asset_name_matches_prepared_file_for_r6p118(self):
        workflow = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()
        before, after = workflow.split("      - name: Publish public GitHub Release asset", 1)
        asset = "Scarlet-Crystal-V48-R6P118-DIAGNOSTIC-LINK-UNSIGNED.ipa"
        branch = "fix/scarlet-v48-r6p118-diagnostic-link-share-20261120"
        self.assertIn('asset="' + asset + '"', before)
        self.assertIn("asset=" + asset, after)
        self.assertIn('refs/heads/' + branch, before)
        self.assertIn('refs/heads/' + branch, after)

    def test_objc_arc_fixture_avoids_new_family_property_ownership_name(self):
        self.assertNotIn("newHost", FIXTURE)
        self.assertIn("updatedHost", FIXTURE)


if __name__ == "__main__":
    unittest.main()

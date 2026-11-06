"""Fail-closed source-sync/7-day renewal/Liquid Glass alignment contracts."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config"
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
LAYOUT=json.loads((CONFIG/"layout-alignment.json").read_text())
UPDATE=json.loads((CONFIG/"auto-update-and-install.json").read_text())
PINS=json.loads((ROOT.parent/"config/scarlet-upstream-pins.json").read_text())

class UpdateAndAlignmentTests(unittest.TestCase):
    def test_actual_original_glass_required_not_simulated(self):
        self.assertTrue(LAYOUT["bottom_tab_bar"]["uses_original_liquid_glass"])
        self.assertEqual(LAYOUT["round_app_switcher"]["count_per_screen"],0)
        self.assertEqual(UI.count('SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR'),1)
        self.assertEqual(UI.count('SCARLET_SINGLE_ROUND_APP_SWITCHER'),0)
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertNotIn("preservedGlassSwitchControl",UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertFalse(LAYOUT["round_app_switcher"]["independent_window_manager_tab"])

    def test_four_bottom_tabs_centered_without_replacing_scarlet_glass(self):
        bar=LAYOUT["bottom_tab_bar"]
        self.assertEqual(len(LAYOUT["screens"]),6)
        self.assertEqual(bar["tab_count"],4)
        self.assertEqual(bar["labels"],["소스","앱","트윅","설정"])
        self.assertEqual(bar["icon_and_label_horizontal_alignment"],"CENTER")
        self.assertEqual(bar["icon_bounds_center_x"],bar["label_bounds_center_x"])
        expected=[bar["x"]+bar["outer_padding"]+bar["tab_width"]/2+
                  i*(bar["tab_width"]+bar["tab_spacing"]) for i in range(4)]
        self.assertEqual(bar["equal_tab_centers"],expected)
        self.assertEqual(bar["x"]*2+bar["width"],LAYOUT["device_width_pt"])

    def test_action_status_and_window_controls_have_distinct_alignment(self):
        row=LAYOUT["card_action_row"]
        self.assertEqual(row["icon_glyph_alignment"],"CENTER")
        self.assertEqual(row["status_alignment"],"HIDDEN_VISUAL_ACCESSIBILITY_ONLY")
        self.assertEqual(row["primary_text_alignment"],"LEFT")
        panel=LAYOUT["window_management"]
        self.assertEqual(panel["segment_labels_alignment"],"CENTER")
        self.assertEqual(panel["segment_width_pt"]*2+
                         panel["segment_gap_pt"]+14,panel["segmented_width_pt"])
        self.assertTrue(panel["min_max_close_equal_width"])
        self.assertTrue(panel["outside_tap_dismiss"])

    def test_figma_visual_report_matches_exact_segment_geometry(self):
        report=json.loads((ROOT/"reports/figma-alignment-audit-20261106.json").read_text())
        measured=report["geometry"]
        expected=LAYOUT["window_management"]
        self.assertEqual(measured["glassOverlaySegmentWidthPt"], expected["segment_width_pt"])
        self.assertEqual(measured["glassOverlaySegmentXPt"],[7,162])
        self.assertEqual(measured["iconLabelCenterOffsetPt"],[0,0,0,0])
        self.assertEqual(measured["bottomBarCenterX"],measured["viewportCenterX"])

    def test_upstream_updates_only_to_reviewed_pins_and_one_fork(self):
        self.assertEqual(set(PINS),{"LIVE_CONTAINER_REF","EMBEDDED_SIDESTORE_REF",
                                    "MINIMUXER_REF","SIDESIGN_REF"})
        self.assertEqual(UPDATE["source_updates"]["rebuilt_app_branch"],
                         "rebuild/scarlet-clean-core-20261106")
        self.assertTrue(UPDATE["source_updates"]["source_diff_only"])
        self.assertIn("draft PR",UPDATE["source_updates"]["upstream_sync_proposal"])
        self.assertTrue(UPDATE["source_updates"]["do_not_replace_upstream_side_store_with_independent_develop_branch"])
        self.assertFalse(UPDATE["release"]["automatically_release_without_validation"])

    def test_no_free_provisioning_bypass_claims(self):
        free=UPDATE["free_signing"]
        self.assertEqual(free["hard_expiration_days"],7)
        self.assertEqual(free["refresh_trigger_hours_remaining"],72)
        self.assertTrue(free["claims_no_free_7_day_bypass"])
        self.assertEqual(free["profile_count"],4)
        self.assertFalse(free["safari_development_ipa_ota_supported"])
        self.assertTrue(free["never_revoke_certificate_or_delete_profiles_automatically"])
        self.assertTrue(UPDATE["release"]["require_signature_and_device_install_receipt"])

if __name__=="__main__":unittest.main()

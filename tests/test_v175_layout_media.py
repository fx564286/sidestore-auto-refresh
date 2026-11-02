import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v175",ROOT/"scripts/patch_v175_layout_media.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class V175LayoutMedia(unittest.TestCase):
    def fixture(self):
        return "\n".join((
            "// SCARLET_V174_BOUNDED_GEOMETRY",
            "// SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER",
            "// SCARLET_V151_ORIENTATION_PARITY",
            "// SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY",
            "// NRG_V64_PORTRAIT_TOUCH_FRAME",
            "- (void)updateVerticalConstraints {",
            m.OLD_EARLY,
            m.OLD_LATE,
            "\n- (UIEdgeInsets)updateMaximizedSafeAreaWithSettings:",
            m.MEDIA_START,
            '  NSLog(@"[SCARLET_V139_VIDEO] legacy");',
            "  [scene requestGeometryUpdateWithPreferences:p errorHandler:nil];",
            "}",
            m.MEDIA_END,
            "}"
        ))
    def test_constraints_are_committed_before_hosted_scene_update(self):
        result=m.patch(self.fixture())
        layout=result[result.index("- (void)updateVerticalConstraints {"):result.index("\n- (UIEdgeInsets)")]
        self.assertLess(layout.index("[NSLayoutConstraint activateConstraints:"),
                        layout.index("[self.view layoutIfNeeded];"))
        self.assertLess(layout.index("[self.view layoutIfNeeded];"),
                        layout.index("[self.appSceneVC updateFrameWithSettingsBlock:"))
        self.assertNotIn("updateSettingsWithBlock:",layout)
        self.assertIn("stage=constraints_committed",layout)
        self.assertEqual(m.patch(result),result)

    def test_media_requests_both_directions_guarded_by_physical_device(self):
        result=m.patch(self.fixture())
        self.assertIn("UIInterfaceOrientationMaskPortrait",result)
        self.assertIn("UIInterfaceOrientationMaskLandscapeRight",result)
        self.assertIn("UIDeviceOrientationIsPortrait",result)
        self.assertIn("UIDeviceOrientationIsLandscape",result)
        self.assertIn("stage=defer reason=physical_orientation_mismatch",result)
        self.assertIn("requestGeometryUpdateWithPreferences",result)
        self.assertNotIn("settings.safeAreaInsetsPortrait =",result)
        self.assertNotIn("AVAudioSession",result)

    def test_rejects_incompatible_baseline(self):
        with self.assertRaises(ValueError):
            m.patch("old unverified source")

if __name__=="__main__":
    unittest.main()

"""Single-source replacement and portrait safety contract."""
import importlib.util
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("v173",ROOT/"scripts/patch_v173_single_scene_owner.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class V173Contract(unittest.TestCase):
    def test_retire_competing_geometry_writers(self):
        source="\n".join([
            "// SCARLET_V169_EVENT_DRIVEN_VIEWPORT",
            "// SCARLET_V170_LANDSCAPE_ONLY",
            "// SCARLET_V171_LANDSCAPE_SCENE_FRAME",
            "// SCARLET_V172_RESTORE_PORTRAIT",
            "// SCARLET_V151_UNIFIED_GUEST_GEOMETRY",
            m.V172_OVERRIDDEN_ORIENTATION,
            "- (void)nrgV169ScheduleGeometry {",
            "    self.nrgV170LandscapeRepairAttempted = YES;",
            "    self.nrgV172LandscapeWasForced = NO;",
            "    [owner.appSceneVC updateFrameWithSettingsBlock:nil];",
            "    [owner nrgV55ReconcileRotationGeometry];",
            "}",
            m.END
        ])
        result=m.patch(source)
        self.assertEqual(result,m.patch(result))
        self.assertEqual(result.count("SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER"),1)
        part=result[result.index(m.START):result.index(m.END)]
        self.assertEqual(part.count("[owner nrgV55ReconcileRotationGeometry];"),1)
        self.assertNotIn("[owner.appSceneVC updateFrameWithSettingsBlock:",part)
        self.assertNotIn("nrgV172LandscapeWasForced",part)
        self.assertIn("safeAreaInsets",part)
        self.assertNotIn("settings.safeAreaInsetsPortrait =",result)
        self.assertIn("baseSettings.interfaceOrientation",result)
        self.assertNotIn("hostCommittedLandscape &&",result)

    def test_fail_closed_when_wrong_baseline(self):
        with self.assertRaises(ValueError): m.patch("no original scene")
if __name__=="__main__":unittest.main()

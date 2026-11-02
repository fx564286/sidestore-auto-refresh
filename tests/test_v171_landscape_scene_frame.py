import importlib.util, unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v171scene",BASE/"scripts/patch_v171_landscape_scene_frame.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LandscapeScene(unittest.TestCase):
    def test_uses_real_landscape_and_preserves_original_portrait(self):
        src=("\n".join(("// SCARLET_V170_LANDSCAPE_ONLY", "// SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY",
                       "// SCARLET_V151_UNIFIED_GUEST_GEOMETRY")))+"\n"+m.OLD
        result=m.patch(src)
        self.assertEqual(result,m.patch(result))
        self.assertEqual(result.count("SCARLET_V171_LANDSCAPE_SCENE_FRAME"),1)
        self.assertIn('self.isMaximized &&',result)
        self.assertIn('self.appSceneVC.isAppRunning && hostWindow',result)
        self.assertIn('CGRectGetWidth(hostWindow.bounds) > CGRectGetHeight(hostWindow.bounds) + 1.0',result)
        self.assertIn('UIInterfaceOrientationIsPortrait(settings.interfaceOrientation)',result)
        self.assertIn('settings.interfaceOrientation = hostOrientation;',result)
        self.assertIn('settings.interfaceOrientation = baseSettings.interfaceOrientation;',result)
        self.assertIn('settings.deviceOrientation = baseSettings.deviceOrientation;',result)
        self.assertNotIn('settings.safeAreaInsetsPortrait =',result)
        self.assertNotIn('settings.frame =',result)
    def test_fails_closed_when_prior_pipeline_missing(self):
        with self.assertRaises(ValueError):m.patch(m.OLD)
if __name__=="__main__":unittest.main()

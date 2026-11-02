from pathlib import Path
import importlib.util
import unittest
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v171",BASE/"scripts/patch_v171_landscape_scene_frame.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LandscapeScene(unittest.TestCase):
    def test_native_scene_repaired_only_after_landscape_commit(self):
        s="// SCARLET_V170_LANDSCAPE_ONLY\n"+m.OLD
        out=m.patch(s)
        self.assertEqual(m.patch(out),out)
        self.assertIn('self.isMaximized && hostWindow',out)
        self.assertIn('UIInterfaceOrientationIsLandscape(hostWindow.windowScene.interfaceOrientation)',out)
        self.assertIn('newFrame.size.width > newFrame.size.height + 1.0',out)
        self.assertIn('settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);',out)
        self.assertIn('} else {\n            settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);\n        }',out)
        self.assertEqual(out.count('SCARLET_V171_LANDSCAPE_SCENE_FRAME'),1)
    def test_guarded_fail_closed(self):
        with self.assertRaises(ValueError):m.patch(m.OLD)
if __name__=="__main__":unittest.main()

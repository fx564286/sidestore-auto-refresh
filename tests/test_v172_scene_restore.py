import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v172", ROOT/"scripts/patch_v172_scene_restore.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class V172Regression(unittest.TestCase):
    def test_restores_only_prior_force_and_not_portrait_safe_area_math(self):
        scene=(ROOT/"scripts/patch_v171_landscape_scene_frame.py").read_text(encoding="utf-8")
        import ast
        # The exact V171 output plus the V170 cache/queue are pinned anchors.
        src="\n".join(("// SCARLET_V171_LANDSCAPE_SCENE_FRAME",
                       "// SCARLET_V170_LANDSCAPE_ONLY",
                       "// SCARLET_V169_EVENT_DRIVEN_VIEWPORT",
                       "// SCARLET_V151_UNIFIED_GUEST_GEOMETRY",
                       mod.PROP,mod.OLD,mod.CACHE,mod.QUEUE))
        patched=mod.patch(src)
        self.assertEqual(mod.patch(patched),patched)
        self.assertEqual(patched.count("SCARLET_V172_RESTORE_PORTRAIT"),1)
        self.assertIn("self.nrgV172LandscapeWasForced = YES",patched)
        self.assertIn("self.nrgV172LandscapeWasForced = NO",patched)
        self.assertIn("!nrgV172PortraitRestorePending",patched)
        self.assertIn("UIInterfaceOrientationIsPortrait(settledWindow.windowScene.interfaceOrientation)",patched)
        self.assertIn("[owner updateMaximizedFrameWithSettings:settings]",patched)
        self.assertNotIn("settings.safeAreaInsetsPortrait =",patched)
        self.assertNotIn("settings.peripheryInsets =",patched)
        self.assertIn("SCARLET_V171_LANDSCAPE_SCENE_FRAME",scene)
    def test_no_patch_without_history(self):
        with self.assertRaises(ValueError):mod.patch(mod.OLD)
if __name__=="__main__":unittest.main()

"""V104 retained UIKit scene activation and zero-private-data diagnostic contract."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"scripts"/"patch_v104_guest_scene_reactivation.py"
spec=importlib.util.spec_from_file_location("v104_scene",PATH)
patch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

SWIFT = '''SCARLET_V103_IMMEDIATE_GUEST_SWITCH
SCARLET_V97_RETAINED_GUEST_HOST_REBIND
NRG_V27_GUEST_GEOMETRY
    private func animateViewAppearance(_ view: UIView, from center: CGPoint?, in window: UIWindow) {
        controller?.lcResumeMinimizedGuest()
        bringViewToFront(view, in: window)
        // Preserve windowed/maximized frame and the user's chosen scale.
    }
'''
APP = '''LC_GUEST_RETURN_V3 NRG_V28_GUEST_LIFECYCLE
- (void)lcSetGuestSceneForeground:(BOOL)foreground {
    if (!self.isAppRunning || !self.presenter) return;
    [self.presenter.scene updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
        settings.foreground = foreground;
    }];
}
            NSData* containerBookmark = [dataURL bookmarkDataWithOptions:0 includingResourceValuesForKeys:0 relativeToURL:0 error:0];
            if(containerBookmark) {
                [bookmarks addObject:containerBookmark];
            }
'''

class V104SceneTests(unittest.TestCase):
    def test_reactivation_requires_visible_frontmost_guest(self):
        after=patch.patch_dock(SWIFT)
        self.assertEqual(after.count(patch.MARK_DOCK),1)
        a=after.index("bringViewToFront(view, in: window)")
        b=after.index("view.layoutIfNeeded()",a)
        c=after.index("controller?.appSceneVC.view.layoutIfNeeded()",b)
        d=after.index("controller?.lcResumeMinimizedGuest()",c)
        self.assertTrue(a < b < c < d)
        self.assertEqual(patch.patch_dock(after),after)

    def test_preserve_scene_lifecycle_and_do_not_read_chat_data(self):
        after=patch.patch_app(APP)
        self.assertIn("settings.foreground = foreground;",after)
        self.assertIn("if (!running || !presenterAvailable) return;",after)
        self.assertEqual(after.count(patch.MARK_APP),1)
        self.assertIn("containerBookmark != nil ? 1 : 0",after)
        self.assertIn("fileExistsAtPath:dataURL.path",after)
        for unsafe in ("NSLog(@\"%@\", dataURL.path)", "sqlite3_open", "SecItemDelete",
                       "removeItemAtPath", "selectedContainer=%@", "NSLog(@\"%@\", self.dataUUID)"):
            self.assertNotIn(unsafe,after)
        self.assertEqual(patch.patch_app(after),after)

    def test_rejects_absent_anchors_and_wrong_patch_order(self):
        with self.assertRaises(ValueError):
            patch.patch_dock(SWIFT.replace("SCARLET_V103_IMMEDIATE_GUEST_SWITCH",""))
        with self.assertRaises(ValueError):
            patch.patch_dock(SWIFT.replace("bringViewToFront(view, in: window)",""))
        with self.assertRaises(ValueError):
            patch.patch_app(APP.replace("NRG_V28_GUEST_LIFECYCLE",""))

    def test_pinned_existing_source_compatibility(self):
        path=os.getenv("LIVE_CONTAINER_TEST_SOURCE")
        if not path:return
        source=(Path(path)/patch.APP).read_text(encoding="utf-8")
        if patch.MARK_APP in source:
            self.assertEqual(patch.patch_app(source),source)
        else:
            patched=patch.patch_app(source)
            self.assertEqual(patch.patch_app(patched),patched)

    def test_generated_final_sources_with_v104(self):
        path=os.getenv("V104_PATCHED_LIVECONTAINER")
        if not path:return
        root=Path(path)
        self.assertEqual(patch.patch_app((root/patch.APP).read_text()),(root/patch.APP).read_text())
        self.assertEqual(patch.patch_dock((root/patch.DOCK).read_text()),(root/patch.DOCK).read_text())

if __name__=="__main__":
    unittest.main()

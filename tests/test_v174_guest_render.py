import importlib.util, sys, unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v174",root/"scripts/patch_v174_guest_render.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class GeometryMediaReview(unittest.TestCase):
    def test_bounded_rotation_epoch_no_repeated_media_resize(self):
        source="\n".join(("// SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER",
                          "// SCARLET_V151_ORIENTATION_PARITY",
                          "// SCARLET_V169_EVENT_DRIVEN_VIEWPORT",
                          m.OLD_STATE,m.OLD_GATE,m.OLD_COMMIT))
        result=m.decorated(source)
        self.assertEqual(m.decorated(result),result)
        self.assertEqual(result.count("SCARLET_V174_BOUNDED_GEOMETRY"),1)
        self.assertIn("if (staleGuest && !physicalChanged && self.nrgV174RepairAttempted) return",result)
        self.assertIn("owner.nrgV174RepairAttempted = YES;",result)
        self.assertNotIn("settings.safeAreaInsetsPortrait =",result)
    def test_onscreen_ios27_surface_preserves_portrait_parent(self):
        source="\n".join(('#import "UIKitPrivate+MultitaskSupport.h"',
                          "// SCARLET_V104_SCENE_PROVENANCE",
                          "// NRG_V28_GUEST_LIFECYCLE",
                          "self.contentView = self.hostingController.sceneViewController.view;",
                          m.OLD_RENDER,
                          "        self.contentView.frame = frame;"))
        result=m.guest(source)
        self.assertEqual(m.guest(result),result)
        self.assertEqual(result.count("SCARLET_V174_RENDER_SURFACE"),1)
        self.assertIn("self.view.bounds",result)
        self.assertIn("decorated.isMaximized",result)
        self.assertIn("self.view.window == hostWindow",result)
        self.assertNotIn("self.view.frame =",result)
        self.assertIn("SCARLET_V174_RENDER_FRAME_DEDUP",result)
        self.assertIn("if (!CGRectEqualToRect(self.contentView.frame, frame))",result)
        self.assertNotIn("AVAudioSession sharedInstance",result)
    def test_not_applicable_to_incompatible_source(self):
        for fn in (m.decorated,m.guest):
            with self.assertRaises(ValueError): fn("stale")
if __name__=="__main__":unittest.main()

"""V137 production contract: one entry owner, native regular glass, safe layout."""
import importlib.util
import os
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

v137=module("patch_v137_rotation_glass_owner")
shared=module("patch_v137_single_glass_entry")

class V137(unittest.TestCase):
    def test_shared_one_button_contract(self):
        s=(ROOT/"scripts/patch_v137_single_glass_entry.py").read_text()
        for token in ("SCARLET_V137_UNIFIED_GUEST_ENTRY","SCARLET_V137_TOUCH_SETTLE",
                      "SCARLET_V137_FINGER_GLASS","nrgV136GeometryStable:host",
                      "usingSpringWithDamping", "CATransaction", "CGAffineTransformMakeScale",
                      "SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];"):
            self.assertIn(token,s)
        for dangerous in ("SecItemDelete(", "setDeviceEndpointIp(", "kill(getpid()"):
            self.assertNotIn(dangerous,s)
    def test_v137_never_calls_deleted_cross_scene_retirement(self):
        # Exercise the genuine V105 -> V132 -> V137 transforms. V137 had
        # deleted retireAllFallbacks: but omitted its new_active_scene call,
        # producing a real Xcode Objective-C selector compile failure.
        v105 = module("patch_v105_delete_legacy_return")
        v132 = module("patch_v132_glass_drag_one_owner")
        previous = v132.boot_patch(v105.DIRECT_CODE)
        self.assertIn('[self retireAllFallbacks:@"new_active_scene"]', previous)
        current = v137.boot(previous)
        self.assertIn("SCARLET_V137_SCENE_OWNER", current)
        self.assertNotIn("retireAllFallbacks:", current)
        self.assertIn("[self retireFallbackInScene:scene", current)
        self.assertEqual(v137.boot(current), current)

    def test_fail_closed(self):
        for fn in (v137.decorated,v137.dock,v137.boot,
                   shared.decorated,shared.boot):
            with self.assertRaises(ValueError):fn("unsupported")
    def test_patched_build_if_supplied(self):
        root=os.getenv("V137_PATCHED_LIVECONTAINER")
        if not root:return
        root=Path(root)
        d=(root/shared.DECORATED).read_text()
        b=(root/shared.BOOT).read_text()
        g=(root/v137.DOCK).read_text()
        self.assertEqual(shared.decorated(d),d)
        self.assertEqual(shared.boot(b),b)
        self.assertEqual(v137.dock(g),g)
        self.assertEqual(d.count("SCARLET_V137_UNIFIED_GUEST_ENTRY"),1)
        self.assertEqual(b.count("SCARLET_V137_UNIFIED_GUEST_ENTRY"),1)
        self.assertEqual(g.count("SCARLET_V137_REGULAR_GLASS"),1)
        self.assertNotIn("nrgWindowOverflow",d)
        self.assertNotIn("nrgV73RestoreFloatingPosition",d)
        self.assertNotIn("nativeAvailableInScene:",b)
        self.assertNotIn("retireAllFallbacks:",b)
        self.assertEqual(b.count("SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];"),1)
        self.assertEqual(b.count("scGuestMorphPresenter = [SCGuestMorphPresenter new];"),1)
        self.assertIn("SCARLET_V137_FINGER_GLASS",b)

if __name__ == "__main__":unittest.main()

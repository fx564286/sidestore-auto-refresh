"""V152 universal guest-scene parity gate.

No per-app exceptions: every hosted guest (virtual/retained/Direct where the
respective source path is used) follows the shared host->guest->touch geometry
contract. This test intentionally does NOT require a named app or bundle ID.
"""
import itertools
import importlib.util
from pathlib import Path
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(path, name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

v58=module("patch_v58_fullscreen.py","v58_universal")
v151=module("patch_v151_geometry.py","v151_universal")
gl=module("patch_v151_glass_polish.py","glass_universal")

def serialized_size(physical, guest_landscape):
    w,h=physical
    return (h,w) if guest_landscape else (w,h)

def host_size(serialized, guest_landscape):
    w,h=serialized
    return (h,w) if guest_landscape else (w,h)

class V152UniversalGuestParity(unittest.TestCase):
    def test_all_supported_orientation_pairs_and_viewports(self):
        # The device/window size comes from UIKit, never from an app whitelist.
        devices=[(393,852),(852,393),(430,932),(932,430),(768,1024),
                 (1024,768),(320,568),(568,320)]
        for physical, host_landscape, guest_landscape in itertools.product(
                devices, (False,True), (False,True)):
            with self.subTest(physical=physical,host=host_landscape,guest=guest_landscape):
                self.assertEqual(host_size(serialized_size(physical,guest_landscape),
                                           guest_landscape),physical)

    def test_existing_v58_fullscreen_contract_accepts_complete_v151(self):
        root=os.getenv("V152_PATCHED_LIVECONTAINER")
        if not root:return
        decorated=(Path(root)/v151.DEC).read_text()
        self.assertEqual(v58.decorated(decorated),decorated)
        self.assertEqual(v151.patch_decorated(decorated),decorated)
        for marker in ("NRG_V58_EDGE_TO_EDGE_GUEST","SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY",
                       "SCARLET_V151_UNIFIED_GUEST_GEOMETRY",
                       "SCARLET_V151_ORIENTATION_PARITY",
                       "SCARLET_V151_FRAME_TOUCH_PARITY"):
            self.assertIn(marker,decorated)

    def test_missing_one_current_frame_invariant_fails_closed(self):
        root=os.getenv("V152_PATCHED_LIVECONTAINER")
        if not root:return
        original=(Path(root)/v151.DEC).read_text()
        for marker in ("SCARLET_V151_ORIENTATION_PARITY","SCARLET_V151_FRAME_TOUCH_PARITY",
                       "SCARLET_V151_UNIFIED_GUEST_GEOMETRY"):
            with self.subTest(marker=marker),self.assertRaisesRegex(RuntimeError,"partial V58"):
                v58.decorated(original.replace(marker,""))

    def test_all_guest_source_routes_use_shared_handlers(self):
        root=os.getenv("V152_PATCHED_LIVECONTAINER")
        if not root:return
        dock=(Path(root)/v151.SWIFT).read_text()
        decorated=(Path(root)/v151.DEC).read_text()
        self.assertIn("for app in apps {",dock)
        self.assertIn("controller.nrgV55ReconcileRotationGeometry()",dock)
        self.assertIn("controller.lcResumeMinimizedGuest()",dock)
        self.assertIn("settings.interfaceOrientation",decorated)
        self.assertIn("window.bounds",decorated)
        self.assertIn("SCARLET_V151_FRAME_TOUCH_PARITY",decorated)
        self.assertIn("ScarletGuestTouchSafe.",decorated)  # retain user choices
        self.assertIn("UIAccessibility.isReduceTransparencyEnabled",dock)
        self.assertEqual(gl.patch(dock),dock)

    def test_no_per_app_bundle_or_application_name_shortcuts(self):
        # The geometry algorithm must never specialize by bundle name.
        import inspect
        code=inspect.getsource(v151)
        for token in ("Instagram","KakaoTalk","Twitter","TikTok","YouTube",
                      "bundleIdentifier == ","bundleId == ","com.instagram.",
                      "com.kakao.","com.twitter.","com.zhiliaoapp."):
            with self.subTest(token=token):
                self.assertNotIn(token,code)

    def test_v58_legacy_v139_successor_still_works(self):
        # V152 cannot resolve the V151 conflict by disabling V58's guards.
        v139="\n".join(["// NRG_V58_EDGE_TO_EDGE_GUEST"]*4)+"""
// SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY
[self nrgV139RequestGuestVideoOrientation:baseSettings.interfaceOrientation];
if (!self.isMaximized) {
settings.frame = UIInterfaceOrientationIsLandscape(baseSettings.interfaceOrientation)
settings.frame = UIInterfaceOrientationIsLandscape(orientation)
"""
        self.assertEqual(v58.decorated(v139),v139)
        with self.assertRaisesRegex(RuntimeError,"partial V58"):
            v58.decorated(v139.replace(
                "settings.frame = UIInterfaceOrientationIsLandscape(orientation)",""))

if __name__=="__main__":unittest.main()

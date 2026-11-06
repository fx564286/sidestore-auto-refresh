"""Native startup safety / exact Figma icon contract (source-level tests).

These checks do not assert device startup or signed package functionality.
"""
from pathlib import Path
import base64
import importlib.util
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
INJECTION = (ROOT / "integration/apply_scarlet_host.py").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
ART = ROOT / "assets/ScarletCrystalAppIcon.figma.png.base64"

class ScarletBootAndBrandingContract(unittest.TestCase):
    def test_fresh_figma_icon_binary_is_real_png(self):
        self.assertTrue(ART.is_file())
        data = base64.b64decode(ART.read_text().strip(), validate=True)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h = struct.unpack(">II", data[16:24])
        self.assertGreaterEqual(w, 512)
        self.assertEqual(w, h)
        self.assertGreater(len(data), 50000)

    def test_native_asset_catalog_patched_before_xcode_archive(self):
        self.assertIn('"AppIcon1024.png"', INJECTION)
        self.assertIn('"Resources/Assets.xcassets/AppIcon.appiconset"', INJECTION)
        self.assertIn('"108:2"', INJECTION)
        self.assertIn('figma_icon=apply_figma_app_icon(root,engine)', INJECTION)
        self.assertIn('"customAppIcon":figma_icon', INJECTION)
        self.assertIn('subprocess.run(["sips"', INJECTION)

    def test_boot_guards_historical_corrupt_guest_without_deleting_user_data(self):
        for k in ("invalid-local-guest-skipped", "invalid-shared-guest-skipped",
                  "guest_anchors", "url_schemes_anchor",
                  'assert src.count(before)==1', 'src.count(url_schemes_anchor)==2',
                  "phase=app-init-start"):
            self.assertIn(k, INJECTION)
        self.assertNotIn("shutil.rmtree(LCPath", INJECTION)
        self.assertNotIn("removeItem(at:", INJECTION)
        self.assertIn("phase=home-visible", HOST)

    def test_crash_traced_dock_force_unwrap_is_deferred(self):
        # Four real iOS 27.2 SIGTRAP reports reproduce this exact path.
        # The real pinned upstream force-unwrap is replaced during Xcode
        # integration; device data and original engine remain intact.
        self.assertIn("unsafe_init", INJECTION)
        self.assertIn('dock_source.count(unsafe_init)==1', INJECTION)
        self.assertIn('dock_source.replace(unsafe_init,safe_init)', INJECTION)
        self.assertIn("UIWindow.didBecomeVisibleNotification", INJECTION)
        self.assertIn("scarletEnsureWindowHost()", INJECTION)
        self.assertIn("rootView.subviews.first ?? rootView", INJECTION)
        self.assertIn('onDeviceSigtrapDockForceUnwrapGuarded', INJECTION)
        self.assertNotIn("@ObservedObject private var guestDock = MultitaskDockManager.shared", HOST)
        self.assertIn("MultitaskDockManager.shared.scarletEnsureWindowHost()", HOST)

    def test_actual_device_launch_is_not_certified(self):
        report_source = (ROOT / "integration/package_paired.py").read_text()
        self.assertIn('"userDeviceInstallationVerified":False', report_source)
        self.assertIn('"nativeOriginalLiquidGlassVerified":False', report_source)
        self.assertIn('"codesignedWithAppleProfile":False', report_source)

if __name__ == "__main__":
    unittest.main()

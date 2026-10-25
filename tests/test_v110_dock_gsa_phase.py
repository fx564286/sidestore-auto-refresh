"""Host switcher regression: delete redundant floating implementation.

The original native window-control gesture must remain the sole entry to
MultitaskDockManager.nrgV72PresentGuestSwitcher. The model (and its same-view
resume lifecycle) stays; no secondary floating icons or app-specific branch.
"""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

dock = load("patch_v110_single_guest_dock")
http = load("patch_v110_gsa_http_phase")
v2 = load("patch_nrg_gsa_http_v2")

class CanonicalSwitchTests(unittest.TestCase):
    def test_safe_http_phase_transform_unchanged(self):
        source = "// SCARLET_V98_GSA_PHASE_TRACE\n" + v2.NEW_CALL + "\n" + v2.HELPER
        result = http.transform(source)
        self.assertEqual(http.transform(result), result)
        self.assertIn("SCARLET_V110_GSA_HTTP_PHASE", result)
        self.assertIn("anisetteClientInfo: anisetteData.clientInfo", result)
        self.assertIn("nrgLogSafeAuthPhase(operation: safeOperation", result)
        with self.assertRaises(ValueError):
            http.transform("unknown source")

    def test_generated_host_has_one_switch_owner_and_no_dock_renderer(self):
        path = os.environ.get("V110_PATCHED_LIVECONTAINER")
        if not path:
            self.assertIn(dock.MARK, (ROOT / "scripts" / "patch_v110_single_guest_dock.py").read_text())
            return
        base = Path(path)
        swift = (base / dock.REL).read_text(encoding="utf-8")
        dock.audit(swift)
        self.assertEqual(dock.transform(swift), swift)
        self.assertEqual(swift.count("public func nrgV72PresentGuestSwitcher("), 1)
        self.assertEqual(swift.count("func bringMultitaskViewToFront(uuid:"), 1)
        self.assertEqual(swift.count("public func addRunningAppWithInfo("), 1)
        self.assertIn("if !Thread.isMainThread {", swift)
        self.assertIn("if view != nil || apps[index].view == nil {", swift)
        self.assertIn("nrgV102NoteFocus(appUUID)", swift)
        self.assertEqual(swift.count("public func removeRunningApp("), 1)
        self.assertIn("prepareKeyboardForGuestSwitch(targetView:", swift)
        self.assertIn("SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND", swift)
        for deleted in ("struct MultitaskDockSwiftView: View",
                        "struct AppIconView: View", "class IconCacheManager",
                        "UIHostingController<AnyView>", "UIScreenEdgePanGestureRecognizer",
                        "setupDockView()", "setupEdgeGestureRecognizers()"):
            with self.subTest(deleted=deleted):
                self.assertNotIn(deleted, swift)
        settings = (base / dock.SETTINGS_REL).read_text()
        dock.audit_dock_settings(settings)
        self.assertEqual(dock.retire_dock_settings(settings), settings)
        self.assertIn('Picker(selection: $multitaskMode)', settings)
        self.assertNotIn('Slider(value: $dockWidth', settings)
        window = (base / "MultitaskSupport/DecoratedAppSceneViewController.m").read_text()
        self.assertIn("nrgV72PresentGuestSwitcherFrom:self", window)
        self.assertIn("nrgWindowOverflow", window)
        direct = (base / "LiveContainer/LCBootstrap.m").read_text()
        self.assertIn("SCGuestMorphPresenter", direct)
        self.assertIn("confirmation=accepted", direct)

    def test_fail_closed_if_upstream_was_replaced(self):
        with self.assertRaisesRegex(ValueError, "missing pre-existing unified switch"):
            dock.transform("unrelated source")

if __name__ == "__main__":
    unittest.main()

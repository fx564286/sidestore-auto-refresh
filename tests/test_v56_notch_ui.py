"""V56 regression: no-new-App-ID guest control capsule and preserved V55 geometry."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(module_name):
    spec=importlib.util.spec_from_file_location(module_name,ROOT/"scripts"/(module_name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v39=load("patch_v39_dock_app_switch_only")
v47=load("patch_v47_resume")
returns=load("patch_guest_return")
v55=load("patch_v55_rotation_geometry")
v56=load("patch_v56_notch_ui")

class V56ControlsTests(unittest.TestCase):
    def test_no_added_extension_or_capability(self):
        source=(ROOT/"scripts/patch_v56_notch_ui.py").read_text()
        self.assertIn("no Widget App ID",source)
        self.assertNotIn("NSSupportsLiveActivities",source)
        self.assertNotIn("CFBundleIdentifier",source)
        self.assertNotIn("SecTask",source)
        self.assertNotIn("misagent_install",source)

    def test_overlay_controls_and_dock_return_absence(self):
        pinned=os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not pinned:
            self.skipTest("set LIVE_CONTAINER_TEST_SOURCE for pinned code")
        target=Path(pinned)/v56.TARGET
        if not target.is_file():
            self.skipTest("pinned LiveContainer target unavailable")
        src=target.read_text()
        if v47.MARK not in src:
            self.assertEqual(src.count(v47.DOCK_ANCHOR),1)
            src=src.replace(v47.DOCK_ANCHOR,v47.DOCK_ADDITION+v47.DOCK_ANCHOR,1)
        src=v55.dock(src)
        src=v39.patch(src)
        after=v56.patch(src)
        self.assertEqual(v56.patch(after),after)
        self.assertNotIn("nrgDockReturnHome",after)
        for expected in (
            "nrgV56IslandHome", "nrgV56IslandExpand",
            "nrgV56MenuHome", "nrgV56MenuApps",
            "nrgV56MenuCurrent", "nrgV56MenuDismiss",
            "nrgV56ShowGuestControls()", "nrgV56RelayoutIsland()",
            "nrgV56IslandHidden = true",
            "window.safeAreaInsets.top + 3.0",
        ):
            self.assertIn(expected,after)
        self.assertIn("nrgV55ReconcileRotationGeometry()",after)
        self.assertIn("ForEach(dockManager.apps) { app in",after)
        # Test production patch order: guest-return first rewrites both
        # removed-app bookkeeping and successful foreground resume.
        base=target.read_text()
        start=base.index("    func bringMultitaskViewToFront(uuid:")
        end=base.index("    private func passURLSchemeToView(",start)
        production=base[:start]+returns.DOCK_RESUME+base[end:]
        start=production.index("    @objc public func removeRunningApp(")
        end=production.index("    @objc public func showDock()",start)
        rewritten="""    @objc public func removeRunningApp(_ appUUID: String) {
        if !Thread.isMainThread {
            DispatchQueue.main.async { self.removeRunningApp(appUUID) }
            return
        }
        self.apps.removeAll { $0.appUUID == appUUID }
        if self.apps.isEmpty { self.hideDock() }
        else if self.isVisible { self.updateDockFrame() }
    }

"""
        production=production[:start]+rewritten+production[end:]
        if v47.MARK not in production:
            production=production.replace(v47.DOCK_ANCHOR,v47.DOCK_ADDITION+v47.DOCK_ANCHOR,1)
        production=v55.dock(production)
        production=v39.patch(production)
        updated=v56.patch(production)
        self.assertEqual(v56.patch(updated),updated)
        self.assertIn("nrgV56ShowGuestControls()\n        print(",updated)
        self.assertIn("self.apps.removeAll { $0.appUUID == appUUID }\n        self.nrgV56RelayoutIsland()",updated)

    def test_requires_existing_v55_and_dock_patch(self):
        with self.assertRaises(RuntimeError):
            v56.patch("unmodified dock")

if __name__=="__main__":
    unittest.main()

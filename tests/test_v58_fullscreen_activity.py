"""V58 pinned regression: portrait/landscape edge-to-edge + native ActivityKit."""
import importlib.util
import os
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

v36=module("patch_v36_multitask_chrome")
v38=module("patch_v38_maximized_safe_area")
v47=module("patch_v47_resume")
v55=module("patch_v55_rotation_geometry")
v39=module("patch_v39_dock_app_switch_only")
v56=module("patch_v56_notch_ui")
v58=module("patch_v58_fullscreen")
island=module("patch_v58_native_activity")

class V58PinnedTests(unittest.TestCase):
    def test_entire_host_bounds_not_shrunken_by_safe_area(self):
        source=os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not source:self.skipTest("pinned source unavailable")
        original=(Path(source)/v58.DECORATED).read_text()
        decorated=v36.patch(original)
        if v38.MARKER not in decorated:
            decorated=decorated.replace(v38.OLD,v38.NEW,1)
        decorated=v55.decorated(decorated)
        new=v58.decorated(decorated)
        self.assertEqual(new,v58.decorated(new))
        self.assertIn("convertRect:window.bounds fromView:window",new)
        self.assertIn("settings.frame = UIInterfaceOrientationIsLandscape(orientation)",new)
        self.assertIn("return UIEdgeInsetsZero;",new)
        self.assertIn("settings.peripheryInsets = UIEdgeInsetsZero;",new)
        self.assertIn("self.view.layer.cornerRadius = 0;",new)
        self.assertIn("NRG_V58_VIEWPORT",new)
        self.assertIn("UIUserInterfaceIdiomPhone",new)

    def test_landscape_rotation_reconciles_real_window_scene_callback(self):
        delegate=v47.patch_delegate(v47.DELEGATE_ANCHOR)
        self.assertIn("func windowScene(_ windowScene: UIWindowScene, didUpdate",delegate)
        self.assertNotIn("func scene(_ scene: UIScene, didUpdate",delegate)
        self.assertIn("nrgV53ReconcileGuestGeometry(for: windowScene)",delegate)
        # Applying the downstream V55 rewrite must not lose this callback.
        updated=v55.delegate(delegate)
        self.assertIn("func windowScene(_ windowScene: UIWindowScene, didUpdate",updated)
        self.assertIn("nrgV53ReconcileGuestGeometry(for: windowScene)",updated)
        decorated=v36.patch((Path('/tmp/nrg-livecontainer-src')/v58.DECORATED).read_text()) if (Path('/tmp/nrg-livecontainer-src')/v58.DECORATED).exists() else None
        if decorated:
            if v38.MARKER not in decorated:
                decorated=decorated.replace(v38.OLD,v38.NEW,1)
            updated=v55.decorated(decorated)
            self.assertIn('NRG_V61_LANDSCAPE_GUEST_RECOVERY',updated)
            self.assertIn('&& !guestIsStale',updated)

    def test_native_island_shares_state_schema(self):
        self.assertIn(island.SHARED_ATTRS,island.WIDGET)
        self.assertIn("ActivityConfiguration(for: NRGGuestActivityAttributes.self)",island.WIDGET)
        self.assertIn("DynamicIslandExpandedRegion(.bottom)",island.WIDGET)
        self.assertIn('Link(destination: URL(string: guest.launchURL)',island.WIDGET)
        self.assertIn("Activity<NRGGuestActivityAttributes>.request(",island.MANAGER)
        self.assertIn("ActivityAuthorizationInfo().areActivitiesEnabled",island.MANAGER)
        self.assertIn("dismissalPolicy: .immediate",island.MANAGER)
        self.assertNotIn("extended-virtual-addressing",island.MANAGER)

    def test_v191_startup_avoids_early_unwrapped_root_subview(self):
        # The device crash is EXC_BREAKPOINT at MultitaskDockManager.init()
        # because the SwiftUI root has no first subview during first commit.
        self.assertIn("NRG_V191_STARTUP_HOST_ATTACH", island.MANAGER)
        self.assertIn("nrgV191AttachGuestWindowHostIfReady()", island.MANAGER)
        self.assertIn("guard let root = window?.rootViewController?.view else { return }",
                      island.MANAGER)
        self.assertIn("?? root", island.MANAGER)
        self.assertIn("if windowHostingView.superview !== anchor", island.MANAGER)
        self.assertNotIn("rootViewController!.view.subviews.first!", island.MANAGER)
        self.assertIn("startup safe UIKit host attachment",
                      __import__('inspect').getsource(island.patch_dock))

    def test_dock_patch_order_and_repeat(self):
        source=os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not source:self.skipTest("pinned source unavailable")
        s=(Path(source)/v58.DOCK).read_text()
        # CI executes this suite twice: once against pristine pinned sources,
        # then again after the build pipeline has already patched that tree.
        # A second V39 transform on a V58 tree incorrectly fails its anchors.
        if "NRG_V58_HOST_WINDOW_GEOMETRY" not in s:
            if v47.MARK not in s:
                s=s.replace(v47.DOCK_ANCHOR,v47.DOCK_ADDITION+v47.DOCK_ANCHOR,1)
            s=v55.dock(s)
            s=v39.patch(s)
            s=v56.patch(s)
            s=v58.dock(s)
        else:
            self.assertIn("NRG_V58_NATIVE_ISLAND_ACTIVITY",s)
        self.assertEqual(v58.dock(s),s)
        patched=island.patch_dock(s)
        self.assertEqual(island.patch_dock(patched),patched)
        self.assertIn("nrgV58RefreshNativeIsland()",patched)
        self.assertIn("import ActivityKit",patched)
        self.assertIn("NRG_V58_HOST_WINDOW_GEOMETRY",patched)
        self.assertIn("hostingController?.view.isHidden = systemIslandEnabled",patched)

    def test_default_widgetless_packer_retained(self):
        packer=(ROOT/"scripts/package_livecontainer_combined.py").read_text()
        self.assertIn('if os.environ.get("NRG_V58_NATIVE_ISLAND") == "1":',packer)
        self.assertIn("result['registration_targets_before_reuse'] = 5",packer)
        self.assertIn("result['registration_targets_before_reuse'] = 4",packer)
        self.assertIn("NSExtensionPointIdentifier",packer)

if __name__=="__main__":
    unittest.main()

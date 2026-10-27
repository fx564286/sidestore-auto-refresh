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
route=module("patch_v60_island_guest_switch")

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
        self.assertIn("convertRect:physicalRect fromView:window",new)
        self.assertIn("NRG_V64_PORTRAIT_TOUCH_FRAME",new)
        self.assertIn("UIInterfaceOrientationIsPortrait(orientation)",new)
        self.assertIn("UIEdgeInsetsInsetRect(physicalRect",new)
        self.assertIn("NRG_V70_PORTRAIT_BOTTOM_BLEED",new)
        if "SCARLET_V129_JIT_VIEWPORT" in new:
            self.assertIn("UIEdgeInsetsMake(touchSafe ? portraitTop : 0, 0, 0, 0)",new)
            self.assertIn("UIEdgeInsetsMake(touchSafe ? 0 : portraitTop, 0, portraitBottom, 0), orientation",new)
            self.assertIn("ScarletGuestTouchSafe.",new)
        else:
            self.assertIn("UIEdgeInsetsMake(portraitTop, 0, 0, 0)",new)
            self.assertIn("UIEdgeInsetsMake(0, 0, portraitBottom, 0), orientation",new)
        self.assertNotIn("UIEdgeInsetsMake(portraitTop, 0, portraitBottom, 0)",new)
        self.assertIn("settings.peripheryInsets = UIEdgeInsetsZero;",new)
        self.assertIn("if (portraitPhone)",new)
        self.assertIn("if (portraitTop < 32.0) portraitTop = 59.0;",new)
        self.assertIn("if (portraitBottom < 10.0) portraitBottom = 34.0;",new)
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

    def test_v61_mru_only_running_guest_sessions_and_fallback(self):
        manager=island.MANAGER
        widget=island.WIDGET
        self.assertIn("NRG_V61_MRU_ISLAND",manager)
        self.assertIn("nrgV61RecentGuestIDs.insert(id, at: 0)",manager)
        self.assertIn("running.compactMap { dock in",manager)
        self.assertIn("DataManager.shared.model.apps",manager)
        self.assertIn("model.uiContainers.contains(where:",manager)
        self.assertIn('URLQueryItem(name: "nrg-multitask", value: "1")',manager)
        self.assertIn('URLQueryItem(name: "container-folder-name", value: item.containerUUID)',manager)
        self.assertIn("guard !guests.isEmpty else",manager)
        self.assertIn("fallback_dock=1",manager)
        self.assertIn("nrgV61LastActivityState != state",manager)
        self.assertIn("!Activity<NRGGuestActivityAttributes>.activities.isEmpty",manager)
        # Never tear down the session while the user expands the Island.
        self.assertNotIn("name: UIApplication.willResignActiveNotification",manager)
        self.assertNotIn("name: UIApplication.didEnterBackgroundNotification",manager)
        self.assertIn("ForEach(context.state.guests, id:",widget)
        self.assertNotIn("ForEach(context.state.installedApps",widget)
        patch_source=__import__('inspect').getsource(island.patch_dock)
        self.assertIn("last-used guest on launch",patch_source)
        self.assertIn("last-used guest on foreground",patch_source)

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
        # V72 intentionally strips the old native Island after V58/V60 have
        # been used to construct the shared guest launch route. The final
        # compiled dock keeps V70 geometry, V192 startup attach and V72 hold.
        if 'NRG_V72_OVERFLOW_LONGPRESS' in s:
            self.assertIn('NRG_V58_HOST_WINDOW_GEOMETRY',s)
            self.assertIn('nrgV191AttachGuestWindowHostIfReady',s)
            self.assertNotIn('import ActivityKit',s)
            self.assertNotIn('nrgV58RefreshNativeIsland',s)
            self.assertNotIn('nrgV56IslandHost',s)
            return
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
        self.assertIn("hostingController?.view.isHidden = apps.isEmpty || (systemIslandEnabled",route.patch_dock(patched))

    def test_default_widgetless_packer_retained(self):
        packer=(ROOT/"scripts/package_livecontainer_combined.py").read_text()
        self.assertIn('if os.environ.get("NRG_V58_NATIVE_ISLAND") == "1":',packer)
        self.assertIn('raise ValueError("V107 rejects obsolete native-Island widget packaging")',packer)
        self.assertIn("result['registration_targets_before_reuse'] = 4",packer)
        self.assertIn("SCARLET_V107_WIDGETLESS_RELEASE_ONLY",packer)

if __name__=="__main__":
    unittest.main()

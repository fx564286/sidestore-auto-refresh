"""V60/V193: native Dynamic Island links for running guest sessions only."""
import importlib.util
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def get(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/(name+'.py'))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
native=get('patch_v58_native_activity')
route=get('patch_v60_island_guest_switch')
workflow=(ROOT/'.github/workflows/livecontainer-build.yml').read_text()

class V60GuestSwitchTests(unittest.TestCase):
    def test_island_has_per_guest_links_not_only_host_home(self):
        self.assertIn('NRG_V193_RUNNING_ONLY_ISLAND', native.MANAGER)
        self.assertIn('DataManager.shared.model.apps',native.MANAGER)
        self.assertIn('nrg-multitask',native.MANAGER)
        self.assertIn('guest.launchURL', native.WIDGET)
        self.assertIn('ForEach(context.state.guests',native.WIDGET)
        self.assertIn('private let homeURL = URL(string: "scarletcrystal251://nrg-apps")!',native.WIDGET)
        self.assertIn('route.scheme = "scarletcrystal251"',native.MANAGER)
        self.assertIn('Label("Scarlet Crystal 열기"',native.WIDGET)
        self.assertIn('running.compactMap',native.MANAGER)
        self.assertIn('containerUUID: dock.appUUID',native.MANAGER) 
        self.assertIn('value: item.containerUUID',native.MANAGER) 
        self.assertNotIn('item.model.uiSelectedContainer?.folderName',native.MANAGER)
        self.assertNotIn('UIApplication.shared.applicationState == .background',native.MANAGER)
        self.assertIn('UIApplication.didBecomeActiveNotification',native.MANAGER)
        self.assertNotIn('UIApplication.didEnterBackgroundNotification',native.MANAGER)
        self.assertIn('Link(destination: URL(string: guest.launchURL)',native.WIDGET)
        self.assertNotIn('Label("앱으로 돌아가기 · 전환"',native.WIDGET)
        self.assertIn('NSSupportsLiveActivities',Path(ROOT/'scripts/patch_v58_native_activity.py').read_text())
    def test_schema_shared_identical_and_bounded(self):
        self.assertIn(native.SHARED_ATTRS,native.WIDGET)
        self.assertIn('struct Guest: Codable, Hashable',native.SHARED_ATTRS)
        self.assertIn('.prefix(6)',native.MANAGER)
        self.assertIn('guard !guests.isEmpty else',native.MANAGER)
        self.assertIn('NRG_V63_RECENT_GUEST_CATALOG',native.MANAGER)
        self.assertIn('route.queryItems = query',native.MANAGER)
    def test_route_and_normal_app_launch_are_distinct_and_repeatable(self):
        sample=(ROOT/'scripts/templates/v3_unified_shell.swift').read_text()
        out=route.patch_shell(sample)
        self.assertEqual(out,route.patch_shell(out))
        self.assertIn('case "nrg-apps":',out)
        self.assertIn('sharedModel.deepLink = url',out)
        self.assertIn('MultitaskDockManager.shared.nrgV58RefreshNativeIsland()',out)
        # Xcode's iOS 15 deployment target rejects referencing the iOS 16-only
        # MultitaskDockManager without guarding every call site.
        self.assertIn('.onAppear {\n            if #available(iOS 16.0, *) {',out)
        self.assertIn('DispatchQueue.main.async {\n                if #available(iOS 16.0, *) {',out)
        self.assertNotIn('.onAppear { MultitaskDockManager.shared',out)
        # This sample is the exact upstream pinned source, with its existing
        # launch and lock/JIT flow retained.
        pinned=Path('/tmp/nrg-livecontainer-src/LiveContainerSwiftUI/Views/AppList/LCAppListView.swift')
        if pinned.exists():
            apps=route.patch_apps(pinned.read_text())
            self.assertEqual(apps,route.patch_apps(apps))
            self.assertIn('multitask: islandMultitask',apps)
            self.assertIn('runApp(multitask: multitask',apps)
            self.assertIn('LCUtils.authenticateUser()',apps)
    def test_v63_recent_guest_launch_across_modes(self):
        # Model runApp is the common launch path, including classic/JIT guest.
        sample = '        UserDefaults.standard.set(uiSelectedContainer?.folderName, forKey: "selectedContainer")' + chr(10)
        patched = route.patch_model(sample)
        self.assertEqual(patched, route.patch_model(patched))
        self.assertIn("NRG_V63_NOTIFY_GUEST_LAUNCH", patched)
        self.assertIn("MultitaskDockManager.shared.nrgV58RefreshNativeIsland()", patched)
        self.assertIn("NRG_V63_RECENT_GUEST_CATALOG", native.MANAGER)
        self.assertIn("model.appInfo.lastLaunched", native.MANAGER)
        self.assertIn("recentCatalog.filter", native.MANAGER)
        self.assertIn("runningCatalog + recentCatalog", native.MANAGER)
        self.assertIn('route.scheme = "scarletcrystal251"', native.MANAGER)
        self.assertNotIn("UIApplication.didEnterBackgroundNotification", native.MANAGER)
        self.assertIn('schemes.append("scarletcrystal251")',
                      (ROOT/"scripts/patch_v58_native_activity.py").read_text())

    def test_workflow_applies_final_patch_twice(self):
        self.assertEqual(workflow.count('python3 builder/scripts/patch_v60_island_guest_switch.py work/LiveContainer'),2)
        self.assertLess(workflow.index('patch_v58_native_activity.py work/LiveContainer'),
                        workflow.index('patch_v60_island_guest_switch.py work/LiveContainer'))

if __name__=='__main__':
    unittest.main()

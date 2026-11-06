"""User acceptance: installed-apps leading + opens original LC manager only.

The SideStore/SideSign engine stays present; SideStore's standalone guest UI
must never appear from the embedded LiveContainer manager. This file tests
the surgical pinned-source patch against a small exact-anchor native fixture.
"""
import importlib.util
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
INTEGRATOR=ROOT/"integration/apply_scarlet_host.py"

def load_patch_module():
    spec=importlib.util.spec_from_file_location("scarlet_guest_manager_patch",INTEGRATOR)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class LCManagerWithoutSideStoreGuestUI(unittest.TestCase):
    def test_installed_apps_header_has_real_file_plus(self):
        home=UI[UI.index("    private var home: some View {"):UI.index("    private func installPathRow(")]
        self.assertIn("SCARLET_INSTALLED_APPS_ADD_FILE",home)
        self.assertIn('Image(systemName: "doc.badge.plus")',home)
        self.assertIn('heading("", "설치된 앱", "")',home)
        self.assertLess(home.index("SCARLET_INSTALLED_APPS_ADD_FILE"),
                        home.index('heading("", "설치된 앱", "")'))
        self.assertIn("onAction(.localImportGuestIPA)",home)
        self.assertIn("SCARLET_HOME_DEVICE_IPA_INSTALL",home)
        self.assertIn("SCARLET_HOME_GUEST_IPA_INSTALL",home)

    def test_real_native_view_not_duplicate_navigation_stack(self):
        fragment=HOST[HOST.index(".sheet(isPresented: $showNativeAppLibrary) {"):
                      HOST.index(".sheet(isPresented: $showNativeSources) {")]
        self.assertIn("LCAppListView()",fragment)
        self.assertIn(".presentationDetents([.large])",fragment)
        self.assertNotIn("NavigationStack {",fragment)
        self.assertIn("case .localImportGuestIPA:",HOST)
        self.assertIn("showNativeAppLibrary = true",HOST)

    def test_surgical_patch_removes_only_the_native_sidestore_guest_buttons(self):
        fixture='''// Upstream app list
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Button("lc.appList.installFromIpa".loc, systemImage: "doc.badge.plus", action: {
                            choosingIPA = true
                        })
                        Button("lc.appList.installFromUrl".loc, systemImage: "link.badge.plus", action: {
                            Task { await startInstallFromUrl() }
                        })
                    }
                }
                ToolbarItem(placement: .topBarLeading) {
                    if(UserDefaults.sideStoreExist()) {
                        Button {
                            LCUtils.openSideStore(delegate: self)
                        } label: {
                            IconImageView(icon: BuiltInSideStoreAppInfo.shared.iconIsDarkIcon(darkModeIcon))
                        }
                    } else {
                        Button("Help", systemImage: "questionmark") {
                            helpPresent = true
                        }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Text("sort")
                }
        if appFound == nil && bundleId == "builtinSideStore" {
            appFound = LCAppModel(appInfo: BuiltInSideStoreAppInfo.shared)
        }
        if url.scheme == "sidestore" && UserDefaults.sideStoreExist() {
            UserDefaults.standard.setValue(url.absoluteString, forKey: "launchAppUrlScheme")
            LCUtils.openSideStore(delegate: self)
            return
        }
'''
        with tempfile.TemporaryDirectory() as temporary:
            engine=Path(temporary)
            file=engine/"LiveContainerSwiftUI/Views/AppList/LCAppListView.swift"
            file.parent.mkdir(parents=True)
            file.write_text(fixture)
            patch=load_patch_module()
            report=patch.hide_embedded_sidestore_guest_navigation(engine)
            source=file.read_text()
            self.assertTrue(report["embeddedSideStoreGuestNavigationRemoved"])
            self.assertTrue(report["embeddedSideStoreEnginePreserved"])
            for required in ('Button("lc.appList.installFromIpa".loc',
                             'Button("lc.appList.installFromUrl".loc',
                             'ToolbarItem(placement: .topBarTrailing)'):
                self.assertIn(required,source)
            for forbidden in ("LCUtils.openSideStore(",
                              "BuiltInSideStoreAppInfo.shared",
                              'bundleId == "builtinSideStore"'):
                self.assertNotIn(forbidden,source)
            self.assertIn('if url.scheme == "sidestore" {',source)
            self.assertNotIn('setValue(url.absoluteString, forKey: "launchAppUrlScheme")',source)

    def test_unrecognized_native_version_refuses_to_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine=Path(temporary)
            file=engine/"LiveContainerSwiftUI/Views/AppList/LCAppListView.swift"
            file.parent.mkdir(parents=True)
            file.write_text("// version changed\n")
            with self.assertRaises(AssertionError):
                load_patch_module().hide_embedded_sidestore_guest_navigation(engine)

if __name__=="__main__":
    unittest.main()

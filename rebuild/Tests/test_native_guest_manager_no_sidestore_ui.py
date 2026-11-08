"""User acceptance: title-leading + opens iPhone Files, never app manager.

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
        home=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
        self.assertIn("SCARLET_INSTALLED_APPS_ADD_FILE",home)
        self.assertIn('Image(systemName: "doc.badge.plus")',home)
        self.assertIn('heading("", "설치된 앱", "")',home)
        self.assertLess(home.index("SCARLET_INSTALLED_APPS_ADD_FILE"),
                        home.index('heading("", "설치된 앱", "")'))
        self.assertIn("onAction(.localImportGuestIPA)",home)
        self.assertIn("SCARLET_INSTALL_CHOICE_DEVICE_IPA",home)
        self.assertNotIn(".contextMenu {",home)
        self.assertIn("SCARLET_INSTALL_CHOICE_GUEST_APP",home)
        self.assertIn("onAction(.serviceInstallIPA)",home)
        self.assertEqual(home.count("\n                Menu {"),1)
        self.assertIn("SCARLET_INSTALL_CHOICE_GUEST_APP",home)
        self.assertLess(home.index("Menu {"), home.index("onAction(.localImportGuestIPA)"))
        self.assertNotIn("installPathRow(",UI)

    def test_scarlet_files_picker_is_direct_not_nested_app_list(self):
        self.assertIn(".fileImporter(isPresented: $showGuestFilePicker,",HOST)
        self.assertIn("stageGuestIPAFromFiles(selected)",HOST)
        self.assertIn('showGuestFilePicker = true',HOST)
        self.assertNotIn("showNativeAppLibrary",HOST)
        self.assertNotIn("guestIPAImportFromAddMenu",HOST)
        fragment=HOST[HOST.index(".sheet(isPresented: $showGuestImportProgress, onDismiss: {"):
                      HOST.index(".sheet(isPresented: $showNativeSources) {")]
        self.assertIn("LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,",fragment)
        self.assertNotIn(".sheet(isPresented: $showNativeAppLibrary",fragment)
        self.assertIn(".interactiveDismissDisabled()",fragment)


    def test_surgical_patch_removes_only_the_native_sidestore_guest_buttons(self):
        fixture='''// Upstream app list
        NavigationView {
            ScrollView {
            }
        }
        .navigationViewStyle(StackNavigationViewStyle())
    init() {
        _installOptions = State(initialValue: [])
    }
            .onAppear {
                if !didAppear {
                    onAppear()
                }
            }
        .betterFileImporter(isPresented: $choosingIPA, types: [.ipa, .tipa], multiple: false, callback: { fileUrls in
        })
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
    func startInstallApp(_ fileUrl:URL) async {
        do {
            try await installIpaFile(fileUrl)
        } catch {
            errorInfo = error.localizedDescription
        }
    }
    func installIpaFile(_ url: URL) async throws {
        // we leave it unsigned even if signing failed
        if let signError {
            if signSuccess {
                errorInfo = signError
            } else {
                errorInfo = signError.loc
            }
        }
    }
    nonisolated func decompress(_ path: String, _ destination: String ,_ progress: Progress) async -> Int32 {
        return 0
    }
    func startInstallFromUrl() async {
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
            self.assertIn("file_import_requested",source)
            self.assertIn("scarletQueuedIPAURL",source)
            self.assertIn("SCARLET_GUEST_IMPORT_PROGRESS_ONLY",source)
            self.assertIn("await startInstallApp(queuedIPA)",source)
            self.assertTrue(report["scarletAppListNotPresentedDuringImport"])
            self.assertIn("import_pipeline_failed",source)
            self.assertIn("import_signing_failed",source)
            self.assertIn("scarletGuestImportSignFailed = true",source)
            self.assertIn("서명 확인이 필요합니다",source)
            self.assertNotIn("IPA 처리 완료",source)
            self.assertIn("launch_unverified",source)
            self.assertIn("url_import_requested",source)
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

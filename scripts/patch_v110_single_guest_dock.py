#!/usr/bin/env python3
"""V111 subtractive consolidation of the existing guest switcher.

Keep MultitaskDockManager as the authoritative live window registry, focus
tracker and lifecycle controller; keep its original nrgV72PresentGuestSwitcher
as the only host guest-selection UI. DELETE the parallel floating SwiftUI
Dock, its second input gesture route, icon cache and expansion UI.
Retain the existing window-control overflow button as the picker entry
point. Do not alter Direct-mode process escape or guest rendering geometry.

This is an edit to the EXISTING V110 builder patch, not another UI layer.
"""
from pathlib import Path
import sys

REL = Path("MultitaskSupport/MultitaskDockView.swift")
SETTINGS_REL = Path("LiveContainerSwiftUI/Views/Settings/LCMultitaskSettingView.swift")
MARK = "SCARLET_V111_CANONICAL_GUEST_SWITCH_OWNER"

def section(source: str, begin: str, end: str, replacement: str = "") -> str:
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError(f"V111 source drift: {begin[:45]!r} count={source.count(begin)}")
    a, b = source.index(begin), source.index(end)
    if a >= b:
        raise ValueError(f"V111 reversed source section: {begin!r}")
    return source[:a] + replacement + source[b:]

def unique(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"V111 {label}: expected one source anchor, got {source.count(old)}")
    return source.replace(old, new, 1)

def transform(source: str) -> str:
    if MARK in source:
        audit(source)
        return source
    required = (
        "SCARLET_V108_NO_BLUE_COLLAPSED_DOCK",
        "nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)",
        "func bringMultitaskViewToFront(uuid: String, from center:",
        "func prepareKeyboardForGuestSwitch(targetView:",
        "nrgV102NoteFocus(guest.folder)",
        "windowHostingView",
        "SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND",
    )
    for token in required:
        if token not in source:
            raise ValueError("V111 missing pre-existing unified switch path: " + token)

    # The whole duplicate floating UI was private to this Swift file.
    # Remove all four view/widget implementations and icon cache, rather than
    # replacing them with hidden/transparent overlays.
    title = "// MARK: - SwiftUI Dock View"
    if source.count(title) != 1:
        raise ValueError("V111 missing duplicate SwiftUI Dock")
    removed = source[source.index(title):]
    for view in ("struct MultitaskDockSwiftView: View",
                 "struct AppIconView: View", "struct LoadingIconView: View",
                 "struct MinimizeAllButtonView: View", "class IconCacheManager"):
        if view not in removed:
            raise ValueError("V111 unexpected duplicate Dock body: " + view)
    source = source[:source.index(title)]

    # Delete the extra root creator + layout geometry. The existing virtual
    # window host is a separate UIKit view and MUST remain untouched.
    source = section(
        source, "    private func setupDockView() {",
        "    @objc public func addRunningApp(")

    # Remove mounting, swiping, cross-screen dragging and resize of the
    # parallel UI. These did not route through the canonical selection picker.
    source = section(
        source, "    @objc public func showDock() {",
        "    // Find and bring corresponding multitask view to front\n")

    source = section(
        source, "    @objc public func toggleDockCollapse() {",
        "    // MARK: - Multitask Mode Check\n")

    # App registry must function with zero floating UI controllers. Retain
    # active app identity, original view, and foreground focus ordering.
    source = section(
        source,
        "    @objc public func addRunningAppWithInfo(_ appInfo: LCAppInfo?, appUUID: String, view: UIView?) {",
        "    @objc public func minimizeAllWindows(",
        '''    // SCARLET_V111_CANONICAL_GUEST_SWITCH_OWNER: one registry, one picker.
    @objc public func addRunningAppWithInfo(_ appInfo: LCAppInfo?, appUUID: String, view: UIView?) {
        // Registration must precede any same-turn switch/termination event.
        // A queued stale registration could otherwise resurrect a dead app.
        if !Thread.isMainThread {
            DispatchQueue.main.async { [weak self] in
                self?.addRunningAppWithInfo(appInfo, appUUID: appUUID, view: view)
            }
            return
        }
        guard isDockEnabled(), !appUUID.isEmpty else { return }
        let appName = appInfo?.displayName() ?? "Unknown App"
        if let index = apps.firstIndex(where: { $0.appUUID == appUUID }) {
            // A background re-registration without a view must not replace
            // an existing retained UIKit scene with a nil pointer.
            if view != nil || apps[index].view == nil {
                apps[index] = DockAppModel(appName: appName, appUUID: appUUID,
                                           appInfo: appInfo, view: view)
            }
        } else {
            apps.append(DockAppModel(appName: appName, appUUID: appUUID,
                                     appInfo: appInfo, view: view))
        }
        nrgV102NoteFocus(appUUID)
    }

''')

    # removeRunningApp is immediately before the (now removed) showDock
    # block; retain removal and session cleanup without UI frame mutation.
    source = section(
        source,
        "    @objc public func removeRunningApp(_ appUUID: String) {",
        "    // Find and bring corresponding multitask view to front\n",
        '''    @objc public func removeRunningApp(_ appUUID: String) {
        if !Thread.isMainThread {
            DispatchQueue.main.async { self.removeRunningApp(appUUID) }
            return
        }
        apps.removeAll { $0.appUUID == appUUID }
        nrgV102FocusDates.removeValue(forKey: appUUID)
    }

''')

    # Remove all notification/render callbacks, including their registrations.
    source = section(
        source, "    @objc private func deviceOrientationDidChange() {",
        "    @objc public func addRunningApp(")
    source = unique(source, "        setupDockView()\n", "", "extra root creation")
    # Drop registrations by their exact pair of blocks; the retained native
    # window host has a separate geometry/recovery observer.
    start = source.index('''        NotificationCenter.default.addObserver(
            self,
            selector: #selector(userDefaultsDidChange),''')
    ending = source.index("\n    }", start)
    source = source[:start] + source[ending:]
    # deinit only served the now-removed Dock observers.
    source = unique(source, '''    deinit {
        NotificationCenter.default.removeObserver(self)
        NotificationCenter.default.removeObserver(self, name: UIDevice.orientationDidChangeNotification, object: nil)
    }

''', "", "Dock-only notification teardown")

    source = unique(source,
        "    internal var hostingController: UIHostingController<AnyView>?\n",
        "", "duplicate floating root property")
    source = unique(source, '''        let dockView = hostingController?.view
        let previousDockHidden = dockView?.isHidden ?? false
        if dockView?.window?.windowScene === owner.windowScene {
            dockView?.isHidden = true
        }

''', "", "picker-to-Dock cross coupling")
    restore1 = '''                if dockView?.window?.windowScene === owner.windowScene {
                    dockView?.isHidden = previousDockHidden
                }
'''
    restore2 = '''                    if dockView?.window?.windowScene === owner.windowScene {
                        dockView?.isHidden = previousDockHidden
                    }
'''
    if source.count(restore1) != 1 or source.count(restore2) != 1:
        raise ValueError("V111 picker floating-Dock cleanup drift")
    source = source.replace(restore1, "").replace(restore2, "")

    # Drop dead floating state and recognizer handles. The gesture on the
    # native overflow control continues to call nrgV72PresentGuestSwitcher.
    source = unique(source, '''    @Published var isVisible: Bool = false
''', "", "unused floating visibility state")
    source = unique(source, '''    private weak var nrgV108LeftEdgeGesture: UIScreenEdgePanGestureRecognizer?
    private weak var nrgV108RightEdgeGesture: UIScreenEdgePanGestureRecognizer?
''', "", "obsolete edge recognizers")

    audit(source)
    return source

def audit(source: str) -> None:
    for token in (
        MARK, "public func nrgV72PresentGuestSwitcher(",
        "nrgV102PresentWindowActions(from: controller, sourceView: sourceView)",
        "func bringMultitaskViewToFront(uuid: String",
        "func prepareKeyboardForGuestSwitch(targetView:",
        "SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND",
        "private func isDockEnabled() -> Bool",
        "public lazy var windowHostingView = VirtualWindowsHostView()"):
        if token not in source:
            raise ValueError("V111 canonical switch or window host missing: " + token)
    for deleted in (
        "struct MultitaskDockSwiftView:", "struct AppIconView:",
        "struct MinimizeAllButtonView:", "struct LoadingIconView:",
        "class IconCacheManager", "UIHostingController<AnyView>",
        "hostingController.rootView", "private func setupDockView()",
        "private func setupEdgeGestureRecognizers()",
        "private func handleEdgeSwipe(", "nrgV108LeftEdgeGesture",
        "setupDockView()", "keyWindow.addSubview(hostingController.view)"):
        if deleted in source:
            raise ValueError("V111 parallel floating Dock not deleted: " + deleted)

def retire_dock_settings(source: str) -> str:
    """Remove inactive Dock settings; preserve virtual/native window choices."""
    legacy = ('    @AppStorage("LCDockWidth", store: LCUtils.appGroupUserDefault) var dockWidth: Double = 80\n',
              '    @AppStorage("LCMultitaskDockStartsTuckedToEdge", store: LCUtils.appGroupUserDefault) var dockStartsTuckedToEdge = false\n')
    if not any(x in source for x in legacy):
        audit_dock_settings(source)
        return source
    for x in legacy:
        source = unique(source, x, "", "unused Dock settings binding")
    source = section(
        source,
        '            Section {\n                VStack(alignment: .leading, spacing: 12) {',
        '        }\n        .navigationTitle("lc.appBanner.multitask".loc)',
        "")
    audit_dock_settings(source)
    return source

def audit_dock_settings(source: str) -> None:
    for retired in ("LCDockWidth", "dockStartsTuckedToEdge", "dockWidth",
                    "Start Dock Tucked To Edge", "Swipe inward from the left",
                    "lc.settings.dockWidth"):
        if retired in source:
            raise ValueError("V111 dead floating dock setting persists: " + retired)
    if ('Picker(selection: $multitaskMode)' not in source
            or 'Text("lc.settings.bottomWindowBar".loc)' not in source):
        raise ValueError("V111 useful native/virtual guest controls were removed")

def apply(root: Path) -> None:
    path = root / REL
    if not path.is_file() or path.is_symlink():
        raise ValueError("V111 canonical Dock source missing")
    before = path.read_text(encoding="utf-8")
    after = transform(before)
    if transform(after) != after:
        raise ValueError("V111 non-idempotent deletion")
    if after != before:
        path.write_text(after, encoding="utf-8")
    settings = root / SETTINGS_REL
    if not settings.is_file() or settings.is_symlink():
        raise ValueError("V111 pinned multitask settings missing")
    prior_settings = settings.read_text(encoding="utf-8")
    clean_settings = retire_dock_settings(prior_settings)
    if retire_dock_settings(clean_settings) != clean_settings:
        raise ValueError("V111 obsolete setting cleanup not idempotent")
    if prior_settings != clean_settings:
        settings.write_text(clean_settings, encoding="utf-8")
    print("[PASS] V111 deleted duplicate guest switch UI, input gestures and dead settings")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v110_single_guest_dock.py <generated-LiveContainer>")
    apply(Path(sys.argv[1]))

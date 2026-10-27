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

    source = share_direct_guest_ui(source)
    source = repair_unresponsive_shared_picker(source)
    source = apply_native_glass_picker(source)
    audit(source)
    return source

def share_direct_guest_ui(source: str) -> str:
    """Route Direct to the SAME existing V72 UIKit picker; no new panel."""
    if "SCARLET_V112_SHARED_GUEST_UI" in source:
        return source
    source = unique(source,
        '''    private var nrgV102WindowActionRequest = false
''',
        '''    private var nrgV102WindowActionRequest = false
    // SCARLET_V112_SHARED_GUEST_UI: Direct and LiveProcess invoke one renderer.
    // This flag changes only the available action (restart vs retained view).
    private var nrgV112DirectGuestRequest = false
    @objc(nrgV112PresentDirectGuestUIFrom:sourceView:)
    public func nrgV112PresentDirectGuestUI(from controller: UIViewController,
                                           sourceView: UIView) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self, weak controller, weak sourceView] in
                guard let controller, let sourceView else { return }
                self?.nrgV112PresentDirectGuestUI(from: controller, sourceView: sourceView)
            }
            return
        }
        nrgV112DirectGuestRequest = true
        defer { nrgV112DirectGuestRequest = false }
        nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)
    }
''', "common Direct picker entry")
    source = unique(source,
        '''        let windowActions = nrgV102WindowActionRequest
        let models = DataManager.shared.model.apps
''',
        '''        let windowActions = nrgV102WindowActionRequest
        let directMode = nrgV112DirectGuestRequest
        // No host DataManager/window registry is required inside a Classic
        // guest process. The panel uses the same SwiftUI/UIKit renderer.
        let models = directMode ? [] : DataManager.shared.model.apps
''', "Direct does not assume host model is alive")
    source = unique(source,
        '''        if #available(iOS 16.1, *) {
            nativeFolders = Set(MultitaskWindowManager.appDict.values.compactMap''',
        '''        if #available(iOS 16.1, *), !directMode {
            nativeFolders = Set(MultitaskWindowManager.appDict.values.compactMap''',
        "Direct does not enumerate host window manager")
    source = unique(source,
        '''        heading.text = windowActions ? "창 관리" : "최근 실행 앱"
''',
        '''        heading.text = windowActions ? "창 관리" : "최근 실행 앱"
''', "keep same picker heading")
    source = unique(source,
        '''        subtitle.text = windowActions ? "현재 게스트 창" : "Scarlet Crystal 내부 · 최근 활성화 순"
''',
        '''        subtitle.text = windowActions ? "현재 게스트 창"
            : directMode ? "현재 게스트 · 다른 앱으로 전환하려면 재시작 필요"
            : "Scarlet Crystal 내부 · 최근 활성화 순"
''', "mode-specific factual subtitle")
    source = unique(source,
        '''        let listHeight = min(CGFloat(max(1, windowActions ? actionsCount : recent.count)) * 54, maxListHeight)
''',
        '''        let listHeight = min(CGFloat(max(1, directMode ? 2
            : (windowActions ? actionsCount : recent.count))) * 54, maxListHeight)
''', "shared panel height")
    source = unique(source,
        '''        if recent.isEmpty && !windowActions {
''',
        '''        if recent.isEmpty && !windowActions && !directMode {
''', "hide misleading Direct empty-state")
    source = unique(source,
        '''        if !windowActions {
        for guest in recent {
''',
        '''        if directMode {
            // The same V100 row style and collapse animation for either mode.
            // Direct cannot preserve its current process while switching apps.
            // This is the only operation that differs, not a second UI.
            let notice = UILabel()
            notice.text = "현재 앱을 종료하면 미저장 진행 상황이 사라질 수 있어."
            notice.font = UIFont.systemFont(ofSize: 12)
            notice.numberOfLines = 2
            notice.textAlignment = .center
            notice.textColor = .secondaryLabel
            rows.addArrangedSubview(notice)

            let item = UIButton(type: .system)
            item.accessibilityIdentifier = "scarlet.v112.direct.restart"
            item.accessibilityLabel = "재시작 후 Scarlet Crystal로 복귀"
            item.contentHorizontalAlignment = .center
            item.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .semibold)
            item.layer.cornerRadius = 15
            item.backgroundColor = UIColor.secondarySystemGroupedBackground
            item.setTitle("재시작 후 Scarlet Crystal로 복귀", for: .normal)
            item.setTitleColor(.label, for: .normal)
            item.heightAnchor.constraint(equalToConstant: 47).isActive = true
            item.addAction(UIAction { _ in
                // This row states exactly what will restart; no implicit
                // guest exit, credential change, or destructive storage action.
                collapse {
                    guard controller.view.window != nil,
                          controller.responds(to: NSSelectorFromString("nrgV112RestartDirectGuest"))
                    else {
                        NSLog("[SCARLET_V112_UI] direct_restart_route_unavailable=1")
                        return
                    }
                    _ = controller.perform(NSSelectorFromString("nrgV112RestartDirectGuest"))
                }
            }, for: .touchUpInside)
            rows.addArrangedSubview(item)
        } else if !windowActions {
        for guest in recent {
''', "Direct action in existing common renderer")
    source = unique(source,
        '''        footer.text = windowActions ? "바깥을 누르면 창 관리 닫기" : "바깥을 누르면 앱 전환 닫기"
''',
        '''        footer.text = windowActions ? "바깥을 누르면 창 관리 닫기"
            : "바깥을 누르면 앱 전환 닫기"
''', "same footer across modes")
    # A runtime-visible ObjC bridge contains no screen or duplicate layout.
    source += '''
// One bridge to the ONE picker. This is not another presenter or view.
@available(iOS 16.0, *)
@objc(SCUnifiedGuestUIBridge)
public final class SCUnifiedGuestUIBridge: NSObject {
    @objc(presentFrom:sourceView:)
    public class func present(from controller: UIViewController, sourceView: UIView) {
        MultitaskDockManager.shared.nrgV112PresentDirectGuestUI(
            from: controller, sourceView: sourceView)
    }
}
'''
    return source

def repair_unresponsive_shared_picker(source: str) -> str:
    """One common picker exposes both recent guests and window controls.

    No additional UIViewController, window, floating icon, or independent
    screen is created. The same UIKit material panel is reconfigured using
    the existing V72/V102 actions. Direct can show the same controls but
    cannot perform retained-window actions on a Classic guest process.
    """
    if "SCARLET_V114_PICKER_TABS" in source:
        return source
    source = unique(
        source,
        '''    private var nrgV112DirectGuestRequest = false
''',
        '''    private var nrgV112DirectGuestRequest = false
    // SCARLET_V114_PICKER_TABS: both modes share the V72 picker and tabs.
    private var nrgV114DirectWindowActionsRequest = false
''', "Direct picker selection state")
    source = unique(
        source,
        '''        let windowActions = nrgV102WindowActionRequest
        let directMode = nrgV112DirectGuestRequest
''',
        '''        let directMode = nrgV112DirectGuestRequest
        let windowActions = nrgV102WindowActionRequest ||
            (directMode && nrgV114DirectWindowActionsRequest)
''', "one picker handles both tab modes")
    source = unique(
        source,
        '''        content.addArrangedSubview(subtitle)

        let scroll = UIScrollView()
''',
        '''        content.addArrangedSubview(subtitle)

        // The original V72 native panel provides both modes to Direct and
        // LiveProcess. No secondary dock, sheet or alert is constructed.
        let tabPicker = UISegmentedControl(items: ["최근 실행 앱", "창 관리"])
        tabPicker.accessibilityIdentifier = "scarlet.v114.shared.guest.tabs"
        tabPicker.selectedSegmentIndex = windowActions ? 1 : 0
        tabPicker.setEnabled(directMode ||
            (controller is DecoratedAppSceneViewController), forSegmentAt: 1)
        content.addArrangedSubview(tabPicker)

        let scroll = UIScrollView()
''', "two entry modes within one common panel")
    source = unique(
        source,
        '''        overlay.addAction(UIAction { _ in collapse({}) }, for: .touchUpInside)

        if recent.isEmpty''',
        '''        overlay.addAction(UIAction { _ in collapse({}) }, for: .touchUpInside)
        tabPicker.addAction(UIAction { [weak self, weak controller, weak sourceView, weak tabPicker] _ in
            guard let self, let controller, let sourceView, let tabPicker else { return }
            let targetWindowActions = tabPicker.selectedSegmentIndex == 1
            guard targetWindowActions != windowActions else { return }
            // SCARLET_V125_TAB_TRANSITION: keep the same modal visible
            // until the replacement content is ready; avoid the old
            // collapse-to-trigger shrink between tab selections.
            let switchContent = {
                if directMode {
                    self.nrgV114DirectWindowActionsRequest = targetWindowActions
                    self.nrgV112PresentDirectGuestUI(from: controller, sourceView: sourceView)
                } else if targetWindowActions {
                    self.nrgV102PresentWindowActions(from: controller, sourceView: sourceView)
                } else {
                    self.nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)
                }
            }
            if UIAccessibility.isReduceMotionEnabled {
                collapse { switchContent() }
            } else {
                // The existing panel owns the transition; never add a
                // competing window, gesture recognizer or overlay.
                collapse { switchContent() }
            }
        }, for: .valueChanged)

        if recent.isEmpty''', "use the existing picker on tab switch")
    source = unique(
        source,
        '''            notice.text = "현재 앱을 종료하면 미저장 진행 상황이 사라질 수 있어."
''',
        '''            notice.text = windowActions
                ? "Direct 실행은 독립 창 조작을 지원하지 않아. 복귀 후 창을 관리할 수 있어."
                : "Direct에서는 다른 앱으로 즉시 전환할 수 없어. 복귀 후 최근 앱을 확인할 수 있어."
''', "accurate Direct mode feature availability")
    source = unique(
        source,
        '''        guard let owner = sourceView.window,
              owner.windowScene?.activationState == .foregroundActive,
              (windowActions || controller.view.window != nil),
              sourceView.isHidden == false else { return }
''',
        '''        guard let owner = sourceView.window,
              owner.windowScene?.activationState == .foregroundActive,
              (windowActions || controller.view.window != nil),
              sourceView.isHidden == false else {
            NSLog("[SCARLET_V114_UI] picker_guard_rejected source_window=%d root_window=%d hidden=%d",
                  sourceView.window != nil ? 1 : 0,
                  controller.view.window != nil ? 1 : 0,
                  sourceView.isHidden ? 1 : 0)
            return
        }
''', "log existing UIKit guard instead of silent no-op")
    return source

def apply_native_glass_picker(source: str) -> str:
    """V125: use system glass in the one existing UIKit picker."""
    marker = "SCARLET_V125_NATIVE_GLASS"
    if marker in source:
        return source
    source = unique(source,
        "        let material = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))",
        """        // SCARLET_V125_NATIVE_GLASS: native iOS glass; accessible fallback.
        let material = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            material.effect = UIGlassEffect()
        }""", "native system glass")
    source = unique(source,
        '        tabPicker.selectedSegmentIndex = windowActions ? 1 : 0\n',
        '''        tabPicker.selectedSegmentIndex = windowActions ? 1 : 0
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            tabPicker.backgroundColor = .clear
        }
''', "glass tab background")
    return source

def audit(source: str) -> None:
    for token in (
        MARK, "SCARLET_V112_SHARED_GUEST_UI",
        "SCARLET_V114_PICKER_TABS",
        'tabPicker.accessibilityIdentifier = "scarlet.v114.shared.guest.tabs"',
        "nrgV114DirectWindowActionsRequest = targetWindowActions",
        "@objc(SCUnifiedGuestUIBridge)",
        "nrgV112PresentDirectGuestUI(from: controller, sourceView: sourceView)",
        "scarlet.v112.direct.restart",
        "controller.perform(NSSelectorFromString",
        "public func nrgV72PresentGuestSwitcher(",
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

// Scarlet Crystal PR48 full-screen guest overlay.
// All UIKit overlay operations are limited to our own separate non-key UIWindow.
// No changes to the guest's frame, orientation, safe areas, root view, P12, or LCAppModel.runApp().
import Foundation
import SwiftUI
import UIKit

// PR48 uses one foreground guest process. Listed installed guests are relaunch
// targets, not concurrently running processes.
struct ScarletGuestSwitchTarget: Identifiable {
    let id: String                       // verified *.app directory name
    let title: String
    let containerID: String?
    let classicMode: UInt
    let isCurrent: Bool
    let canSwitch: Bool
    let isShared: Bool
    let icon: UIImage?
    let reason: String?
}

// A separate non-key UIWindow can still swallow touches in transparent
// corners. Only the visible round button or the expanded card is interactive;
// all other touches fall through to the full-screen guest.
@available(iOS 17.0, *)
final class ScarletGuestTouchPassthroughWindow: UIWindow {
    var isExpanded = false
    var dockRight = false
    // A stable full-scene non-key window avoids clipping the 62pt glass
    // circle inside a 72pt moving UIWindow. All taps outside the exact
    // circle and panel pass through to the running guest.
    var buttonCenter: CGPoint = .zero
    var panelRect: CGRect = .zero

    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        guard bounds.contains(point) else { return false }
        if hypot(point.x - buttonCenter.x, point.y - buttonCenter.y) <= 35 {
            return super.point(inside: point, with: event)
        }
        return isExpanded && panelRect.contains(point) &&
            super.point(inside: point, with: event)
    }
}

@available(iOS 17.0, *)
struct ScarletFullscreenGuestFloatingTab: View {
    let guestTitle: String
    let reloadApps: () -> [ScarletGuestSwitchTarget]
    let onPanel: (Bool, Int) -> Void
    let initialDockRight: Bool
    let initialButtonCenter: CGPoint
    let onSwitch: (ScarletGuestSwitchTarget) -> Bool
    let onExit: () -> Void

    @State private var isOpen = false
    @State private var apps: [ScarletGuestSwitchTarget] = []
    @State private var feedback: String?
    @State private var transitionVersion = 0
    @State private var dockRight = false
    @State private var screenButtonCenter = CGPoint.zero
    @AppStorage("Scarlet.Feature.SwitcherMotion.V1",
                store: LCUtils.appGroupUserDefault) private var switcherMotion = true
    @AppStorage("Scarlet.Feature.SwitcherHaptics.V1",
                store: LCUtils.appGroupUserDefault) private var switcherHaptics = true

    private let spring = Animation.spring(response: 0.47, dampingFraction: 0.82)

    private var otherApps: [ScarletGuestSwitchTarget] {
        // Only an actual active LiveProcess/guest scene is switchable.
        // Previously launched-but-terminated apps belong in the App List.
        apps.filter { !$0.isCurrent && $0.canSwitch }
    }

    private func openPanel() {
        apps = reloadApps()
        feedback = nil
        transitionVersion += 1
        onPanel(true, apps.count)
        if switcherHaptics {
            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
        }
        withAnimation(switcherMotion ? spring : nil) { isOpen = true }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_opened",
            fields: ["count": String(apps.count), "api": "UIKit.UIGlassEffect"])
    }

    private func closePanel() {
        transitionVersion += 1
        let version = transitionVersion
        withAnimation(switcherMotion ? spring : nil) { isOpen = false }
        Task { @MainActor in
            if switcherMotion {
                try? await Task.sleep(for: .milliseconds(390))
            }
            if version == transitionVersion && !isOpen { onPanel(false, apps.count) }
        }
    }

    private func switchTo(_ target: ScarletGuestSwitchTarget) {
        if target.isCurrent {
            closePanel()
            return
        }
        guard target.canSwitch else {
            if switcherHaptics {
                UINotificationFeedbackGenerator().notificationOccurred(.warning)
            }
            feedback = "이 앱은 먼저 앱 목록에서 한 번 실행·서명해야 합니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_target_needs_setup",
                fields: ["reason": "unprepared_guest"])
            return
        }
        if switcherHaptics {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
        if !onSwitch(target) {
            feedback = "실행 중이던 세션이 종료됐습니다. 앱 목록에서 다시 실행할 수 있습니다."
            if switcherHaptics {
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
        }
    }

    // Draw the optical surface behind independent readable foreground content.
    // SwiftUI glass matched-IDs across a resizing UIWindow blanked the card.
    @ViewBuilder
    private func glassPlate(radius: CGFloat) -> some View {
        // Exact native material owner used by the main container tab.
        SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }

    // The title passed from UIKit can be a bundle identifier. Only show
    // the name read from a current, real guest Info.plist, not a virtual path.
    private var currentAppName: String {
        apps.first(where: { $0.isCurrent })?.title ?? "현재 실행 중인 앱"
    }

    private func otherAppRow(_ app: ScarletGuestSwitchTarget) -> some View {
        Button {
            switchTo(app)
        } label: {
            HStack(spacing: 11) {
                Group {
                    if let icon = app.icon {
                        Image(uiImage: icon)
                            .resizable()
                            .interpolation(.high)
                            .scaledToFit()
                    } else {
                        Image(systemName: "app.fill")
                            .font(.title2)
                    }
                }
                .frame(width: 43, height: 43)
                .background(.white.opacity(0.13),
                            in: RoundedRectangle(cornerRadius: 11))
                .clipShape(RoundedRectangle(cornerRadius: 11))
                Text(app.title)
                    .font(.subheadline.weight(.medium)).lineLimit(1)
                Spacer(minLength: 0)
                Image(systemName: app.canSwitch ? "arrow.left.arrow.right.circle.fill"
                                               : "exclamationmark.circle")
                    .font(.title3)
                    .foregroundStyle(app.canSwitch ? Color.accentColor : Color.secondary)
            }
            .padding(.vertical, 5)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("SCARLET_PR48_GUEST_SWITCH_TARGET")
    }

    private var appPanelContent: some View {
        ZStack(alignment: .topLeading) {
            glassPlate(radius: 28)
                .allowsHitTesting(false)
            VStack(alignment: .leading, spacing: 16) {
                HStack(spacing: 9) {
                    Image(systemName: "square.stack.3d.up.fill").font(.headline)
                    Text("앱 전환").font(.title3.weight(.semibold))
                    Spacer(minLength: 0)
                }
                if otherApps.isEmpty {
                    Text("다른 실행 중인 앱 없음")

                        .font(.footnote).foregroundStyle(.secondary)
                } else {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(otherApps) { entry in otherAppRow(entry) }
                        }
                    }
                    .frame(maxHeight: 300)
                }
                if let feedback {
                    Text(feedback).font(.caption).foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                Button {
                    if switcherHaptics {
                        UINotificationFeedbackGenerator().notificationOccurred(.success)
                    }
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "fullscreen_tab_exit_requested")
                    onExit()
                } label: {
                    Label("앱 목록", systemImage: "rectangle.portrait.and.arrow.right")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 46)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("SCARLET_PR48_GUEST_EXIT")
            }
            .padding(19)
            .foregroundStyle(.primary)
            .zIndex(2)
        }
        .frame(maxWidth: .infinity, minHeight: 210, maxHeight: 435)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        // One contrast-aware boundary, not the two overlapping UIKit and
        // SwiftUI rims. The main tab still uses the original UIKit rim.
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.24), lineWidth: 0.75)
                .allowsHitTesting(false)
        }
        // No oversized translucent shadow: its layer was clipped to the
        // separate transparent UIWindow and left rectangular/halo artifacts.
        .padding(.horizontal, 12)
        .onAppear {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_panel_content_rendered",
                fields: ["count": String(apps.count)])
        }
        .accessibilityIdentifier("SCARLET_PR48_AIRPODS_GLASS_PANEL")
    }

    private var appPanel: some View { appPanelContent }

    private var roundTabButton: some View {
        Button {
            if isOpen { closePanel() } else { openPanel() }
        } label: {
            ZStack {
                Circle()
                    .fill(.clear)
                    .background {
                        if #available(iOS 26.0, *),
                           !UIAccessibility.isReduceTransparencyEnabled {
                            SCNativeLiquidGlassSurface(cornerRadius: 31, showsRim: false)
                                .clipShape(Circle())
                        } else {
                            Circle().fill(.regularMaterial)
                        }
                    }
                    .overlay {
                        Circle()
                            .strokeBorder(Color.primary.opacity(0.28), lineWidth: 0.8)
                    }
                Group {
                    if switcherMotion {
                        Image(systemName: isOpen ? "xmark" : "square.stack.3d.up.fill")
                            .symbolEffect(.bounce, value: isOpen)
                    } else {
                        Image(systemName: isOpen ? "xmark" : "square.stack.3d.up.fill")
                    }
                }
                .font(.system(size: 23, weight: .semibold))
                .foregroundStyle(.primary)
            }
            .frame(width: 62, height: 62)
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        // Native pan handles dragging in stable screen coordinates.
        .accessibilityHint("드래그하여 위치를 옮길 수 있습니다")
        .accessibilityIdentifier("SCARLET_PR48_GUEST_ROUND_TAB")
    }

    @ViewBuilder
    private var roundTab: some View {
        roundTabButton
    }

    var body: some View {
        GeometryReader { geometry in
            let panelWidth = min(CGFloat(430), max(CGFloat(72), geometry.size.width - 32))
            let panelHeight = min(panelWidth * 1.02, CGFloat(435),
                                  max(CGFloat(210), geometry.size.height - 156))
            ZStack(alignment: .topLeading) {
                // The panel may be centered independently of the button.
                // Neither opening nor closing moves its screen-space center.
                if isOpen {
                    appPanel
                        .frame(width: panelWidth, height: panelHeight)
                        .position(x: geometry.size.width / 2,
                                  y: geometry.size.height / 2)
                        .transition(.opacity.combined(with: .scale(scale: 0.96)))
                }
                roundTab
                    .frame(width: 72, height: 72)
                    .position(x: screenButtonCenter.x, y: screenButtonCenter.y)
            }
            .frame(width: geometry.size.width, height: geometry.size.height)
        }
        .ignoresSafeArea()
        .animation(switcherMotion ? spring : nil, value: isOpen)
        .onAppear {
            screenButtonCenter = initialButtonCenter
            dockRight = initialDockRight
        }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletGuestFloatingDockChanged"))) { note in
            if let x = note.userInfo?["x"] as? CGFloat,
               let y = note.userInfo?["y"] as? CGFloat {
                screenButtonCenter = CGPoint(x: x, y: y)
            }
            if let right = note.userInfo?["right"] as? Bool {
                dockRight = right
            }
        }
    }
}

// UIkit pan tracks finger in fixed screen space; no moving-window feedback.
@available(iOS 17.0, *)
@MainActor
private final class ScarletGuestScreenPan: NSObject, UIGestureRecognizerDelegate {
    let onChange: (CGPoint, UIGestureRecognizer.State) -> Void
    init(onChange: @escaping (CGPoint, UIGestureRecognizer.State) -> Void) {
        self.onChange = onChange
        super.init()
    }
    func gestureRecognizerShouldBegin(_ recognizer: UIGestureRecognizer) -> Bool {
        guard let view = recognizer.view,
              let overlay = view.window as? ScarletGuestTouchPassthroughWindow,
              !overlay.isExpanded else { return false }
        let point = recognizer.location(in: overlay)
        // V10 is a full-scene overlay. The button is at a persisted absolute
        // screen point, NOT the bottom corner of the UIWindow.
        return hypot(point.x - overlay.buttonCenter.x,
                     point.y - overlay.buttonCenter.y) <= 35
    }
    @objc func didPan(_ gesture: UIPanGestureRecognizer) {
        guard let window = gesture.view?.window else { return }
        let point = gesture.location(in: window)
        let screenPoint = window.convert(point, to: window.screen.coordinateSpace)
        onChange(screenPoint, gesture.state)
    }
}

@available(iOS 17.0, *)
@MainActor
@objc(ScarletFullscreenGuestTabInstaller)
final class ScarletFullscreenGuestTabInstaller: NSObject {
    private static var floatingWindow: ScarletGuestTouchPassthroughWindow?
    private static weak var guestWindow: UIWindow?
    private static var dragOrigin: CGPoint?
    private static var dragCenter: CGPoint?
    private static var dragStartScreen: CGPoint?
    private static var dragHandler: ScarletGuestScreenPan?
    private static var rotationObserver: NSObjectProtocol?
    private static var rotationGeneration = 0
    private static var lastStableSceneSize: CGSize?
    private static var rotationWatchTask: Task<Void, Never>?
    private static var lastFailure: String?
    private static let positionXKey = "ScarletGuestRoundTabCenterXFractionV1"
    private static let positionYKey = "ScarletGuestRoundTabCenterYFractionV1"

    private static func allowedCenter(_ value: CGPoint, in window: UIWindow) -> CGPoint {
        let b = window.windowScene?.coordinateSpace.bounds ?? window.bounds
        let safe = window.safeAreaInsets
        let loX = safe.left + 38
        let hiX = max(loX, b.width - safe.right - 38)
        let loY = safe.top + 38
        let hiY = max(loY, b.height - safe.bottom - 38)
        return CGPoint(x: min(max(value.x, loX), hiX),
                       y: min(max(value.y, loY), hiY))
    }

    private static func center(in window: UIWindow) -> CGPoint {
        if let dragCenter { return allowedCenter(dragCenter, in: window) }
        let b = window.windowScene?.coordinateSpace.bounds ?? window.bounds
        let defaults = UserDefaults.lc()
        let x = (defaults?.object(forKey: positionXKey) as? NSNumber)?.doubleValue
        let y = (defaults?.object(forKey: positionYKey) as? NSNumber)?.doubleValue
        let xFraction = (x?.isFinite == true && x! >= 0 && x! <= 1) ? x! : 0
        let yFraction = (y?.isFinite == true && y! >= 0 && y! <= 1) ? y! : 1
        let fallback = CGPoint(x: window.safeAreaInsets.left + 44,
                               y: b.height - window.safeAreaInsets.bottom - 44)
        return allowedCenter(
            CGPoint(x: x == nil ? fallback.x : b.width * xFraction,
                    y: y == nil ? fallback.y : b.height * yFraction),
            in: window)
    }

    private static func frame(in window: UIWindow) -> CGRect {
        // Stable full-screen *overlay only*; the guest's original UIWindow
        // and all of its safe areas/constraints remain untouched.
        window.windowScene?.coordinateSpace.bounds ?? window.bounds
    }

    private static func panelFrame(in window: UIWindow) -> CGRect {
        let b = window.bounds
        let panelWidth = min(CGFloat(430), max(CGFloat(72), b.width - 32))
        let panelHeight = min(panelWidth * 1.02, CGFloat(435),
                              max(CGFloat(210), b.height - 156))
        return CGRect(x: (b.width - panelWidth) / 2,
                      y: (b.height - panelHeight) / 2,
                      width: panelWidth, height: panelHeight)
    }

    private static func syncButtonCenter(in host: UIWindow) {
        guard let overlay = floatingWindow else { return }
        let point = center(in: host)
        overlay.buttonCenter = point
        overlay.dockRight = point.x >= host.bounds.midX
        NotificationCenter.default.post(
            name: Notification.Name("ScarletGuestFloatingDockChanged"),
            object: nil,
            userInfo: ["x": point.x, "y": point.y,
                       "right": point.x >= host.bounds.midX])
    }

    private static func placeFloatingWindow() {
        guard let guestWindow, let floatingWindow else { return }
        let next = frame(in: guestWindow)
        if floatingWindow.frame != next { floatingWindow.frame = next }
        floatingWindow.panelRect = panelFrame(in: floatingWindow)
        syncButtonCenter(in: guestWindow)
    }

    private static func panChanged(screenPoint: CGPoint, state: UIGestureRecognizer.State) {
        guard let host = guestWindow else { return }
        let bounds = host.windowScene?.coordinateSpace.bounds ?? host.bounds
        switch state {
        case .began:
            dragStartScreen = screenPoint
            dragOrigin = center(in: host)
        case .changed:
            guard let touch = dragStartScreen, let initial = dragOrigin else { return }
            dragCenter = allowedCenter(
                CGPoint(x: initial.x + screenPoint.x - touch.x,
                        y: initial.y + screenPoint.y - touch.y), in: host)
            syncButtonCenter(in: host)
        case .ended:
            if let current = dragCenter {
                let defaults = UserDefaults.lc()
                defaults?.set(Double(current.x / max(bounds.width, 1)), forKey: positionXKey)
                defaults?.set(Double(current.y / max(bounds.height, 1)), forKey: positionYKey)
                dragCenter = nil
                dragOrigin = nil
                dragStartScreen = nil
                syncButtonCenter(in: host)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "floating_tab_position_saved",
                    fields: ["result": "normalized_screen_center"])
            } else {
                dragStartScreen = nil
                dragOrigin = nil
            }
        case .cancelled, .failed:
            dragCenter = nil
            dragOrigin = nil
            dragStartScreen = nil
            placeFloatingWindow()
        default: break
        }
    }

    private static func resizeOverlay(open: Bool, appCount: Int) {
        guard let floating = floatingWindow else { return }
        // Toggling the panel never changes the UIWindow frame, the saved
        // button center, or the guest app view. Only hit testing expands.
        floating.isExpanded = open
        floating.panelRect = panelFrame(in: floating)
        UIView.performWithoutAnimation {
            floating.rootViewController?.view.setNeedsLayout()
            floating.rootViewController?.view.layoutIfNeeded()
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_geometry_applied",
            fields: ["state": open ? "expanded" : "collapsed",
                     "result": "button_center_unchanged"])
    }

    // UIDevice.orientationDidChangeNotification fires for face-up, sensor
    // jitter, and repeated orientations even if UIWindowScene does not resize.
    // V7 set alpha=0 for every event, causing flicker in portrait use.
    // Probe while visible; suspend only after real geometry changes.
    private static func settleOverlayAfterRotation() {
        guard let floatingWindow, let guestWindow else { return }
        guard rotationWatchTask == nil else { return }
        let original = guestWindow.windowScene?.coordinateSpace.bounds.size
            ?? guestWindow.bounds.size
        let baseline = lastStableSceneSize ?? original
        lastStableSceneSize = baseline
        let overlayIdentity = ObjectIdentifier(floatingWindow)
        rotationGeneration += 1
        let token = rotationGeneration
        rotationWatchTask = Task { @MainActor in
            defer {
                if rotationGeneration == token { rotationWatchTask = nil }
            }
            var previous = original
            var geometryChanged = false
            var stableSamples = 0
            for _ in 0..<18 {
                try? await Task.sleep(for: .milliseconds(65))
                guard !Task.isCancelled, rotationGeneration == token,
                      let host = self.guestWindow,
                      let overlay = self.floatingWindow,
                      ObjectIdentifier(overlay) == overlayIdentity
                else { return }
                let current = host.windowScene?.coordinateSpace.bounds.size
                    ?? host.bounds.size
                if abs(current.width - baseline.width) > 1 ||
                   abs(current.height - baseline.height) > 1 {
                    if !geometryChanged {
                        geometryChanged = true
                        overlay.alpha = 0
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "overlay_rotation_suspended",
                            fields: ["reason": "geometry_changed"])
                    }
                    if abs(current.width - previous.width) < 0.5 &&
                       abs(current.height - previous.height) < 0.5 {
                        stableSamples += 1
                    } else {
                        stableSamples = 0
                    }
                    if stableSamples >= 4 {
                        resizeOverlay(open: overlay.isExpanded, appCount: 0)
                        overlay.rootViewController?.view.setNeedsLayout()
                        overlay.rootViewController?.view.layoutIfNeeded()
                        lastStableSceneSize = current
                        overlay.alpha = 1
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "overlay_rotation_resumed",
                            fields: ["result": current.width > current.height
                                ? "landscape" : "portrait"])
                        return
                    }
                }
                previous = current
            }
            // No real scene rotation: do not hide, remount, or resize.
            guard geometryChanged, rotationGeneration == token,
                  let overlay = self.floatingWindow,
                  ObjectIdentifier(overlay) == overlayIdentity,
                  let host = self.guestWindow else { return }
            resizeOverlay(open: overlay.isExpanded, appCount: 0)
            lastStableSceneSize =
                host.windowScene?.coordinateSpace.bounds.size ?? host.bounds.size
            overlay.alpha = 1
            ScarletDiagnosticRecorder.shared.record(
                "guest", "overlay_rotation_unstable",
                status: "warning", fields: ["reason": "geometry_did_not_settle"])
        }
    }

    // Use the host's real LC_HOME_PATH rather than the guest-virtualized
    // Documents path. Only inspect existing bundles; do not create folders
    // or alter app metadata, certificates, or guest sandboxes.
    private static func installedApps() -> [ScarletGuestSwitchTarget] {
        let fm = FileManager.default
        guard let home = getenv("LC_HOME_PATH") else { return [] }
        let localHome = URL(fileURLWithPath: String(cString: home))
        let localRoot = localHome.appendingPathComponent("Documents")
        var locations: [(URL, URL, Bool)] = [
            (localRoot.appendingPathComponent("Applications"),
             localRoot.appendingPathComponent("Data/Application"), false)
        ]
        if let shared = LCSharedUtils.appGroupPath() {
            let base = shared.appendingPathComponent("LiveContainer")
            locations.append((base.appendingPathComponent("Applications"),
                              base.appendingPathComponent("Data/Application"), true))
        }

        let selected = UserDefaults.lc()?.string(forKey: "selected")
        // Registry includes only attached, visible native LiveProcess scenes.
        // A prior "lastLaunched" plist entry does NOT prove a process lives.
        let activeSceneIDs = Set(
            ScarletGuestSceneRegistry.availableGuests().map(\.id))
        var found = Set<String>()
        var result: [ScarletGuestSwitchTarget] = []

        for (appRoot, dataRoot, shared) in locations {
            guard let items = try? fm.contentsOfDirectory(at: appRoot,
                            includingPropertiesForKeys: [.isDirectoryKey],
                            options: [.skipsHiddenFiles]) else { continue }
            for url in items where url.pathExtension.lowercased() == "app" {
                let folder = url.lastPathComponent
                // LC's original launcher resolves local before shared apps.
                guard !found.contains(folder), !folder.hasPrefix("."),
                      (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true,
                      let appData = NSDictionary(contentsOf: url.appendingPathComponent("Info.plist"))
                              as? [String: Any],
                      let meta = NSDictionary(contentsOf: url.appendingPathComponent("LCAppInfo.plist"))
                              as? [String: Any],
                      let display = (appData["CFBundleDisplayName"] as? String) ??
                                    (appData["CFBundleName"] as? String),
                      !display.isEmpty,
                      (meta["isHidden"] as? Bool) != true,
                      (meta["isLocked"] as? Bool) != true else { continue }
                found.insert(folder)

                let containers = meta["LCContainers"] as? [[String: Any]] ?? []
                let selectedID = (meta["LCDataUUID"] as? String) ??
                                 (containers.first?["folderName"] as? String)
                let containerExists = selectedID.flatMap { id in
                    let p = dataRoot.appendingPathComponent(id).path
                    var directory = ObjCBool(false)
                    return fm.fileExists(atPath: p, isDirectory: &directory) &&
                            directory.boolValue ? id : nil
                }
                // Guest orientation is declared by its signed app itself.
                // Host supports landscape already; portrait-only guests cannot
                // safely be forced without stretching their UIWindow.
                let orientationList = appData["UISupportedInterfaceOrientations"]
                    as? [String] ?? []
                let supportsLandscape = orientationList.contains(
                    "UIInterfaceOrientationLandscapeLeft") ||
                    orientationList.contains("UIInterfaceOrientationLandscapeRight")
                if folder == selected {
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "orientation_capability_checked",
                        fields: ["result": orientationList.isEmpty
                            ? "unspecified"
                            : (supportsLandscape ? "landscape_supported"
                                                : "portrait_only")])
                }
                let hasExecuted = meta["lastLaunched"] is Date
                let isCurrent = folder == selected
                let activeScene = containerExists.map {
                    activeSceneIDs.contains($0) && MultitaskManager.isUsing(container: $0)
                } ?? false
                guard isCurrent || activeScene else { continue }
                let needsJIT = (meta["isJITNeeded"] as? Bool) == true
                        || (appData["LC32BitTranslationLayer"] != nil)
                let nonInjected = (meta["dontLoadTweakLoader"] as? Bool) == true
                        || (meta["dontInjectTweakLoader"] as? Bool) == true
                let requestedClassic = (meta["classicMode"] as? Bool) == true
                let classicCache = meta["LCClassicModeCache"] as? [String: Any]
                let cachedMode = classicCache?["defaultClassicMode"] as? NSNumber
                let modeIsCurrent = (classicCache?["systemMajorVersion"] as? Int)
                        == ProcessInfo.processInfo.operatingSystemVersion.majorVersion
                let compatibleClassic = !requestedClassic
                        || (cachedMode != nil && modeIsCurrent)
                let canSwitch = activeScene
                        && containerExists != nil
                        && hasExecuted && !needsJIT && !nonInjected
                        && compatibleClassic
                let iconFile = url.appendingPathComponent("LCAppIconLight.png")
                result.append(ScarletGuestSwitchTarget(
                    id: folder, title: display, containerID: containerExists,
                    classicMode: requestedClassic ? UInt(cachedMode?.uintValue ?? 0) : 0,
                    isCurrent: isCurrent, canSwitch: canSwitch,
                    isShared: shared,
                    icon: UIImage(contentsOfFile: iconFile.path),
                    reason: canSwitch ? nil : "needs_host_setup"))
            }
        }
        result.sort {
            if $0.isCurrent != $1.isCurrent { return $0.isCurrent }
            return $0.title.localizedStandardCompare($1.title) == .orderedAscending
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_candidates_scanned",
            fields: ["count": String(result.count),
                     "result": "live_scenes_only"])
        return result
    }

    // The previously launched target is already prepared by the exact native
    // LCAppModel.runApp signing/container workflow. We use LC's own existing
    // selected / selectedContainer boot keys, not any virtual-window API.
    private static func switchGuest(to target: ScarletGuestSwitchTarget) -> Bool {
        guard target.canSwitch, !target.isCurrent,
              let container = target.containerID,
              let defaults = UserDefaults.lc() else { return false }
        // Revalidate that it is still a prepared, accessible LC guest.
        guard installedApps().contains(where: { $0.id == target.id && $0.canSwitch })
        else { return false }
        // A running native LiveContainer multitask scene owns live RAM state.
        // Activate it in place instead of terminating it via the legacy
        // launchToGuestApp path. Never create a virtual-sized app window here.
        if #available(iOS 16.1, *),
           MultitaskManager.isUsing(container: container),
           (MultitaskWindowManager.openExistingAppWindow(dataUUID: container) ||
            MultitaskDockManager.shared.bringMultitaskViewToFront(uuid: container)) {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_existing_multitask_session",
                status: "success", fields: ["result": "memory_session_resumed"])
            return true
        }
        // Do not silently kill the current fullscreen guest by invoking
        // launchToGuestApp. This would destroy in-memory work in the app.
        // A terminated target is available through the host's App List.
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_requires_relaunch",
            status: "blocked", fields: ["reason": "single_process_fullscreen"])
        return false
    }

    @objc(installForGuestName:)
    static func installForGuestName(_ rawName: NSString) {
        guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive ||
                                $0.activationState == .foregroundInactive }),
              let original = scene.windows.first(where: { $0.isKeyWindow }),
              original.rootViewController?.viewIfLoaded?.window != nil else {
            if lastFailure != "window_not_ready" {
                lastFailure = "window_not_ready"
                NSLog("[SCARLET_GUEST_TAB] window_not_ready")
            }
            return
        }
        if let floatingWindow, floatingWindow.windowScene === scene,
           !floatingWindow.isHidden {
            guestWindow = original
            if floatingWindow.alpha > 0 { placeFloatingWindow() }
            return
        }
        rotationGeneration += 1
        rotationWatchTask?.cancel()
        rotationWatchTask = nil
        floatingWindow?.isHidden = true
        floatingWindow = nil
        guestWindow = original
        lastStableSceneSize = scene.coordinateSpace.bounds.size
        dragOrigin = nil
        dragCenter = nil
        dragStartScreen = nil
        dragHandler = nil

        let name = (rawName as String).isEmpty ? "현재 게스트" : rawName as String
        let content = ScarletFullscreenGuestFloatingTab(
            guestTitle: name,
            reloadApps: installedApps,
            onPanel: resizeOverlay,
            initialDockRight: center(in: original).x >=
                (original.windowScene?.coordinateSpace.bounds ?? original.bounds).midX,
            initialButtonCenter: center(in: original),
            onSwitch: switchGuest,
            onExit: {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_tab_exit_requested")
                guard let defaults = UserDefaults.lc() else { return }
                defaults.set("ui", forKey: "selected")
                defaults.removeObject(forKey: "selectedContainer")
                _ = LCSharedUtils.launchToGuestApp(withClassicMode: 0)
            }
        )
        let overlay = ScarletGuestTouchPassthroughWindow(windowScene: scene)
        overlay.windowLevel = UIWindow.Level.alert + 1
        overlay.backgroundColor = .clear
        overlay.isOpaque = false
        overlay.layer.backgroundColor = UIColor.clear.cgColor
        overlay.layer.masksToBounds = false
        let controller = UIHostingController(rootView: content)
        controller.view.backgroundColor = .clear
        controller.view.isOpaque = false
        let panHandler = ScarletGuestScreenPan(onChange: panChanged)
        let pan = UIPanGestureRecognizer(target: panHandler,
                                        action: #selector(ScarletGuestScreenPan.didPan(_:)))
        pan.delegate = panHandler
        pan.cancelsTouchesInView = true
        controller.view.addGestureRecognizer(pan)
        dragHandler = panHandler
        overlay.rootViewController = controller
        overlay.frame = frame(in: original)
        overlay.buttonCenter = center(in: original)
        overlay.panelRect = panelFrame(in: overlay)
        // Stay non-key to protect guest keyboard and all native presentations.
        overlay.isHidden = false
        floatingWindow = overlay
        if rotationObserver == nil {
            rotationObserver = NotificationCenter.default.addObserver(
                forName: UIDevice.orientationDidChangeNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in
                    settleOverlayAfterRotation()
                }
            }
        }
        lastFailure = nil
        NSLog("[SCARLET_GUEST_TAB] mounted_nonkey_window")
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_tab_mounted",
            fields: ["api": "UIKit.UIWindow", "material_owner": "system"])
    }
}

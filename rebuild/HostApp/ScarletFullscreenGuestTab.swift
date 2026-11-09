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
    var panelHitHeight: CGFloat = 270

    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        let circleX = dockRight ? bounds.width - 36 : CGFloat(36)
        let circleY = bounds.height - 36
        let dx = point.x - circleX
        let dy = point.y - circleY
        if dx * dx + dy * dy <= 35 * 35 {
            return super.point(inside: point, with: event)
        }
        guard isExpanded else { return false }
        let panelBottom = bounds.height - 79
        let top = max(CGFloat(0), panelBottom - panelHitHeight)
        let panel = CGRect(x: 12, y: top,
                           width: max(0, bounds.width - 24),
                           height: max(0, panelBottom - top))
        return panel.contains(point) && super.point(inside: point, with: event)
    }
}

@available(iOS 17.0, *)
struct ScarletFullscreenGuestFloatingTab: View {
    let guestTitle: String
    let reloadApps: () -> [ScarletGuestSwitchTarget]
    let onPanel: (Bool, Int) -> Void
    let initialDockRight: Bool
    let onSwitch: (ScarletGuestSwitchTarget) -> Bool
    let onExit: () -> Void

    @State private var isOpen = false
    @State private var apps: [ScarletGuestSwitchTarget] = []
    @State private var feedback: String?
    @State private var transitionVersion = 0
    @State private var dockRight = false

    private let spring = Animation.spring(response: 0.47, dampingFraction: 0.82)

    private var otherApps: [ScarletGuestSwitchTarget] {
        apps.filter { !$0.isCurrent }
    }

    private func openPanel() {
        apps = reloadApps()
        feedback = nil
        transitionVersion += 1
        onPanel(true, apps.count)
        UIImpactFeedbackGenerator(style: .soft).impactOccurred()
        withAnimation(spring) { isOpen = true }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_opened",
            fields: ["count": String(apps.count), "api": "UIKit.UIGlassEffect"])
    }

    private func closePanel() {
        transitionVersion += 1
        let version = transitionVersion
        withAnimation(spring) { isOpen = false }
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(390))
            if version == transitionVersion && !isOpen { onPanel(false, apps.count) }
        }
    }

    private func switchTo(_ target: ScarletGuestSwitchTarget) {
        if target.isCurrent {
            closePanel()
            return
        }
        guard target.canSwitch else {
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
            feedback = "이 앱은 먼저 앱 목록에서 한 번 실행·서명해야 합니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_target_needs_setup",
                fields: ["reason": "unprepared_guest"])
            return
        }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        if !onSwitch(target) {
            feedback = "전환 요청에 실패했습니다. 앱 목록에서 실행해 주세요."
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    // Draw the optical surface behind independent readable foreground content.
    // SwiftUI glass matched-IDs across a resizing UIWindow blanked the card.
    @ViewBuilder
    private func glassPlate(radius: CGFloat) -> some View {
        // Exact native material owner used by the main container tab.
        SCNativeLiquidGlassSurface(cornerRadius: radius)
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }

    private var currentAppCard: some View {
        HStack(spacing: 11) {
            Image(systemName: "app.fill")
                .font(.system(size: 25))
                .frame(width: 43, height: 43)
                .background(.white.opacity(0.13),
                            in: RoundedRectangle(cornerRadius: 13))
            VStack(alignment: .leading, spacing: 3) {
                Text(guestTitle)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Image(systemName: "checkmark.circle.fill")
                    .font(.caption).foregroundStyle(.green)
                    .accessibilityLabel("현재 실행 중")
            }
            Spacer(minLength: 0)
        }
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
                currentAppCard
                Divider().opacity(0.5)
                if otherApps.isEmpty {
                    Text("전환 가능한 앱 없음")
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
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
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
        .frame(maxWidth: .infinity, minHeight: 300, maxHeight: 435)
        .padding(.horizontal, 12)
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .strokeBorder(
                    LinearGradient(colors: [.white.opacity(0.58),
                                            .white.opacity(0.12),
                                            .white.opacity(0.42)],
                                   startPoint: .topLeading, endPoint: .bottomTrailing),
                    lineWidth: 0.9)
                .allowsHitTesting(false)
        }
        .shadow(color: .black.opacity(0.19), radius: 20, y: 9)
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
                            SCNativeLiquidGlassSurface(cornerRadius: 31).clipShape(Circle())
                        } else {
                            Circle().fill(.regularMaterial)
                        }
                    }
                    .overlay {
                        Circle()
                            .strokeBorder(.white.opacity(0.58), lineWidth: 0.85)
                    }
                Image(systemName: isOpen ? "xmark" : "square.stack.3d.up.fill")
                    .font(.system(size: 23, weight: .semibold))
                    .symbolEffect(.bounce, value: isOpen)
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

    private var panelStack: some View {
        VStack(alignment: dockRight ? .trailing : .leading, spacing: 9) {
            if isOpen {
                appPanel
                    .transition(.asymmetric(
                        insertion: .scale(scale: 0.81, anchor: .bottomLeading)
                            .combined(with: .opacity),
                        removal: .scale(scale: 0.88, anchor: .bottomLeading)
                            .combined(with: .opacity)))
            }
            roundTab
                .padding(dockRight ? .trailing : .leading, 5)
                .padding(.bottom, 5)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity,
               alignment: dockRight ? .bottomTrailing : .bottomLeading)
    }

    @ViewBuilder
    var body: some View {
        if #available(iOS 26.0, *) {
            GlassEffectContainer(spacing: 14) { panelStack }
                .animation(spring, value: isOpen)
                .onAppear { dockRight = initialDockRight }
                .onReceive(NotificationCenter.default.publisher(
                    for: Notification.Name("ScarletGuestFloatingDockChanged"))) { note in
                    if let right = note.userInfo?["right"] as? Bool { dockRight = right }
                }
        } else {
            panelStack.animation(spring, value: isOpen)
                .onAppear { dockRight = initialDockRight }
                .onReceive(NotificationCenter.default.publisher(
                    for: Notification.Name("ScarletGuestFloatingDockChanged"))) { note in
                    if let right = note.userInfo?["right"] as? Bool { dockRight = right }
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
        let cx = overlay.dockRight ? overlay.bounds.width - 36 : CGFloat(36)
        let cy = overlay.bounds.height - 36
        return hypot(point.x - cx, point.y - cy) <= 35
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
    private static var width: CGFloat = 72
    private static var height: CGFloat = 72
    private static var dragOrigin: CGPoint?
    private static var dragCenter: CGPoint?
    private static var dragStartScreen: CGPoint?
    private static var dragHandler: ScarletGuestScreenPan?
    private static var rotationObserver: NSObjectProtocol?
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
        let b = window.windowScene?.coordinateSpace.bounds ?? window.bounds
        let safe = window.safeAreaInsets
        let point = center(in: window)
        let isRight = point.x >= b.midX
        floatingWindow?.dockRight = isRight
        // Expanded card is CENTERED in the guest scene, while the collapsed
        // button keeps its saved draggable location. Neither changes the guest.
        if width > 72 {
            let x = (b.width - width) / 2
            let y = min(max(point.y - height + 36, max(CGFloat(0),safe.top + 5)),
                        max(CGFloat(0),b.height - height - safe.bottom - 5))
            return CGRect(x: x, y: y, width: width, height: height)
        }
        let x = min(max(point.x - 36, safe.left + 5),
                    max(safe.left + 5, b.width - 72 - safe.right - 5))
        let y = min(max(point.y - 36, safe.top + 5),
                    max(safe.top + 5, b.height - 72 - safe.bottom - 5))
        return CGRect(x: x, y: y, width: 72, height: 72)
    }

    private static func placeFloatingWindow() {
        guard let guestWindow, let floatingWindow else { return }
        let next = frame(in: guestWindow)
        if floatingWindow.frame != next { floatingWindow.frame = next }
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
            placeFloatingWindow()
        case .ended:
            if let current = dragCenter {
                let defaults = UserDefaults.lc()
                defaults?.set(Double(current.x / max(bounds.width, 1)), forKey: positionXKey)
                defaults?.set(Double(current.y / max(bounds.height, 1)), forKey: positionYKey)
                dragCenter = nil
                dragOrigin = nil
                dragStartScreen = nil
                placeFloatingWindow()
                NotificationCenter.default.post(
                    name: Notification.Name("ScarletGuestFloatingDockChanged"),
                    object: nil, userInfo: ["right": current.x >= bounds.midX])
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
        guard let host = guestWindow, let floating = floatingWindow else { return }
        let bounds = host.windowScene?.coordinateSpace.bounds ?? host.bounds
        width = open ? min(430, max(72, bounds.width - 32)) : 72
        let cardHeight = width * 1.02
        height = open ? min(cardHeight, max(260, bounds.height - 135)) + 84 : 72
        floating.isExpanded = open
        floating.panelHitHeight = max(0, height - 78)
        let next = frame(in: host)
        // Animate inner SwiftUI content only; never double-animate UIWindow.
        UIView.performWithoutAnimation {
            floating.frame = next
            floating.rootViewController?.view.setNeedsLayout()
            floating.rootViewController?.view.layoutIfNeeded()
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_geometry_applied",
            fields: ["state": open ? "expanded" : "collapsed"])
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
                let hasExecuted = meta["lastLaunched"] is Date
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
                let canSwitch = containerExists != nil
                        && hasExecuted && !needsJIT && !nonInjected
                        && compatibleClassic
                let iconFile = url.appendingPathComponent("LCAppIconLight.png")
                result.append(ScarletGuestSwitchTarget(
                    id: folder, title: display, containerID: containerExists,
                    classicMode: requestedClassic ? UInt(cachedMode?.uintValue ?? 0) : 0,
                    isCurrent: folder == selected, canSwitch: canSwitch,
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
            fields: ["count": String(result.count)])
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
        let priorApp = defaults.string(forKey: "selected")
        let priorContainer = defaults.string(forKey: "selectedContainer")
        defaults.set(target.id, forKey: "selected")
        defaults.set(container, forKey: "selectedContainer")
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_relaunch_requested",
            fields: ["result": "prepared_guest"])
        let success = LCSharedUtils.launchToGuestApp(withClassicMode: target.classicMode)
        if !success {
            if let priorApp { defaults.set(priorApp, forKey: "selected") }
            else { defaults.removeObject(forKey: "selected") }
            if let priorContainer { defaults.set(priorContainer, forKey: "selectedContainer") }
            else { defaults.removeObject(forKey: "selectedContainer") }
        }
        return success
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
            placeFloatingWindow()
            return
        }
        floatingWindow?.isHidden = true
        floatingWindow = nil
        guestWindow = original
        width = 72
        height = 72
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
        // Stay non-key to protect guest keyboard and all native presentations.
        overlay.isHidden = false
        floatingWindow = overlay
        if rotationObserver == nil {
            rotationObserver = NotificationCenter.default.addObserver(
                forName: UIDevice.orientationDidChangeNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in
                    placeFloatingWindow()
                    try? await Task.sleep(for: .milliseconds(200))
                    placeFloatingWindow()
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

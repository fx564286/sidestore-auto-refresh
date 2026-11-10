// Scarlet Crystal PR48 full-screen guest overlay.
// All UIKit overlay operations are limited to our own separate non-key UIWindow.
// No changes to the guest's frame, orientation, safe areas, root view, P12, or LCAppModel.runApp().
import Foundation
import SwiftUI
import UIKit

// V14 distinguishes recent launched guests from live native scenes.
 // A recent guest remains in the menu after Home -> launch another app,
 // but only live scenes promise in-memory switching.
struct ScarletGuestSwitchTarget: Identifiable {
    let id: String                       // verified *.app directory name
    let title: String
    let bundleID: String?
    let containerID: String?
    let classicMode: UInt
    let isCurrent: Bool
    let canSwitch: Bool
    let canRelaunch: Bool
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
        if isExpanded {
            // The panel is modal in its own non-key UIWindow. Swallow an
            // outside tap HERE so the SwiftUI clear backdrop can dismiss
            // the panel; do not forward it to the running guest below.
            return super.point(inside: point, with: event)
        }
        // Collapsed: native guest remains interactive everywhere except
        // the round floating button at its persisted absolute position.
        return hypot(point.x - buttonCenter.x,
                     point.y - buttonCenter.y) <= 35 &&
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
        // A -> Home -> B keeps A visible even when iOS terminated A.
        // Mark cold rows explicitly rather than claiming restored RAM state.
        apps.filter { !$0.isCurrent }
    }

    private func openPanel() {
        apps = reloadApps()
        ScarletGuestSessionLedger.traceSwitcher("panel_opened", count: apps.count)
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
        ScarletGuestSessionLedger.traceSwitcher("panel_closed")
        transitionVersion += 1
        // Restore round-button-only hit testing synchronously. Keeping
        // UIWindow.isExpanded true during the 390ms dismiss animation
        // previously swallowed guest input and caused overlay ghost taps.
        onPanel(false, apps.count)
        withAnimation(switcherMotion ? spring : nil) { isOpen = false }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_dismissed",
            fields: ["result": "round_button_restored_at_saved_center"])
    }

    private func switchTo(_ target: ScarletGuestSwitchTarget) {
        ScarletGuestSessionLedger.traceSwitcher(
            target.isCurrent ? "switch_tapped_current"
                : (target.canSwitch ? "switch_tapped_live" : "switch_tapped_cold"))
        if target.isCurrent {
            closePanel()
            return
        }
        guard target.canSwitch || target.canRelaunch else {
            if switcherHaptics {
                UINotificationFeedbackGenerator().notificationOccurred(.warning)
            }
            feedback = "이 앱은 실행 준비가 필요합니다. 앱 목록에서 서명·실행 상태를 확인하세요."
            ScarletGuestSessionLedger.traceSwitcher("switch_rejected")
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_target_needs_setup",
                fields: ["reason": "guest_not_ready_for_relaunch"])
            return
        }
        if switcherHaptics {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
        if onSwitch(target) {
            // A cold target restarts through LC; it is not a preserved RAM scene.
            ScarletGuestSessionLedger.traceSwitcher("switch_submitted")
            closePanel()
        } else {
            ScarletGuestSessionLedger.traceSwitcher("switch_submit_failed")
            feedback = "앱 전환 요청이 실패했습니다. 앱 목록에서 서명·실행 상태를 확인하세요."
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
        apps.first(where: { $0.isCurrent })?.title ??
            (guestTitle.isEmpty || guestTitle == "현재 게스트"
                ? "현재 실행 중인 앱" : guestTitle)
    }

    // A full-screen guest is a single real process but may not be tracked
    // as an LC LiveProcess native multitask scene. Always show this one
    // running guest; do not put every installed/previously launched app here.
    private var currentAppRow: some View {
        Button { closePanel() } label: {
            HStack(spacing: 11) {
                Group {
                    if let icon = apps.first(where: { $0.isCurrent })?.icon {
                        Image(uiImage: icon).resizable().scaledToFit()
                    } else {
                        Image(systemName: "app.fill").font(.title2)
                    }
                }
                .frame(width: 43, height: 43)
                .background(.white.opacity(0.13),
                            in: RoundedRectangle(cornerRadius: 11))
                .clipShape(RoundedRectangle(cornerRadius: 11))
                Text(currentAppName).font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Spacer(minLength: 0)
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            }
            .padding(.vertical, 5)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("SCARLET_GUEST_CURRENT_RUNNING")
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
                VStack(alignment: .leading, spacing: 3) {
                    Text(app.title).font(.subheadline.weight(.medium)).lineLimit(1)
                    Text(app.canSwitch ? "실행 중 · 작업 유지"
                         : (app.canRelaunch ? "최근 실행 · 누르면 다시 열기"
                                            : "최근 실행 · 실행 준비 필요"))
                        .font(.caption2).foregroundStyle(.secondary)
                }
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
                currentAppRow
                if !otherApps.isEmpty {
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
                // The overlay is modal only while expanded. A clear full-
                // scene backdrop receives outside taps without drawing a
                // dimming mask over the running guest or weakening Liquid
                // Glass. The native window routes these taps here.
                if isOpen {
                    Color.clear
                        .contentShape(Rectangle())
                        .onTapGesture {
                            ScarletGuestSessionLedger.traceSwitcher(
                                "panel_dismissed_outside")
                            closePanel()
                        }
                        .frame(width: geometry.size.width,
                               height: geometry.size.height)
                    // Exactly ONE visible switcher surface. Do not leave
                    // the separate 62pt X bubble overlapping its glass card.
                    appPanel
                        .frame(width: panelWidth, height: panelHeight)
                        .position(x: geometry.size.width / 2,
                                  y: geometry.size.height / 2)
                        .transition(.opacity.combined(with: .scale(scale: 0.96)))
                } else {
                    // Persisted normalized coordinates are never overwritten
                    // by open/dismiss. The same 62pt round button returns
                    // to its pre-open screen location, including after drag.
                    roundTab
                        .frame(width: 72, height: 72)
                        .position(x: screenButtonCenter.x, y: screenButtonCenter.y)
                        .transition(.identity)
                }
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
    private static var foregroundObserver: NSObjectProtocol?
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
        guard let floatingWindow else { return }
        // Rotation can replace the guest's key UIWindow. Reacquire the
        // current real owner instead of tracking a stale weak window pointer.
        if let key = floatingWindow.windowScene?.windows.first(where: {
            $0 !== floatingWindow && $0.isKeyWindow
        }) {
            guestWindow = key
        }
        guard let guestWindow else { return }
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
        guard let floatingWindow else { return }
        placeFloatingWindow()
        guard let guestWindow else { return }
        // A second orientation/foreground event must supersede the previous
        // probe; the old task must not leave a transparent overlay behind.
        rotationGeneration += 1
        rotationWatchTask?.cancel()
        rotationWatchTask = nil
        floatingWindow.alpha = 1
        floatingWindow.isHidden = false
        placeFloatingWindow()
        let original = guestWindow.windowScene?.coordinateSpace.bounds.size
            ?? guestWindow.bounds.size
        let baseline = lastStableSceneSize ?? original
        lastStableSceneSize = baseline
        let overlayIdentity = ObjectIdentifier(floatingWindow)
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
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "overlay_rotation_geometry_changed",
                            fields: ["result": "visible_relayout"])
                    }
                    // Never blank the floating button during rotation. Resize
                    // the overlay frame and recompute its normalized center on
                    // every observed scene size change.
                    placeFloatingWindow()
                    overlay.alpha = 1
                    if abs(current.width - previous.width) < 0.5 &&
                       abs(current.height - previous.height) < 0.5 {
                        stableSamples += 1
                    } else {
                        stableSamples = 0
                    }
                    if stableSamples >= 4 {
                        placeFloatingWindow()
                        ScarletGuestSessionLedger.traceSwitcher("rotation_relayout")
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
            placeFloatingWindow()
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
    private static func installedApps(guestIdentifier: String? = nil) -> [ScarletGuestSwitchTarget] {
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

        // During LC guest bootstrap selected is consumed/removed. The guest
        // TweakLoader passes NSUserDefaults.lcGuestAppId, which remains the
        // true runtime bundle identity. Never treat the guest's virtualized
        // standard UserDefaults or a display title as current-app authority.
        let selected = UserDefaults.lc()?.string(forKey: "selected")
        let runtimeID = guestIdentifier?.trimmingCharacters(in: .whitespacesAndNewlines)
        let hasRuntimeIdentity = runtimeID.map { !$0.isEmpty } ?? false
        // Registry includes only attached, visible native LiveProcess scenes.
        // The current full-screen guest is detected independently via the
        // actual LCAppModel boot keys or the bootstrap's guest identifier.
        // A prior "lastLaunched" plist entry does NOT prove a process lives.
        let activeSceneIDs = Set(
            ScarletGuestSceneRegistry.availableGuests().map(\.id))
        var found = Set<String>()
        var result: [ScarletGuestSwitchTarget] = []
        let recent = ScarletGuestSessionLedger.recent()
        let recentFolders = Set(recent.map(\.folder))

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
                let bundleID = appData["CFBundleIdentifier"] as? String
                // Only the bootstrapped LC guest bundle ID may identify
                // the current full-screen guest. The original guest bundle
                // identifier can differ for LC's doUseLCBundleId override.
                // Host's selected key is a launch request, not running state.
                let originalBundleID = meta["LCOrignalBundleIdentifier"] as? String
                let matchesRuntime = folder == runtimeID || bundleID == runtimeID ||
                    ((meta["doUseLCBundleId"] as? Bool) == true &&
                     originalBundleID == runtimeID)
                let isCurrent = hasRuntimeIdentity
                    ? matchesRuntime
                    : (folder == selected || bundleID == selected)
                let activeScene = containerExists.map {
                    activeSceneIDs.contains($0) && MultitaskManager.isUsing(container: $0)
                } ?? false
                guard isCurrent || activeScene || recentFolders.contains(folder) else {
                    continue
                }
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
                let canRelaunch = containerExists != nil
                        && !needsJIT && !nonInjected && compatibleClassic
                        && (recentFolders.contains(folder) || hasExecuted)
                let canSwitch = activeScene
                        && canRelaunch
                let iconFile = url.appendingPathComponent("LCAppIconLight.png")
                result.append(ScarletGuestSwitchTarget(
                    id: folder, title: display, bundleID: bundleID,
                    containerID: containerExists,
                    classicMode: requestedClassic ? UInt(cachedMode?.uintValue ?? 0) : 0,
                    isCurrent: isCurrent, canSwitch: canSwitch,
                    canRelaunch: canRelaunch,
                    isShared: shared,
                    icon: UIImage(contentsOfFile: iconFile.path) ??
                          ScarletGuestIconCatalog.icon(forFolder: folder),
                    reason: canSwitch ? nil : "needs_host_setup"))
            }
        }
        result.sort {
            if $0.isCurrent != $1.isCurrent { return $0.isCurrent }
            if $0.canSwitch != $1.canSwitch { return $0.canSwitch }
            let lRank = ScarletGuestSessionLedger.rank(folder: $0.id) ?? 999
            let rRank = ScarletGuestSessionLedger.rank(folder: $1.id) ?? 999
            if lRank != rRank { return lRank < rRank }
            return $0.title.localizedStandardCompare($1.title) == .orderedAscending
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_candidates_scanned",
            fields: ["count": String(result.count),
                     "result": "live_and_launched_history"])
        if hasRuntimeIdentity {
            let currentCount = result.filter(\.isCurrent).count
            ScarletGuestSessionLedger.traceSwitcher(
                currentCount == 1 ? "runtime_current_resolved"
                                  : "runtime_current_unresolved",
                count: currentCount)
            ScarletDiagnosticRecorder.shared.record(
                "guest", "runtime_identity_classified",
                status: currentCount == 1 ? "success" : "warning",
                fields: ["count": String(currentCount),
                         "result": currentCount == 1
                             ? "current_guest_identified" : "current_guest_unresolved"])
        }
        return result
    }

    // Two distinct routes: revive an owned native LiveProcess scene if
    // still resident; otherwise relaunch a previously registered guest via
    // LC's original host bootstrap. Cold reopening does NOT preserve RAM.
    private static func switchGuest(
        to target: ScarletGuestSwitchTarget, runtimeGuestID: String
    ) -> Bool {
        guard !target.isCurrent, target.id.hasSuffix(".app"),
              !target.id.contains("/"), !target.id.contains("\\"),
              let latest = installedApps(guestIdentifier: runtimeGuestID).first(where: {
                  $0.id == target.id && !$0.isCurrent
              }) else { return false }
        if latest.canSwitch, let container = latest.containerID,
           MultitaskManager.isUsing(container: container),
           (MultitaskWindowManager.openExistingAppWindow(dataUUID: container) ||
            MultitaskDockManager.shared.bringMultitaskViewToFront(uuid: container)) {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_existing_multitask_session",
                status: "success", fields: ["result": "memory_session_resumed"])
            return true
        }
        // The iPhone diagnostic reports multi_scene_unavailable. This must
        // take a working cold path instead of rendering an inert A/B row.
        guard latest.canRelaunch, let container = latest.containerID,
              let defaults = UserDefaults.lc() else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_requires_relaunch",
                status: "blocked", fields: ["reason": "guest_not_prepared"])
            return false
        }
        let previousApp = defaults.object(forKey: "selected")
        let previousContainer = defaults.object(forKey: "selectedContainer")
        defaults.set(latest.id, forKey: "selected")
        defaults.set(container, forKey: "selectedContainer")
        guard defaults.string(forKey: "selected") == latest.id,
              defaults.string(forKey: "selectedContainer") == container else {
            if let previousApp { defaults.set(previousApp, forKey: "selected") }
            else { defaults.removeObject(forKey: "selected") }
            if let previousContainer {
                defaults.set(previousContainer, forKey: "selectedContainer")
            } else { defaults.removeObject(forKey: "selectedContainer") }
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_cold_handoff",
                status: "error", fields: ["reason": "selection_readback_failed"])
            return false
        }
        // A successful launch API return only accepts an OS handoff request.
        // Preserve old session membership for rollback and verify that the
        // next boot actually loads the exact requested guest.
        let oldSession = ScarletGuestSessionLedger.recent()
        ScarletGuestSessionLedger.noteSwitchHandoff(to: [
            latest.id, latest.bundleID ?? ""
        ])
        ScarletGuestSessionLedger.noteLaunch(
            folder: latest.id, title: latest.title, dataUUID: container)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_cold_handoff",
            fields: ["result": "submitted_to_original_lc",
                     "memory": "not_preserved"])
        // Original LC returns acceptance of a relaunch request, not proof
        // the newly selected guest finished launching.
        let submitted = LCSharedUtils.launchToGuestApp(
            withClassicMode: latest.classicMode)
        if !submitted {
            ScarletGuestSessionLedger.cancelSwitchHandoff()
            ScarletGuestSessionLedger.restore(oldSession)
            if let previousApp { defaults.set(previousApp, forKey: "selected") }
            else { defaults.removeObject(forKey: "selected") }
            if let previousContainer {
                defaults.set(previousContainer, forKey: "selectedContainer")
            } else { defaults.removeObject(forKey: "selectedContainer") }
        }
        return submitted
    }

    @objc(installForGuestName:)
    static func installForGuestName(_ rawName: NSString) {
        guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive ||
                                $0.activationState == .foregroundInactive }),
              // Some full-screen LC guest scenes never expose a key window
              // after an app-to-app handoff. Recover only the visible normal
              // level root guest window, not an alert/keyboard/our overlay.
              let original = scene.windows.first(where: { window in
                    window !== floatingWindow && window.isKeyWindow &&
                    window.rootViewController?.viewIfLoaded?.window != nil
              }) ?? scene.windows.first(where: { window in
                    window !== floatingWindow && !window.isHidden &&
                    window.windowLevel == .normal &&
                    window.rootViewController?.viewIfLoaded?.window != nil
              }) else {
            if lastFailure != "window_not_ready" {
                lastFailure = "window_not_ready"
                ScarletGuestSessionLedger.traceSwitcher("mount_window_not_ready")
                NSLog("[SCARLET_GUEST_TAB] window_not_ready")
            }
            return
        }
        if let floatingWindow, floatingWindow.windowScene === scene,
           !floatingWindow.isHidden {
            guestWindow = original
            floatingWindow.alpha = 1
            placeFloatingWindow()
            settleOverlayAfterRotation()
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

        let runtimeGuestID = rawName as String
        ScarletGuestSessionLedger.confirmSwitchHandoff(runtimeGuestID: runtimeGuestID)
        let content = ScarletFullscreenGuestFloatingTab(
            guestTitle: "현재 실행 중인 앱",
            reloadApps: { installedApps(guestIdentifier: runtimeGuestID) },
            onPanel: resizeOverlay,
            initialDockRight: center(in: original).x >=
                (original.windowScene?.coordinateSpace.bounds ?? original.bounds).midX,
            initialButtonCenter: center(in: original),
            onSwitch: { switchGuest(to: $0, runtimeGuestID: runtimeGuestID) },
            onExit: {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_tab_exit_requested")
                guard let defaults = UserDefaults.lc() else { return }
                ScarletGuestSessionLedger.beginReturnToHost()
                defaults.set("ui", forKey: "selected")
                defaults.removeObject(forKey: "selectedContainer")
                if !LCSharedUtils.launchToGuestApp(withClassicMode: 0) {
                    ScarletGuestSessionLedger.cancelReturnToHost()
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "return_to_host_request_failed",
                        status: "warning")
                }
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
        if foregroundObserver == nil {
            foregroundObserver = NotificationCenter.default.addObserver(
                forName: UIApplication.didBecomeActiveNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in
                    // A guest may rotate while inactive, without producing an
                    // observable UIDevice.orientationDidChangeNotification.
                    settleOverlayAfterRotation()
                }
            }
        }
        if lastFailure == "window_not_ready" {
            ScarletGuestSessionLedger.traceSwitcher("mount_window_recovered")
        }
        lastFailure = nil
        ScarletGuestSessionLedger.traceSwitcher("fullscreen_tab_mounted")
        NSLog("[SCARLET_GUEST_TAB] mounted_nonkey_window")
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_tab_mounted",
            fields: ["api": "UIKit.UIWindow", "material_owner": "system"])
    }
}

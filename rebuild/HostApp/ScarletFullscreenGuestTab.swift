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

@available(iOS 26.0, *)
private struct ScarletUIKitGlassBackdrop: UIViewRepresentable {
    let radius: CGFloat

    func makeUIView(context: Context) -> UIVisualEffectView {
        let glass = UIGlassEffect(style: .regular)
        glass.isInteractive = true
        glass.tintColor = UIColor.systemIndigo.withAlphaComponent(0.08)
        let view = UIVisualEffectView(effect: glass)
        view.isUserInteractionEnabled = false
        view.layer.cornerRadius = radius
        view.layer.cornerCurve = .continuous
        view.clipsToBounds = true
        return view
    }

    func updateUIView(_ view: UIVisualEffectView, context: Context) {
        view.layer.cornerRadius = radius
    }
}

@available(iOS 17.0, *)
struct ScarletFullscreenGuestFloatingTab: View {
    let guestTitle: String
    let reloadApps: () -> [ScarletGuestSwitchTarget]
    let onPanel: (Bool, Int) -> Void
    let onSwitch: (ScarletGuestSwitchTarget) -> Bool
    let onExit: () -> Void

    @State private var isOpen = false
    @State private var apps: [ScarletGuestSwitchTarget] = []
    @State private var feedback: String?
    @State private var transitionVersion = 0
    @Namespace private var glassMotion

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
            feedback = "이 앱은 먼저 홍수정에서 한 번 실행·서명해야 합니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switch_target_needs_setup",
                fields: ["reason": "unprepared_guest"])
            return
        }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        if !onSwitch(target) {
            feedback = "전환 요청을 완료하지 못했습니다. 홍수정에서 실행해 주세요."
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    @ViewBuilder
    private func glassPlate(radius: CGFloat, interactive: Bool) -> some View {
        if #available(iOS 26.0, *),
           !UIAccessibility.isReduceTransparencyEnabled {
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(.clear)
                .background(ScarletUIKitGlassBackdrop(radius: radius))
                .glassEffect(interactive ? .regular.interactive() : .regular,
                             in: .rect(cornerRadius: radius))
        } else {
            RoundedRectangle(cornerRadius: radius, style: .continuous)
                .fill(.regularMaterial)
        }
    }

    private var currentAppCard: some View {
        HStack(spacing: 12) {
            Image(systemName: "app.fill")
                .font(.system(size: 25))
                .frame(width: 48, height: 48)
                .background(.white.opacity(0.13),
                            in: RoundedRectangle(cornerRadius: 13))
            VStack(alignment: .leading, spacing: 3) {
                Text(guestTitle)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Label("전체화면 실행 중", systemImage: "checkmark.circle.fill")
                    .font(.caption2)
                    .foregroundStyle(.green)
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
                VStack(alignment: .leading, spacing: 3) {
                    Text(app.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                    Text(app.canSwitch ? "탭하여 앱 전환 · 재실행"
                                      : "홍수정에서 먼저 설정 필요")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Image(systemName: app.canSwitch ? "arrow.left.arrow.right.circle.fill"
                                               : "exclamationmark.circle")
                    .font(.title3)
                    .foregroundStyle(app.canSwitch ? Color.accentColor : Color.secondary)
            }
            .padding(.vertical, 3)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("SCARLET_PR48_GUEST_SWITCH_TARGET")
    }

    private var appPanelContent: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                Image(systemName: "sparkles")
                    .symbolRenderingMode(.hierarchical)
                    .foregroundStyle(.tint)
                Text("앱 전환")
                    .font(.headline.weight(.semibold))
                Spacer()
                Text("\(apps.count)개")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            Text("실행 중인 앱")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            currentAppCard
            Divider().opacity(0.55)
            HStack {
                Text("설치된 다른 앱")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            if otherApps.isEmpty {
                Text("전환할 다른 게스트 앱이 없습니다.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 5)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(otherApps) { entry in
                            otherAppRow(entry)
                        }
                    }
                }
                .frame(maxHeight: 260)
            }
            if let feedback {
                Text(feedback)
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Divider().opacity(0.45)
            Button {
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_tab_exit_requested")
                onExit()
            } label: {
                Label("게스트 종료 · 홍수정으로", systemImage: "rectangle.portrait.and.arrow.right")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 42)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("SCARLET_PR48_GUEST_EXIT")
        }
        .padding(16)
        .frame(maxWidth: 326, alignment: .leading)
        .background {
            glassPlate(radius: 28, interactive: false)
        }
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .strokeBorder(
                    LinearGradient(
                        colors: [.white.opacity(0.65), .white.opacity(0.09),
                                 .white.opacity(0.42)],
                        startPoint: .topLeading, endPoint: .bottomTrailing),
                    lineWidth: 0.9)
        }
        .shadow(color: .black.opacity(0.22), radius: 22, y: 10)
        .accessibilityIdentifier("SCARLET_PR48_AIRPODS_GLASS_PANEL")
    }

    @ViewBuilder
    private var appPanel: some View {
        if #available(iOS 26.0, *) {
            appPanelContent
                .glassEffectID("guest-expanded", in: glassMotion)
                .glassEffectTransition(.matchedGeometry)
        } else {
            appPanelContent
        }
    }

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
                            ScarletUIKitGlassBackdrop(radius: 31).clipShape(Circle())
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
        .accessibilityIdentifier("SCARLET_PR48_GUEST_ROUND_TAB")
    }

    @ViewBuilder
    private var roundTab: some View {
        if #available(iOS 26.0, *) {
            roundTabButton
                .glassEffect(.regular.interactive(), in: .circle)
                .glassEffectID("guest-collapsed", in: glassMotion)
        } else {
            roundTabButton
        }
    }

    private var panelStack: some View {
        VStack(alignment: .leading, spacing: 9) {
            if isOpen {
                appPanel
                    .transition(.asymmetric(
                        insertion: .scale(scale: 0.81, anchor: .bottomLeading)
                            .combined(with: .opacity),
                        removal: .scale(scale: 0.88, anchor: .bottomLeading)
                            .combined(with: .opacity)))
            }
            roundTab.padding(.leading, 5).padding(.bottom, 5)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }

    @ViewBuilder
    var body: some View {
        if #available(iOS 26.0, *) {
            GlassEffectContainer(spacing: 14) { panelStack }
                .animation(spring, value: isOpen)
        } else {
            panelStack.animation(spring, value: isOpen)
        }
    }
}

@available(iOS 17.0, *)
@MainActor
@objc(ScarletFullscreenGuestTabInstaller)
final class ScarletFullscreenGuestTabInstaller: NSObject {
    private static var floatingWindow: UIWindow?
    private static weak var guestWindow: UIWindow?
    private static var width: CGFloat = 72
    private static var height: CGFloat = 72
    private static var rotationObserver: NSObjectProtocol?
    private static var lastFailure: String?

    private static func frame(in window: UIWindow) -> CGRect {
        let bounds = window.windowScene?.coordinateSpace.bounds ?? window.bounds
        let inset = window.safeAreaInsets
        return CGRect(x: max(8, inset.left + 12),
                      y: max(0, bounds.height - max(12, inset.bottom + 9) - height),
                      width: min(width, max(64, bounds.width - 16)),
                      height: min(height, max(64, bounds.height - 16)))
    }

    private static func placeFloatingWindow() {
        guard let guestWindow, let floatingWindow else { return }
        let next = frame(in: guestWindow)
        if floatingWindow.frame != next { floatingWindow.frame = next }
    }

    private static func resizeOverlay(open: Bool, appCount: Int) {
        guard let host = guestWindow, let floating = floatingWindow else { return }
        let bounds = host.windowScene?.coordinateSpace.bounds ?? host.bounds
        width = open ? min(358, max(72, bounds.width - 16)) : 72
        let desiredHeight: CGFloat = min(590, CGFloat(270 + max(0, appCount - 1) * 59))
        height = open ? min(desiredHeight, max(170, bounds.height - 80)) : 72
        let next = frame(in: host)
        UIView.animate(withDuration: 0.47, delay: 0,
                       usingSpringWithDamping: 0.82,
                       initialSpringVelocity: 0.34,
                       options: [.beginFromCurrentState, .allowUserInteraction]) {
            floating.frame = next
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

        let name = (rawName as String).isEmpty ? "현재 게스트" : rawName as String
        let content = ScarletFullscreenGuestFloatingTab(
            guestTitle: name,
            reloadApps: installedApps,
            onPanel: resizeOverlay,
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
        let overlay = UIWindow(windowScene: scene)
        overlay.windowLevel = UIWindow.Level.alert + 1
        overlay.backgroundColor = .clear
        overlay.isOpaque = false
        let controller = UIHostingController(rootView: content)
        controller.view.backgroundColor = .clear
        controller.view.isOpaque = false
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

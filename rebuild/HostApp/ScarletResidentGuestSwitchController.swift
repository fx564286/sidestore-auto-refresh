// V41: full-screen, non-resizable LiveProcess host on iPhone.
// Ownership: main Scarlet process. This is NOT the historical LC
// virtual-window side dock; it owns only a non-key circular overlay.
// In-memory A/B switching is valid ONLY while original LiveProcess PIDs
// survive. OS termination still makes RAM restoration impossible.
import Foundation
import SwiftUI
import UIKit

@available(iOS 17.0, *)
@MainActor
final class ScarletResidentGuestSwitchController {
    static let shared = ScarletResidentGuestSwitchController()
    private var overlay: ScarletGuestTouchPassthroughWindow?
    private var panHandler: ScarletGuestScreenPan?
    private var backgroundObserver: NSObjectProtocol?
    private var foregroundObserver: NSObjectProtocol?
    private let positionXKey = "ScarletGuestRoundTabCenterXFractionV1"
    private let positionYKey = "ScarletGuestRoundTabCenterYFractionV1"

    private init() {}

    private var owner: MultitaskDockManager {
        MultitaskDockManager.shared
    }

    // Scene-space geometry is read-only. Guest UIWindow frames are never
    // scaled, inset, cropped or moved to accommodate this button.
    private func center(in window: UIWindow) -> CGPoint {
        let bounds = window.windowScene?.coordinateSpace.bounds ?? window.bounds
        let safe = window.safeAreaInsets
        let x = (UserDefaults.lc()?.object(forKey: positionXKey) as? NSNumber)?.doubleValue
        let y = (UserDefaults.lc()?.object(forKey: positionYKey) as? NSNumber)?.doubleValue
        let raw = CGPoint(
            x: x.map { bounds.width * $0 } ?? safe.left + 44,
            y: y.map { bounds.height * $0 } ??
                bounds.height - safe.bottom - 44)
        let minX = safe.left + 38, minY = safe.top + 38
        return CGPoint(
            x: min(max(raw.x, minX), max(minX, bounds.width - safe.right - 38)),
            y: min(max(raw.y, minY), max(minY, bounds.height - safe.bottom - 38)))
    }

    private func panelFrame(_ window: UIWindow) -> CGRect {
        let bounds = window.bounds
        let width = min(CGFloat(430), max(CGFloat(72), bounds.width - 32))
        let height = min(width * 1.02, CGFloat(435),
                         max(CGFloat(210), bounds.height - 156))
        return CGRect(x: (bounds.width - width) / 2,
                      y: (bounds.height - height) / 2,
                      width: width, height: height)
    }

    private func notifyCenter(_ point: CGPoint, window: UIWindow) {
        window.buttonCenter = point
        window.dockRight = point.x >= window.bounds.midX
        NotificationCenter.default.post(
            name: Notification.Name("ScarletGuestFloatingDockChanged"),
            object: nil,
            userInfo: ["x": point.x, "y": point.y,
                       "right": window.dockRight])
    }

    // Exactly the entries launched in V40's CURRENT active work session.
    // The owner registry is resident PID evidence, not an install list.
    private func targets() -> [ScarletGuestSwitchTarget] {
        let resident = Dictionary(
            owner.scarletAllResidentSessions().map { ($0.appUUID, $0) },
            uniquingKeysWith: { a, _ in a })
        let allModels = DataManager.shared.model.apps +
            DataManager.shared.model.hiddenApps
        let active = owner.scarletCurrentResident()
        return ScarletGuestSessionLedger.recent().compactMap { entry in
            guard let uuid = entry.dataUUID,
                  let session = resident[uuid],
                  let model = allModels.first(where: {
                      $0.appInfo.relativeBundlePath == entry.folder
                  }) else { return nil }
            let decorated = session.view?._viewDelegate()
                as? DecoratedAppSceneViewController
            let processAlive = decorated?.appSceneVC.isAppRunning ?? false
            let icon: UIImage?
            if let path = model.appInfo.bundlePath() {
                icon = UIImage(contentsOfFile: path + "/LCAppIconLight.png")
            } else {
                icon = nil
            }
            return ScarletGuestSwitchTarget(
                id: entry.folder,
                title: model.displayName,
                bundleID: model.appInfo.bundleIdentifier(),
                containerID: uuid,
                classicMode: 0,
                isCurrent: uuid == active,
                canSwitch: processAlive && uuid != active,
                canRelaunch: true,
                isShared: model.uiIsShared,
                icon: icon,
                reason: processAlive ? nil : "liveprocess_terminated")
        }
    }

    private func switchTo(_ target: ScarletGuestSwitchTarget) -> Bool {
        guard let uuid = target.containerID else { return false }
        if owner.scarletActivateResident(uuid: uuid) {
            // The same AppScene VC and PID remain in memory.
            ScarletDiagnosticRecorder.shared.record(
                "guest", "resident_switch_completed",
                status: "success",
                fields: ["result": "existing_extension_process",
                         "memory": "preserved_while_process_alive",
                         "same_pid": "true"])
            return true
        }
        // An iOS-killed extension has no RAM to resume. Reuse the existing
        // signed app with the original LiveContainer signing pipeline;
        // report a fresh launch instead of asserting state restoration.
        let models = DataManager.shared.model.apps +
            DataManager.shared.model.hiddenApps
        guard let model = models.first(where: {
            $0.appInfo.relativeBundlePath == target.id
        }) else { return false }
        owner.scarletReturnToHome()
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_process_terminated",
            status: "warning",
            fields: ["reason": "extension_pid_not_alive",
                     "memory": "not_preserved"])
        Task { @MainActor in
            do {
                try await model.runApp(multitask: true,
                                       containerFolderName: uuid)
            } catch {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "resident_relaunch_failed",
                    status: "error",
                    fields: ["reason": "original_lc_launch_failed"])
            }
        }
        return true
    }

    func mountIfNecessary() {
        guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive ||
                    $0.activationState == .foregroundInactive }),
              owner.scarletCurrentResident() != nil else { return }
        if let overlay, overlay.windowScene === scene {
            refresh()
            overlay.isHidden = false
            return
        }
        overlay?.isHidden = true
        overlay = nil

        let window = ScarletGuestTouchPassthroughWindow(windowScene: scene)
        window.windowLevel = UIWindow.Level.alert + 1
        window.backgroundColor = .clear
        window.isOpaque = false
        window.frame = scene.coordinateSpace.bounds
        window.buttonCenter = center(in: window)
        window.panelRect = panelFrame(window)
        window.dockRight = window.buttonCenter.x >= window.bounds.midX
        let firstPoint = window.buttonCenter

        let tab = ScarletFullscreenGuestFloatingTab(
            guestTitle: "현재 실행 중인 앱",
            reloadApps: { [weak self] in self?.targets() ?? [] },
            onPanel: { [weak self, weak window] open, _ in
                guard let self, let window else { return }
                window.isExpanded = open
                window.panelRect = self.panelFrame(window)
            },
            initialDockRight: window.dockRight,
            initialButtonCenter: firstPoint,
            onSwitch: { [weak self] target in
                self?.switchTo(target) ?? false
            },
            onExit: { [weak self] in
                self?.owner.scarletReturnToHome()
            })
        let host = UIHostingController(rootView: tab)
        host.view.backgroundColor = .clear
        host.view.isOpaque = false
        window.rootViewController = host

        let pan = ScarletGuestScreenPan { [weak self, weak window] point, state in
            guard let self, let window,
                  state == .changed || state == .ended else { return }
            let bounds = window.bounds
            let safe = window.safeAreaInsets
            let minX = safe.left + 38, minY = safe.top + 38
            let clamped = CGPoint(
                x: min(max(point.x, minX),
                       max(minX, bounds.width - safe.right - 38)),
                y: min(max(point.y, minY),
                       max(minY, bounds.height - safe.bottom - 38)))
            self.notifyCenter(clamped, window: window)
            if state == .ended {
                UserDefaults.lc()?.set(
                    Double(clamped.x / max(1, bounds.width)),
                    forKey: self.positionXKey)
                UserDefaults.lc()?.set(
                    Double(clamped.y / max(1, bounds.height)),
                    forKey: self.positionYKey)
            }
        }
        let gesture = UIPanGestureRecognizer(
            target: pan, action: #selector(ScarletGuestScreenPan.didPan(_:)))
        gesture.delegate = pan
        gesture.cancelsTouchesInView = true
        host.view.addGestureRecognizer(gesture)
        panHandler = pan
        overlay = window
        window.isHidden = false  // Never call makeKey: preserve guest keyboard.

        if backgroundObserver == nil {
            backgroundObserver = NotificationCenter.default.addObserver(
                forName: UIApplication.willResignActiveNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in
                    guard let current = self.owner.scarletCurrentResident(),
                          let entry = ScarletGuestSessionLedger.recent().first(where: {
                              $0.dataUUID == current
                          }) else { return }
                    ScarletGuestSessionLedger.noteGuestDeparted(folder: entry.folder)
                }
            }
        }
        if foregroundObserver == nil {
            foregroundObserver = NotificationCenter.default.addObserver(
                forName: UIApplication.didBecomeActiveNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in self.refresh() }
            }
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_switcher_mounted",
            fields: ["result": "separate_nonkey_round_tab",
                     "virtual_window": "disabled"])
    }

    func refresh() {
        guard let overlay else { return }
        if let scene = overlay.windowScene {
            overlay.frame = scene.coordinateSpace.bounds
        }
        overlay.panelRect = panelFrame(overlay)
        notifyCenter(center(in: overlay), window: overlay)
    }

    func hide() {
        overlay?.isHidden = true
        overlay?.isExpanded = false
    }
}

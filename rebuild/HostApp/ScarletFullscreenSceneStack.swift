// Scarlet V45 experimental single-viewport LiveProcess compositor.
// This is NOT a virtual UIWindow, not a decorated LC scene, not a scene
// session, and does not mutate the full-screen guest's display scale.
// Keep it mounted while Scarlet's Home UI is visible so live process view
// controllers are not torn down by dismissing a sheet.
import Foundation
import UIKit
import SwiftUI

@available(iOS 17.0, *)
@MainActor
final class ScarletFullscreenSceneStack: NSObject, ObservableObject,
                                         AppSceneViewControllerDelegate {
    struct Slot: Identifiable {
        let id: String  // LC *.app directory; never written to diagnostics
        let dataUUID: String
        let title: String
        let bundleID: String?
        let icon: UIImage?
        var pid: Int32
        var failed: Bool
    }
    @Published private(set) var slots: [Slot] = []
    @Published private(set) var activeID: String?
    @Published private(set) var isVisible = false
    @Published private(set) var lastError: String?
    weak var viewport: ScarletFullscreenSceneViewport?
    private var overlayWindow: ScarletGuestTouchPassthroughWindow?

    func enqueueSignedGuest(_ app: LCAppModel) throws {
        guard let folder = app.appInfo.relativeBundlePath,
              folder.hasSuffix(".app"), !folder.contains("/"),
              let uuid = app.uiSelectedContainer?.folderName,
              !uuid.isEmpty else {
            throw NSError(domain: "scarlet.fullscreen", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "게스트 데이터 컨테이너가 준비되지 않았습니다."])
        }
        if let previous = slots.first(where: { $0.id == folder && $0.dataUUID == uuid }),
           previous.pid > 0,
           viewport?.isAlive(folder: folder) == true {
            _ = activate(folder: folder)
            return
        }
        let icon = UIImage(contentsOfFile:
            (app.appInfo.bundlePath() ?? "") + "/LCAppIconLight.png")
        if let old = slots.firstIndex(where: { $0.id == folder }) {
            slots.remove(at: old)
        }
        slots.append(Slot(id: folder, dataUUID: uuid,
                          title: app.displayName,
                          bundleID: app.bundleIdentifier,
                          icon: icon, pid: 0, failed: false))
        activeID = folder
        lastError = nil
        isVisible = true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_queued",
            fields: ["count": String(slots.count), "memory": "not_verified"])
        viewport?.reconcile()
        updateOverlay()
    }

    func attach(_ vc: ScarletFullscreenSceneViewport) {
        viewport = vc
        vc.reconcile()
        updateOverlay()
    }

    func updateOverlay() {
        guard let scene = viewport?.view.window?.windowScene else { return }
        if !isVisible {
            overlayWindow?.isHidden = true
            return
        }
        if overlayWindow?.windowScene !== scene {
            overlayWindow?.isHidden = true
            overlayWindow = nil
        }
        if overlayWindow == nil {
            let window = ScarletGuestTouchPassthroughWindow(windowScene: scene)
            window.backgroundColor = .clear
            window.isOpaque = false
            window.windowLevel = UIWindow.Level.alert + 1
            window.frame = scene.coordinateSpace.bounds
            let circle = CGPoint(x: window.bounds.maxX - 48,
                                 y: window.bounds.midY)
            window.buttonCenter = circle
            window.isExpanded = false
            window.rootViewController = UIHostingController(
                rootView: ScarletFullscreenGuestFloatingTab(
                    guestTitle: "현재 실행 중인 앱",
                    reloadApps: { [weak self] in self?.availableTargets() ?? [] },
                    onPanel: { [weak window] expanded, _ in
                        window?.isExpanded = expanded
                    },
                    initialDockRight: true,
                    initialButtonCenter: circle,
                    onSwitch: { [weak self] target in
                        self?.activate(folder: target.id) ?? false
                    },
                    onExit: { [weak self] in self?.goHome() }
                )
            )
            window.rootViewController?.view.backgroundColor = .clear
            overlayWindow = window
        }
        overlayWindow?.frame = scene.coordinateSpace.bounds
        overlayWindow?.isHidden = false
    }

    private func availableTargets() -> [ScarletGuestSwitchTarget] {
        slots.map { slot in
            let live = slot.pid > 0 &&
                       (viewport?.isAlive(folder: slot.id) ?? false)
            return ScarletGuestSwitchTarget(
                id: slot.id, title: slot.title,
                bundleID: slot.bundleID, containerID: slot.dataUUID,
                classicMode: 0, isCurrent: activeID == slot.id,
                canSwitch: live && activeID != slot.id,
                canRelaunch: false, isShared: false,
                icon: slot.icon,
                reason: live ? nil : "process_not_live")
        }
    }

    @discardableResult
    func activate(folder: String) -> Bool {
        guard let slot = slots.first(where: { $0.id == folder }),
              slot.pid > 0, viewport?.isAlive(folder: folder) == true,
              viewport?.select(folder: folder) == true else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_reuse_failed",
                status: "warning",
                fields: ["reason": "process_not_live",
                         "memory": "not_preserved"])
            return false
        }
        activeID = folder
        isVisible = true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_reused",
            status: "success", fields: [
                "process_pid": String(slot.pid),
                "memory": "same_live_process",
                "count": String(slots.count)])
        updateOverlay()
        return true
    }

    func goHome() {
        // No close, terminate, detach, scene destruction or relaunch.
        // Keep each remote scene in the original full-screen viewport.
        isVisible = false
        overlayWindow?.isHidden = true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_home",
            fields: ["count": String(slots.count),
                     "memory": "retained_until_pid_exits"])
    }

    func sceneStarted(_ vc: AppSceneViewController, error: Error?) {
        guard let index = slots.firstIndex(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        }) else { return }
        if error != nil || vc.pid <= 0 {
            slots[index].failed = true
            lastError = "게스트 원격 실행을 시작하지 못했습니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_start_failed",
                status: "error", fields: ["reason": "liveprocess_failed"])
            if slots[index].id == activeID { goHome() }
            return
        }
        slots[index].pid = vc.pid
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_started",
            status: "success",
            fields: ["process_pid": String(vc.pid),
                     "memory": "new_live_process"])
    }

    // Objective-C delegate callbacks from the ORIGINAL AppSceneViewController.
    func appSceneVCAppDidExit(_ vc: AppSceneViewController!) {
        guard let vc else { return }
        if let index = slots.firstIndex(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        }) {
            slots[index].pid = 0
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_exited",
            fields: ["memory": "not_preserved"])
        if activeID == vc.bundleId { goHome() }
    }

    func appSceneVC(_ vc: AppSceneViewController!,
                    didInitializeWithError error: Error!) {
        guard let vc else { return }
        sceneStarted(vc, error: error)
    }

    func appSceneVCWillActivateScene(_ vc: AppSceneViewController!) {
        guard let vc else { return }
        vc.updateSettings { settings in
            guard let settings else { return }
            // SINGLE fullscreen viewport. Never use 320x480, UIScreen
            // display scaling, swapped landscape frames or V41 sizing.
            let full = vc.view.bounds
            let safe = vc.view.window?.safeAreaInsets ?? .zero
            settings.peripheryInsets = safe
            settings.safeAreaInsetsPortrait = safe
            settings.setFrame(full)
            if let orientation = vc.view.window?.windowScene?.interfaceOrientation {
                settings.setInterfaceOrientation(orientation)
            }
            settings.deviceOrientation = UIDevice.current.orientation
        }
        vc.contentView?.autoresizingMask =
            [.flexibleWidth, .flexibleHeight]
    }

    func appSceneVC(_ vc: AppSceneViewController!,
                    didUpdateFrom settings: UIMutableApplicationSceneSettings!,
                    transitionContext context: Any!,
                    lifecycleActionType actionType: UInt32) {
        guard let vc, let settings else { return }
        settings.interruptionPolicy = 0
        vc.presenter?.scene.updateSettings(settings,
                                            withTransitionContext: context,
                                            completion: nil)
    }
}

// One persistent UIViewController root for all remote guest scenes. No
// DecoratedAppSceneViewController, window manager, scene destruction or scaling.
@available(iOS 17.0, *)
@MainActor
final class ScarletFullscreenSceneViewport: UIViewController {
    private weak var stack: ScarletFullscreenSceneStack?
    private var controllers: [String: AppSceneViewController] = [:]
    private var lastBounds: CGSize = .zero

    init(stack: ScarletFullscreenSceneStack) {
        self.stack = stack
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("storyboard not supported") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        view.clipsToBounds = false
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        stack?.attach(self)
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        if view.bounds.size != lastBounds {
            lastBounds = view.bounds.size
            for vc in controllers.values {
                vc.view.frame = view.bounds
            }
        }
        if let scene = view.window?.windowScene {
            // Fail closed if the SwiftUI presenter provides a safe-area
            // rectangle smaller than the real phone screen. Do NOT
            // enlarge/scale the guest window to "fix" a clipped preview.
            let expected = scene.coordinateSpace.bounds.size
            let actual = view.bounds.size
            guard abs(expected.width - actual.width) < 2,
                  abs(expected.height - actual.height) < 2 else {
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "fullscreen_scene_geometry_rejected",
                    status: "blocked", fields: [
                        "width_pt": String(Int(actual.width)),
                        "height_pt": String(Int(actual.height)),
                        "reason": "viewport_not_screen_bounds"])
                return
            }
            reconcile()
        }
    }

    func isAlive(folder: String) -> Bool {
        controllers[folder]?.isAppRunning == true
    }

    func select(folder: String) -> Bool {
        guard let target = controllers[folder],
              target.isAppRunning else { return false }
        for (key, vc) in controllers {
            // A hidden scene stays ATTACHED and its NSExtension request
            // continues. No app process kills or UIKit view detachment.
            vc.view.layer.opacity = key == folder ? 1 : 0
            vc.view.isUserInteractionEnabled = key == folder
        }
        view.bringSubviewToFront(target.view)
        stack?.updateOverlay()
        return true
    }

    func reconcile() {
        guard isViewLoaded, let scene = view.window?.windowScene,
              let stack else { return }
        let expected = scene.coordinateSpace.bounds.size
        let actual = view.bounds.size
        guard abs(expected.width - actual.width) < 2,
              abs(expected.height - actual.height) < 2,
              actual.width > 0, actual.height > 0 else { return }
        for slot in stack.slots {
            if controllers[slot.id] != nil { continue }
            guard !slot.failed else { continue }
            // Input is the original LC relative .app path and existing
            // dataUUID. The pinned NSExtension owns each guest process.
            guard let vc = AppSceneViewController(
                bundleId: slot.id, dataUUID: slot.dataUUID,
                delegate: stack) else {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_scene_vc_unavailable",
                    status: "error")
                continue
            }
            vc.scarletNativeFullscreenSlot = true
            vc.scaleRatio = 1
            vc.view.frame = view.bounds
            vc.view.autoresizingMask =
                [.flexibleWidth, .flexibleHeight]
            addChild(vc)
            view.addSubview(vc.view)
            vc.didMove(toParent: self)
            controllers[slot.id] = vc
        }
        if let active = stack.activeID {
            _ = select(folder: active)
        }
    }
}

@available(iOS 17.0, *)
struct ScarletFullscreenSceneViewportRepresentable: UIViewControllerRepresentable {
    @ObservedObject var stack: ScarletFullscreenSceneStack
    func makeUIViewController(context: Context)
        -> ScarletFullscreenSceneViewport {
        ScarletFullscreenSceneViewport(stack: stack)
    }
    func updateUIViewController(_ vc: ScarletFullscreenSceneViewport,
                                context: Context) {
        vc.reconcile()
        stack.updateOverlay()
    }
}

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
    // Catalog is host-owned LCAppModel data, not a second install database.
    // The switcher can now start an eligible installed guest without going
    // through Scarlet Home. Existing live scenes are always preferred.
    private var installedModels: [String: LCAppModel] = [:]
    private var pendingInPlaceLaunch = false

    // An embedded LiveProcess and the original LC full-screen bootstrap
    // must not both own this host process at the same time. Disallow toggles
    // until all resident guest processes have exited and been released.
    var hasResidentSession: Bool {
        // V48 root cause: stale failed/exited guest slots kept the native
        // experimental engine latched even AFTER the user switched it OFF.
        // A historical row is not a running LC LiveProcess session. Keep the
        // compositor mounted only while a boot is pending or an owner is live.
        if pendingInPlaceLaunch { return true }
        return slots.contains { slot in
            guard !slot.failed else { return false }
            if slot.pid <= 0 { return isVisible }  // provisional async start
            return viewport?.isAlive(folder: slot.id) ?? true
        }
    }

    var hasLiveResidentProcess: Bool {
        slots.contains { slot in
            slot.pid > 0 && viewport?.isAlive(folder: slot.id) == true
        }
    }

    func livePID(folder: String) -> Int32? {
        guard slots.contains(where: { $0.id == folder }) else { return nil }
        return viewport?.activePID(folder: folder)
    }

    func containsResidentGuest(folder: String) -> Bool {
        slots.contains { $0.id == folder }
    }

    func updateInstalledModels(_ apps: [LCAppModel]) {
        var indexed: [String: LCAppModel] = [:]
        for app in apps {
            guard let folder = app.appInfo.relativeBundlePath,
                  folder.hasSuffix(".app"), folder != ".app",
                  !folder.contains("/"), !folder.contains("\\") else { continue }
            indexed[folder] = app
        }
        installedModels = indexed
    }

    private func eligibleForInPlaceLaunch(_ app: LCAppModel) -> Bool {
        app.appInfo.defaultClassicMode == 0 &&
        !app.appInfo.isJITNeeded && !app.appInfo.is32bit &&
        app.uiSelectedContainer != nil
    }

    func enqueueSignedGuest(_ app: LCAppModel) throws {
        guard let folder = app.appInfo.relativeBundlePath,
              folder.hasSuffix(".app"), !folder.contains("/"),
              let uuid = app.uiSelectedContainer?.folderName,
              !uuid.isEmpty else {
            throw NSError(domain: "scarlet.fullscreen", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "게스트 데이터 컨테이너가 준비되지 않았습니다."])
        }
        if let previous = slots.first(where: { $0.id == folder && $0.dataUUID == uuid }),
           let confirmedPID = viewport?.activePID(folder: folder),
           confirmedPID > 0 {
            if let index = slots.firstIndex(where: { $0.id == folder }) {
                slots[index].pid = confirmedPID
                slots[index].failed = false
            }
            _ = activate(folder: folder)
            return
        }
        // This is the same installed guest, but its remote LiveProcess is
        // already dead. The previous controller's key must be released or
        // reconcile() will silently skip the user's next launch request.
        if slots.contains(where: { $0.id == folder }) {
            guard viewport?.releaseExitedController(folder: folder) != false else {
                throw NSError(domain: "scarlet.fullscreen", code: 3,
                              userInfo: [NSLocalizedDescriptionKey:
                                  "기존 게스트가 실행 중입니다. 기존 장면 전환을 확인하세요."])
            }
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_dead_controller_cleared",
                fields: ["result": "stale_dead_scene_only"])
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
        guard let scene = viewport?.view.window?.windowScene else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "resident_overlay_no_window_scene",
                status: "warning", fields: ["window_attached": "false"])
            return
        }
        if !isVisible {
            overlayWindow?.isHidden = true
            ScarletDiagnosticRecorder.shared.record(
                "guest", "resident_overlay_hidden",
                fields: ["result": "mode_or_home_hidden",
                         "live_session": hasResidentSession ? "true" : "false"])
            return
        }
        if overlayWindow?.windowScene !== scene {
            overlayWindow?.isHidden = true
            overlayWindow = nil
        }
        if overlayWindow == nil {
            guard let host = viewport?.view.window else { return }
            let window = ScarletFullscreenGuestTabInstaller.makeResidentSwitcherWindow(
                host: host, scene: scene,
                reloadApps: { [weak self] in self?.availableTargets() ?? [] },
                onSwitch: { [weak self] target in
                    self?.switchOrLaunch(target) ?? false
                },
                onExit: { [weak self] in self?.goHome() })
            overlayWindow = window
        }
        overlayWindow?.frame = scene.coordinateSpace.bounds
        overlayWindow?.isHidden = false
        if let w = overlayWindow {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "resident_overlay_visible",
                fields: ["window_attached": w.windowScene != nil ? "true" : "false",
                         "overlay_visible": w.isHidden ? "false" : "true",
                         "button_x_pt": String(Int(w.buttonCenter.x)),
                         "button_y_pt": String(Int(w.buttonCenter.y)),
                         "scene_width_pt": String(Int(scene.coordinateSpace.bounds.width)),
                         "scene_height_pt": String(Int(scene.coordinateSpace.bounds.height)),
                         "original_pan_used": "true"])
        }
    }

    private func availableTargets() -> [ScarletGuestSwitchTarget] {
        var targets = slots.map { slot in
            let live = slot.pid > 0 &&
                       (viewport?.isAlive(folder: slot.id) ?? false)
            let canRestart = !live && installedModels[slot.id].map {
                eligibleForInPlaceLaunch($0)
            } == true
            return ScarletGuestSwitchTarget(
                id: slot.id, title: slot.title,
                bundleID: slot.bundleID, containerID: slot.dataUUID,
                classicMode: 0, isCurrent: activeID == slot.id,
                canSwitch: live && activeID != slot.id,
                canRelaunch: canRestart, isShared: false,
                icon: slot.icon,
                reason: live ? nil : "process_not_live")
        }
        // Only guests launched in this work session belong in multitasking.
        // All installation and first launch actions remain in Scarlet Home.
        return targets
    }

    @discardableResult
    private func switchOrLaunch(_ target: ScarletGuestSwitchTarget) -> Bool {
        guard target.id.hasSuffix(".app"), !target.id.contains("/"),
              !target.id.contains("\\") else { return false }
        if target.canSwitch {
            let reused = activate(folder: target.id)
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_direct_switch",
                status: reused ? "success" : "warning",
                fields: ["result": reused ? "same_pid_scene_selected"
                                            : "live_scene_unavailable"])
            return reused
        }
        guard target.canRelaunch, !pendingInPlaceLaunch,
              !slots.contains(where: { $0.id == target.id && $0.pid > 0 &&
                viewport?.isAlive(folder: $0.id) == true }),
              let model = installedModels[target.id],
              eligibleForInPlaceLaunch(model) else { return false }
        pendingInPlaceLaunch = true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_inplace_launch_requested",
            fields: ["result": "accepted_no_host_handoff",
                     "memory": "new_process_expected"])
        Task { @MainActor [weak self] in
            guard let self else { return }
            defer { self.pendingInPlaceLaunch = false }
            do {
                // Native LiveContainer signApp retains original keychain,
                // certificate, team, extensions and guest data containers.
                try await model.signApp(force: false)
                // Match the original LC host: record a launched work-session
                // entry before remote bootstrap, and roll it back on failure.
                let earlier = ScarletGuestSessionLedger.recent()
                ScarletGuestSessionLedger.noteLaunch(
                    folder: target.id, title: model.displayName,
                    dataUUID: model.uiSelectedContainer?.folderName)
                do {
                    try self.enqueueSignedGuest(model)
                } catch {
                    ScarletGuestSessionLedger.restore(earlier)
                    throw error
                }
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_scene_inplace_launch_queued",
                    fields: ["result": "same_host_viewport_no_home",
                             "memory": "not_verified"])
            } catch {
                self.lastError = error.localizedDescription
                ScarletDiagnosticRecorder.shared.recordError(
                    "guest", "fullscreen_scene_inplace_launch_failed", error: error)
            }
        }
        return true
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
                     "memory": "retained_until_pid_exits",
                     "overlay_visible": overlayWindow?.isHidden == false ? "true" : "false",
                     "live_session": hasResidentSession ? "true" : "false"])
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_home_visibility_probe",
            fields: ["host_visible": "true",
                     "overlay_visible": overlayWindow?.isHidden == false ? "true" : "false",
                     "controller_present": viewport != nil ? "true" : "false"])

    }

    // A PID can be reported before the remote UIKit surface is interactive.
    // Retry only a bounded number of times while leaving the old scene visible.
    private func revealStartedScene(_ folder: String, attemptsRemaining: Int = 8) {
        guard activeID == folder else { return }
        if viewport?.select(folder: folder) == true {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_inplace_display_handoff",
                status: "success",
                fields: ["result": "live_scene_selected",
                         "memory": "same_host_scene_stack"])
            return
        }
        guard attemptsRemaining > 0 else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_inplace_display_handoff",
                status: "warning", fields: ["result": "scene_not_ready"])
            return
        }
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 180_000_000)
            self?.revealStartedScene(folder, attemptsRemaining: attemptsRemaining - 1)
        }
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
        // Keep prior scene visible until this exact remote process reports
        // readiness; never flash an uninitialized black child scene.
        if slots[index].id == activeID {
            revealStartedScene(slots[index].id)
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_started",
            status: "success",
            fields: ["process_pid": String(vc.pid),
                     "memory": "new_live_process"])
    }

    // Objective-C delegate callbacks from the ORIGINAL AppSceneViewController.
    func appSceneVCAppDidExit(_ vc: AppSceneViewController!) {
        guard let vc, viewport?.ownsController(vc, folder: vc.bundleId) == true
        else { return }
        let wasActive = activeID == vc.bundleId
        if let index = slots.firstIndex(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        }) {
            slots.remove(at: index)
        }
        // Removing a dead remote controller is NOT killing a live guest.
        // Drop only the exact exited instance, never a sibling or replacement.
        let released = viewport?.releaseExitedController(folder: vc.bundleId) == true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_exited",
            fields: ["memory": "not_preserved",
                     "dead_controller_released": released ? "true" : "false"])
        if wasActive {
            activeID = nil
            goHome()
        }
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
            let windowScene = vc.view.window?.windowScene
            // A full-bleed SwiftUI overlay can report zero guest-safe insets.
            // Read the actual key UIWindow rather than inferring status bar
            // and home indicator geometry from the guest's ignored-safe view.
            let safe = windowScene?.windows.first(where: { $0.isKeyWindow })?.safeAreaInsets
                ?? vc.view.window?.safeAreaInsets ?? .zero
            let sceneBounds = windowScene?.coordinateSpace.bounds ?? .zero
            let guestInsets = vc.view.safeAreaInsets
            let normalWindow = windowScene?.windows.first(where: {
                $0.windowLevel == .normal && !$0.isHidden
            })
            let rootInsets = normalWindow?.safeAreaInsets ?? .zero
            ScarletDiagnosticRecorder.shared.record(
                "layout", "fullscreen_scene_host_safe_area",
                fields: ["safe_top_pt": String(Int(safe.top)),
                         "safe_bottom_pt": String(Int(safe.bottom)),
                         "safe_left_pt": String(Int(safe.left)),
                         "safe_right_pt": String(Int(safe.right)),
                         "window_safe_top_pt": String(Int(rootInsets.top)),
                         "window_safe_bottom_pt": String(Int(rootInsets.bottom)),
                         "guest_safe_top_pt": String(Int(guestInsets.top)),
                         "guest_safe_bottom_pt": String(Int(guestInsets.bottom)),
                         "scene_width_pt": String(Int(sceneBounds.width)),
                         "scene_height_pt": String(Int(sceneBounds.height)),
                         "viewport_width_pt": String(Int(vc.view.bounds.width)),
                         "viewport_height_pt": String(Int(vc.view.bounds.height)),
                         "island_overlap_suspected":
                             (rootInsets.top > 20 && guestInsets.top < 2)
                             ? "true" : "false",
                         "window_count": String(windowScene?.windows.count ?? 0),
                         "source": "key_and_normal_window_comparison"])
            // Keep the original V48 remote parameters until real device data
            // distinguishes the overridden remote scene inset from a
            // dynamically invalid superview inset. No speculative scaling.
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
    private var lastRejectedBounds: CGSize?
    private var lastInsetsSignature: String = ""
    private var appliedRemoteInsets: [ObjectIdentifier: UIEdgeInsets] = [:]

    // V48-R5: iOS 27 finishes attaching the remote _UISceneHostingController
    // AFTER appSceneVCWillActivateScene. The previous initial/FBScene hooks
    // alone did not synchronize a safe inset once the real UIWindow existed.
    // Keep the guest's full original pixel viewport and update its safe
    // CONTENT REGION; no frame transform, inset overlay or guest resizing.
    private func resolvedHostInsets(_ scene: UIWindowScene) -> UIEdgeInsets {
        var safe = scene.windows.first(where: {
            $0.windowLevel == .normal && !$0.isHidden
        })?.safeAreaInsets ?? view.window?.safeAreaInsets ?? .zero
        if scene.interfaceOrientation.isPortrait {
            let statusBottom = scene.statusBarManager?.statusBarFrame.maxY ?? 0
            safe.top = max(safe.top, statusBottom)
        }
        return safe
    }

    private func synchronizeAttachedGuestSafeAreas(_ scene: UIWindowScene) {
        let safe = resolvedHostInsets(scene)
        guard safe.top > 0 || safe.bottom > 0 ||
              safe.left > 0 || safe.right > 0 else {
            ScarletDiagnosticRecorder.shared.record(
                "layout", "attached_guest_safearea_unavailable",
                status: "warning",
                fields: ["reason": "host_and_statusbar_zero"])
            return
        }
        for controller in controllers.values where controller.scarletNativeFullscreenSlot {
            let key = ObjectIdentifier(controller)
            if let previous = appliedRemoteInsets[key],
               UIEdgeInsetsEqualToEdgeInsets(previous, safe) { continue }
            // additionalSafeAreaInsets affects content in the hosting
            // controller, not UIView.frame or the guest display scale.
            // Record first to avoid a reentrant layout pass retransmitting
            // the same scene settings before the UIKit callback returns.
            appliedRemoteInsets[key] = safe
            controller.additionalSafeAreaInsets = .zero
            let base = controller.view.safeAreaInsets
            controller.additionalSafeAreaInsets = UIEdgeInsets(
                top: max(0, safe.top - base.top),
                left: max(0, safe.left - base.left),
                bottom: max(0, safe.bottom - base.bottom),
                right: max(0, safe.right - base.right))
            controller.updateSettings { settings in
                guard let settings else { return }
                settings.peripheryInsets = safe
                settings.safeAreaInsetsPortrait = safe
                if #available(iOS 19.0, *) {
                    settings.safeAreaEdgeInsets = safe
                }
            }
            ScarletDiagnosticRecorder.shared.record(
                "layout", "attached_guest_safearea_synchronized",
                status: safe.top > 0 ? "success" : "warning",
                fields: ["result": "attached_native_scene_runtime_update",
                         "safe_top_pt": String(Int(safe.top)),
                         "safe_bottom_pt": String(Int(safe.bottom)),
                         "guest_safe_top_pt": String(Int(controller.view.safeAreaInsets.top)),
                         "viewport_width_pt": String(Int(view.bounds.width)),
                         "viewport_height_pt": String(Int(view.bounds.height)),
                         "scene_width_pt": String(Int(scene.coordinateSpace.bounds.width)),
                         "scene_height_pt": String(Int(scene.coordinateSpace.bounds.height))])
        }
    }

    private func captureSafeAreaSnapshot(_ event: String) {
        guard let window = view.window else { return }
        let s = window.windowScene
        let actual = view.safeAreaInsets
        let host = window.safeAreaInsets
        let key = s?.windows.first(where: { $0.isKeyWindow })
        let normal = s?.windows.first(where: {
            $0.windowLevel == .normal && !$0.isHidden
        })
        let n = normal?.safeAreaInsets ?? .zero
        let signature = [Int(actual.top),Int(actual.bottom),Int(host.top),
                         Int(host.bottom),Int(n.top),Int(n.bottom),
                         Int(view.bounds.width),Int(view.bounds.height)].map(String.init).joined(separator: ":")
        guard signature != lastInsetsSignature else { return }
        lastInsetsSignature = signature
        ScarletDiagnosticRecorder.shared.record(
            "layout", event,
            fields: ["safe_top_pt": String(Int(actual.top)),
                     "safe_bottom_pt": String(Int(actual.bottom)),
                     "window_safe_top_pt": String(Int(host.top)),
                     "window_safe_bottom_pt": String(Int(host.bottom)),
                     "guest_safe_top_pt": String(Int(n.top)),
                     "guest_safe_bottom_pt": String(Int(n.bottom)),
                     "host_key": key === normal ? "true" : "false",
                     "viewport_width_pt": String(Int(view.bounds.width)),
                     "viewport_height_pt": String(Int(view.bounds.height)),
                     "scene_width_pt": String(Int(s?.coordinateSpace.bounds.width ?? 0)),
                     "scene_height_pt": String(Int(s?.coordinateSpace.bounds.height ?? 0)),
                     "window_count": String(s?.windows.count ?? 0),
                     "island_overlap_suspected": n.top > 20 && actual.top < 2 ? "true" : "false"])
    }

    override func viewSafeAreaInsetsDidChange() {
        super.viewSafeAreaInsetsDidChange()
        captureSafeAreaSnapshot("resident_viewport_safearea_changed")
    }

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
        captureSafeAreaSnapshot("resident_viewport_layout_snapshot")
        guard let scene = view.window?.windowScene else { return }
        // Check real UIWindowScene size *before* touching any child scene.
        // During rotation, SwiftUI may first deliver a cropped safe-area frame.
        // V45 accidentally applied this provisional frame to every guest,
        // then rejected it: the rejection happened after the damage.
        let expected = scene.coordinateSpace.bounds.size
        let actual = view.bounds.size
        guard actual.width > 0, actual.height > 0,
              abs(expected.width - actual.width) < 2,
              abs(expected.height - actual.height) < 2 else {
            if lastRejectedBounds != actual {
                lastRejectedBounds = actual
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "fullscreen_scene_geometry_rejected",
                    status: "blocked", fields: [
                        "width_pt": String(Int(actual.width)),
                        "height_pt": String(Int(actual.height)),
                        "reason": "viewport_not_screen_bounds"])
            }
            return
        }
        lastRejectedBounds = nil
        if actual != lastBounds {
            lastBounds = actual
            // The same unscaled viewport is applied to all resident scenes.
            // No virtual-window geometry, letterboxing or transform is used.
            let full = view.bounds
            let orientation = scene.interfaceOrientation
            for vc in controllers.values {
                vc.view.frame = full
                vc.updateSettings { settings in
                    guard let settings else { return }
                    settings.setFrame(full)
                    settings.setInterfaceOrientation(orientation)
                }
            }
            ScarletDiagnosticRecorder.shared.record(
                "layout", "fullscreen_scene_geometry_applied",
                fields: ["width_pt": String(Int(actual.width)),
                         "height_pt": String(Int(actual.height)),
                         "reason": "verified_fullscreen_viewport"])
        }
        reconcile()
        synchronizeAttachedGuestSafeAreas(scene)
    }

    func isAlive(folder: String) -> Bool {
        controllers[folder]?.isAppRunning == true
    }

    func activePID(folder: String) -> Int32? {
        guard let owned = controllers[folder], owned.isAppRunning,
              owned.pid > 0 else { return nil }
        return owned.pid
    }

    func ownsController(_ controller: AppSceneViewController, folder: String) -> Bool {
        controllers[folder] === controller
    }

    @discardableResult
    func releaseExitedController(folder: String) -> Bool {
        guard let old = controllers[folder] else { return true }
        guard !old.isAppRunning else { return false }
        old.willMove(toParent: nil)
        old.view.removeFromSuperview()
        old.removeFromParent()
        controllers.removeValue(forKey: folder)
        appliedRemoteInsets.removeValue(forKey: ObjectIdentifier(old))
        return true
    }

    func select(folder: String) -> Bool {
        guard let target = controllers[folder],
              target.isAppRunning,
              target.contentView?.superview != nil else { return false }
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
            // Do not show an uninitialized LiveProcess surface (black flash).
            // The prior guest remains fully attached, visible and touchable.
            vc.view.layer.opacity = 0
            vc.view.isUserInteractionEnabled = false
            addChild(vc)
            view.addSubview(vc.view)
            vc.didMove(toParent: self)
            controllers[slot.id] = vc
        }
        if let active = stack.activeID,
           stack.slots.contains(where: { $0.id == active && $0.pid > 0 }) {
            _ = select(folder: active)
        }
        // Newly created controllers are not present during the earlier
        // viewDidLayoutSubviews pass. Synchronize after attaching them.
        synchronizeAttachedGuestSafeAreas(scene)
    }
}

@available(iOS 17.0, *)
struct ScarletFullscreenSceneViewportRepresentable: UIViewControllerRepresentable {
    @ObservedObject var stack: ScarletFullscreenSceneStack
    let installedApps: [LCAppModel]
    func makeUIViewController(context: Context)
        -> ScarletFullscreenSceneViewport {
        ScarletFullscreenSceneViewport(stack: stack)
    }
    func updateUIViewController(_ vc: ScarletFullscreenSceneViewport,
                                context: Context) {
        stack.updateInstalledModels(installedApps)
        vc.reconcile()
        stack.updateOverlay()
    }
}

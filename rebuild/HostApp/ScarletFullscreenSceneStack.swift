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
    // P52: reference only for guest native tone/readback; never attach this
    // to the host root SwiftUI .preferredColorScheme, which changes all of
    // Scarlet Crystal's original semantic colors and native glass materials.
    @Published private(set) var hostStatusBarScheme: ColorScheme? = nil
    // P51: native clock/icons share the same physical top region as guest
    // interactive controls. Fail closed until THIS guest's layout is proven
    // safe; do not crop, offset or mutate the guest's full FBScene.
    @Published private(set) var nativeStatusBarCollisionShield = false
    private var nativeStatusBarUnsafePIDs: Set<Int32> = []
    private var nativeStatusBarSafePIDs: Set<Int32> = []
    @Published private(set) var lastError: String?
    weak var viewport: ScarletFullscreenSceneViewport?
    // R5 recovery: observation only, no guest UIKit method interception.
    private var guestProcessStartTimes: [ObjectIdentifier: Date] = [:]
    private var pendingReveal: Set<String> = []
    private var remoteAttachSeen: Set<String> = []
    private var firstRevealCompleted: Set<String> = []
    // Compatibility fallback is once per guest per host session. It can
    // never displace another live resident guest or revoke a certificate.
    private var classicFallbackAttempted: Set<String> = []
    private var pendingClassicFallback: Set<String> = []
    private var overlayWindow: ScarletGuestTouchPassthroughWindow?
    // A resident overlay can be non-key and lose background hit ownership.
    // Gesture is attached to the actual parent viewport, not a guest process.
    var activeOutsideOverlay: ScarletGuestTouchPassthroughWindow? {
        guard isVisible, let overlayWindow, !overlayWindow.isHidden,
              overlayWindow.isExpanded else { return nil }
        return overlayWindow
    }
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

    // Reset both native hit-testing and retained SwiftUI expansion BEFORE
    // hiding the overlay or selecting a different guest.
    private func collapseSwitcherForNavigation(_ reason: String) {
        guard let overlayWindow else { return }
        overlayWindow.dismissState?.requestImmediateClose()
        overlayWindow.isExpanded = false
        viewport?.setResidentOutsideDismissEnabled(false)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switch_panel_navigation_reset",
            fields: ["reason": reason, "overlay_expanded": "false"])
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
        collapseSwitcherForNavigation("enqueue_guest")
        slots.append(Slot(id: folder, dataUUID: uuid,
                          title: app.displayName,
                          bundleID: app.bundleIdentifier,
                          icon: icon, pid: 0, failed: false))
        activeID = folder
        // New guest must not inherit the preceding guest's visual style
        // or assume its header is safe. Native status bar is temporarily
        // withheld until the attached guest supplies its measured geometry.
        hostStatusBarScheme = nil
        nativeStatusBarCollisionShield = true
        pendingReveal.remove(folder)
        remoteAttachSeen.remove(folder)
        firstRevealCompleted.remove(folder)
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
            viewport?.setResidentOutsideDismissEnabled(false)
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
            window.expandedChanged = { [weak self] expanded in
                self?.viewport?.setResidentOutsideDismissEnabled(expanded)
            }
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
              slot.pid > 0, viewport?.isAlive(folder: folder) == true else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_reuse_failed",
                status: "warning",
                fields: ["reason": "process_not_live",
                         "memory": "not_preserved"])
            return false
        }
        // A hidden compositor is intentionally prevented from foregrounding
        // its remote guest. Explicit user activation must reveal the viewport
        // BEFORE select() is allowed to resume this exact guest's audio.
        let wasVisible = isVisible
        let wasShielded = nativeStatusBarCollisionShield
        collapseSwitcherForNavigation("activate_guest")
        nativeStatusBarCollisionShield = !nativeStatusBarSafePIDs.contains(slot.pid) ||
            nativeStatusBarUnsafePIDs.contains(slot.pid)
        isVisible = true
        guard viewport?.select(folder: folder) == true else {
            isVisible = wasVisible
            nativeStatusBarCollisionShield = wasShielded
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_reuse_failed",
                status: "warning", fields: [
                    "reason": "remote_content_not_ready",
                    "memory": "not_preserved"])
            return false
        }
        activeID = folder
        // After select() switched guest surfaces, restore only that live
        // guest's measured native tone on the key host scene.
        viewport?.syncKeyHostStatusBarForActiveGuest()
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_reused",
            status: "success", fields: [
                "process_pid": String(slot.pid),
                "memory": "same_live_process",
                "count": String(slots.count)])
        updateOverlay()
        return true
    }

    // P49 revealed that changing the key-host SwiftUI root's colorScheme
    // changes the native statusbar but ALSO the entire host palette. P52
    // preserves guest tone as passive evidence; never force host appearance.
    // P51: Status bar ownership (P49) was fixed on iPhone, but that
    // SUCCESS exposed overlap with guest action controls at physical y0.
    // A second zero-risk snapshot must not clear the first proven collision:
    // Instagram scrolls away from the colliding header between samples.
    func reportNativeStatusBarCollisionRisk(pid: Int32, unsafe: Int,
                                            sample: Int, scene: UIWindowScene?) {
        guard sample == 650 || sample == 2600, pid > 0, isVisible,
              let activeID,
              slots.contains(where: { $0.id == activeID && $0.pid == pid })
        else { return }
        if unsafe > 0 {
            nativeStatusBarUnsafePIDs.insert(pid)
            nativeStatusBarSafePIDs.remove(pid)
        } else if !nativeStatusBarUnsafePIDs.contains(pid) {
            nativeStatusBarSafePIDs.insert(pid)
        }
        let shield = nativeStatusBarUnsafePIDs.contains(pid) ||
            !nativeStatusBarSafePIDs.contains(pid)
        nativeStatusBarCollisionShield = shield
        ScarletDiagnosticRecorder.shared.record(
            "layout", "resident_native_status_bar_collision_policy",
            fields: ["process_pid": String(pid),
                     "sample_index": String(sample),
                     "visible_unsafe_controls": String(unsafe),
                     "result": shield ? "native_icons_withheld_guest_collision"
                                      : "native_icons_allowed_safe_guest"])
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.32) {
            [weak self, weak scene] in
            guard let self, self.isVisible, let scene,
                  let activeID = self.activeID,
                  self.nativeStatusBarCollisionShield == shield,
                  self.slots.contains(where: { $0.id == activeID && $0.pid == pid })
            else { return }
            let hidden = scene.statusBarManager?.isStatusBarHidden == true
            ScarletDiagnosticRecorder.shared.record(
                "layout", "resident_native_status_bar_collision_readback",
                fields: ["process_pid": String(pid),
                         "sample_index": String(sample),
                         "status_hidden": hidden ? "true" : "false",
                         "expected_hidden": shield ? "true" : "false",
                         "result": hidden == shield
                             ? "native_status_collision_policy_matched"
                             : "native_status_collision_policy_mismatch"])
        }
    }

    func clearNativeStatusBarCollisionRisk(pid: Int32) {
        nativeStatusBarUnsafePIDs.remove(pid)
        nativeStatusBarSafePIDs.remove(pid)
    }

    func syncKeyHostStatusBarTone(pid: Int32, tone: Int,
                                  scene: UIWindowScene) {
        guard isVisible, let activeID,
              slots.contains(where: { $0.id == activeID && $0.pid == pid && pid > 0 })
              else { return }
        let next: ColorScheme? = tone == 1 ? .light : (tone == 2 ? .dark : nil)
        guard hostStatusBarScheme != next else { return }
        hostStatusBarScheme = next
        let desired: UIStatusBarStyle = tone == 1 ? .darkContent :
            (tone == 2 ? .lightContent : .default)
        ScarletDiagnosticRecorder.shared.record(
            "layout", "resident_key_host_status_bar_tone_observed",
            fields: ["process_pid": String(pid),
                     "surface_tone": String(tone),
                     "preferred_style_raw": String(Int(desired.rawValue)),
                     "result": "guest_tone_read_only_original_palette_preserved"])
        // P52: there is no global presentation override. The readback is
        // diagnostic only and can differ from the guest contrast preference.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.30) {
            [weak self, weak scene] in
            guard let self, self.isVisible, let scene,
                  self.activeID == activeID,
                  self.hostStatusBarScheme == next else { return }
            let observed = scene.statusBarManager?.statusBarStyle.rawValue ?? -1
            let keyPresent = scene.windows.contains(where: { $0.isKeyWindow })
            ScarletDiagnosticRecorder.shared.record(
                "layout", "resident_key_host_status_bar_readback",
                fields: ["process_pid": String(pid),
                         "surface_tone": String(tone),
                         "host_key": keyPresent ? "true" : "false",
                         "status_hidden": scene.statusBarManager?.isStatusBarHidden == true
                             ? "true" : "false",
                         "preferred_style_raw": String(Int(desired.rawValue)),
                         "status_style_raw": String(Int(observed)),
                         "result": observed == desired.rawValue && keyPresent
                             ? "unforced_host_status_style_matches_guest"
                             : "unforced_host_status_style_mismatch_guest"])
        }
    }

    func restoreForegroundOnHostActive() {
        guard isVisible, let activeID,
              viewport?.isAlive(folder: activeID) == true else { return }
        let refreshed = viewport?.refreshExistingRemoteScene(folder: activeID) == true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_host_active_refresh",
            fields: ["result": refreshed ? "foreground_reasserted_on_existing_pid"
                                          : "native_scene_not_attached",
                     "memory": "no_resign_no_process_restart"])
        if !refreshed {
            revealStartedScene(activeID)
        }
    }

    func goHome() {
        // A hidden UIWindow is not equivalent to a closed SwiftUI card.
        collapseSwitcherForNavigation("go_home")
        // No close, terminate, detach, scene destruction or relaunch.
        // Keep each remote scene in the original full-screen viewport.
        isVisible = false
        // Release all P49/P51 guest-only presentation preferences on Home.
        hostStatusBarScheme = nil
        nativeStatusBarCollisionShield = false
        // R6.1: returning to the Scarlet host is a real audio-focus change.
        // A retained LiveProcess must not keep playing simply because its
        // full-screen remote view is hidden. Preserve its process and data.
        viewport?.pauseAllResidentAudioOnHome()
        overlayWindow?.isHidden = true
        viewport?.setResidentOutsideDismissEnabled(false)
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

    // Some closed-source guests cannot start in a LiveProcess extension.
    // If a new extension terminates immediately, perform one ORIGINAL LC
    // launch attempt using the exact same installed .app and data container.
    // Only safe when no other live resident guest will lose its work state.
    private func recoverFastFailedGuest(_ folder: String, dataUUID: String,
                                        reason: String) {
        guard !classicFallbackAttempted.contains(folder),
              !pendingClassicFallback.contains(folder) else { return }
        pendingClassicFallback.insert(folder)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "experimental_guest_compatibility_route_scheduled",
            status: "warning",
            fields: ["reason": reason,
                     "result": "classic_original_LC_eligible_if_no_live_guest",
                     "mode": "experimental_remains_enabled"])
        Task { @MainActor [weak self] in
            // Original LC unregisters the exited extension container after
            // notifying its delegate. Do not race that unregister callback.
            try? await Task.sleep(nanoseconds: 650_000_000)
            guard let self else { return }
            self.pendingClassicFallback.remove(folder)
            guard !self.classicFallbackAttempted.contains(folder) else { return }
            // Never tear down an app A just to rescue app B.
            guard !self.hasLiveResidentProcess, !self.pendingInPlaceLaunch else {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "experimental_guest_compatibility_route_blocked",
                    status: "warning",
                    fields: ["reason": "another_live_guest_or_launch_in_progress",
                             "memory": "preserve_other_guest_work"])
                return
            }
            guard let model = self.installedModels[folder],
                  model.appInfo.relativeBundlePath == folder,
                  model.uiSelectedContainer?.folderName == dataUUID,
                  let defaults = UserDefaults.lc() else {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "experimental_guest_compatibility_route_blocked",
                    status: "warning",
                    fields: ["reason": "original_model_container_or_defaults_unavailable"])
                return
            }
            self.classicFallbackAttempted.insert(folder)
            // This uses the exact path already used by the original LC
            // cold-handoff implementation. Never uninstall or re-sign here.
            defaults.set(folder, forKey: "selected")
            defaults.set(dataUUID, forKey: "selectedContainer")
            let accepted = LCSharedUtils.launchToGuestApp(withClassicMode: 0)
            ScarletDiagnosticRecorder.shared.record(
                "guest", "experimental_guest_compatibility_route_submitted",
                status: accepted ? "warning" : "error",
                fields: ["result": accepted
                           ? "classic_original_LC_launch_requested"
                           : "original_launch_not_accepted",
                         "mode": "experimental_remains_enabled",
                         "memory": "this_guest_new_process_other_live_guests_protected"])
            if !accepted {
                self.lastError = "실험 모드에서 게스트 실행이 실패했습니다. 기본 실행 전환도 승인되지 않았습니다."
            }
        }
    }

    // PID readiness and remote UIKit presentation readiness are different.
    // An actual iPhone can leave a black remote surface until the user goes
    // Home and back, because first handoff occurs before UIKit content attach.
    private func revealStartedScene(_ folder: String,
                                    attemptsRemaining: Int = 60,
                                    isRetry: Bool = false) {
        guard activeID == folder else {
            pendingReveal.remove(folder)
            return
        }
        let ready = viewport?.isRemoteReady(folder: folder) == true
        if ready, viewport?.select(folder: folder) == true {
            pendingReveal.remove(folder)
            if firstRevealCompleted.insert(folder).inserted {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_scene_first_surface_revealed",
                    status: "success",
                    fields: ["result": "content_attached_foreground_requested",
                             "memory": "same_host_scene_stack"])
            }
            return
        }
        guard attemptsRemaining > 0 else {
            pendingReveal.remove(folder)
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_first_surface_timeout",
                status: "warning", fields: ["reason": "remote_content_not_attached",
                                             "memory": "pid_not_render_readiness"])
            return
        }
        if pendingReveal.insert(folder).inserted {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_waiting_for_remote_content",
                fields: ["reason": "pid_precedes_presenter_scene_and_content_view"])
        } else if !isRetry {
            // Native attach callback may arrive during an existing retry;
            // that retry remains authoritative to prevent timer duplication.
            return
        }
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 250_000_000)
            self?.revealStartedScene(folder,
                attemptsRemaining: attemptsRemaining - 1, isRetry: true)
        }
    }

    func sceneStarted(_ vc: AppSceneViewController, error: Error?) {
        guard let index = slots.firstIndex(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        }) else { return }
        if error != nil || vc.pid <= 0 {
            slots[index].failed = true
            let ns = error as NSError?
            let folder = slots[index].id
            let dataUUID = slots[index].dataUUID
            lastError = "게스트 원격 실행을 시작하지 못했습니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "fullscreen_scene_start_failed",
                status: "error",
                fields: ["reason": "liveprocess_failed",
                         "error_domain": ns?.domain ?? "no_nserror",
                         "error_code": ns.map { String($0.code) } ?? "unknown",
                         "process_pid": String(vc.pid),
                         "stage": "before_or_during_remote_extension_request"])
            if folder == activeID { goHome() }
            recoverFastFailedGuest(folder, dataUUID: dataUUID,
                                   reason: "extension_initialization_failed")
            return
        }
        slots[index].pid = vc.pid
        ScarletGuestIslandReceiptObserver.shared.observe(pid: vc.pid)
        guestProcessStartTimes[ObjectIdentifier(vc)] = Date()
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

    // Native signal after setUpAppPresenter added _contentView to its real
    // owning VC. This was absent in R2/R3, where PID could be reported first.
    func appSceneVCDidAttachRemoteContent(_ vc: AppSceneViewController!) {
        guard let vc, viewport?.ownsController(vc, folder: vc.bundleId) == true else { return }
        remoteAttachSeen.insert(vc.bundleId)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_remote_content_attached",
            fields: ["result": "native_after_content_subview",
                     "window_attached": vc.view.window != nil ? "true" : "false",
                     "process_pid": String(vc.pid)])
        if activeID == vc.bundleId {
            revealStartedScene(vc.bundleId)
        }
    }

    // Objective-C delegate callbacks from the ORIGINAL AppSceneViewController.
    func appSceneVCAppDidExit(_ vc: AppSceneViewController!) {
        guard let vc, viewport?.ownsController(vc, folder: vc.bundleId) == true
        else { return }
        let wasActive = activeID == vc.bundleId
        // The upstream Objective-C controller exposes dataUUID as an
        // implicitly optional String. Preserve the exact existing slot's
        // verified data container rather than force-unwrapping on an exit.
        let exitedDataUUID = slots.first(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        })?.dataUUID
        pendingReveal.remove(vc.bundleId)
        remoteAttachSeen.remove(vc.bundleId)
        firstRevealCompleted.remove(vc.bundleId)
        let pid = vc.pid
        let lifetime = guestProcessStartTimes.removeValue(forKey: ObjectIdentifier(vc))
        let durationMs = lifetime.map {
            String(max(0, Int(Date().timeIntervalSince($0) * 1000)))
        } ?? "unknown"
        if let index = slots.firstIndex(where: {
            $0.id == vc.bundleId && $0.dataUUID == vc.dataUUID
        }) {
            slots.remove(at: index)
        }
        // Removing a dead remote controller is NOT killing a live guest.
        // Drop only the exact exited instance, never a sibling or replacement.
        let released = viewport?.releaseExitedController(folder: vc.bundleId) == true
        let fastExit = lifetime.map { Date().timeIntervalSince($0) < 4 } ?? false
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_process_exited",
            fields: ["memory": "not_preserved",
                     "dead_controller_released": released ? "true" : "false",
                     "process_pid": String(pid),
                     "duration_ms": durationMs,
                     "fast_exit": fastExit ? "true" : "false",
                     "reason": "native_exit_callback_no_ips_reason",
                     "source": "original_LC_scene_delegate"])
        if wasActive {
            activeID = nil
            goHome()
        }
        if fastExit && wasActive, let exitedDataUUID {
            recoverFastFailedGuest(vc.bundleId, dataUUID: exitedDataUUID,
                                   reason: "liveprocess_exited_under_4s")
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
            // The FBScene authority owns all safe-area settings; this
            // delegate owns only full-resolution frame and orientation.
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
// Guest-side AVAudioSession receipts are scoped to the exact LiveProcess
// PID, just like the original pause/resume commands. A singleton keeps
// observation valid across SwiftUI viewport reparenting without attaching
// a new App ID, window, or signing entitlement.
@available(iOS 17.0, *)
@MainActor
private final class ScarletGuestAudioReceiptObserver {
    static let shared = ScarletGuestAudioReceiptObserver()
    private var observedPIDs: Set<Int32> = []

    func observe(pid: Int32) {
        guard pid > 0, observedPIDs.insert(pid).inserted else { return }
        let center = CFNotificationCenterGetDarwinNotifyCenter()
        for action in ["pause", "resume"] {
            for outcome in ["ok", "error"] {
                let notification = "com.scarlet.guest.audio.ack.\(action).\(outcome).\(pid)"
                CFNotificationCenterAddObserver(
                    center, Unmanaged.passUnretained(self).toOpaque(),
                    { _, _, name, _, _ in
                        guard let name else { return }
                        let parts = String(describing: name.rawValue)
                            .components(separatedBy: ".")
                        guard parts.count == 8,
                              parts[0] == "com", parts[1] == "scarlet",
                              parts[4] == "ack" else { return }
                        let action = parts[5]
                        let outcome = parts[6]
                        let processPID = parts[7]
                        DispatchQueue.main.async {
                            ScarletDiagnosticRecorder.shared.record(
                                "guest", "guest_audio_device_receipt",
                                status: outcome == "ok" ? "success" : "warning",
                                fields: ["action": action,
                                         "result": outcome,
                                         "process_pid": processPID,
                                         "source": "guest_liveprocess_darwin_ack",
                                         "scope": "av_audio_session_set_active"])
                        }
                    },
                    notification as CFString, nil, .deliverImmediately)
            }
        }
    }
}

// R6P24: prove that the *outgoing* resident guest, not the new guest or
// the host, received the keyboard focus-release request. These are request
// and keyboard-hide event receipts, not proof of a visually closed keyboard.
@available(iOS 17.0, *)
@MainActor
private final class ScarletGuestKeyboardReceiptObserver {
    static let shared = ScarletGuestKeyboardReceiptObserver()
    private var observedPIDs: Set<Int32> = []

    func observe(pid: Int32) {
        guard pid > 0, observedPIDs.insert(pid).inserted else { return }
        let center = CFNotificationCenterGetDarwinNotifyCenter()
        for outcome in ["resign_requested", "no_active_responder",
                        "no_owned_window", "keyboard_hidden"] {
            let name = "com.scarlet.guest.keyboard.ack.\(outcome).\(pid)"
            CFNotificationCenterAddObserver(
                center, Unmanaged.passUnretained(self).toOpaque(),
                { _, _, event, _, _ in
                    guard let event else { return }
                    let parts=String(describing:event.rawValue)
                        .components(separatedBy: ".")
                    guard parts.count == 7,
                          parts[0] == "com", parts[1] == "scarlet",
                          parts[2] == "guest", parts[3] == "keyboard",
                          parts[4] == "ack",
                          Int32(parts[6]) != nil else { return }
                    DispatchQueue.main.async {
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "guest_keyboard_device_receipt",
                            status: "info",
                            fields: ["result": parts[5], "process_pid": parts[6],
                                     "scope": "outgoing_guest_first_responder"])
                    }
                },
                name as CFString, nil, .deliverImmediately)
        }
    }
}

// R6P15: guest-only safe-area correction evidence. The guest writes an
// anonymous bounded readback into the existing LC App Group and posts a
// PID-scoped Darwin notification. A host hosting-owner 62pt readback alone
// is not proof that the guest UIKit root received a safe content region.
@available(iOS 17.0, *)
@MainActor
private final class ScarletGuestIslandReceiptObserver {
    static let shared = ScarletGuestIslandReceiptObserver()
    private var subscribed: Set<Int32> = []
    private var seen: Set<String> = []
    var onTopRiskMeasured: ((Int32, Int, Int, Int, Int, Int, Int) -> Void)?
    var onSurfaceToneMeasured: ((Int32, Int) -> Void)?
    var onHeaderTransformVerified: ((Int32, Bool) -> Void)?

    func observe(pid: Int32) {
        guard pid > 0 else { return }
        if subscribed.insert(pid).inserted {
            let event = "com.scarlet.guest.island.ack.\(pid)"
            CFNotificationCenterAddObserver(
                CFNotificationCenterGetDarwinNotifyCenter(),
                Unmanaged.passUnretained(self).toOpaque(),
                { _, _, _, _, _ in
                    DispatchQueue.main.async {
                        ScarletGuestIslandReceiptObserver.shared.readBack()
                    }
                }, event as CFString, nil, .deliverImmediately)
        }
        readBack() // Reconcile a receipt sent before the listener attached.
    }

    private func readBack() {
        guard let bytes = LCUtils.appGroupUserDefault.data(
                forKey: "Scarlet.Guest.IslandRootReceipt.V1"),
              let rows = try? JSONSerialization.jsonObject(with: bytes)
                  as? [[String: Any]] else { return }
        for row in rows {
            guard let token = row["receipt"] as? String,
                  !seen.contains(token),
                  let pid = (row["pid"] as? NSNumber)?.int32Value,
                  subscribed.contains(pid),
                  let epoch = (row["epoch"] as? NSNumber)?.doubleValue,
                  Date().timeIntervalSince1970 - epoch >= 0,
                  Date().timeIntervalSince1970 - epoch < 180,
                  let result = row["result"] as? String else { continue }
            seen.insert(token)
            let target = (row["target"] as? NSNumber)?.intValue ?? -1
            let before = (row["before"] as? NSNumber)?.intValue ?? -1
            let after = (row["after"] as? NSNumber)?.intValue ?? -1
            if result == "guest_short_header_quarantined" {
                ScarletDiagnosticRecorder.shared.record("layout", result,
                    fields: ["process_pid": String(pid), "safe_top_pt": String(target)])
                continue
            }
            if result == "guest_header_layout_owner_probe" {
                var fields: [String: String] = [
                    "process_pid": String(pid), "safe_top_pt": String(target)]
                for key in [
                    "sample_index", "header_ambiguous", "header_autoresize_mask",
                    "header_constraints_capped", "header_constraints_inspected", "header_constraints_relevant",
                    "header_controller_layout_impl_origin", "header_controller_parent_match", "header_controls_before",
                    "header_edges", "header_height", "header_images_after",
                    "header_layout_impl_origin", "header_local_y", "header_parent_autoresizes",
                    "header_parent_controller_layout_impl_origin", "header_parent_edges", "header_parent_guide_y",
                    "header_parent_layout_impl_origin", "header_parent_layout_override", "header_parent_prefers_status_hidden",
                    "header_parent_slot", "header_prefers_status_hidden", "header_probe_status",
                    "header_scene_status_height", "header_scene_status_hidden", "header_setbounds_impl_origin",
                    "header_setcenter_impl_origin", "header_setframe_impl_origin", "header_severe_nodes",
                    "header_slot", "header_translates", "header_window_y"
                ] {
                    if let value = row[key] as? NSNumber { fields[key] = value.stringValue }
                }
                ScarletDiagnosticRecorder.shared.record("layout", result, fields: fields)
                if let constraints = row["header_constraints"] as? [[String: Any]] {
                    for (index, constraint) in constraints.prefix(16).enumerated() {
                        var detail = fields
                        detail["header_constraint_index"] = String(index)
                        for key in [
                    "header_constraint_autoresizing", "header_constraint_constant", "header_constraint_first_attr",
                    "header_constraint_first_kind", "header_constraint_holder", "header_constraint_mask_known",
                    "header_constraint_multiplier_milli", "header_constraint_priority", "header_constraint_relation",
                    "header_constraint_second_attr", "header_constraint_second_kind", "header_constraint_source"
                ] {
                            if let value = constraint[key] as? NSNumber {
                                detail[key] = value.stringValue
                            }
                        }
                        ScarletDiagnosticRecorder.shared.record(
                            "layout", "guest_header_constraint_probe", fields: detail)
                    }
                }
                continue
            }
            if ["guest_short_header_trial_staged",
                "guest_short_header_trial_reverted",
                "guest_short_header_trial_retained",
                "guest_header_constraint_bridge_staged",
                "guest_header_constraint_bridge_reverted",
                "guest_header_constraint_bridge_retained"].contains(result) {
                // R6P37: this is a single specific child controller's
                // Y-only safe-guide experiment. Never log app/view identity.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "safe_top_pt": String(target),
                    "result": result
                ]
                for key in ["header_before_y", "header_after_y",
                    "header_controls_before", "header_controls_after",
                    "header_images_after", "header_gate_pass"] {
                    if let value = row[key] as? NSNumber {
                        fields[key] = value.stringValue
                    }
                }
                if let reason = row["reason"] as? String,
                   ["parent_safe_guide_anchor", "no_immediate_reduction",
                    "native_layout_overrode", "late_safe_guide_confirmed",
                    "late_layout_not_persistent",
                    "parent_safe_guide_constraint",
                    "late_native_anchor_confirmed"].contains(reason) {
                    fields["reason"] = reason
                }
                let isConstraintBridge = result.hasPrefix(
                    "guest_header_constraint_bridge_")
                ScarletDiagnosticRecorder.shared.record(
                    "layout", isConstraintBridge
                        ? "guest_header_constraint_bridge_receipt"
                        : "guest_short_header_trial_receipt",
                    status: ["guest_short_header_trial_retained",
                             "guest_header_constraint_bridge_retained"].contains(result)
                        ? "success" : "info", fields: fields)
                continue
            }
            if result == "guest_geometry_probe_status" {
                // R6P36: a missing guest snapshot is an observable fact;
                // preserve only closed failure reasons and anonymous flags.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "safe_top_pt": String(target)
                ]
                if let reason = row["reason"] as? String,
                   ["scheduled", "window_released", "root_replaced",
                    "root_stale", "window_ineligible", "scene_ineligible",
                    "root_detached", "safe_unready", "frame_invalid"].contains(reason) {
                    fields["reason"] = reason
                }
                for key in ["sample_index", "probe_window_present",
                    "probe_window_visible", "probe_window_normal",
                    "probe_scene_present", "probe_scene_state",
                    "probe_portrait", "probe_root_present",
                    "probe_root_match", "probe_root_attached",
                    "probe_root_safe_top", "probe_replacement"] {
                    if let v = row[key] as? NSNumber {
                        fields[key] = v.stringValue
                    }
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_geometry_probe_status", fields: fields)
                continue
            }
            if result == "guest_ancestor_layout_probe" {
                // R6P35: only numeric geometry of at most two severely
                // unsafe UIKit controls and their bounded ancestor chains.
                // No class names, text, identifiers or app content.
                if let nodes = row["nodes"] as? [[String: Any]] {
                    for node in nodes.prefix(48) {
                        var fields: [String: String] = [
                            "process_pid": String(pid),
                            "safe_top_pt": String(target)
                        ]
                        for key in ["sample_index", "selected_nodes",
                            "owner_reached_nodes", "root_reached_nodes",
                            "ancestor_rows_capped"] {
                            if let v = row[key] as? NSNumber {
                                fields[key] = v.stringValue
                            }
                        }
                        for key in [
                            "node_slot", "scroll_slot", "ancestor_slot",
                            "ancestor_depth", "ancestor_window_y",
                            "ancestor_parent_window_y", "ancestor_local_y",
                            "ancestor_guide_y", "ancestor_safe_top",
                            "ancestor_bounds_y", "ancestor_height",
                            "ancestor_vertical_constraints", "ancestor_autoresize_mask",
                            "ancestor_translates", "ancestor_is_controller_root",
                            "ancestor_controller_safe_top", "ancestor_is_scroll",
                            "ancestor_is_control", "ancestor_clips",
                            "ancestor_has_transform", "ancestor_is_owner",
                            "ancestor_is_root"
                        ] {
                            if let v = node[key] as? NSNumber {
                                fields[key] = v.stringValue
                            }
                        }
                        ScarletDiagnosticRecorder.shared.record(
                            "layout", "guest_ancestor_layout_probe",
                            fields: fields)
                    }
                }
                continue
            }
            if result == "guest_constraint_owner_probe" {
                if let nodes = row["nodes"] as? [[String: Any]] {
                    for node in nodes.prefix(12) {
                        var fields: [String: String] = [
                            "process_pid": String(pid), "safe_top_pt": String(target)
                        ]
                        for key in ["sample_index", "scene_activation_state", "probe_nodes_capped"] {
                            if let value = row[key] as? NSNumber { fields[key] = value.stringValue }
                        }
                        for key in [
                    "node_slot", "scroll_slot", "node_window_x", "node_window_width", "node_window_height", "node_window_y",
                    "node_window_bottom", "node_owner_y", "node_local_y",
                    "node_autoresizing", "node_ambiguous", "node_in_navbar",
                    "controller_safe_top", "constraint_count", "constraint_inspected",
                    "constraint_frame_refs", "constraint_content_refs", "constraint_safe_refs",
                    "constraint_external_refs", "constraint_center_refs", "constraint_other_refs",
                    "constraint_first_attribute", "constraint_other_attribute", "constraint_first_relation",
                    "constraint_first_constant", "constraint_first_priority", "constraint_scan_capped",
                    "owner_offset_y", "owner_bounds_y"
                        ] {
                            if let value = node[key] as? NSNumber { fields[key] = value.stringValue }
                        }
                        ScarletDiagnosticRecorder.shared.record(
                            "layout", "guest_constraint_owner_probe", fields: fields)
                    }
                }
                continue
            }
            if result == "guest_always_policy_quarantined" {
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_always_policy_quarantined",
                    fields: ["process_pid": String(pid), "safe_top_pt": String(target)])
                continue
            }
            if ["guest_header_postforeground_trial_staged",
                "guest_header_local_transform_staged",
                "guest_header_local_transform_first_pass",
                "guest_header_local_transform_retained",
                "guest_owner_layout_contract_staged",
                "guest_owner_layout_contract_first_pass",
                "guest_owner_layout_contract_retained",
                "guest_owner_layout_contract_reverted",
                "guest_header_local_transform_reverted",
                "guest_header_local_transform_invalidated",
                "guest_header_scroll_motion_safe",
                "guest_header_detached_fullscene_retained",
                "guest_header_detached_probe_deferred",
                "guest_header_detached_risk_provisional",
                "guest_header_detached_risk_confirmed"].contains(result) {
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_header_local_transform_receipt",
                    status: result == "guest_header_local_transform_reverted"
                        ? "warning" : "info",
                    fields: ["process_pid": String(pid),
                             "result": result,
                             "safe_top_pt": String(target),
                             "sample_index":
                                String((row["sample_index"] as? NSNumber)?.intValue ?? -1),
                             "header_controls_before":
                                String((row["header_controls_before"] as? NSNumber)?.intValue ?? -1),
                             "header_controls_after":
                                String((row["header_controls_after"] as? NSNumber)?.intValue ?? -1),
                             "header_gate_pass":
                                (row["header_gate_pass"] as? NSNumber)?.boolValue == true
                                    ? "true" : "false",
                             // P45: why the P44 native header was invalidated.
                             // The source only publishes bounded numeric geometry.
                             "header_current_y":
                                String((row["header_current_y"] as? NSNumber)?.intValue ?? -999),
                             "header_checked_controls":
                                String((row["header_checked_controls"] as? NSNumber)?.intValue ?? -1),
                             "header_visible_controls":
                                String((row["header_visible_controls"] as? NSNumber)?.intValue ?? -1),
                             "header_unsafe_controls":
                                String((row["header_unsafe_controls"] as? NSNumber)?.intValue ?? -1),
                             "header_affine_retained":
                                (row["header_affine_retained"] as? NSNumber)?.boolValue == true
                                    ? "true" : "false",
                             "header_invalidation_reason":
                                String((row["header_invalidation_reason"] as? NSNumber)?.intValue ?? -1),
                             "header_detached_severe":
                                String((row["header_detached_severe"] as? NSNumber)?.intValue ?? -1),
                             "header_detached_first_y":
                                String((row["header_detached_first_y"] as? NSNumber)?.intValue ?? -999),
                             "header_detached_visible_controls":
                                String((row["header_detached_visible_controls"] as? NSNumber)?.intValue ?? -1),
                             "header_detached_samples":
                                String((row["header_detached_samples"] as? NSNumber)?.intValue ?? -1)])
                if result == "guest_header_local_transform_retained" ||
                   result == "guest_owner_layout_contract_retained" {
                    onHeaderTransformVerified?(pid, true)
                } else if result == "guest_header_local_transform_reverted" ||
                          result == "guest_owner_layout_contract_reverted" ||
                          result == "guest_header_local_transform_invalidated" {
                    onHeaderTransformVerified?(pid, false)
                }
                continue
            }
            if result == "guest_chrome_surface_tone" {
                let tone = (row["surface_tone"] as? NSNumber)?.intValue ?? 0
                guard (0...2).contains(tone) else { continue }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_surface_tone",
                    fields: ["process_pid": String(pid),
                             "surface_tone": String(tone),
                             "result": "guest_native_uikit_background"])
                onSurfaceToneMeasured?(pid, tone)
                continue
            }
            if result == "guest_content_geometry_probe" {
                // Anonymous window-space measurements only. No view names,
                // text, guest IDs, screenshots, labels or private class names.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "safe_top_pt": String(target),
                    "root_safe_top_pt": String(before)
                ]
                let numericFields = ["sample_index", "root_frame_y", "root_guide_y",
                    "visited", "candidate_controls", "top_controls",
                    "unsafe_controls", "visible_unsafe_controls",
                    "clipped_unsafe_controls", "unsafe_controls_in_scroll",
                    "unsafe_controls_outside_scroll",
                    "unsafe_controls_under_zero_inset_child_owner",
                    "first_top_control_y",
                    "first_unsafe_control_y", "scroll_top_without_inset",
                    "scroll_first_y", "top_text_nodes", "unsafe_text_nodes",
                    "first_unsafe_text_y", "top_image_nodes",
                    "unsafe_image_nodes", "visible_unsafe_images",
                    "clipped_unsafe_images", "unsafe_image_nodes_in_scroll",
                    "unsafe_image_nodes_outside_scroll", "first_unsafe_image_y",
                    "max_depth_seen",
                    // R6P27: anonymized closest-scroll *visible* content owner.
                    "owner_groups", "owner_dominant_controls",
                    "owner_dominant_images", "owner_tie", "owner_frame_y",
                    "owner_frame_width_pct", "owner_frame_height_pct",
                    "owner_adjusted_inset_top", "owner_content_inset_top",
                    "owner_offset_y", "owner_adjustment_behavior",
                    "owner_nested_scrolls", "owner_scroll_enabled",
                    "owner_content_height_pct", "owner_safe_top"]
                for field in numericFields {
                    if let number = row[field] as? NSNumber {
                        fields[field] = number.stringValue
                    }
                }
                for flag in ["scan_capped", "depth_capped", "count_capped"] {
                    if let value = row[flag] as? NSNumber {
                        fields[flag] = value.boolValue ? "true" : "false"
                    }
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_content_geometry_probe", fields: fields)
                if let unsafe = (row["visible_unsafe_controls"] as? NSNumber)?.intValue,
                   let first = (row["first_unsafe_control_y"] as? NSNumber)?.intValue,
                   let sample = (row["sample_index"] as? NSNumber)?.intValue {
                    // P50: deliver existing guest-owned scroll classification to the
                    // host. Counts are anonymous and PID-scoped.
                    let scrolling = (row["unsafe_controls_in_scroll"] as? NSNumber)?.intValue ?? -1
                    let stationary = (row["unsafe_controls_outside_scroll"] as? NSNumber)?.intValue ?? -1
                    onTopRiskMeasured?(pid, unsafe, first, target, sample,
                                       scrolling, stationary)
                }
                continue
            }
            if result == "guest_scroll_target_classifier" {
                // Exclusion counts correspond exactly to the R6P22 predicates.
                // All fields remain anonymous integers; no class names,
                // UI text, guest IDs, URLs, paths or certificates.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "safe_top_pt": String(target)
                ]
                let keys = ["seen", "nested", "not_top_full_width",
                    "not_vertical", "existing_inset", "not_at_top",
                    "busy", "missing_unsafe_descendant", "eligible"]
                for key in keys {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                if let capped = row["scan_budget_exhausted"] as? NSNumber {
                    fields["scan_budget_exhausted"] =
                        capped.boolValue ? "true" : "false"
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_scroll_target_classifier", fields: fields)
                continue
            }
            if result == "guest_local_owner_inset_applied" ||
               result == "guest_local_owner_inset_skipped" {
                // R6P28: report a scroll's *local* top inset, not the
                // guest root's already-valid 62pt safe-area receipt.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "result": result,
                    "safe_top_pt": String(target),
                    "guest_root_top_pt": String(before),
                    "guest_root_after_pt": String(after)
                ]
                for key in ["owner_groups", "owner_dominant_controls",
                            "owner_dominant_images", "owner_frame_y",
                            "owner_safe_top"] {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                if let reason = row["reason"] as? String,
                   ["local_safe_gap_closed", "owner_guard_not_satisfied",
                    "ambiguous_visible_owner",
                    "write_readback_rollback"].contains(reason) {
                    fields["reason"] = reason
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_local_owner_inset_receipt",
                    status: result == "guest_local_owner_inset_applied"
                        ? "success" : "info", fields: fields)
                continue
            }
            if result == "guest_residual_auto_classifier" {
                // R6P30: anonymous counts for P29 owner-gate exclusion,
                // no guest/app identities or view class names.
                var fields: [String: String] = ["process_pid": String(pid)]
                for key in ["owner_groups", "candidate_with_controls",
                    "candidate_frame_matched", "candidate_safe_matched",
                    "candidate_inset_matched", "candidate_content_matched",
                    "candidate_state_matched", "candidate_disabled_scroll",
                    "owner_gate_pass"] {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_residual_auto_classifier", fields: fields)
                continue
            }
            if result == "guest_local_owner_quarantined" {
                // P30 quarantine receipt used to be [REDACTED]: its old
                // string included digits and exceeded the recorder threshold.
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_local_owner_quarantined",
                    fields: ["process_pid": String(pid), "safe_top_pt": String(target)])
                continue
            }
            if result == "guest_always_anchor_readback" {
                var fields: [String: String] = [
                    "process_pid": String(pid), "safe_top_pt": String(target)
                ]
                for key in ["anchor_initial_inset_pt", "anchor_initial_offset_y",
                    "anchor_observed_inset_pt", "anchor_observed_offset_y",
                    "anchor_final_offset_y", "anchor_attempts",
                    "owner_bounds_y", "scene_activation_state"] {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                if let reason = row["reason"] as? String,
                   ["late_anchor_attempted", "initial_anchor_attempted",
                    "anchor_not_attempted"].contains(reason) {
                    fields["reason"] = reason
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_always_anchor_readback", fields: fields)
                continue
            }
            if ["guest_always_owner_retry_scheduled",
                "guest_always_owner_retry_exhausted",
                "guest_always_trial_staged", "guest_always_trial_reverted",
                "guest_always_trial_retained"].contains(result) {
                // R6P31: nonvertical UIKit ALWAYS trial; only late retention
                // is a stable code-path confirmation, never visual/touch proof.
                var fields: [String: String] = [
                    "process_pid": String(pid), "result": result,
                    "safe_top_pt": String(target),
                    "owner_auto_before_pt": String(before),
                    "owner_auto_after_pt": String(after)
                ]
                for key in ["owner_dominant_controls", "visible_unsafe_controls"] {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                if let reason = row["reason"] as? String,
                   ["owner_metrics_not_stable",
                    "strict_owner_unavailable_after_retry",
                    "native_inset_tentative", "no_immediate_geometry_improvement",
                    "late_geometry_not_persistent",
                    "late_native_inset_confirmed"].contains(reason) {
                    fields["reason"] = reason
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_always_inset_receipt",
                    status: result == "guest_always_trial_retained"
                        ? "success" : "info", fields: fields)
                continue
            }
            if ["guest_residual_auto_skipped",
                "guest_residual_auto_reverted",
                "guest_residual_auto_retained"].contains(result) {
                // R6P29: this is UIKit's own automatic adjustment on the
                // residual full-viewport scroll, not another root inset.
                var fields: [String: String] = [
                    "process_pid": String(pid),
                    "result": result,
                    "safe_top_pt": String(target),
                    "owner_auto_before_pt": String(before),
                    "owner_auto_after_pt": String(after)
                ]
                for key in ["owner_dominant_controls", "visible_unsafe_controls"] {
                    if let number = row[key] as? NSNumber {
                        fields[key] = number.stringValue
                    }
                }
                if let reason = row["reason"] as? String,
                   ["multiple_matching_owners", "no_matching_fullscreen_owner",
                    "no_measured_overlap_reduction",
                    "automatic_inset_proved"].contains(reason) {
                    fields["reason"] = reason
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_residual_auto_inset_receipt",
                    status: result == "guest_residual_auto_retained"
                        ? "success" : "info", fields: fields)
                continue
            }
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_root_safearea_receipt",
                status: result == "guest_root_corrected" ? "success"
                    : (result == "guest_root_update_unconfirmed"
                        ? "warning" : "info"),
                fields: ["result": result,
                         "process_pid": String(pid),
                         "safe_top_pt": String(target),
                         "guest_root_top_pt": String(before),
                         "guest_root_after_pt": String(after)])
        }
        if seen.count > 128 { seen.removeAll() }
    }
}

@available(iOS 17.0, *)
@MainActor
final class ScarletFullscreenSceneViewport: UIViewController {
    private weak var stack: ScarletFullscreenSceneStack?
    private var controllers: [String: AppSceneViewController] = [:]
    private var lastBounds: CGSize = .zero
    private var lastRejectedBounds: CGSize?
    private var lastInsetsSignature: String = ""
    // R3: geometry has exactly one writer: FBScene authority in UIKitHooks.m.
    // Swift only observes the hosting owner's UIKit readback.
    private var observedRemoteInsets: [ObjectIdentifier: UIEdgeInsets] = [:]
    private var outsideDismissGesture: UITapGestureRecognizer?
    private var lastHostingOwnerProbes: [ObjectIdentifier: String] = [:]
    private var audioScopedPID: Int32 = 0
    private var hiddenAudioReconcileReported = false
    // P41: one host-owned native scene slot per measured unsafe guest PID.
    private let transparentChrome = UIView(frame: .zero)
    private var chromeEligiblePIDs: Set<Int32> = []
    private var lastChromeTop: CGFloat = -1
    private var chromeAppearanceIsLight: Bool?
    private var chromeAppearancePID: Int32 = 0
    private var chromeStatusBarPreference: UIStatusBarStyle = .default
    // R6P43: host-measured FBScene geometry (not guest UIWindow bounds)
    // and the guest's own UIKit background tone, never the host trait.
    private var chromeVerifiedPIDs: Set<Int32> = []
    // P44: fullscreen scene remains unmodified when a measured native
    // interactive header proves safe at immediate and delayed readback.
    private var chromeHeaderProtectedPIDs: Set<Int32> = []
    private var chromePendingFallbackPIDs: Set<Int32> = []
    // P47: existing 2600ms foreground sample may be the first valid trial;
    // a late PID-scoped readback supersedes the early fallback deadline.
    private var chromeLateTrialPIDs: Set<Int32> = []
    // P48: only a second independently attached *guest-process* measurement
    // can authorize the irreversible host FBScene y62/h894 crop. The P44
    // failure receipt is evidence about a retired trial, not current UI.
    private var chromeFirstUnsafeSampleByPID: [Int32: (first: Int, top: Int)] = [:]
    private var chromeFreshUnsafeProofPIDs: Set<Int32> = []
    // P50: Freshly proven Island risk on a scroll surface cannot justify
    // changing the size of the *whole* FBScene and clipping its scroll area.
    private var chromeFirstScrollRiskByPID: [Int32: (inScroll: Int, outside: Int)] = [:]
    private var chromeScrollCropVetoPIDs: Set<Int32> = []
    private var chromeSurfaceToneByPID: [Int32: Int] = [:]

    override var prefersStatusBarHidden: Bool { false }
    override var childForStatusBarHidden: UIViewController? { nil }
    override var preferredStatusBarStyle: UIStatusBarStyle {
        chromeStatusBarPreference
    }
    override var childForStatusBarStyle: UIViewController? { nil }

    // R6P43: the host trait in signed P42 reports .dark even while
    // Instagram's guest UI is white. Only the *guest process* can classify
    // its own visible UIKit opaque background without screenshots/text.
    // 0=unknown, 1=light, 2=dark. Unknown is not an app-color guess.
    private func applyNativeChromeAppearance(
        for guest: AppSceneViewController, scene: UIWindowScene) {
        let tone = chromeSurfaceToneByPID[guest.pid] ?? 0
        guard tone == 1 || tone == 2 else {
            if chromeAppearancePID != guest.pid || chromeAppearanceIsLight != nil {
                // Never carry guest A's black color into an unmeasured B.
                chromeAppearancePID = guest.pid
                chromeAppearanceIsLight = nil
                view.backgroundColor = .systemBackground
                chromeStatusBarPreference = .default
                setNeedsStatusBarAppearanceUpdate()
                view.window?.rootViewController?.setNeedsStatusBarAppearanceUpdate()
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_appearance_unresolved",
                    fields: ["process_pid": String(guest.pid),
                             "result": "guest_background_not_observable",
                             "surface_tone": String(tone)])
            }
            return
        }
        let isLight = tone == 1
        guard chromeAppearanceIsLight != isLight ||
              chromeAppearancePID != guest.pid else { return }
        chromeAppearancePID = guest.pid
        chromeAppearanceIsLight = isLight
        view.backgroundColor = isLight ? .white : .black
        chromeStatusBarPreference = isLight ? .darkContent : .lightContent
        setNeedsStatusBarAppearanceUpdate()
        view.window?.rootViewController?.setNeedsStatusBarAppearanceUpdate()
        ScarletDiagnosticRecorder.shared.record(
            "layout", "guest_chrome_appearance_applied",
            fields: ["process_pid": String(guest.pid),
                     "result": isLight ? "light_guest_backdrop"
                                         : "dark_guest_backdrop",
                     "surface_tone": String(tone),
                     "chrome_dark_status_text": isLight ? "true" : "false",
                     "slot_top_pt": String(Int(chromeTop(in: scene)))])
        DispatchQueue.main.async { [weak self, weak scene] in
            guard let self, self.view.window?.windowScene === scene else {
                return
            }
            let actual = scene?.statusBarManager?.statusBarStyle.rawValue ?? -1
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_chrome_status_style_readback",
                fields: ["result": "uikit_status_bar_observed",
                         "status_hidden": scene?.statusBarManager?.isStatusBarHidden == true
                             ? "true" : "false",
                         "status_style_raw": String(Int(actual)),
                         "chrome_dark_status_text": self.chromeAppearanceIsLight == true
                             ? "true" : "false"])
        }
    }

    private func onGuestSurfaceTone(pid: Int32, tone: Int) {
        guard controllers.values.contains(where: { $0.pid == pid }),
              (0...2).contains(tone) else { return }
        chromeSurfaceToneByPID[pid] = tone
        if let active = stack?.activeID, stack?.isVisible == true,
           let guest = controllers[active], guest.pid == pid,
           let scene = view.window?.windowScene {
            applyNativeChromeAppearance(for: guest, scene: scene)
            ScarletFullscreenGuestTabInstaller.updateResidentStatusBar(
                chromeStatusBarPreference, scene: scene)
            stack?.syncKeyHostStatusBarTone(pid: pid, tone: tone, scene: scene)
        }
    }

    func syncKeyHostStatusBarForActiveGuest() {
        guard let stack, stack.isVisible,
              let activeID = stack.activeID,
              let guest = controllers[activeID], guest.pid > 0,
              let scene = view.window?.windowScene else { return }
        stack.syncKeyHostStatusBarTone(
            pid: guest.pid, tone: chromeSurfaceToneByPID[guest.pid] ?? 0,
            scene: scene)
    }

    private func publishNativeChromeVerifiedPIDs(_ scene: UIWindowScene) {
        let verified: [Int] = controllers.values.compactMap { vc in
            let pid = vc.pid
            return pid > 0 && vc.isAppRunning &&
                chromeVerifiedPIDs.contains(pid) &&
                chromeEligiblePIDs.contains(pid) &&
                vc.scarletNativeTransparentChromeSlot &&
                chromeTop(in: scene) > 0 ? Int(pid) : nil
        }
        LCUtils.appGroupUserDefault.set(verified,
            forKey: "Scarlet.Guest.TransparentChromeVerifiedPIDs.V1")
    }

    // R6P43: P42 iPhone showed remote contentView.height 894, even though
    // the guest's separate UIWindow did not satisfy P41's height guard.
    // Publish PID verification ONLY after reading the actual remote view.
    private func verifyNativeChromeRemoteSlot(
        controller: AppSceneViewController, scene: UIWindowScene,
        expected: CGRect, attempt: Int = 0) {
        DispatchQueue.main.asyncAfter(
            deadline: .now() + (attempt == 0 ? 0.20 : 0.45)) {
            [weak self, weak controller, weak scene] in
            guard let self, let vc = controller, let realScene = scene,
                  self.view.window?.windowScene === realScene,
                  vc.pid > 0, vc.isAppRunning,
                  self.chromeEligiblePIDs.contains(vc.pid),
                  vc.scarletNativeTransparentChromeSlot,
                  self.chromeTop(in: realScene) > 0 else { return }
            let content = vc.contentView?.bounds.height ?? -1
            let rect = vc.view.frame
            let correct = abs(rect.minY - expected.minY) < 2 &&
                abs(rect.width - expected.width) < 2 &&
                abs(rect.height - expected.height) < 2 &&
                abs(content - expected.height) < 2
            if correct {
                if self.chromeVerifiedPIDs.insert(vc.pid).inserted {
                    self.publishNativeChromeVerifiedPIDs(realScene)
                    ScarletDiagnosticRecorder.shared.record(
                        "layout", "guest_chrome_remote_slot_verified",
                        fields: ["process_pid": String(vc.pid),
                                 "result": "fbscene_content_matches_host_slot",
                                 "slot_y_pt": String(Int(rect.minY)),
                                 "slot_height_pt": String(Int(rect.height)),
                                 "remote_content_height_pt": String(Int(content))])
                }
            } else if attempt < 4 {
                self.verifyNativeChromeRemoteSlot(
                    controller: vc, scene: realScene,
                    expected: expected, attempt: attempt + 1)
            } else {
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_remote_slot_unverified",
                    status: "warning",
                    fields: ["process_pid": String(vc.pid),
                             "result": "remote_scene_size_not_confirmed",
                             "slot_y_pt": String(Int(rect.minY)),
                             "slot_height_pt": String(Int(rect.height)),
                             "remote_content_height_pt": String(Int(content))])
            }
        }
    }

    private func chromeTop(in scene: UIWindowScene) -> CGFloat {
        guard scene.interfaceOrientation.isPortrait else { return 0 }
        let value = resolvedHostInsets(scene).top
        return value >= 20 && value <= 130 ? value : 0
    }

    private func contentSlot(in scene: UIWindowScene, reserved: Bool) -> CGRect {
        let full = view.bounds
        let top = reserved ? chromeTop(in: scene) : 0
        return CGRect(x: full.minX, y: full.minY + top,
                      width: full.width, height: full.height - top)
    }

    private func updateNativeChromeSlots(_ scene: UIWindowScene) {
        // Publish the EXACT active PID allowlist; a global chrome 62pt
        // flag caused P40's fallback root repair on return from Home.
        let pids: [Int] = controllers.values.compactMap { vc in
            vc.pid > 0 && vc.isAppRunning && chromeEligiblePIDs.contains(vc.pid)
                ? Int(vc.pid) : nil
        }
        LCUtils.appGroupUserDefault.set(pids,
            forKey: "Scarlet.Guest.TransparentChromeActivePIDs.V1")
        LCUtils.appGroupUserDefault.set(Double(chromeTop(in: scene)),
            forKey: "Scarlet.Guest.TransparentChromeTop.V1")
        publishNativeChromeVerifiedPIDs(scene)
        for vc in controllers.values {
            let reserved = vc.pid > 0 && chromeEligiblePIDs.contains(vc.pid) &&
                chromeTop(in: scene) > 0
            let rect = contentSlot(in: scene, reserved: reserved)
            if vc.scarletNativeTransparentChromeSlot != reserved ||
                abs(vc.view.frame.minY - rect.minY) > 0.5 ||
                abs(vc.view.frame.height - rect.height) > 0.5 ||
                abs(vc.view.frame.width - rect.width) > 0.5 {
                if !reserved { chromeVerifiedPIDs.remove(vc.pid) }
                vc.scarletApplyNativeTransparentChromeSlot(reserved)
                vc.view.frame = rect
                let orientation = scene.interfaceOrientation
                vc.updateSettings { settings in
                    guard let settings else { return }
                    settings.setFrame(rect)
                    settings.setInterfaceOrientation(orientation)
                }
                if reserved {
                    verifyNativeChromeRemoteSlot(
                        controller: vc, scene: scene, expected: rect)
                } else {
                    publishNativeChromeVerifiedPIDs(scene)
                }
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_adaptive_slot_applied",
                    fields: ["process_pid": String(vc.pid),
                             "result": reserved ? "measured_unsafe_owner"
                                                  : "native_fullscreen_preserved",
                             "slot_y_pt": String(Int(rect.minY)),
                             "slot_height_pt": String(Int(rect.height)),
                             "scale_milli": "1000"])
            }
        }
        let pid = stack?.activeID.flatMap { controllers[$0]?.pid }
        let active = stack?.isVisible == true && pid.map {
            chromeEligiblePIDs.contains($0)
        } == true
        let top = active ? chromeTop(in: scene) : 0
        if stack?.isVisible == true, let id = stack?.activeID,
           let guest = controllers[id] {
            // Safe guests also need their own backdrop: P42 retained the
            // previous guest's black host background across A->B.
            applyNativeChromeAppearance(for: guest, scene: scene)
            ScarletFullscreenGuestTabInstaller.updateResidentStatusBar(
                chromeStatusBarPreference, scene: scene)
            stack?.syncKeyHostStatusBarTone(
                pid: guest.pid, tone: chromeSurfaceToneByPID[guest.pid] ?? 0,
                scene: scene)
        }
        transparentChrome.frame = CGRect(x: 0,y: 0,
                                         width: view.bounds.width,height: top)
        transparentChrome.isHidden = top < 1
        if abs(lastChromeTop - top) > 0.5 {
            lastChromeTop = top
            ScarletDiagnosticRecorder.shared.record(
                "layout", "resident_transparent_chrome_slot",
                fields: ["result": active ? "selected_risky_guest_only"
                                           : "native_unshifted_guest",
                         "slot_top_pt": String(Int(top)),
                         "host_width_pt": String(Int(view.bounds.width)),
                         "host_height_pt": String(Int(view.bounds.height)),
                         "chrome_touches": "false", "scale_milli": "1000"])
        }
    }

    private func onUnsafeGuestControls(pid: Int32, unsafe: Int,
                                        first: Int, top: Int, sample: Int,
                                        inScroll: Int, outsideScroll: Int) {
        guard sample == 650 || sample == 2600 else { return }
        guard unsafe >= 3 && top >= 20 && top <= 130,
              first >= -3 && first < top - 15,
              !chromeEligiblePIDs.contains(pid),
              controllers.values.contains(where: {
                  $0.pid == pid && $0.isAppRunning
              }) else { return }
        guard !chromeHeaderProtectedPIDs.contains(pid) else { return }
        if sample == 650 {
            chromeFirstUnsafeSampleByPID[pid] = (first: first, top: top)
            chromeFirstScrollRiskByPID[pid] =
                (inScroll: inScroll, outside: outsideScroll)
            // Give the independently measured guest header a bounded native
            // pass/revert window. Do not physically crop its remote FBScene
            // until a failed/absent result is observed.
            guard chromePendingFallbackPIDs.insert(pid).inserted else { return }
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_header_fullscreen_trial_pending",
                fields: ["process_pid": String(pid),
                         "result": "retain_full_native_fbscene_until_proven"])
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) {
                [weak self] in
                guard let self,
                      !self.chromeLateTrialPIDs.contains(pid),
                      self.chromePendingFallbackPIDs.remove(pid) != nil,
                      !self.chromeHeaderProtectedPIDs.contains(pid) else { return }
                self.applyP43FallbackChrome(pid: pid,
                    unsafe: unsafe, first: first, top: top, sample: sample)
            }
        } else {
            // P48: require a second CURRENT attached guest root report.
            // P47 cropped first, then its 2600ms sample found root.safeTop=0
            // (safe_unready): the crop had erased its own proof opportunity.
            // Merely waiting for a timer does not prove that the unsafe
            // header still exists. Do not promote an old failed trial.
            guard let initial = chromeFirstUnsafeSampleByPID[pid],
                  abs(initial.top - top) <= 3,
                  abs(initial.first - first) <= 16 else {
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_fresh_risk_proof_missing",
                    fields: ["process_pid": String(pid),
                             "sample_index": String(sample),
                             "result": "full_fbscene_preserved_no_matching_root"])
                return
            }
            // P50: two independent guest snapshots can prove the risk is
            // real, but a risk INSIDE scrolling content cannot authorize
            // the old y62/h894 whole-scene crop. Leave the real 956pt FBScene.
            if let scroll = chromeFirstScrollRiskByPID[pid],
               scroll.inScroll > 0, inScroll > 0 {
                chromeScrollCropVetoPIDs.insert(pid)
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_chrome_scroll_crop_veto_armed",
                    fields: ["process_pid": String(pid),
                             "sample_index": String(sample),
                             "visible_unsafe_controls": String(unsafe),
                             "unsafe_controls_in_scroll": String(inScroll),
                             "unsafe_controls_outside_scroll": String(outsideScroll),
                             "result": "scrolling_content_needs_full_remote_frame"])
            }
            chromeFreshUnsafeProofPIDs.insert(pid)
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_chrome_fresh_risk_proof_confirmed",
                fields: ["process_pid": String(pid),
                         "sample_index": String(sample),
                         "visible_unsafe_controls": String(unsafe),
                         "first_unsafe_control_y": String(first),
                         "safe_top_pt": String(top)])
            // Late native root measurement is only evidence of a real
            // foreground guest. Preserve fullscreen until its own 220ms+
            // 1050ms native readback can complete. The first timer is
            // ignored for this PID, not for any other guest.
            guard chromeLateTrialPIDs.insert(pid).inserted else { return }
            chromePendingFallbackPIDs.insert(pid)
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_header_foreground_retry_window",
                fields: ["process_pid": String(pid),
                         "sample_index": String(sample),
                         "result": "second_attached_sample_await_native_readback"])
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.7) {
                [weak self] in
                guard let self,
                      self.chromeLateTrialPIDs.remove(pid) != nil,
                      self.chromePendingFallbackPIDs.remove(pid) != nil,
                      !self.chromeHeaderProtectedPIDs.contains(pid) else { return }
                self.applyP43FallbackChrome(pid: pid,
                    unsafe: unsafe, first: first, top: top, sample: sample)
            }
        }
    }

    private func onNativeHeaderTransform(pid: Int32, retained: Bool) {
        guard controllers.values.contains(where: {
            $0.pid == pid && $0.isAppRunning
        }) else { return }
        chromePendingFallbackPIDs.remove(pid)
        chromeLateTrialPIDs.remove(pid)
        if retained {
            chromeHeaderProtectedPIDs.insert(pid)
            // A delayed receipt is possible. Do not strand the guest in
            // the old cropped native slot after its header passed.
            chromeEligiblePIDs.remove(pid)
            chromeVerifiedPIDs.remove(pid)
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_fullscreen_header_verified",
                fields: ["process_pid": String(pid),
                         "result": "full_fbscene_and_native_header"])
            if let scene = view.window?.windowScene {
                updateNativeChromeSlots(scene)
                synchronizeAttachedGuestSafeAreas(scene)
            }
        } else {
            chromeHeaderProtectedPIDs.remove(pid)
            applyP43FallbackChrome(pid: pid,
                unsafe: 3, first: 0, top: view.window?.windowScene.map { Int(chromeTop(in: $0)) } ?? 0,
                sample: 650)
        }
    }

    private func applyP43FallbackChrome(pid: Int32, unsafe: Int,
                                       first: Int, top: Int, sample: Int) {
        guard !chromeEligiblePIDs.contains(pid),
              !chromeHeaderProtectedPIDs.contains(pid),
              controllers.values.contains(where: {
                  $0.pid == pid && $0.isAppRunning
              }) else { return }
        // P48 independent crop authorization: the P44 failure/timeout is
        // never proof of *current* Island overlap. Only an independently
        // corroborated sample from the same still-running PID qualifies.
        guard chromeFreshUnsafeProofPIDs.contains(pid) else {
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_chrome_stale_crop_withheld",
                fields: ["process_pid": String(pid),
                         "sample_index": String(sample),
                         "result": "full_fbscene_preserved_until_live_guest_proof"])
            return
        }
        // P50: the two attached observations identify scrolling UIKit
        // content, not a stationary header. Shrinking the entire remote
        // FBScene by 62pt creates the hard clipping boundary reported on
        // the iPhone, regardless of how real that top risk is.
        guard !chromeScrollCropVetoPIDs.contains(pid) else {
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_chrome_scroll_surface_crop_withheld",
                fields: ["process_pid": String(pid),
                         "sample_index": String(sample),
                         "result": "full_fbscene_preserved_scroll_owner"])
            return
        }
        chromeEligiblePIDs.insert(pid)
        ScarletDiagnosticRecorder.shared.record(
            "layout", "guest_chrome_adaptive_qualified",
            fields: ["process_pid": String(pid),
                     "visible_unsafe_controls": String(unsafe),
                     "first_unsafe_control_y": String(first),
                     "safe_top_pt": String(top),
                     "sample_index": String(sample),
                     "result": "p43_fallback_after_header_pilot"])
        if let scene = view.window?.windowScene {
            updateNativeChromeSlots(scene)
            synchronizeAttachedGuestSafeAreas(scene)
        }
    }

    func setResidentOutsideDismissEnabled(_ enabled: Bool) {
        guard let tap = outsideDismissGesture else { return }
        if tap.isEnabled == enabled { return }
        tap.isEnabled = enabled
        // Only while the panel is expanded do outside guest touches belong
        // to the modal overlay; the guest receives normal input otherwise.
        tap.cancelsTouchesInView = enabled
        tap.delaysTouchesEnded = enabled
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_host_outside_gesture_state",
            fields: ["result": enabled ? "expanded_host_receives_taps"
                                         : "collapsed_guest_receives_taps",
                     "overlay_expanded": enabled ? "true" : "false"])
    }

    @objc private func didTapResidentBackground(_ tap: UITapGestureRecognizer) {
        guard tap.state == .ended, let overlay = stack?.activeOutsideOverlay
        else { return }
        let location = view.convert(tap.location(in: view), to: overlay)
        guard !overlay.panelRect.insetBy(dx: -3, dy: -3).contains(location)
        else { return }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_host_background_tap_received",
            fields: ["result": "original_R5_close_requested",
                     "overlay_expanded": "true"])
        overlay.dismissState?.requestClose()
    }

    // V48-R5: iOS 27 finishes attaching the remote _UISceneHostingController
    // AFTER appSceneVCWillActivateScene. The previous initial/FBScene hooks
    // alone did not synchronize a safe inset once the real UIWindow existed.
    // Keep the guest's full original pixel viewport and update its safe
    // CONTENT REGION; no frame transform, inset overlay or guest resizing.
    private func resolvedHostInsets(_ scene: UIWindowScene) -> UIEdgeInsets {
        // V48-R6: creating the switcher overlay UIWindow transiently makes
        // `windows.first(normal)`/`view.safeAreaInsets` report a 0pt top.
        // Device log: 62 -> 0 -> 62 within 0.5ms, flagged as
        // island_overlap_suspected. A 0pt top applied to the guest puts its
        // top bar under Dynamic Island, so resolve against the window that
        // actually contains this viewport and never downgrade a positive top.
        var safe = scene.windows.first(where: {
            $0.windowLevel == .normal && !$0.isHidden
        })?.safeAreaInsets ?? view.window?.safeAreaInsets ?? .zero
        if let host = view.window?.safeAreaInsets {
            safe.top = max(safe.top, host.top)
            safe.bottom = max(safe.bottom, host.bottom)
        }
        if scene.interfaceOrientation.isPortrait {
            let statusBottom = scene.statusBarManager?.statusBarFrame.maxY ?? 0
            safe.top = max(safe.top, statusBottom)
        }
        return safe
    }

    private func synchronizeAttachedGuestSafeAreas(_ scene: UIWindowScene) {
        let hostSafe = resolvedHostInsets(scene)
        guard hostSafe.top > 0 || hostSafe.bottom > 0 ||
              hostSafe.left > 0 || hostSafe.right > 0 else {
            ScarletDiagnosticRecorder.shared.record(
                "layout", "attached_guest_safearea_unavailable",
                status: "warning",
                fields: ["reason": "host_and_statusbar_zero"])
            return
        }
        for controller in controllers.values where controller.scarletNativeFullscreenSlot {
            let key = ObjectIdentifier(controller)
            // Never let a transient resolver zero erase a real island inset.
            var safe = hostSafe
            if scene.interfaceOrientation.isPortrait, safe.top < 2,
               let previous = observedRemoteInsets[key], previous.top >= 18 {
                safe.top = previous.top
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "guest_zero_safe_top_rejected",
                    status: "warning",
                    fields: ["result": "kept_previous_positive_top",
                             "rejected_top_pt": "0",
                             "kept_top_pt": String(Int(previous.top))])
            }
            // Check the *nested* UIKit hosting scene on EVERY reconcile.
            // The initial FBScene settings callback can arrive before
            // _UISceneHostingController.sceneViewController even exists.
            // Cache outer FBScene settings independently from this owner.
            let owner = controller.scarletApplyHostingContentSafeArea(safe)
            let ownerSignature = owner.map { String(Int($0.doubleValue)) } ?? "unavailable"
            if lastHostingOwnerProbes[key] != ownerSignature {
                lastHostingOwnerProbes[key] = ownerSignature
                ScarletDiagnosticRecorder.shared.record(
                    "layout", "native_hosting_safearea_owner_readback",
                    status: owner == nil ? "warning" : "info",
                    fields: ["result": owner == nil ? "hosting_owner_unavailable"
                                                  : "hosting_owner_available",
                             "safe_top_pt": String(Int(safe.top)),
                             "guest_safe_top_pt": String(Int(controller.view.safeAreaInsets.top)),
                             "host_owner_top_pt": String(Int(owner?.doubleValue ?? -1))])
                if controller.scarletNativeTransparentChromeSlot {
                    // Read back both rectangles. Requesting FBScene geometry
                    // is not proof it became the actual guest content frame.
                    ScarletDiagnosticRecorder.shared.record(
                        "layout", "guest_chrome_native_frame_readback",
                        fields: ["result": owner == nil
                                     ? "hosting_pending" : "hosting_attached",
                                 "host_safe_top_pt": String(Int(safe.top)),
                                 "slot_y_pt": String(Int(controller.view.frame.minY)),
                                 "slot_height_pt": String(Int(controller.view.bounds.height)),
                                 "remote_content_height_pt": String(Int(controller.contentView?.bounds.height ?? -1)),
                                 "guest_root_safe_top_pt": String(Int(controller.view.safeAreaInsets.top)),
                                 "hosting_safe_top_pt": String(Int(owner?.doubleValue ?? -1))])
                }
            }
            // The R2 device trace had a 62pt owner readback but guest UI
            // still overlapped the island. Remove repeated ancestor writes:
            // they can race asynchronous FBScene update callbacks.
            if let previous = observedRemoteInsets[key],
               UIEdgeInsetsEqualToEdgeInsets(previous, safe) { continue }
            observedRemoteInsets[key] = safe
            ScarletDiagnosticRecorder.shared.record(
                "layout", "guest_geometry_authority_observed",
                fields: ["result": "read_only_host_observer",
                         "safe_top_pt": String(Int(safe.top)),
                         "safe_bottom_pt": String(Int(safe.bottom)),
                         "guest_safe_top_pt": String(Int(controller.view.safeAreaInsets.top)),
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
        // R6P15: the host alone knows the normal-window island inset before
        // remote LiveProcess UIKit starts. Share only this anonymous geometry
        // as a fallback for the guest's OWN root-controller safe-area check.
        // Never publish the transient viewport zero or an overlay window.
        if s?.interfaceOrientation.isPortrait == true,
           n.top >= 20, n.top <= 130 {
            let key = "Scarlet.Guest.PortraitSafeTop.V1"
            let previous = LCUtils.appGroupUserDefault.double(forKey: key)
            if abs(previous - Double(n.top)) >= 1 {
                LCUtils.appGroupUserDefault.set(Double(n.top), forKey: key)
            }
        }
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
        // R6P42: never expose a forced black background through a clear
        // chrome slot while the remote app uses a light interface.
        view.backgroundColor = .systemBackground
        view.clipsToBounds = false
        transparentChrome.backgroundColor = .clear
        transparentChrome.isUserInteractionEnabled = false
        transparentChrome.isAccessibilityElement = false
        transparentChrome.autoresizingMask = [.flexibleWidth]
        view.insertSubview(transparentChrome, at: 0)
        LCUtils.appGroupUserDefault.set([Int](),
            forKey: "Scarlet.Guest.TransparentChromeActivePIDs.V1")
        LCUtils.appGroupUserDefault.set([Int](),
            forKey: "Scarlet.Guest.TransparentChromeVerifiedPIDs.V1")
        ScarletGuestIslandReceiptObserver.shared.onSurfaceToneMeasured = {
            [weak self] pid, tone in
            self?.onGuestSurfaceTone(pid: pid, tone: tone)
        }
        ScarletGuestIslandReceiptObserver.shared.onTopRiskMeasured = {
            [weak self] pid, unsafe, first, top, sample, inScroll, outside in
            guard let self else { return }
            self.stack?.reportNativeStatusBarCollisionRisk(
                pid: pid, unsafe: unsafe, sample: sample,
                scene: self.view.window?.windowScene)
            self.onUnsafeGuestControls(pid: pid, unsafe: unsafe,
                first: first, top: top, sample: sample,
                inScroll: inScroll, outsideScroll: outside)
        }
        ScarletGuestIslandReceiptObserver.shared.onHeaderTransformVerified = {
            [weak self] pid, retained in
            self?.onNativeHeaderTransform(pid: pid, retained: retained)
        }
        let outside = UITapGestureRecognizer(target: self,
            action: #selector(didTapResidentBackground(_:)))
        outside.isEnabled = false
        outside.cancelsTouchesInView = true
        outside.delaysTouchesEnded = true
        view.addGestureRecognizer(outside)
        outsideDismissGesture = outside
        NotificationCenter.default.addObserver(
            self, selector: #selector(onHostAppBecameActive),
            name: UIApplication.didBecomeActiveNotification, object: nil)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "resident_host_background_gesture_installed",
            fields: ["result": "native_viewport_ancestor_recognizer"])
    }

    @objc private func onHostAppBecameActive() {
        stack?.restoreForegroundOnHostActive()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        stack?.attach(self)
        stack?.restoreForegroundOnHostActive()
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
            ScarletDiagnosticRecorder.shared.record(
                "layout", "fullscreen_scene_geometry_applied",
                fields: ["width_pt": String(Int(actual.width)),
                         "height_pt": String(Int(actual.height)),
                         "reason": "verified_native_adaptive_chrome_viewport"])
        }
        updateNativeChromeSlots(scene)
        reconcile()
        synchronizeAttachedGuestSafeAreas(scene)
    }

    func isAlive(folder: String) -> Bool {
        controllers[folder]?.isAppRunning == true
    }

    func isRemoteReady(folder: String) -> Bool {
        controllers[folder]?.scarletRemoteContentReady() == true
    }

    func refreshExistingRemoteScene(folder: String) -> Bool {
        guard let owner = controllers[folder], owner.isAppRunning,
              owner.scarletRemoteContentReady() else { return false }
        // This exact original LC API reasserts foreground after the user
        // returns from Home without touching guest process/data/signature.
        owner.setBackgroundNotificationEnabled(false)
        owner.view.setNeedsLayout()
        owner.contentView?.setNeedsLayout()
        return true
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
        if old.pid == audioScopedPID { audioScopedPID = 0 }
        controllers.removeValue(forKey: folder)
        observedRemoteInsets.removeValue(forKey: ObjectIdentifier(old))
        lastHostingOwnerProbes.removeValue(forKey: ObjectIdentifier(old))
        chromeEligiblePIDs.remove(old.pid)
        chromeVerifiedPIDs.remove(old.pid)
        chromeHeaderProtectedPIDs.remove(old.pid)
        chromePendingFallbackPIDs.remove(old.pid)
        chromeLateTrialPIDs.remove(old.pid)
        chromeFirstUnsafeSampleByPID.removeValue(forKey: old.pid)
        chromeFreshUnsafeProofPIDs.remove(old.pid)
        chromeFirstScrollRiskByPID.removeValue(forKey: old.pid)
        chromeScrollCropVetoPIDs.remove(old.pid)
        chromeSurfaceToneByPID.removeValue(forKey: old.pid)
        stack?.clearNativeStatusBarCollisionRisk(pid: old.pid)
        if let scene = view.window?.windowScene {
            updateNativeChromeSlots(scene)
        }
        return true
    }

    /// V48-R6: cross-process audio scope. Each guest lives in its own
    /// LiveProcess extension, so only that process can deactivate its own
    /// AVAudioSession. The guest hook registers `com.scarlet.guest.audio.*`
    /// for its own PID; this posts to that exact PID and nothing else.
    private func postGuestAudioScope(_ action: String, pid: Int32) {
        guard pid > 0 else { return }
        // Subscribe before dispatch: the guest may acknowledge immediately.
        ScarletGuestAudioReceiptObserver.shared.observe(pid: pid)
        let name = "com.scarlet.guest.audio.\(action).\(pid)"
        CFNotificationCenterPostNotification(
            CFNotificationCenterGetDarwinNotifyCenter(),
            CFNotificationName(name as CFString), nil, nil, true)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "guest_audio_scope_applied",
            fields: ["action": action, "process_pid": String(pid),
                     "result": "posted_not_device_verified"])
    }

    /// R6P24: each LiveProcess owns its own UIKit first responder. Request
    /// keyboard dismissal for the outgoing PID before showing the next one.
    /// Do not use host.view.endEditing(), which cannot reach guest UIKit.
    private func dismissGuestKeyboard(pid: Int32) {
        guard pid > 0 else { return }
        ScarletGuestKeyboardReceiptObserver.shared.observe(pid: pid)
        let name = "com.scarlet.guest.keyboard.dismiss.\(pid)"
        CFNotificationCenterPostNotification(
            CFNotificationCenterGetDarwinNotifyCenter(),
            CFNotificationName(name as CFString), nil, nil, true)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "guest_keyboard_dismiss_requested",
            fields: ["process_pid": String(pid),
                     "scope": "outgoing_guest", "result": "posted_not_verified"])
    }

    // R6.1: an audio-scoped PID can no longer stay selected when the host
    // Home UI is visible. Clearing it also guarantees a resume signal when
    // the SAME retained guest returns (without requiring PID recreation).
    func pauseAllResidentAudioOnHome() {
        for vc in controllers.values where vc.pid > 0 && vc.isAppRunning {
            dismissGuestKeyboard(pid: vc.pid)
            postGuestAudioScope("pause", pid: vc.pid)
        }
        audioScopedPID = 0
    }

    func select(folder: String) -> Bool {
        // R6P3: SwiftUI can call reconcile() after goHome() has paused every
        // retained LiveProcess. Never let a hidden guest receive resume or
        // foreground notifications merely because its view is still mounted.
        // Only explicit in-app activation makes stack.isVisible true.
        guard stack?.isVisible == true else { return false }
        guard let target = controllers[folder],
              target.isAppRunning,
              target.scarletRemoteContentReady() else { return false }
        if audioScopedPID != target.pid {
            // Send on the outgoing LiveProcess before its surface is hidden.
            // This cannot erase input data or steal the new app's focus.
            for (key, vc) in controllers where key != folder &&
                    vc.pid > 0 && vc.isAppRunning {
                dismissGuestKeyboard(pid: vc.pid)
            }
        }
        for (key, vc) in controllers {
            // A hidden scene stays ATTACHED and its NSExtension request
            // continues. No app process kills or UIKit view detachment.
            vc.view.layer.opacity = key == folder ? 1 : 0
            vc.view.isUserInteractionEnabled = key == folder
        }
        view.bringSubviewToFront(target.view)
        if let scene = view.window?.windowScene {
            updateNativeChromeSlots(scene)
        }
        // V48-R6: every resident guest is a separate LiveProcess with its own
        // AVAudioSession, so the host's session cannot silence another
        // process. Tell the exact guest PIDs to pause/resume their own
        // session; processes, RAM and scenes stay untouched.
        if audioScopedPID != target.pid {
            for (key, vc) in controllers where key != folder {
                postGuestAudioScope("pause", pid: vc.pid)
            }
            postGuestAudioScope("resume", pid: target.pid)
            audioScopedPID = target.pid
        }
        // One-shot foreground request after the real remote surface is
        // attached. Never restart or re-sign an existing guest process.
        let foregroundRequested = target.scarletEnsureRemoteForeground()
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_scene_remote_foreground_confirmed",
            fields: ["result": foregroundRequested
                         ? "native_one_shot_request_sent" : "not_ready",
                     "process_pid": String(target.pid)])
        if let scene = view.window?.windowScene {
            synchronizeAttachedGuestSafeAreas(scene)
        }
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
            // R6P9: original LC init() starts NSExtension XPC before this
            // child belongs to any UIWindow. The device observed initial
            // host owner unavailable, then 62pt after remote attachment.
            // Request an *unstarted* VC; this is resident-only and does not
            // affect original/classic LiveContainer or signed guest bundles.
            guard let vc = AppSceneViewController(
                bundleId: slot.id, dataUUID: slot.dataUUID,
                delegate: stack, scarletDeferExtensionRequest: true) else {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_scene_vc_unavailable",
                    status: "error")
                continue
            }
            vc.scarletNativeFullscreenSlot = true
            vc.scarletNativeTransparentChromeSlot = false
            vc.scaleRatio = 1
            vc.view.frame = contentSlot(in: scene, reserved: false)
            // Parent autoresize must never expand a reserved 894pt scene
            // back to 956pt while the guest is hidden.
            vc.view.autoresizingMask = []
            // Do not show an uninitialized LiveProcess surface (black flash).
            // The prior guest remains fully attached, visible and touchable.
            vc.view.layer.opacity = 0
            vc.view.isUserInteractionEnabled = false
            addChild(vc)
            view.addSubview(vc.view)
            vc.didMove(toParent: self)
            controllers[slot.id] = vc
        }
        // The actual host/window/parent relation now exists. Start each
        // resident extension at most once only AFTER attaching its VC.
        // Reconcile is already called on viewDidAppear, verified full-screen
        // layout and SwiftUI updates; no polling timer, fixed status-bar
        // offsets, or process recycling.
        for (folder, vc) in controllers
            where stack.slots.contains(where: { $0.id == folder }) {
            if vc.scarletBeginDeferredExtensionIfHosted() {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_scene_xpc_started_after_host_attach",
                    fields: ["result": "window_scene_and_parent_present",
                             "stage": "before_extension_request"])
            }
        }
        if let active = stack.activeID,
           stack.slots.contains(where: { $0.id == active && $0.pid > 0 }) {
            if stack.isVisible {
                hiddenAudioReconcileReported = false
                _ = select(folder: active)
            } else if !hiddenAudioReconcileReported {
                hiddenAudioReconcileReported = true
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "home_audio_reactivation_suppressed",
                    fields: ["reason": "hidden_resident_viewport",
                             "process_retained": "true"])
            }
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

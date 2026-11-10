// V23: explicit host/guest work-session switcher. Never infer that an
// installed or previously launched app is still resident in memory.
// Only launched apps from the CURRENT session appear. Old ledgers remain
// untouched for rollback, and guest data/certificates are not modified.
import Foundation
import CoreFoundation

@available(iOS 17.0, *)
@MainActor
enum ScarletGuestSessionLedger {
    struct Entry: Codable, Equatable {
        let folder: String
        let lastOpened: Date
        let title: String?
        let dataUUID: String?
    }
    // Preserve V14 and V19 keys for rollback; no migrating stale entries.
    // Legacy key: Scarlet.Guest.RecentSessions.V14
    // Legacy key: Scarlet.Guest.ActiveSwitcherSession.V19
    private static let key = "Scarlet.Guest.ActiveSwitcherSession.V23"
    private static let hostReturnKey = "Scarlet.Guest.HostReturnTicket.V23"
    private static let guestBootMarkerKey = "Scarlet.Guest.LaunchBootEpoch.V33"
    private static let maxItems = 8
    private static let returnTicketValidity: TimeInterval = 120
    private static var hasEnteredHostWorkSession = false

    private static var store: UserDefaults { LCUtils.appGroupUserDefault }

    // A->the Scarlet app list->B is a continuation of the same session.
    // Mark the return only when the guest explicitly requests that route.
    static func beginReturnToHost() {
        store.set(Date(), forKey: hostReturnKey)
    }

    static func cancelReturnToHost() {
        store.removeObject(forKey: hostReturnKey)
    }

    // Called at the *first* appearance of the Scarlet host, not at every
    // tab change or guest switch. A cold host entry starts with an empty
    // switcher; a recent explicit guest->host return retains A so launching
    // B shows A,B. Never touch actual guest app/container data.
    static func prepareForHostAppearance() {
        let ticket = store.object(forKey: hostReturnKey) as? Date
        store.removeObject(forKey: hostReturnKey)
        guard !hasEnteredHostWorkSession else { return }
        hasEnteredHostWorkSession = true
        let age = ticket.map { Date().timeIntervalSince($0) }
        let explicitReturn = age.map {
            $0 >= 0 && $0 <= returnTicketValidity
        } ?? false
        // iOS may restore Scarlet from Home without using the LC guest's
        // "Return" button. Previously every such fresh host process erased
        // A before B was launched. Preserve *launched-only* session history
        // on the same physical iOS boot; never claim cold apps retain RAM.
        let bootEpoch = Date().timeIntervalSince1970 -
            ProcessInfo.processInfo.systemUptime
        let savedEpoch = store.object(forKey: guestBootMarkerKey) as? Double
        let sameBoot = savedEpoch.map { abs($0 - bootEpoch) < 120 } ?? false
        let isContinuation = explicitReturn ||
            (sameBoot && !recent().isEmpty)
        if !isContinuation {
            guard let empty = try? JSONEncoder().encode([Entry]()) else { return }
            store.set(empty, forKey: key)
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switcher_work_session_started",
            fields: ["result": explicitReturn ? "guest_return_continued"
                       : isContinuation ? "same_boot_guest_history_continued"
                       : "cold_host_new_session"])
    }

    // The actual full-screen guest has a virtualized app sandbox, so its
    // private JSONL cannot be read from the host's diagnostic viewer.
    // Relay ONLY a fixed whitelist of anonymous switcher lifecycle events.
    // This never includes guest names, bundle IDs, credentials or screenshots.
    private static let switchTraceKey = "Scarlet.Guest.SwitcherTrace.V20"
    private static let switchTraceCursor = "Scarlet.Guest.SwitcherTraceCursor.V20"
    private static let switchTraceEvents: Set<String> = [
        "fullscreen_tab_mounted", "panel_opened", "panel_closed",
        "switch_tapped_live", "switch_tapped_cold", "switch_tapped_current",
        "switch_rejected", "switch_submitted", "switch_submit_failed",
        "rotation_relayout", "native_panel_opened", "native_switch_tapped",
        "native_switch_rejected", "native_switch_activated",
        "hook_entered", "framework_loaded", "framework_missing",
        "provider_ready", "provider_missing",
        "mount_window_not_ready", "mount_window_recovered",
        "runtime_current_resolved", "runtime_current_unresolved",
        "switch_target_boot_ack", "switch_target_boot_mismatch",
        "switch_host_live_requested",
        "glass_morph_opened", "glass_morph_closed"
    ]

    struct SwitchTrace: Codable {
        let id: String
        let event: String
        let count: Int
    }

    static func traceSwitcher(_ event: String, count: Int = 0) {
        guard switchTraceEvents.contains(event) else { return }
        let previous = (store.data(forKey: switchTraceKey))
            .flatMap { try? JSONDecoder().decode([SwitchTrace].self, from: $0) } ?? []
        let entry = SwitchTrace(id: UUID().uuidString, event: event,
                                count: max(0, min(count, 8)))
        if let encoded = try? JSONEncoder().encode(
            Array((previous + [entry]).suffix(48))) {
            store.set(encoded, forKey: switchTraceKey)
        }
    }

    private static var traceReaderReported = false

    static func replaySwitcherTraceToHostJournal() {
        guard let raw = store.data(forKey: switchTraceKey),
              let entries = try? JSONDecoder().decode([SwitchTrace].self, from: raw),
              !entries.isEmpty else {
            // Only report the absence once per host process. Do not erase
            // the cursor or legacy session data when guest trace is missing.
            if !traceReaderReported {
                traceReaderReported = true
                ScarletDiagnosticRecorder.shared.record(
                    "guest_switcher", "trace_bridge_empty",
                    fields: ["reason": "missing_or_unreadable"])
            }
            return
        }
        if !traceReaderReported {
            traceReaderReported = true
            ScarletDiagnosticRecorder.shared.record(
                "guest_switcher", "trace_bridge_readable",
                fields: ["count": String(entries.count)])
        }
        let cursor = UserDefaults.standard.string(forKey: switchTraceCursor)
        let start = cursor.flatMap { previous in
            entries.lastIndex(where: { $0.id == previous }).map { $0 + 1 }
        } ?? 0
        if start < entries.count {
            for entry in entries[start...] where switchTraceEvents.contains(entry.event) {
                ScarletDiagnosticRecorder.shared.record(
                    "guest_switcher", entry.event,
                    fields: ["count": String(entry.count), "source": "guest_app_group"])
            }
        }
        if let newest = entries.last?.id {
            UserDefaults.standard.set(newest, forKey: switchTraceCursor)
        }
    }

    // Keep an exact, short-lived pending target only in the existing secure
    // App Group; export an ANONYMOUS acknowledgement to the host diagnostic
    // journal after the next TweakLoader guest bootstrap.
    private static let switchPendingKey = "Scarlet.Guest.PendingSwitch.V24"
    private struct PendingSwitch: Codable {
        let possibleBundleIDs: [String]
        let createdAt: Date
    }

    static func noteSwitchHandoff(to expectedBundleIDs: [String]) {
        let safe = Array(Set(expectedBundleIDs.filter { !$0.isEmpty })).prefix(3)
        guard !safe.isEmpty,
              let encoded = try? JSONEncoder().encode(PendingSwitch(
                  possibleBundleIDs: Array(safe), createdAt: Date())) else { return }
        store.set(encoded, forKey: switchPendingKey)
    }

    static func cancelSwitchHandoff() {
        store.removeObject(forKey: switchPendingKey)
    }

    static func confirmSwitchHandoff(runtimeGuestID: String) {
        guard let raw = store.data(forKey: switchPendingKey),
              let pending = try? JSONDecoder().decode(PendingSwitch.self, from: raw)
        else { return }
        let age = Date().timeIntervalSince(pending.createdAt)
        guard age >= 0 && age <= 90 else {
            cancelSwitchHandoff()
            return
        }
        let matched = pending.possibleBundleIDs.contains(runtimeGuestID)
        traceSwitcher(matched ? "switch_target_boot_ack" : "switch_target_boot_mismatch")
        cancelSwitchHandoff()
    }

    static func recent() -> [Entry] {
        guard let data = store.data(forKey: key),
              let raw = try? JSONDecoder().decode([Entry].self, from: data)
        else { return [] }
        // A session lasts until a fresh, unrelated host entry, not an
        // arbitrary 30-minute timeout. Background pauses must not silently
        // remove A during a legitimate A->host->B workflow.
        return Array(raw.filter {
            $0.folder.hasSuffix(".app") &&
            !$0.folder.contains("/") &&
            !$0.folder.contains("\\") &&
            $0.folder != ".app"
        }.prefix(maxItems))
    }

    static func noteLaunch(folder: String, title: String, dataUUID: String?) {
        guard folder.hasSuffix(".app"), !folder.contains("/"),
              !folder.contains("\\"), folder != ".app" else { return }
        // Only truly launched guests are inserted. Importing or scanning an
        // installed .app must never create a switcher tab.
        let items = [Entry(folder: folder, lastOpened: Date(),
                           title: String(title.prefix(100)),
                           dataUUID: dataUUID)] +
            recent().filter { $0.folder != folder }
        guard let encoded = try? JSONEncoder().encode(Array(items.prefix(maxItems)))
        else { return }
        store.set(encoded, forKey: key)
        store.set(Date().timeIntervalSince1970 -
                  ProcessInfo.processInfo.systemUptime, forKey: guestBootMarkerKey)
        // Detect App Group/entitlement storage failures at the exact
        // pre-handoff write point, rather than reporting a saved A/B list
        // that the next guest cannot read. No credentials are recorded.
        let persisted = store.data(forKey: key) == encoded
        ScarletDiagnosticRecorder.shared.record(
            "guest", "recent_session_registered",
            status: persisted ? "success" : "warning",
            fields: [
                "count": String(min(items.count, maxItems)),
                "readback": persisted ? "persisted" : "failed"
            ])
    }

    static func restore(_ entries: [Entry]) {
        guard let data = try? JSONEncoder().encode(Array(entries.prefix(maxItems)))
        else { return }
        store.set(data, forKey: key)
    }

    static func remove(folder: String) {
        let remaining = recent().filter { $0.folder != folder }
        guard let encoded = try? JSONEncoder().encode(remaining) else { return }
        store.set(encoded, forKey: key)
    }

    static func rank(folder: String) -> Int? {
        recent().firstIndex { $0.folder == folder }
    }
}

// V34: LiveContainer's original virtual-window manager exists ONLY in the
// Scarlet host process. The guest overlay runs in a different LiveProcess
// extension, so MultitaskManager.isUsing() there cannot find host windows.
// Share opaque container IDs via the pre-existing App Group, and send only
// a constant Darwin notification. Never transfer guest app names or content.
@available(iOS 17.0, *)
@MainActor
enum ScarletGuestLiveBridge {
    private static let liveKey = "Scarlet.Guest.LiveContainers.V34"
    private static let requestKey = "Scarlet.Guest.LiveSwitchRequest.V34"
    private static let eventName = "com.kdt.livecontainer.scarlet.live-switch-v34"
    private static var hostObserverInstalled = false
    private static var lastHandledNonce = ""

    private struct Request: Codable {
        let container: String
        let nonce: String
        let requestedAt: Date
    }

    private static var defaults: UserDefaults {
        LCUtils.appGroupUserDefault
    }

    static func noteLiveContainer(_ id: String) {
        guard !id.isEmpty, id.count < 128, !id.contains("/") else { return }
        let known = defaults.stringArray(forKey: liveKey) ?? []
        defaults.set(Array(([id] + known.filter { $0 != id }).prefix(8)),
                     forKey: liveKey)
    }

    static func isHostKnownLive(_ id: String) -> Bool {
        (defaults.stringArray(forKey: liveKey) ?? []).contains(id)
    }

    static func requestHostLiveSwitch(_ id: String) -> Bool {
        guard isHostKnownLive(id), !id.isEmpty, id.count < 128,
              !id.contains("/"), !id.contains("\\") else { return false }
        let request = Request(container: id, nonce: UUID().uuidString,
                              requestedAt: Date())
        guard let data = try? JSONEncoder().encode(request) else { return false }
        defaults.set(data, forKey: requestKey)
        defaults.synchronize()
        CFNotificationCenterPostNotification(
            CFNotificationCenterGetDarwinNotifyCenter(),
            CFNotificationName(rawValue: eventName as CFString),
            nil, nil, true)
        return true  // request delivered; NOT a verified window switch
    }

    static func installHostReceiver() {
        guard !hostObserverInstalled else { return }
        hostObserverInstalled = true
        CFNotificationCenterAddObserver(
            CFNotificationCenterGetDarwinNotifyCenter(), nil,
            { _, _, _, _, _ in
                Task { @MainActor in
                    ScarletGuestLiveBridge.handleHostRequest()
                }
            },
            eventName as CFString, nil, .deliverImmediately)
    }

    private static func handleHostRequest() {
        guard let data = defaults.data(forKey: requestKey),
              let request = try? JSONDecoder().decode(Request.self, from: data),
              request.nonce != lastHandledNonce else { return }
        lastHandledNonce = request.nonce
        let age = Date().timeIntervalSince(request.requestedAt)
        guard age >= 0, age < 10, request.container.count < 128,
              !request.container.contains("/") else { return }
        let resident = MultitaskManager.isUsing(container: request.container)
        let resumed = resident &&
            MultitaskDockManager.shared.bringMultitaskViewToFront(
                uuid: request.container)
        if !resumed {
            // A guest LiveProcess might have been reclaimed by iOS. Do not
            // keep telling the guest that this window is alive.
            let known = defaults.stringArray(forKey: liveKey) ?? []
            defaults.set(known.filter { $0 != request.container },
                         forKey: liveKey)
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest_switcher", resumed ? "live_window_resumed" :
                                          "live_window_unavailable",
            status: resumed ? "success" : "warning",
            fields: ["result": resumed ? "original_window_reactivated" :
                                         "process_not_resident"])
    }
}

// V23: explicit host/guest work-session switcher. Never infer that an
// installed or previously launched app is still resident in memory.
// Only launched apps from the CURRENT session appear. Old ledgers remain
// untouched for rollback, and guest data/certificates are not modified.
import Foundation

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
    // V37 namespace prevents stale V23 Kakao/Instagram launch history
    // from being treated as current. Old data stays untouched for rollback.
    private static let key = "Scarlet.Guest.ActiveSwitcherSession.V37"
    private static let hostReturnKey = "Scarlet.Guest.HostReturnTicket.V37"
    private static let guestBootMarkerKey = "Scarlet.Guest.LaunchBootEpoch.V37"
    private static let guestDepartedKey = "Scarlet.Guest.DepartedTicket.V37"
    private static let guestDepartureValidity: TimeInterval = 120

    private struct GuestDeparture: Codable {
        let folder: String
        let time: Date
        let bootEpoch: Double
    }

    // Only a verified foreground guest can prove a recent Home handoff.
    static func noteGuestDeparted(folder: String) {
        guard recent().contains(where: { $0.folder == folder }) else { return }
        let departure = GuestDeparture(
            folder: folder, time: Date(),
            bootEpoch: Date().timeIntervalSince1970 -
                ProcessInfo.processInfo.systemUptime)
        if let data = try? JSONEncoder().encode(departure) {
            store.set(data, forKey: guestDepartedKey)
        }
    }
    private static let maxItems = 8
    private static let returnTicketValidity: TimeInterval = 120
    private static var hasEnteredHostWorkSession = false
    private static var lastHostForegroundAt: Date?
    private static let unrelatedHostReturnResetAfter: TimeInterval = 120

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
        lastHostForegroundAt = Date()
        let age = ticket.map { Date().timeIntervalSince($0) }
        let explicitReturn = age.map {
            $0 >= 0 && $0 <= returnTicketValidity
        } ?? false
        // Same device boot alone was too weak: unrelated old apps
        // reappeared. Require an actual recent guest -> Home transition.
        let departure = store.data(forKey: guestDepartedKey)
            .flatMap { try? JSONDecoder().decode(GuestDeparture.self, from: $0) }
        store.removeObject(forKey: guestDepartedKey)
        let bootEpoch = Date().timeIntervalSince1970 -
            ProcessInfo.processInfo.systemUptime
        let savedEpoch = store.object(forKey: guestBootMarkerKey) as? Double
        let sameBoot = savedEpoch.map { abs($0 - bootEpoch) < 120 } ?? false
        let guestWasJustActive = departure.map { item in
            let age = Date().timeIntervalSince(item.time)
            return age >= 0 && age <= guestDepartureValidity &&
                abs(item.bootEpoch - bootEpoch) < 120 &&
                recent().contains(where: { $0.folder == item.folder })
        } ?? false
        let isContinuation = explicitReturn ||
            (sameBoot && guestWasJustActive)
        if !isContinuation {
            guard let empty = try? JSONEncoder().encode([Entry]()) else { return }
            store.set(empty, forKey: key)
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switcher_work_session_started",
            fields: ["result": explicitReturn ? "guest_return_continued"
                       : isContinuation ? "verified_guest_departure_continued"
                       : "cold_host_new_session"])
    }

    // A Scarlet host process can survive in the background for hours.
    // The first-appearance guard must not keep Kakao/Instagram from a
    // previous work session forever merely because this PID survived.
    static func reconcileHostForeground() {
        guard hasEnteredHostWorkSession else { return }
        let now = Date()
        defer { lastHostForegroundAt = now }
        guard let previous = lastHostForegroundAt,
              now.timeIntervalSince(previous) >= unrelatedHostReturnResetAfter
        else { return }

        let ticket = store.object(forKey: hostReturnKey) as? Date
        let explicit = ticket.map {
            let age = now.timeIntervalSince($0)
            return age >= 0 && age <= returnTicketValidity
        } ?? false
        let departure = store.data(forKey: guestDepartedKey)
            .flatMap { try? JSONDecoder().decode(GuestDeparture.self, from: $0) }
        let bootEpoch = now.timeIntervalSince1970 -
            ProcessInfo.processInfo.systemUptime
        let validDeparture = departure.map { item in
            let age = now.timeIntervalSince(item.time)
            return age >= 0 && age <= guestDepartureValidity &&
                abs(item.bootEpoch - bootEpoch) < 120 &&
                recent().contains(where: { $0.folder == item.folder })
        } ?? false
        store.removeObject(forKey: hostReturnKey)
        store.removeObject(forKey: guestDepartedKey)
        guard !explicit && !validDeparture else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switcher_work_session_continued",
                fields: ["reason": "recent_guest_handoff"])
            return
        }
        guard let empty = try? JSONEncoder().encode([Entry]()) else { return }
        store.set(empty, forKey: key)
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switcher_work_session_reset",
            fields: ["reason": "unrelated_foreground_entry",
                     "count": "0"])
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
        "glass_morph_opened", "glass_morph_closed"
    ]

    struct SwitchTrace: Codable {
        let id: String
        let event: String
        let count: Int
        // Older V20 records have no timestamp. They must not be replayed
        // into a V38 "this launch only" diagnostic report.
        let createdAt: Date?
    }

    static func traceSwitcher(_ event: String, count: Int = 0) {
        guard switchTraceEvents.contains(event) else { return }
        let previous = (store.data(forKey: switchTraceKey))
            .flatMap { try? JSONDecoder().decode([SwitchTrace].self, from: $0) } ?? []
        let entry = SwitchTrace(id: UUID().uuidString, event: event,
                                count: max(0, min(count, 8)),
                                createdAt: Date())
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
            let processStart =
                ScarletDiagnosticRecorder.shared.currentProcessStartDate
            // A 48-entry store says nothing about THIS app launch.
            // Count only fresh entries to prevent an old backlog being
            // mistaken for active/visible guest app evidence.
            let fresh = entries.filter { entry in
                entry.createdAt.map { $0 >= processStart } ?? false
            }
            ScarletDiagnosticRecorder.shared.record(
                "guest_switcher", "trace_bridge_readable",
                fields: ["count": String(fresh.count),
                         "source": "current_process_only"])
        }
        let cursor = UserDefaults.standard.string(forKey: switchTraceCursor)
        let start = cursor.flatMap { previous in
            entries.lastIndex(where: { $0.id == previous }).map { $0 + 1 }
        } ?? 0
        if start < entries.count {
            let currentProcessStart =
                ScarletDiagnosticRecorder.shared.currentProcessStartDate
            for entry in entries[start...]
                where switchTraceEvents.contains(entry.event) &&
                    (entry.createdAt.map { $0 >= currentProcessStart } ?? false) {
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

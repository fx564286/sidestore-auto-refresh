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
    // V43: start with ZERO tabs on the first V43 launch. V40/V42 guest history
    // and their previous-return tickets stay intact for exact V40 rollback.
    // ONLY a guest launched in this V43 work can create a V43 return ticket;
    // after A->Home->B in this work, A remains without importing old apps.
    private static let key = "Scarlet.Guest.ActiveSwitcherSession.V43"
    private static let sessionIDKey = "Scarlet.Guest.WorkSessionID.V43"
    private static let hostReturnKey = "Scarlet.Guest.HostReturnTicket.V43"
    private static let guestBootMarkerKey = "Scarlet.Guest.LaunchBootEpoch.V43"
    private static let guestDepartedKey = "Scarlet.Guest.DepartedTicket.V43"
    private static let guestDepartureValidity: TimeInterval = 120
    private static let maxItems = 8
    private static var hasEnteredHostWorkSession = false
    private static var lastHostForegroundAt: Date?

    private struct GuestDeparture: Codable {
        let folder: String
        let workID: String
        let time: Date
        let bootEpoch: Double
    }

    private struct HostReturn: Codable {
        let folder: String
        let workID: String
        let time: Date
    }

    private static var store: UserDefaults { LCUtils.appGroupUserDefault }

    private static func bootEpoch() -> Double {
        Date().timeIntervalSince1970 - ProcessInfo.processInfo.systemUptime
    }

    private static func departureIsValid(_ departure: GuestDeparture?,
                                         workID: String?,
                                         at now: Date) -> Bool {
        guard let departure, let workID, !workID.isEmpty,
              departure.workID == workID else { return false }
        let age = now.timeIntervalSince(departure.time)
        return age >= 0 && age <= guestDepartureValidity &&
            abs(departure.bootEpoch - bootEpoch()) < 120 &&
            recent().contains(where: { $0.folder == departure.folder })
    }

    private static func startFreshWorkSession() {
        let id = UUID().uuidString
        store.set(id, forKey: sessionIDKey)
        if let empty = try? JSONEncoder().encode([Entry]()) {
            store.set(empty, forKey: key)
        }
        store.removeObject(forKey: hostReturnKey)
        store.removeObject(forKey: guestDepartedKey)
        // Never change guest containers, LastLaunched or signing profiles.
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switcher_new_work_session",
            fields: ["count": "0", "result": "fresh_launch"])
    }

    // This ticket is minted in the ACTUAL foreground guest. Merely having
    // an old "Return" Date, or still being on the same iPhone boot, cannot
    // resurrect an unrelated app.
    static func noteGuestDeparted(folder: String) {
        guard recent().contains(where: { $0.folder == folder }),
              let workID = store.string(forKey: sessionIDKey),
              !workID.isEmpty else { return }
        let departure = GuestDeparture(
            folder: folder, workID: workID, time: Date(),
            bootEpoch: bootEpoch())
        if let data = try? JSONEncoder().encode(departure) {
            store.set(data, forKey: guestDepartedKey)
        }
    }

    // Scarlet's own back button may use this explicit return. It is bound
    // to the same guest and work session as the foreground departure.
    static func beginReturnToHost(folder: String) {
        noteGuestDeparted(folder: folder)
        guard let departure = store.data(forKey: guestDepartedKey)
                .flatMap({ try? JSONDecoder().decode(GuestDeparture.self, from: $0) }),
              departure.folder == folder else { return }
        let ticket = HostReturn(folder: folder, workID: departure.workID,
                                time: Date())
        if let data = try? JSONEncoder().encode(ticket) {
            store.set(data, forKey: hostReturnKey)
        }
    }

    static func cancelReturnToHost() {
        store.removeObject(forKey: hostReturnKey)
    }

    // Called once when Scarlet first becomes visible in this host process.
    // A legitimate A -> Home -> Scarlet -> B retains A only if A really
    // departed within the same workID, boot and short handoff window.
    static func prepareForHostAppearance() {
        guard !hasEnteredHostWorkSession else { return }
        hasEnteredHostWorkSession = true
        lastHostForegroundAt = Date()
        let now = Date()
        let workID = store.string(forKey: sessionIDKey)
        let departure = store.data(forKey: guestDepartedKey)
            .flatMap { try? JSONDecoder().decode(GuestDeparture.self, from: $0) }
        let explicit = store.data(forKey: hostReturnKey)
            .flatMap { try? JSONDecoder().decode(HostReturn.self, from: $0) }
        // Consume BOTH handoff markers exactly once, even on invalid data.
        store.removeObject(forKey: hostReturnKey)
        store.removeObject(forKey: guestDepartedKey)
        let legitimateGuest = departureIsValid(departure, workID: workID, at: now)
        let explicitlyReturned = legitimateGuest && explicit.map { ticket in
            let age = now.timeIntervalSince(ticket.time)
            return age >= 0 && age <= guestDepartureValidity &&
                ticket.workID == workID && ticket.folder == departure?.folder
        } == true
        if !legitimateGuest {
            startFreshWorkSession()
        }
        ScarletDiagnosticRecorder.shared.record(
            "guest", "switcher_work_session_started",
            fields: ["result": explicitlyReturned ? "verified_guest_return_continued"
                : legitimateGuest ? "verified_guest_departure_continued"
                : "cold_host_new_session",
                     "count": String(recent().count),
                     "memory": "not_verified"])
    }

    // A living Scarlet host is the SAME work session. Time passing alone
    // never expires its A/B tabs; only a new unrelated host process or an
    // explicit fresh-work action can reset the active work.
    static func reconcileHostForeground() {
        guard hasEnteredHostWorkSession else { return }
        lastHostForegroundAt = Date()
    }

    static func beginNewWork() {
        hasEnteredHostWorkSession = true
        lastHostForegroundAt = Date()
        startFreshWorkSession()
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
        "glass_morph_opened", "glass_morph_closed",
        "runtime_guest_process_observed"
    ]

    struct SwitchTrace: Codable {
        let id: String
        let event: String
        let count: Int
        // Older V20 records have no timestamp. They must not be replayed
        // into a V38 "this launch only" diagnostic report.
        let createdAt: Date?
        // Ephemeral PID only; never record app names, bundle IDs or device IDs.
        let processPID: Int32?
    }

    static func traceSwitcher(_ event: String, count: Int = 0,
                              processPID: Int32? = nil) {
        guard switchTraceEvents.contains(event) else { return }
        let previous = (store.data(forKey: switchTraceKey))
            .flatMap { try? JSONDecoder().decode([SwitchTrace].self, from: $0) } ?? []
        let entry = SwitchTrace(id: UUID().uuidString, event: event,
                                count: max(0, min(count, 8)),
                                createdAt: Date(),
                                processPID: processPID.flatMap { $0 > 0 ? $0 : nil })
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
                var fields = ["count": String(entry.count),
                              "source": "guest_app_group"]
                if let pid = entry.processPID, pid > 0 {
                    fields["process_pid"] = String(pid)
                }
                ScarletDiagnosticRecorder.shared.record(
                    "guest_switcher", entry.event, fields: fields)
            }
        }
        if let newest = entries.last?.id {
            UserDefaults.standard.set(newest, forKey: switchTraceCursor)
        }
    }

    // R6P7: the LiveProcess bootloader records Info.plist declarations
    // before/after NSBundle + CFBundle main bundle substitution. This does
    // not inspect or change UIKit geometry, guest windows or Safe Areas.
    private static let guestPolicyKey = "Scarlet.Guest.LaunchPolicy.V1"
    private static let guestPolicyCursor = "Scarlet.Guest.LaunchPolicyCursor.V1"
    static func replayGuestLaunchPolicyToHostJournal() {
        guard let raw = store.data(forKey: guestPolicyKey),
              let decoded = try? JSONSerialization.jsonObject(with: raw),
              let rows = decoded as? [[String: Any]], !rows.isEmpty else {
            ScarletDiagnosticRecorder.shared.record(
                "launch_policy", "guest_policy_probe_unavailable",
                fields: ["reason": "no_guest_bootloader_result"])
            return
        }
        let cursor = UserDefaults.standard.string(forKey: guestPolicyCursor)
        let start = cursor.flatMap { id in
            rows.lastIndex(where: { $0["id"] as? String == id }).map { $0 + 1 }
        } ?? 0
        let currentStart = ScarletDiagnosticRecorder.shared.currentProcessStartDate
            .timeIntervalSince1970
        let allowed = ["host_status_hidden", "guest_status_hidden",
                       "actual_status_hidden", "cf_status_hidden",
                       "host_controller_status", "guest_controller_status",
                       "actual_controller_status", "host_fullscreen",
                       "guest_fullscreen", "actual_fullscreen",
                       "host_scene_manifest", "guest_scene_manifest",
                       "actual_scene_manifest", "host_orientations",
                       "guest_orientations", "actual_orientations"]
        if start < rows.count {
            for row in rows[start...] {
                guard let epoch = (row["epoch"] as? NSNumber)?.doubleValue,
                      epoch >= currentStart,
                      let pid = (row["pid"] as? NSNumber)?.int32Value,
                      pid > 0, let stage = row["stage"] as? String,
                      ["before_bundle_swap", "after_bundle_swap"].contains(stage)
                else { continue }
                var fields = ["stage": stage,
                              "process_pid": String(pid),
                              "source": "original_lc_bootloader",
                              "policy_only": "true"]
                for key in allowed {
                    if let value = row[key] as? NSNumber {
                        let n = value.intValue
                        if n >= -1 && n <= 20 {
                            fields[key] = String(n)
                        }
                    }
                }
                ScarletDiagnosticRecorder.shared.record(
                    "launch_policy", "guest_bundle_policy_observed",
                    fields: fields)
            }
        }
        if let last = rows.last?["id"] as? String {
            UserDefaults.standard.set(last, forKey: guestPolicyCursor)
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
        traceSwitcher(matched ? "switch_target_boot_ack" : "switch_target_boot_mismatch",
                      processPID: ProcessInfo.processInfo.processIdentifier)
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
        // Never create a phantom tab without a host-established work ID.
        guard let workID = store.string(forKey: sessionIDKey),
              !workID.isEmpty else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "switcher_launch_rejected_without_work",
                status: "warning", fields: ["reason": "no_active_work_session"])
            return
        }
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

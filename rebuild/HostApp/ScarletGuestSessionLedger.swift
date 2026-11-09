// V19: bounded *current switcher session* rather than a permanent
// installed/ever-launched app list. This is NOT proof that a process
// remains in memory. Stored in the existing LC host; no extra App ID.
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
    // Keep the old V14 history intact for rollback, but never load it into
    // the switcher: it accumulated every installed app after a few days.
    // Legacy key: Scarlet.Guest.RecentSessions.V14
    private static let key = "Scarlet.Guest.ActiveSwitcherSession.V19"
    private static let maxItems = 8
    private static let inactivityTimeout: TimeInterval = 30 * 60

    private static var store: UserDefaults { LCUtils.appGroupUserDefault }

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
        "runtime_current_resolved", "runtime_current_unresolved"
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

    static func recent() -> [Entry] {
        guard let data = store.data(forKey: key),
              let raw = try? JSONDecoder().decode([Entry].self, from: data)
        else { return [] }
        // Require a simple installed .app name, never untrusted paths.
        // A new work session starts after 30 minutes with no guest launch.
        // This prevents previously opened apps from masquerading as open tabs
        // after overnight restarts, while A->Home->B within a session survives
        // the full-screen LC process handoff.
        let valid = Array(raw.filter {
            $0.folder.hasSuffix(".app") &&
            !$0.folder.contains("/") &&
            !$0.folder.contains("\\") &&
            $0.folder != ".app"
        }.prefix(maxItems))
        // Expire EACH cold tab independently. A recently relaunched B must
        // not keep an unrelated, much older installed C in the switcher.
        let now = Date()
        return valid.filter { entry in
            let idle = now.timeIntervalSince(entry.lastOpened)
            return idle >= -120 && idle <= inactivityTimeout
        }
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

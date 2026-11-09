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

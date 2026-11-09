// V14: persistent *launched* guest list. This is NOT a claim that a process
// is still in memory. Runs inside the host and its original LiveContainer
// framework, never in a separate signed extension or additional App ID.
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
    private static let key = "Scarlet.Guest.RecentSessions.V14"
    private static let maxItems = 24

    private static var store: UserDefaults { LCUtils.appGroupUserDefault }

    static func recent() -> [Entry] {
        guard let data = store.data(forKey: key),
              let raw = try? JSONDecoder().decode([Entry].self, from: data)
        else { return [] }
        // Require a simple installed .app name, never untrusted paths.
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

#!/usr/bin/env python3
"""V183 P00: recover logs even if LiveProcess / SideStore cannot start.

Host-local, bounded, allowlisted event journal in Application Support, never
dependent on XPC, App Group, pairing, Keychain or SideStore database.
Existing SideStore logTail remains available via a separate opt-in button.
Never change the user's Liquid Glass code, dock, colors or Figma tokens.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V183_HOST_LOG_FALLBACK"
REL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")

VIEW_START = "struct V3LogsView: View {"
VIEW_END = "\nstruct V3ExperimentalView: View {"

NEW_VIEW = r'''// SCARLET_V183_HOST_LOG_FALLBACK: operation evidence belongs to the host too.
// This app-private file is not an App Group store; failures in LiveProcess
// cannot hide the status events needed to diagnose that same failure.
// Only hard-coded event names are allowed; no PINs, credentials, account IDs,
// Apple replies, pairing records, request bodies or filesystem paths.
enum ScarletV183Event: String {
    case hostStarted = "host.started"
    case logsOpened = "logs.opened"
    case pairingStarted = "pairing.started"
    case pairingWaiting = "pairing.waiting"
    case pairingCodeReady = "pairing.pin_received"
    case pairingCompleted = "pairing.record_saved"
    case pairingFailed = "pairing.failed"
    case pairingStopped = "pairing.cancelled"
    case authStarted = "auth.started"
    case authNeedsInput = "auth.prompt_available"
    case authCompleted = "auth.completed"
    case authFailed = "auth.failed"
    case authUnknown = "auth.result_unconfirmed"
    case authCancelRequested = "auth.cancel_requested"
    case refreshRequested = "refresh.requested"
    case refreshVerified = "refresh.manifest_verified"
    case refreshFailed = "refresh.failed"
    case serviceLogsLoaded = "sidestore.logs_loaded"
    case serviceLogsEmpty = "sidestore.logs_empty"
    case serviceLogsUnavailable = "sidestore.logs_unavailable"
}

@MainActor
enum ScarletV183HostLog {
    private static let maxBytes = 131_072
    private static var memory: [String] = []

    private static func location() -> URL? {
        guard let library = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return nil
        }
        return library.appendingPathComponent("ScarletCrystalDiagnostics",
            isDirectory: true).appendingPathComponent("host-events.log")
    }

    static func record(_ event: ScarletV183Event) {
        let stamp = ISO8601DateFormatter().string(from: Date())
        let line = "[SCARLET_DIAG] time=" + stamp +
            " component=host event=" + event.rawValue + "\n"
        memory.append(line)
        if memory.count > 240 { memory.removeFirst(memory.count - 240) }
        guard let url = location() else { return }
        do {
            try FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            if !FileManager.default.fileExists(atPath: url.path) {
                try Data().write(to: url, options: .atomic)
            }
            let handle = try FileHandle(forWritingTo: url)
            do {
                try handle.seekToEnd()
                try handle.write(contentsOf: Data(line.utf8))
                try handle.close()
            } catch {
                try? handle.close()
                throw error
            }
            let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
            let size = (attributes?[.size] as? NSNumber)?.intValue ?? 0
            if size > maxBytes {
                let bytes = try Data(contentsOf: url)
                // Trim at the next newline so no partial event is presented.
                let suffix = bytes.suffix(maxBytes / 2)
                let text = String(decoding: suffix, as: UTF8.self)
                let lines = text.split(separator: "\n", omittingEmptySubsequences: true)
                let completeLines = lines.dropFirst()
                let bounded = completeLines.joined(separator: "\n") + "\n"
                try Data(bounded.utf8).write(to: url, options: .atomic)
            }
        } catch {
            // Read-only memory fallback preserves current-session evidence
            // without adding a dependency on App Groups or the service.
        }
    }

    static func contents() -> String {
        if let url = location(),
           let data = try? Data(contentsOf: url), !data.isEmpty {
            return String(decoding: data.suffix(maxBytes), as: UTF8.self)
        }
        return memory.joined()
    }

    static func export() -> URL? {
        let text = contents()
        guard !text.isEmpty else { return nil }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("Scarlet-Crystal-Device-Diagnostics.txt")
        do {
            try Data(text.utf8).write(to: url, options: .atomic)
            return url
        } catch {
            return nil
        }
    }
}

private struct ScarletV183LogFile: Identifiable {
    let id = UUID()
    let url: URL
}

private struct ScarletV183LogShareSheet: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

struct V3LogsView: View {
    @State private var hostTail = ""
    @State private var sideStoreTail = ""
    @State private var message = ""
    @State private var copied = false
    @State private var loadingService = false
    @State private var exportedFile: ScarletV183LogFile?

    var body: some View {
        List {
            Section("Scarlet Crystal Device Logs") {
                Text("Saved on this iPhone without SideStore or LiveProcess. No passwords, pairing PINs, Apple verification codes or account contents are recorded.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                HStack {
                    Button("Reload") { reloadLocal() }
                    Button(copied ? "Copied" : "Copy Logs") {
                        UIPasteboard.general.string = hostTail
                        copied = true
                    }
                    .disabled(hostTail.isEmpty)
                    Button("Share Log File") {
                        if let url = ScarletV183HostLog.export() {
                            exportedFile = ScarletV183LogFile(url: url)
                        } else {
                            message = "This device could not create the log export file."
                        }
                    }
                    .disabled(hostTail.isEmpty)
                }
                Text(hostTail.isEmpty
                     ? "No host events recorded yet. This screen records events automatically while the app is running."
                     : String(hostTail.suffix(70_000)))
                    .font(.system(.caption2, design: .monospaced))
                    .textSelection(.enabled)
            }
            Section("SideStore Service Logs (optional)") {
                Text("Service logs require LiveProcess. If that service crashes, the device logs above remain available.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                Button(loadingService ? "Connecting..." : "Load SideStore Logs") {
                    Task { await loadServiceLogs() }
                }
                .disabled(loadingService)
                if !sideStoreTail.isEmpty {
                    Button("Copy SideStore Logs") {
                        // SideStore's raw console output may contain private
                        // material; never include it in automatic host export.
                        UIPasteboard.general.string = sideStoreTail
                    }
                    Text(String(sideStoreTail.suffix(30_000)))
                        .font(.system(.caption2, design: .monospaced))
                        .textSelection(.enabled)
                }
                if !message.isEmpty {
                    Text(message).font(.footnote).foregroundColor(.secondary)
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Operation Logs")
        .sheet(item: $exportedFile) { item in
            ScarletV183LogShareSheet(url: item.url)
        }
        .task {
            ScarletV183HostLog.record(.logsOpened)
            reloadLocal()
            // A visible log viewer follows new host events. No connection
            // attempts or file polling continue after the view disappears.
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                guard !Task.isCancelled else { return }
                reloadLocal()
            }
        }
    }

    private func reloadLocal() {
        hostTail = ScarletV183HostLog.contents()
    }

    private func loadServiceLogs() async {
        guard !loadingService else { return }
        loadingService = true
        defer { loadingService = false; reloadLocal() }
        do {
            let reply = try await V3ServiceBridge.shared.request(
                operation: "logTail", requestDeadline: Date().addingTimeInterval(15))
            sideStoreTail = reply["tail"] as? String ?? ""
            if sideStoreTail.isEmpty {
                ScarletV183HostLog.record(.serviceLogsEmpty)
                message = "SideStore returned no console log entries. Device logs are still available above."
            } else {
                ScarletV183HostLog.record(.serviceLogsLoaded)
                message = ""
            }
        } catch {
            ScarletV183HostLog.record(.serviceLogsUnavailable)
            sideStoreTail = ""
            message = "SideStore cannot provide its log right now. The saved Scarlet Crystal device log above remains readable and shareable."
        }
    }
}
'''


def replace_one(source: str, before: str, after: str, description: str) -> str:
    count = source.count(before)
    if count != 1:
        raise ValueError(f"V183 log source drift: {description} expected one anchor, got {count}")
    return source.replace(before, after, 1)


def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "Share Log File" not in source:
            raise ValueError("V183 host log fallback partial patch")
        return source

    if source.count(VIEW_START) != 1 or source.count(VIEW_END) != 1:
        raise ValueError("V183 original Operation Logs view unavailable")
    start = source.index(VIEW_START)
    end = source.index(VIEW_END, start)
    original_view = source[start:end]
    for existing in ('operation: "logTail"', "Copy Logs", 'Text(String(tail.suffix(120_000)))'):
        if existing not in original_view:
            raise ValueError("V183 unexpected original log viewer: " + existing)
    source = source[:start] + NEW_VIEW + source[end:]

    source = replace_one(source,
        "final class V3SideStoreStatusStore: ObservableObject {\n    init() {\n",
        "final class V3SideStoreStatusStore: ObservableObject {\n    init() {\n"
        "        ScarletV183HostLog.record(.hostStarted)\n",
        "host process startup journal")

    source = replace_one(source,
        '''    func begin() {
        guard canBegin else { return }
        task?.cancel()
''',
        '''    func begin() {
        guard canBegin else { return }
        ScarletV183HostLog.record(.authStarted)
        task?.cancel()
''',
        "user-started Apple sign-in")

    source = replace_one(source,
        '''        reconciliationGate.invalidate()
        cancellationWasAttempted = true
        isCancelling = true
''',
        '''        reconciliationGate.invalidate()
        ScarletV183HostLog.record(.authCancelRequested)
        cancellationWasAttempted = true
        isCancelling = true
''',
        "cancel event without credentials")

    source = replace_one(source,
        '''        .onChange(of: auth.isSignedIn) { isSignedIn in
''',
        '''        .onChange(of: auth.state) { newState in
            switch newState {
            case "awaitingPrompt": ScarletV183HostLog.record(.authNeedsInput)
            case "completed": ScarletV183HostLog.record(.authCompleted)
            case "failed": ScarletV183HostLog.record(.authFailed)
            case "resultUnknown": ScarletV183HostLog.record(.authUnknown)
            default: break
            }
        }
        .onChange(of: auth.isSignedIn) { isSignedIn in
''',
        "auth state transitions")

    source = replace_one(source,
        '''            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
''',
        '''            ScarletV183HostLog.record(.pairingStarted)
            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
''',
        "pairing initiation")

    source = replace_one(source,
        '''            onDevicePairPhase = reply["phase"] as? String ?? "unknown"
            onDevicePairPin = reply["pin"] as? String ?? ""
''',
        '''            let priorPhase = onDevicePairPhase
            onDevicePairPhase = reply["phase"] as? String ?? "unknown"
            if priorPhase != onDevicePairPhase {
                switch onDevicePairPhase {
                case "waiting": ScarletV183HostLog.record(.pairingWaiting)
                case "pin": ScarletV183HostLog.record(.pairingCodeReady)
                case "complete": ScarletV183HostLog.record(.pairingCompleted)
                case "failed": ScarletV183HostLog.record(.pairingFailed)
                case "idle": ScarletV183HostLog.record(.pairingStopped)
                default: break
                }
            }
            onDevicePairPin = reply["pin"] as? String ?? ""
''',
        "pairing event transitions without PIN value")

    source = replace_one(source,
        '''        let newRequestID = UUID().uuidString
        attempt.begin(requestID: newRequestID)
        message = "Starting Refresh..."
''',
        '''        let newRequestID = UUID().uuidString
        attempt.begin(requestID: newRequestID)
        ScarletV183HostLog.record(.refreshRequested)
        message = "Starting Refresh..."
''',
        "manual refresh begins")

    source = replace_one(source,
        '''        case .completed:
            let manifest = record["manifest"] as? [String: Any]
''',
        '''        case .completed:
            ScarletV183HostLog.record(.refreshVerified)
            let manifest = record["manifest"] as? [String: Any]
''',
        "verified refresh completion")

    source = replace_one(source,
        '''        case .failed:
            renderFailure(health: record["health"] as? String ?? health, record: record)
''',
        '''        case .failed:
            ScarletV183HostLog.record(.refreshFailed)
            renderFailure(health: record["health"] as? String ?? health, record: record)
''',
        "refresh failure")

    return source


def apply(root: Path) -> None:
    target = root / REL
    if not target.is_file() or target.is_symlink():
        raise ValueError("V183 host Swift shell file missing")
    old = target.read_text(encoding="utf-8")
    new = patch(old)
    if patch(new) != new:
        raise ValueError("V183 host log patch not idempotent")
    if old != new:
        target.write_text(new, encoding="utf-8")
    print("[V183] host-side event log + local share file independent of SideStore service")
    print("[V183] no PIN/password/account/token/Apple 2FA values written to the host journal")
    print("[V183] Liquid Glass and Figma components untouched")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v183_host_diagnostic_logs.py <LiveContainer>")
    apply(Path(sys.argv[1]))

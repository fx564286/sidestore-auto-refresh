// Scarlet Crystal first-party on-device diagnostic journal.
// Never record Apple IDs, passwords, OTPs, provisioning data, UDIDs, IPA
// paths, guest display names, raw network payloads or NSError.userInfo.
// JSON Lines are private to this app, not an App Group or remote server.
import Foundation
import SwiftUI
import CryptoKit
import UIKit

final class ScarletDiagnosticRecorder: @unchecked Sendable {
    static let shared = ScarletDiagnosticRecorder()
    // Replaced by pinned Xcode integration at archive time (not a device ID).
    static let buildCommit = "__SCARLET_BUILD_SHA__"
    private let lock = NSLock()
    private let fm = FileManager.default
    private let directory: URL
    private let sessionID = UUID().uuidString.prefix(8).lowercased()
    private let salt = UUID().uuidString
    private var sequence: UInt64 = 0
    // Full, device-local diagnostic history for the experimental compositor.
    // Bounded to 8 x 4 MiB, never exported to a network service automatically.
    private let maxFileBytes = 4_000_000
    private let retainedFiles = 8
    // Process-specific journal, independent of archived runs.
    private let launchedAt = Date()
    var currentProcessStartDate: Date { launchedAt }
    private static let allowedFields: Set<String> = [
        "action", "tab", "result", "reason", "status", "state", "code",
        "domain", "count", "duration_ms", "width_pt", "height_pt",
        "safe_top_pt", "safe_bottom_pt", "orientation", "engine",
        "available", "stage", "guest_ref", "window_attached",
        "scene", "os_major", "os_minor", "physical_memory_mb",
        "certificate_present", "password_present", "team_match", "build_sha",
        // Boolean/categorical safety checks needed to distinguish entitlement,
        // App Group and certificate failures on the installed iPhone.
        "entitled_app_group", "group_accessible", "signed_host_identity",
        "lc_cert_present", "installation_verified", "material_owner",
        "optical_verified", "api", "source", "retry_minutes",
        "process_pid", "memory", "stage", "worker_stage",
        // New V48-R3 diagnostic fields: numbers, bools and fixed enum states.
        "old_mode", "new_mode", "live_session", "gesture_phase",
        "button_x_pt", "button_y_pt", "finger_x_pt", "finger_y_pt",
        "drag_dx_pt", "drag_dy_pt", "window_count", "host_key",
        "host_visible", "overlay_visible", "overlay_expanded", "safe_left_pt",
        "safe_right_pt", "guest_safe_top_pt", "guest_safe_bottom_pt",
        "window_safe_top_pt", "window_safe_bottom_pt",
        "scene_width_pt", "scene_height_pt", "viewport_width_pt",
        "viewport_height_pt", "layout_status", "island_overlap_suspected",
        "launch_mode", "toggle_enabled", "sample_index", "history_count",
        "native_drag_gesture_state", "original_pan_used", "controller_present",
        "host_owner_top_pt", "error_domain", "error_code", "fast_exit",
        "mode",
        // R6P8: R6P7 guest bootloader correctly collected these 0/1/-1
        // launch-policy counts, but the recorder silently dropped them.
        // Only anonymous bounded BOOL/array-count fields are permitted.
        "policy_only",
        "host_status_hidden", "guest_status_hidden",
        "actual_status_hidden", "cf_status_hidden",
        "host_controller_status", "guest_controller_status",
        "actual_controller_status", "host_fullscreen",
        "guest_fullscreen", "actual_fullscreen",
        "host_scene_manifest", "guest_scene_manifest",
        "actual_scene_manifest", "host_orientations",
        "guest_orientations", "actual_orientations",
        "policy_fields_received", "policy_fields_persisted"
    ]

    private init() {
        let root = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        directory = root.appendingPathComponent("ScarletCrystal/Diagnostics", isDirectory: true)
        try? fm.createDirectory(at: directory, withIntermediateDirectories: true)
        var excluded = directory
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try? excluded.setResourceValues(values)
        // Rotate once when the recorder starts for this app process.
        // Old V37 session.jsonl is archived, never appended by V38.
        let current = directory.appendingPathComponent("session.jsonl")
        if fm.fileExists(atPath: current.path) {
            for index in stride(from: retainedFiles - 1, through: 1, by: -1) {
                let previous = directory.appendingPathComponent(
                    index == 1 ? "session.jsonl" : "session.\(index - 1).jsonl")
                let next = directory.appendingPathComponent("session.\(index).jsonl")
                if fm.fileExists(atPath: next.path) { try? fm.removeItem(at: next) }
                if fm.fileExists(atPath: previous.path) {
                    try? fm.moveItem(at: previous, to: next)
                }
            }
        }
        fm.createFile(atPath: current.path, contents: nil)
    }

    private func logURL(_ index: Int = 0) -> URL {
        directory.appendingPathComponent(index == 0 ? "session.jsonl" : "session.\(index).jsonl")
    }

    private static func sanitized(_ source: String) -> String {
        // Keep protocol-independent error categories and numbers, not payloads.
        let candidate = String(source.prefix(80))
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
        if !candidate.unicodeScalars.allSatisfy({ allowed.contains($0) }) {
            return "[REDACTED]"
        }
        // Reject even syntactically well-formed high entropy secrets and IDs.
        if candidate.count > 54 || candidate.contains("@") ||
            (candidate.count >= 24 && candidate.rangeOfCharacter(from: .decimalDigits) != nil) {
            return "[REDACTED]"
        }
        return candidate
    }

    func guestReference(_ identifier: String) -> String {
        let digest = SHA256.hash(data: Data((salt + ":" + identifier).utf8))
        return digest.prefix(6).map { String(format: "%02x", $0) }.joined()
    }

    func record(_ category: String, _ event: String, status: String = "info",
                fields: [String: String] = [:]) {
        lock.lock()
        defer { lock.unlock() }
        sequence += 1
        let safeFields = Dictionary(uniqueKeysWithValues: fields.compactMap { key, value -> (String, String)? in
            guard Self.allowedFields.contains(key) else { return nil }
            return (key, Self.sanitized(value))
        })
        let timestamp = ISO8601DateFormatter()
        timestamp.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let payload: [String: Any] = [
            "schema": 1, "time": timestamp.string(from: Date()),
            "session": sessionID, "seq": sequence,
            "category": Self.sanitized(category),
            "event": Self.sanitized(event),
            "status": Self.sanitized(status),
            "fields": safeFields
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
              data.count < 8192 else { return }
        let dest = logURL()
        let currentBytes = (try? fm.attributesOfItem(
            atPath: dest.path)[.size] as? NSNumber)?.intValue ?? 0
        if currentBytes + data.count + 1 > maxFileBytes,
           let previous = try? Data(contentsOf: dest) {
            // Trim only this launch's journal; never mix old process
            // entries into a newly rotated "session" file.
            let tail = Data(previous.suffix(maxFileBytes / 2))
            if let firstNewline = tail.firstIndex(of: 10) {
                try? Data(tail.suffix(from: firstNewline + 1))
                    .write(to: dest, options: .atomic)
            }
        }
        if !fm.fileExists(atPath: dest.path) {
            fm.createFile(atPath: dest.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: dest) {
            handle.seekToEndOfFile()
            handle.write(data)
            handle.write(Data([10]))
            handle.closeFile()
        }
        NSLog("[SCARLET_DIAG] category=%@ event=%@ status=%@ seq=%llu",
              Self.sanitized(category), Self.sanitized(event),
              Self.sanitized(status), sequence)
    }

    func recordError(_ category: String, _ event: String, error: Error) {
        let code = error as NSError
        record(category, event, status: "error",
               fields: ["domain": code.domain, "code": String(code.code)])
    }

    func readRecent(maxLines: Int = 350) -> String {
        readRecent(maxLines: maxLines, includeHistory: false)
    }

    func readRecent(maxLines: Int, includeHistory: Bool) -> String {
        lock.lock()
        defer { lock.unlock() }
        var all: [String] = []
        let indices = includeHistory
            ? Array((0..<retainedFiles).reversed()) : [0]
        for index in indices {
            if let body = try? String(contentsOf: logURL(index), encoding: .utf8) {
                all.append(contentsOf: body.split(separator: "\n").map(String.init))
            }
        }
        return all.suffix(maxLines).joined(separator: "\n")
    }

    // Build-time embedded, version-pinned, immutable remediation log.
    // The current-run JSONL remains small and privacy filtered. Only the
    // explicit user-shared report includes historical code diffs/prompt.
    // CI replaces both markers with base64 of repo-tracked audited sources.
    private static let remediationHistoryBlob = "__SCARLET_REMEDIATION_HISTORY_B64__"
    private static let handoffPromptBlob = "__SCARLET_HANDOFF_PROMPT_B64__"
    private static func decodedAudit(_ base64: String) -> String {
        guard let data = Data(base64Encoded: base64),
              let text = String(data: data, encoding: .utf8) else {
            return "EMBEDDED_AUDIT_UNAVAILABLE: missing or invalid archive payload."
        }
        return text
    }

    func makeShareFile(includeHistory: Bool = false) -> URL? {
        lock.lock()
        defer { lock.unlock() }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let file = fm.temporaryDirectory.appendingPathComponent(
            "Scarlet-Crystal-\(includeHistory ? "History" : "CurrentRun")-\(formatter.string(from: Date())).txt")
        var body = """
        Scarlet Crystal · 사용자 요청 진단 보고서
        Generated: \(Date())
        App: \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown")
        Build: \(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown")
        SourceCommit: \(Self.buildCommit)
        OS: \(ProcessInfo.processInfo.operatingSystemVersionString)
        Collection: local-only JSONL, no credentials/OTP/UDID/guest names
        LogScope: \(includeHistory ? "current launch + archived launches" : "CURRENT LAUNCH ONLY")
        CurrentSession: \(sessionID)
        CurrentLaunchAt: \(launchedAt)
        Note: iOS fatal crash .ips is generated by iOS and may need separate collection.

        """
        let indices = includeHistory
            ? Array((0..<retainedFiles).reversed()) : [0]
        for index in indices {
            if let chunk = try? String(contentsOf: logURL(index), encoding: .utf8), !chunk.isEmpty {
                body += "\n===== \(index == 0 ? "CURRENT RUN" : "ARCHIVED RUN \(index)") · session.\(index).jsonl =====\n"
                body += chunk
            }
        }
        // R6P10: full immutable fix history, including where/how each line
        // was changed. This survives log rotation and app restarts because
        // it is bundled into the signed binary; not the rolling JSONL.
        body += "\n===== REMEDIATION HISTORY · FILE/FUNCTION/BEFORE/AFTER DIFF =====\n"
        body += Self.decodedAudit(Self.remediationHistoryBlob)
        body += "\n===== NO-REPEAT POLICY & AI HANDOFF PROMPT =====\n"
        body += Self.decodedAudit(Self.handoffPromptBlob)
        body += "\n===== END OF EMBEDDED AUDIT =====\n"
        do {
            try body.write(to: file, atomically: true, encoding: .utf8)
            return file
        } catch {
            return nil
        }
    }
}

@available(iOS 16.0, *)
struct ScarletDiagnosticLogView: View {
    @State private var text = "기록된 이벤트가 없습니다."
    @State private var shareFile: URL?
    @State private var includeHistory = false

    private func reload() {
        // A returned guest can hand off without a fresh host .onAppear.
        // Import shared guest hook/switcher events whenever logs are opened.
        if #available(iOS 17.0, *) {
            ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()
            ScarletGuestSessionLedger.replayGuestLaunchPolicyToHostJournal()
        }
        ScarletDiagnosticRecorder.shared.record("diagnostics", "viewer_opened")
        let content = ScarletDiagnosticRecorder.shared.readRecent(
            maxLines: 350, includeHistory: includeHistory)
        text = content.isEmpty ? "기록된 이벤트가 없습니다." : content
        shareFile = ScarletDiagnosticRecorder.shared.makeShareFile(
            includeHistory: includeHistory)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("기본값은 이번 실행 로그만 표시·공유합니다. 이전 실행 기록은 직접 선택했을 때만 포함됩니다. 암호·인증번호·Apple ID는 기록하지 않습니다.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            Picker("로그 범위", selection: $includeHistory) {
                Text("이번 실행").tag(false)
                Text("이전 기록 포함").tag(true)
            }
            .pickerStyle(.segmented)
            .onChange(of: includeHistory) { _ in reload() }
            .accessibilityIdentifier("SCARLET_DIAGNOSTICS_LOG_SCOPE")
            HStack(spacing: 12) {
                Button {
                    reload()
                } label: {
                    Label("새로고침", systemImage: "arrow.clockwise")
                }
                .accessibilityIdentifier("SCARLET_DIAGNOSTICS_REFRESH")
                if let shareFile {
                    ShareLink(item: shareFile) {
                        Label("로그 공유", systemImage: "square.and.arrow.up")
                    }
                    .accessibilityIdentifier("SCARLET_DIAGNOSTICS_SHARE")
                }
            }
            .buttonStyle(.bordered)
            ScrollView {
                Text(text)
                    .font(.system(size: 11, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            Text("치명적인 iOS 종료는 앱 내부 기록이 중단될 수 있습니다. 그때는 iPhone 분석 데이터의 .ips 보고서도 필요합니다.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .navigationTitle("진단 로그")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear(perform: reload)
        .accessibilityIdentifier("SCARLET_DIAGNOSTICS_VIEW")
    }
}

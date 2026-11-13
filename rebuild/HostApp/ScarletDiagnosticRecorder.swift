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
        "domain", "count", "duration_ms", "elapsed_ms", "width_pt", "height_pt",
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
        "policy_fields_received", "policy_fields_persisted",
        // R6P11: anonymous guest Mach-O SDK contract, no identifier/path.
        "sdk_major", "sdk_minor", "sdk_source",
        // Guest-owned UIKit readback only; no names, screenshots or bundle IDs.
        "guest_root_top_pt", "guest_root_after_pt",
        // R6P18: anonymous, bounded guest descendant geometry only; all
        // strings and identifiers remain excluded by the recorder whitelist.
        "slot_top_pt", "slot_y_pt", "slot_height_pt",
        "host_width_pt", "host_height_pt", "scale_milli", "chrome_touches",
        "remote_content_height_pt", "hosting_safe_top_pt",
        "chrome_dark_status_text", "status_style_raw", "surface_tone",
        "root_safe_top_pt", "root_frame_y", "root_guide_y", "visited",
        "candidate_controls", "top_controls", "unsafe_controls",
        "first_top_control_y", "first_unsafe_control_y",
        "scroll_top_without_inset", "scroll_first_y", "scan_capped",
        "top_text_nodes", "unsafe_text_nodes", "first_unsafe_text_y",
        "top_image_nodes", "unsafe_image_nodes", "first_unsafe_image_y",
        "max_depth_seen", "depth_capped", "count_capped",
        // R6P23: bounded read-only ancestry and scroll-selection predicates.
        "unsafe_controls_in_scroll", "unsafe_controls_outside_scroll",
        // R6P26: R6P25 native guest/host packets contained four bounded
        // counters, but the final recorder silently dropped all four.
        "visible_unsafe_controls", "clipped_unsafe_controls",
        "visible_unsafe_images", "clipped_unsafe_images",
        "unsafe_controls_under_zero_inset_child_owner",
        "unsafe_image_nodes_in_scroll", "unsafe_image_nodes_outside_scroll",
        "seen", "nested", "not_top_full_width", "not_vertical",
        "existing_inset", "not_at_top", "busy",
        "missing_unsafe_descendant", "eligible", "scan_budget_exhausted",
        // R6P27: bounded ownership metrics; no UIView names or identifiers.
        "owner_groups", "owner_dominant_controls", "owner_dominant_images",
        "owner_tie", "owner_frame_y", "owner_frame_width_pct",
        "owner_frame_height_pct", "owner_adjusted_inset_top",
        "owner_content_inset_top", "owner_offset_y",
        "owner_adjustment_behavior", "owner_nested_scrolls",
        "owner_scroll_enabled", "owner_content_height_pct", "owner_safe_top",
        // R6P29: UIKit-automatic residual owner readback; no identifiers.
        "owner_auto_before_pt", "owner_auto_after_pt",
        "candidate_with_controls", "candidate_frame_matched",
        "candidate_safe_matched", "candidate_inset_matched",
        "candidate_content_matched", "candidate_state_matched",
        "candidate_disabled_scroll", "owner_gate_pass",
        "anchor_initial_inset_pt", "anchor_initial_offset_y",
        "anchor_observed_inset_pt", "anchor_observed_offset_y",
        "anchor_final_offset_y", "anchor_attempts",
        "owner_bounds_y", "scene_activation_state",
        "node_slot", "scroll_slot", "node_window_x", "node_window_width", "node_window_height", "node_window_y",
                    "node_window_bottom", "node_owner_y", "node_local_y",
                    "node_autoresizing", "node_ambiguous", "node_in_navbar",
                    "controller_safe_top", "constraint_count", "constraint_inspected",
                    "constraint_frame_refs", "constraint_content_refs", "constraint_safe_refs",
                    "constraint_external_refs", "constraint_center_refs", "constraint_other_refs",
                    "constraint_first_attribute", "constraint_other_attribute", "constraint_first_relation",
                    "constraint_first_constant", "constraint_first_priority", "constraint_scan_capped",
                    "probe_nodes_capped", "native_error_stage", "native_error_domain",
                    "native_error_code", "native_error_kind", "native_underlying_domain",
                    "native_underlying_code", "native_underlying_kind", "native_error_depth",
        // R6P35: exact per-ancestor coordinate lineage of severely unsafe
        // controls, no classes/names/labels or arbitrary strings.
        "selected_nodes", "owner_reached_nodes", "root_reached_nodes",
        "ancestor_rows_capped", "ancestor_slot", "ancestor_depth",
        "ancestor_window_y", "ancestor_parent_window_y",
        "ancestor_local_y", "ancestor_guide_y", "ancestor_safe_top",
        "ancestor_bounds_y", "ancestor_height",
        "ancestor_vertical_constraints", "ancestor_autoresize_mask",
        "ancestor_translates", "ancestor_is_controller_root",
        "ancestor_controller_safe_top", "ancestor_is_scroll",
        "ancestor_is_control", "ancestor_clips", "ancestor_has_transform",
        "ancestor_is_owner", "ancestor_is_root",
        // R6P36: bounded reasons for missing time-scoped guest readbacks.
        "probe_window_present", "probe_window_visible",
        "probe_window_normal", "probe_scene_present",
        "probe_scene_state", "probe_portrait", "probe_root_present",
        "probe_root_match", "probe_root_attached",
        "probe_root_safe_top", "probe_replacement",
        // R6P37: anonymous proof of only the 50pt nested header owner.
        "header_before_y", "header_after_y", "header_controls_before",
        "header_controls_after", "header_images_after", "header_gate_pass",
        // R6P38: numeric parent contract and constraint endpoints only.
        "header_ambiguous", "header_autoresize_mask", "header_constraint_autoresizing",
        "header_constraint_constant", "header_constraint_first_attr", "header_constraint_first_kind",
        "header_constraint_holder", "header_constraint_mask_known", "header_constraint_multiplier_milli",
        "header_constraint_priority", "header_constraint_relation", "header_constraint_second_attr",
        "header_constraint_second_kind", "header_constraint_source", "header_constraints_capped",
        "header_constraints_inspected", "header_constraints_relevant", "header_controller_layout_impl_origin",
        "header_controller_parent_match", "header_edges", "header_height",
        "header_layout_impl_origin", "header_local_y", "header_parent_autoresizes",
        "header_parent_controller_layout_impl_origin", "header_parent_edges", "header_parent_guide_y",
        "header_parent_layout_impl_origin", "header_parent_layout_override", "header_parent_prefers_status_hidden",
        "header_parent_slot", "header_prefers_status_hidden", "header_probe_status",
        "header_scene_status_height", "header_scene_status_hidden", "header_setbounds_impl_origin",
        "header_setcenter_impl_origin", "header_setframe_impl_origin", "header_severe_nodes",
        "header_slot", "header_translates", "header_window_y",
        "header_constraint_index",
        // P45: no guest identity, text or view class. Show true cause of
        // losing full native scroll surface after a P44 transform pass.
        "header_current_y", "header_checked_controls",
        "header_visible_controls", "header_unsafe_controls",
        "header_affine_retained", "header_invalidation_reason"
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
        var fields = ["domain": code.domain, "code": String(code.code)]
        if code.domain == "SideStoreSupport.ScarletNativeRefreshFailure",
           let native = code.userInfo["ScarletNativeRefreshEvidence"] as? [String: String] {
            for key in [
                "native_error_stage", "native_error_domain", "native_error_code",
                    "native_error_kind", "native_underlying_domain", "native_underlying_code",
                    "native_underlying_kind", "native_error_depth"
            ] {
                if let value = native[key] { fields[key] = value }
            }
        }
        record(category, event, status: "error", fields: fields)
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

    // Put decisions BEFORE verbose JSONL: truncated previews must still
    // show R6P9+ attempts, their mechanisms and changed source files.
    private static func remediationDecisionIndex() -> String {
        guard let bytes = Data(base64Encoded: remediationHistoryBlob),
              let document = try? JSONSerialization.jsonObject(with: bytes)
                  as? [String: Any],
              let entries = document["entries"] as? [[String: Any]]
        else { return "AUDIT_INDEX_UNAVAILABLE: embedded history missing.\n" }
        var rows = [
            "PRE-EDIT GATE: compare problem, causal mechanism and exact code diff.",
            "Renamed functions, version labels or timings are NOT new solutions.",
            "Complete before/after changed source remains in appended history.",
            "Historical attempts: \(entries.count)",
            "All historical attempts (oldest first):"
        ]
        for attempt in entries {
            let id = attempt["id"] as? String ?? "?"
            let version = attempt["version"] as? String ?? "?"
            let issue = attempt["problem"] as? String ?? "?"
            let mechanism = attempt["mechanism"] as? String ?? "?"
            let status = attempt["status"] as? String ?? "?"
            let changes = attempt["code_locations"] as? [[String: Any]] ?? []
            let files = Set(changes.compactMap { change -> String? in
                guard let path = change["file"] as? String else { return nil }
                return path.components(separatedBy: "/").last
            }).sorted()
            let sources = files.isEmpty ? "source_unavailable"
                : files.joined(separator: ",")
            rows.append("\(id) | \(version) | \(issue) | \(mechanism) | \(status) | \(sources)")
        }
        rows.append("Inspect the full JSON and handoff prompt before code edits.")
        return rows.joined(separator: "\n") + "\n"
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
        body += "\n===== NO-REPEAT DECISION INDEX · READ BEFORE EDIT =====\n"
        body += Self.remediationDecisionIndex()
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
            ScarletGuestSessionLedger.replayGuestSDKContractToHostJournal()
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

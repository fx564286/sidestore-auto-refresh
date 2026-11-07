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
    private let maxFileBytes = 1_500_000
    private let retainedFiles = 4
    private static let allowedFields: Set<String> = [
        "action", "tab", "result", "reason", "status", "state", "code",
        "domain", "count", "duration_ms", "width_pt", "height_pt",
        "safe_top_pt", "safe_bottom_pt", "orientation", "engine",
        "available", "stage", "guest_ref", "window_attached",
        "scene", "os_major", "os_minor", "physical_memory_mb",
        "certificate_present", "password_present", "team_match", "build_sha"
    ]

    private init() {
        let root = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        directory = root.appendingPathComponent("ScarletCrystal/Diagnostics", isDirectory: true)
        try? fm.createDirectory(at: directory, withIntermediateDirectories: true)
        var excluded = directory
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try? excluded.setResourceValues(values)
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
        if (try? fm.attributesOfItem(atPath: dest.path)[.size] as? NSNumber)?.intValue ?? 0 > maxFileBytes {
            // Retain four bounded journals and never remove app/guest data.
            for index in stride(from: retainedFiles - 1, through: 1, by: -1) {
                let previous = logURL(index - 1)
                let next = logURL(index)
                if fm.fileExists(atPath: next.path) { try? fm.removeItem(at: next) }
                if fm.fileExists(atPath: previous.path) { try? fm.moveItem(at: previous, to: next) }
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
        lock.lock()
        defer { lock.unlock() }
        var all: [String] = []
        for index in (0..<retainedFiles).reversed() {
            if let body = try? String(contentsOf: logURL(index), encoding: .utf8) {
                all.append(contentsOf: body.split(separator: "\n").map(String.init))
            }
        }
        return all.suffix(maxLines).joined(separator: "\n")
    }

    func makeShareFile() -> URL? {
        lock.lock()
        defer { lock.unlock() }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let file = fm.temporaryDirectory.appendingPathComponent(
            "Scarlet-Crystal-Diagnostics-\(formatter.string(from: Date())).txt")
        var body = """
        Scarlet Crystal · 사용자 요청 진단 보고서
        Generated: \(Date())
        App: \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown")
        Build: \(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown")
        SourceCommit: \(Self.buildCommit)
        OS: \(ProcessInfo.processInfo.operatingSystemVersionString)
        Collection: local-only JSONL, no credentials/OTP/UDID/guest names
        Note: iOS fatal crash .ips is generated by iOS and may need separate collection.

        """
        for index in (0..<retainedFiles).reversed() {
            if let chunk = try? String(contentsOf: logURL(index), encoding: .utf8), !chunk.isEmpty {
                body += "\n===== session.\(index).jsonl =====\n"
                body += chunk
            }
        }
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

    private func reload() {
        ScarletDiagnosticRecorder.shared.record("diagnostics", "viewer_opened")
        let content = ScarletDiagnosticRecorder.shared.readRecent()
        text = content.isEmpty ? "기록된 이벤트가 없습니다." : content
        shareFile = ScarletDiagnosticRecorder.shared.makeShareFile()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("앱 실행, 탭 전환, 게스트 실행, 설치 요청, 인증 연결 상태와 오류 코드를 기록합니다. 암호·인증번호·Apple ID는 기록하지 않습니다.")
                .font(.footnote)
                .foregroundStyle(.secondary)
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

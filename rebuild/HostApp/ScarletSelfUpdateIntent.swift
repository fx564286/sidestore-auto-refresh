// Foreground App Intent, no Minis, no shell or arbitrary download URL.
import AppIntents
import Foundation
import CryptoKit
import SideStoreSupport
import UserNotifications

@available(iOS 17.0, *)
public struct ScarletSelfUpdateIntentsPackage: AppIntentsPackage {}

@available(iOS 17.0, *)
public struct ScarletSelfUpdateIntent: AppIntent {
    public static let title: LocalizedStringResource = "Scarlet Crystal 업데이트"
    public static let description: IntentDescription? = IntentDescription("공식 릴리스의 새 버전을 확인하고 내장 SideStore로 업데이트합니다.")
    public static let openAppWhenRun = true

    public init() {}
    @MainActor public func perform() async throws -> some IntentResult & ProvidesDialog {
        let message = await ScarletSelfUpdate.run()
        return .result(dialog: IntentDialog(stringLiteral: message))
    }
}

@available(iOS 17.0, *)
@MainActor
enum ScarletSelfUpdate {
    private static let repository = "fx564286/sidestore-auto-refresh"
    private static let baseID = "com.kdt.livecontainer.P8EZT3U5N4"
    private static let ticketKey = "Scarlet.SelfUpdate.Pending.V133"
    private static let maxIPA = 150 * 1024 * 1024
    private(set) static var isRunning = false

    private struct Asset: Decodable, Sendable {
        let name: String
        let size: Int
        let digest: String?
        let browser_download_url: URL
    }
    private struct Release: Decodable, Sendable {
        let tag_name: String
        let draft: Bool
        let assets: [Asset]
    }
    private struct Manifest: Decodable, Sendable {
        let schema: Int
        let version: String
        let sourceCommit: String
        let sha256: String
        let bundleIdentifier: String
        let asset: String
        let size: Int
        let signed: Bool
        let deviceVerified: Bool
    }
    private struct Candidate: Sendable {
        let build: Int
        let tag: String
        let manifest: Asset
    }
    private enum UpdateError: Error {
        case invalidRelease, invalidArchive, ownerChanged
    }

    private static func build(_ value: String) -> Int? {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3, parts[0] == "3", parts[1] == "8",
              let number = Int(parts[2]), number > 0, number <= 999999,
              value == "3.8.\(number)" else { return nil }
        return number
    }
    private static func currentBuild() -> Int? {
        (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String).flatMap(build)
    }
    private static func isSHA(_ value: String, length: Int) -> Bool {
        value.utf8.count == length && value.utf8.allSatisfy {
            (48...57).contains($0) || (97...102).contains($0)
        }
    }
    private static func downloadURL(tag: String, name: String) -> URL? {
        guard tag.range(of: "^scarlet-v48-r6p[0-9]+-[a-z0-9-]+-unsigned-[0-9]{8}$",
                        options: .regularExpression) != nil,
              name.range(of: "^[A-Za-z0-9._-]+$", options: .regularExpression) != nil else { return nil }
        return URL(string: "https://github.com/\(repository)/releases/download/\(tag)/\(name)")
    }
    private static func validResponse(_ response: URLResponse, api: Bool = false) -> Bool {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200,
              let url = http.url, url.scheme == "https", let host = url.host else { return false }
        return api ? host == "api.github.com" :
            ["github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"].contains(host)
    }
    private static func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
    private nonisolated static func fileDigest(_ file: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        var hash = SHA256()
        while let block = try handle.read(upToCount: 1024 * 1024), !block.isEmpty {
            try Task.checkCancellation()
            hash.update(data: block)
        }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
    private static func select(_ releases: [Release]) throws -> (Candidate, Release)? {
        var matches: [(Candidate, Release)] = []
        for release in releases where !release.draft {
            let tag = release.tag_name
            let prefix = "scarlet-v48-r6p"
            guard tag.hasPrefix(prefix),
                  let number = Int(tag.dropFirst(prefix.count).prefix(while: { $0.isASCII && $0.isNumber })),
                  number >= 133,
                  let manifestURL = downloadURL(tag: tag, name: "scarlet-update.json") else { continue }
            let manifests = release.assets.filter { $0.name == "scarlet-update.json" }
            if manifests.isEmpty { continue } // historical diagnostic builds are not update channels
            guard manifests.count == 1, let asset = manifests.first,
                  asset.browser_download_url == manifestURL, (1...16384).contains(asset.size),
                  let digest = asset.digest, digest.hasPrefix("sha256:"),
                  isSHA(String(digest.dropFirst(7)), length: 64) else { throw UpdateError.invalidRelease }
            matches.append((Candidate(build: number, tag: tag, manifest: asset), release))
        }
        let ordered = matches.sorted { $0.0.build > $1.0.build }
        if ordered.count > 1 && ordered[0].0.build == ordered[1].0.build { throw UpdateError.invalidRelease }
        return ordered.first
    }

    static func run() async -> String {
        guard !isRunning else { return "Scarlet 업데이트가 이미 진행 중입니다." }
        guard let currentBuild = currentBuild() else { return "현재 앱 버전을 확인할 수 없습니다." }
        // The host itself must be authorized; do not install another Team's copy.
        guard ScarletSigningReadiness.inspect().canRequestNativeRefresh,
              let group = ScarletSigningReadiness.authorizedSideStoreGroupID(),
              let root = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group),
              UserDefaults.sideStoreExist() else {
            return "Scarlet의 서명 및 내장 SideStore 권한을 먼저 확인하세요."
        }
        isRunning = true
        defer { isRunning = false }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 180
        configuration.httpAdditionalHeaders = ["User-Agent": "ScarletCrystal-Update"]
        let session = URLSession(configuration: configuration)
        defer { session.invalidateAndCancel() }
        var dispatched = false
        do {
            let endpoint = URL(string: "https://api.github.com/repos/fx564286/sidestore-auto-refresh/releases?per_page=100")!
            let (catalog, response) = try await session.data(from: endpoint)
            guard validResponse(response, api: true), catalog.count <= 8 * 1024 * 1024 else {
                throw UpdateError.invalidRelease
            }
            let releases = try JSONDecoder().decode([Release].self, from: catalog)
            guard let (candidate, release) = try select(releases) else {
                return "검증된 업데이트 릴리스가 아직 없습니다."
            }
            guard currentBuild < candidate.build else { return "검증된 릴리스 기준 최신 버전입니다. (3.8.\(currentBuild))" }
            let (manifestBytes, manifestResponse) = try await session.data(from: candidate.manifest.browser_download_url)
            guard validResponse(manifestResponse), manifestBytes.count == candidate.manifest.size,
                  "sha256:" + digest(manifestBytes) == candidate.manifest.digest else {
                throw UpdateError.invalidRelease
            }
            let manifest = try JSONDecoder().decode(Manifest.self, from: manifestBytes)
            let expectedVersion = "3.8.\(candidate.build)"
            guard manifest.schema == 1, manifest.version == expectedVersion,
                  manifest.bundleIdentifier == baseID, !manifest.signed, !manifest.deviceVerified,
                  isSHA(manifest.sourceCommit, length: 40), isSHA(manifest.sha256, length: 64),
                  manifest.asset.hasPrefix("Scarlet-Crystal-V48-R6P\(candidate.build)-"),
                  manifest.asset.hasSuffix("-UNSIGNED.ipa"),
                  (1_000_000...maxIPA).contains(manifest.size),
                  let url = downloadURL(tag: candidate.tag, name: manifest.asset) else {
                throw UpdateError.invalidRelease
            }
            let assets = release.assets.filter { $0.name == manifest.asset }
            guard assets.count == 1, let asset = assets.first, asset.browser_download_url == url,
                  asset.size == manifest.size, asset.digest == "sha256:" + manifest.sha256 else {
                throw UpdateError.invalidRelease
            }
            let accountSnapshot = await ScarletNativeSavedAccounts.list()
            let active = accountSnapshot.accounts.filter { $0.active }
            guard accountSnapshot.status == "ready", active.count == 1,
                  let account = active.first, account.ownerVerified, account.certificateReady,
                  group == "group.com.SideStore.SideStore." + account.teamID else {
                return "현재 Scarlet 서명팀과 동일한 Apple ID 및 유효한 인증서를 설정에서 확인하세요."
            }
            let scope = digest(Data((account.id.trimmingCharacters(in: .whitespacesAndNewlines)
                .lowercased() + "|" + account.teamID).utf8))
            let directory = root.appendingPathComponent("ScarletDeviceInstall/accounts/" + scope, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let staged = directory.appendingPathComponent("scarlet-self-update-\(UUID().uuidString).ipa")
            let (temporary, downloadResponse) = try await session.download(from: url)
            defer { try? FileManager.default.removeItem(at: temporary) }
            guard validResponse(downloadResponse),
                  (try temporary.resourceValues(forKeys: [.fileSizeKey])).fileSize == manifest.size else {
                throw UpdateError.invalidArchive
            }
            try FileManager.default.moveItem(at: temporary, to: staged)
            defer { try? FileManager.default.removeItem(at: staged) }
            let actual = try await Task.detached(priority: .utility) {
                try Self.fileDigest(staged)
            }.value
            guard actual == manifest.sha256 else { throw UpdateError.invalidArchive }
            try Task.checkCancellation()
            let verified = await ScarletNativeSavedAccounts.list()
            let owners = verified.accounts.filter { $0.active }
            guard verified.status == "ready", owners.count == 1,
                  owners[0].id == account.id, owners[0].teamID == account.teamID,
                  owners[0].ownerVerified, owners[0].certificateReady,
                  ScarletSigningReadiness.authorizedSideStoreGroupID() == group else {
                throw UpdateError.ownerChanged
            }
            try Task.checkCancellation()
            UserDefaults.standard.set(["version": expectedVersion, "source": manifest.sourceCommit,
                                       "bundle": Bundle.main.bundleIdentifier ?? "",
                                       "scope": scope, "file": staged.lastPathComponent], forKey: ticketKey)
            dispatched = true
            ScarletDiagnosticRecorder.shared.record("sidestore", "shortcut_update_dispatched",
                fields: ["source": "shortcut", "installation_verified": "false"])
            // Self installation can terminate the current process before the
            // callback. A persistent ticket is verified on next host launch.
            try await ScarletDeviceInstaller.install(stagedIPA: staged, teamID: account.teamID,
                hostGroupID: group, selfUpdateHostPath: Bundle.main.bundleURL.path,
                selfUpdateVersion: expectedVersion, selfUpdateSHA256: manifest.sha256)
            ScarletDiagnosticRecorder.shared.record("sidestore", "shortcut_update_returned",
                fields: ["source": "shortcut", "installation_verified": "false"])
            return "설치 엔진 요청이 반환됐습니다. Scarlet을 다시 열어 새 버전을 확인하세요."
        } catch {
            // Keep the ticket after dispatch: an interrupted response is not
            // evidence that the native installer failed to commit the build.
            let reason: String
            if let category = error as? UpdateError {
                switch category {
                case .invalidRelease: reason = "update_release_invalid"
                case .invalidArchive: reason = "update_archive_invalid"
                case .ownerChanged: reason = "active_account_changed_before_install"
                }
            } else if error is CancellationError {
                reason = "update_cancelled"
            } else {
                reason = dispatched ? "update_worker_unverified" : "update_transport_failed"
            }
            ScarletDiagnosticRecorder.shared.record("sidestore", "shortcut_update_failed",
                status: "error", fields: ["source": "shortcut", "reason": reason,
                                          "installation_verified": "false"])
            // Do not log raw network errors, paths or account identity.
            return dispatched
                ? "설치 결과가 아직 확인되지 않았습니다. Scarlet을 다시 열어 버전을 확인하세요."
                : "업데이트 요청이 차단됐습니다. Scarlet 진단 로그를 확인하세요."
        }
    }

    static func verifyInstalledBuild() {
        guard let ticket = UserDefaults.standard.dictionary(forKey: ticketKey),
              let version = ticket["version"] as? String,
              let source = ticket["source"] as? String,
              let bundle = ticket["bundle"] as? String,
              Bundle.main.bundleIdentifier == bundle,
              Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String == version,
              ScarletDiagnosticRecorder.buildSourceStamp == "scarlet-source-commit:" + source,
              ScarletSigningReadiness.inspect().canRequestNativeRefresh else { return }
        // A self-reinstall can kill the old process before its staging defer.
        // Remove only the exact UUID file referenced by the verified ticket.
        if let scope = ticket["scope"] as? String, isSHA(scope, length: 64),
           let file = ticket["file"] as? String, file.hasPrefix("scarlet-self-update-"),
           file.hasSuffix(".ipa"),
           UUID(uuidString: String(file.dropFirst("scarlet-self-update-".count).dropLast(4))) != nil,
           let group = ScarletSigningReadiness.authorizedSideStoreGroupID(),
           let root = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group) {
            let directory = root.appendingPathComponent("ScarletDeviceInstall/accounts/" + scope, isDirectory: true)
            let staged = directory.appendingPathComponent(file)
            if staged.resolvingSymlinksInPath().deletingLastPathComponent() == directory.resolvingSymlinksInPath() {
                try? FileManager.default.removeItem(at: staged)
            }
        }
        UserDefaults.standard.removeObject(forKey: ticketKey)
        ScarletDiagnosticRecorder.shared.record("sidestore", "shortcut_update_installed_build_verified",
            fields: ["source": "shortcut", "installation_verified": "true"])
        // Use existing notification permission; never require it for installation.
        Task { @MainActor in
            let center = UNUserNotificationCenter.current()
            let settings = await center.notificationSettings()
            guard settings.authorizationStatus == .authorized ||
                  settings.authorizationStatus == .provisional else { return }
            let content = UNMutableNotificationContent()
            content.title = "Scarlet Crystal 업데이트 확인"
            content.body = "설치된 버전 " + version + "의 실행을 확인했습니다."
            try? await center.add(UNNotificationRequest(identifier: "scarlet.update." + version,
                content: content, trigger: nil))
        }
    }
}

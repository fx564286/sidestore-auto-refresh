// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI
import UIKit
import UniformTypeIdentifiers
import Security

// Host-owned task state survives dismissing or reopening a progress sheet.
// The original LC importer remains responsible for actual guest installation.
@MainActor
final class ScarletGuestImportActivity: ObservableObject {
    enum Phase: Equatable {
        case idle, importing, imported, signingUnverified, failed
    }
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var progress: Double = 0

    var isRunning: Bool { phase == .importing }
    var hasActivity: Bool { phase != .idle }
    var title: String {
        switch phase {
        case .idle: return ""
        case .importing: return "게스트 앱 가져오는 중"
        case .imported: return "게스트 앱 가져오기 완료"
        case .signingUnverified: return "서명 확인이 필요합니다"
        case .failed: return "게스트 앱 가져오기 실패"
        }
    }
    var detail: String {
        switch phase {
        case .idle: return ""
        case .importing: return "창을 내려도 가져오기가 계속됩니다."
        case .imported: return "가져오기 완료 · 실제 실행은 별도 확인"
        case .signingUnverified: return "가져왔지만 JIT-Less 서명 확인이 필요합니다."
        case .failed: return "원본 LiveContainer 가져오기에서 오류가 발생했습니다."
        }
    }
    func start() {
        progress = 0
        phase = .importing
        ScarletDiagnosticRecorder.shared.record("guest_import", "worker_started",
            fields: ["owner": "host_view"])
    }
    func update(_ value: Double) {
        guard isRunning else { return }
        progress = min(1, max(0, value))
    }
    func finish(signingUnverified: Bool, failed: Bool) {
        guard isRunning else { return }
        phase = failed ? .failed :
            (signingUnverified ? .signingUnverified : .imported)
        ScarletDiagnosticRecorder.shared.record("guest_import", "worker_finished",
            status: failed ? "error" : (signingUnverified ? "warning" : "info"),
            fields: ["result": failed ? "import_failed" :
                (signingUnverified ? "imported_signing_unverified" : "imported_launch_unverified")])
    }
}

@available(iOS 17.0, *)
struct ScarletIntegratedHostView: View {
    @Environment(\.scenePhase) private var scenePhase
    @EnvironmentObject private var sharedModel: SharedModel
    // Guest window enumeration is sourced lazily from the live scene registry.
    // Avoid initializing the dock before UIWindow and its view tree exist.
    @StateObject private var downloadHelper = DownloadHelper()
    @StateObject private var originalSources = AltStoreSourcesViewModel()
    @StateObject private var guestImportActivity = ScarletGuestImportActivity()
    // A single Files picker serves both explicitly selected installation routes.
    private enum IPAInstallRoute { case guest, device }
    @State private var pendingIPAInstallRoute: IPAInstallRoute = .guest
    @State private var showGuestFilePicker = false
    @State private var showGuestImportProgress = false
    @State private var queuedGuestIPAURL: URL?
    @State private var installProgressMinimized = false
    @State private var showNativeSources = false
    @State private var showSourceURLInput = false
    @State private var newSourceURL = ""
    @State private var sourceIsSaving = false
    @State private var sourceIsDownloading = false
    @State private var sourceDownloadTask: Task<Void, Never>?
    @State private var showSourceDownloadSheet = false
    @State private var sourceDownloadStage = "IPA 서버에 연결 중"
    @State private var sourceDownloadError: String?
    @State private var sourceDownloadedIPA: URL?
    @State private var sourceInputError: String?
    @State private var showScarletAppleIDLogin = false
    @State private var appleAuthVerified = false
    // Ignore delayed auth readbacks after a newer foreground/login transition.
    @State private var authStateReadGeneration: UInt64 = 0
    @State private var showOriginalError: String?
    @State private var signingRecoveryNeeded = false
    @State private var launchingGuestKeys: Set<String> = []
    // Guest removal never alters data containers, Keychain or certificates.
    @State private var pendingGuestUninstallKey: String?
    @State private var confirmGuestUninstall = false

    // Recorded values are deliberately categorical. No Apple ID, guest name,
    // certificate, UDID, user path, IPA URL or credential is ever serialized.
    private func recordTab(_ raw: String) {
        let tabs = ["소스": "sources", "앱": "apps",
                    "트윅": "tweaks", "설정": "settings"]
        ScarletDiagnosticRecorder.shared.record(
            "navigation", "tab_selected",
            fields: ["tab": tabs[raw] ?? "unknown"])
    }

    private func refreshStoredLoginState() {
        guard #available(iOS 17.0, *) else { return }
        // Foreground activation, login completion and sheet dismissal can
        // trigger overlapping XPC Keychain reads. A stale false result must
        // not overwrite a newer authenticated state.
        authStateReadGeneration &+= 1
        let requestGeneration = authStateReadGeneration
        Task { @MainActor in
            let stored = await ScarletConnectedSideSignEngine().storedAuthenticated()
            guard requestGeneration == authStateReadGeneration,
                  !showScarletAppleIDLogin else {
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "host_session_read_discarded",
                    fields: ["reason": "stale_or_login_active"])
                return
            }
            appleAuthVerified = stored
            ScarletDiagnosticRecorder.shared.record(
                "auth", stored ? "host_session_restored" : "host_session_unavailable",
                status: stored ? "success" : "info")
        }
    }

    private func recordLayout() {
        let window = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first(where: { $0.isKeyWindow })
        let orientation = String(describing: UIDevice.current.orientation)
        ScarletDiagnosticRecorder.shared.record(
            "layout", "orientation_observed",
            fields: [
                "orientation": orientation,
                "width_pt": String(Int(window?.bounds.width ?? 0)),
                "height_pt": String(Int(window?.bounds.height ?? 0)),
                "safe_top_pt": String(Int(window?.safeAreaInsets.top ?? 0)),
                "safe_bottom_pt": String(Int(window?.safeAreaInsets.bottom ?? 0))
            ])
    }

    private var guestItems: [ScarletGuestPresentation] {
        // LCAppModel.isAppRunning is a *launch-in-progress* flag, not proof
        // that a LiveContainer guest scene is visible. Use real dock/scene
        // window ownership before exposing the Running filter.
        let activeContainers = Set(ScarletGuestSceneRegistry.availableGuests().map(\.id))
        return sharedModel.apps.map { app in
            let visible = app.appInfo.containers.contains {
                activeContainers.contains($0.folderName)
            }
            return ScarletGuestPresentation(
                id: app.appInfo.relativeBundlePath ?? app.bundleIdentifier,
                title: app.displayName,
                detail: visible ? "실행 중"
                         : app.isAppRunning ? "실행 요청 중" : "설치됨",
                isRunning: visible,
                lastOpenedAt: app.appInfo.lastLaunched,
                iconPNG: app.appInfo.iconIsDarkIcon(false)?.pngData()
            )
        }
    }

    // On-device, privacy-preserving certificate preflight; only booleans and
    // a team-match classification are exported, never P12/password/team IDs.
    private func recordGuestCertificatePreflight() {
        let cert = LCUtils.certificateData()
        let password = LCSharedUtils.certificatePassword()
        var teamMatch = "unverified"
        if let cert, let password,
           let certificateTeam = LCUtils.getCertTeamId(withKeyData: cert, password: password) {
            let task = SecTaskCreateFromSelf(nil)
            if let entitlement = SecTaskCopyValueForEntitlement(
                task, "com.apple.developer.team-identifier" as CFString, nil),
               let hostTeam = entitlement.takeRetainedValue() as? String {
                teamMatch = certificateTeam == hostTeam ? "match" : "mismatch"
            }
        }
        let permissions = ScarletSigningReadiness.inspect()
        ScarletDiagnosticRecorder.shared.record("guest", "certificate_preflight",
            fields: ["certificate_present": cert == nil ? "false" : "true",
                     "password_present": password == nil ? "false" : "true",
                     "team_match": teamMatch,
                     "entitled_app_group": permissions.sideStoreAppGroupEntitled ? "true" : "false",
                     "group_accessible": permissions.sideStoreAppGroupAccessible ? "true" : "false",
                     "signed_host_identity": permissions.actualHostIdentity ? "match" : "mismatch"])
    }

    private func validateJITLessSigner() {
        // Pinned LC's original diagnostic signs only a temporary test dylib.
        // Run its synchronous semaphore on a utility queue; never block UI.
        // Existing certificates, profiles and installed guests are untouched.
        ScarletDiagnosticRecorder.shared.record("guest", "jitless_probe_started")
        DispatchQueue.global(qos: .utility).async {
            LCUtils.validateJITLessSetup { verified, _ in
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "jitless_probe_finished",
                    status: verified ? "success" : "error",
                    fields: ["result": verified ? "signature_valid" : "signature_invalid"])
            }
        }
    }

    // The original LC settings can read the bundled SideStore certificate,
    // but independent Scarlet has no second app-list/SideStore screen to visit.
    // Import only a VALID same-team existing P12, and only when LC has none.
    // Never log a P12, password, account, team ID or Keychain value.
    private func bridgeExistingSideStoreCertificateIfSafe() {
        guard LCUtils.certificateData() == nil else { return }
        // UserDefaults(suiteName:) in pinned LC can fall back to standard defaults.
        // Writing a certificate there is NOT granting an App Group entitlement.
        // Only Apple-issued signed entitlement + actual group container access
        // can authorize guest certificate storage; do not mutate on failure.
        let permissions = ScarletSigningReadiness.inspect()
        guard permissions.canRequestNativeRefresh else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "certificate_bridge_skipped", status: "blocked",
                fields: ["reason": permissions.safeBlockCategory])
            return
        }
        // Pinned SideStore KeychainAccess uses Bundle.Info.appbundleIdentifier
        // ("com.SideStore.SideStore"). Older bundled LC exports may instead
        // use the LiveContainer service. Verify each candidate's PKCS#12 team
        // before importing; never overwrite an existing LC certificate.
        let sideStoreServices = ["com.SideStore.SideStore", "com.kdt.livecontainer"]
        var verifiedCertificate: Data?
        var verifiedPassword: String?
        var lastReason = "missing"
        for service in sideStoreServices {
            let certificateQuery: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrAccount as String: "signingCertificate",
                kSecReturnData as String: true,
                kSecMatchLimit as String: kSecMatchLimitOne,
                kSecAttrService as String: service,
                kSecAttrSynchronizable as String: kSecAttrSynchronizableAny
            ]
            var item: CFTypeRef?
            let certStatus = SecItemCopyMatching(certificateQuery as CFDictionary, &item)
            guard certStatus == errSecSuccess,
                  let candidate = item as? Data, !candidate.isEmpty else {
                if certStatus != errSecItemNotFound { lastReason = "keychain_unavailable" }
                continue
            }
            let passwordQuery: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrAccount as String: "signingCertificatePassword",
                kSecReturnData as String: true,
                kSecMatchLimit as String: kSecMatchLimitOne,
                kSecAttrService as String: service,
                kSecAttrSynchronizable as String: kSecAttrSynchronizableAny
            ]
            var passwordItem: CFTypeRef?
            let pwdStatus = SecItemCopyMatching(passwordQuery as CFDictionary, &passwordItem)
            if pwdStatus != errSecSuccess && pwdStatus != errSecItemNotFound {
                lastReason = "password_keychain_unavailable"
                continue
            }
            // SideStore supports unencrypted PKCS#12: nil/empty password
            // is valid only when the actual certificate team verifies.
            let password = (passwordItem as? Data)
                .flatMap { String(data: $0, encoding: .utf8) } ?? ""
            guard let certificateTeam = LCUtils.getCertTeamId(
                withKeyData: candidate, password: password),
                  let hostTeam = LCSharedUtils.teamIdentifier(),
                  certificateTeam == hostTeam else {
                lastReason = "certificate_team_or_password_invalid"
                continue
            }
            verifiedCertificate = candidate
            verifiedPassword = password
            break
        }
        guard let certData = verifiedCertificate,
              let password = verifiedPassword else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "certificate_bridge_skipped",
                fields: ["reason": lastReason])
            return
        }
        // Same storage keys used by the original LCSettingsView.
        LCUtils.appGroupUserDefault.set(certData, forKey: "LCCertificateData")
        LCUtils.appGroupUserDefault.set(password, forKey: "LCCertificatePassword")
        LCUtils.appGroupUserDefault.set(Date(), forKey: "LCCertificateUpdateDate")
        guard LCUtils.certificateData() == certData,
              LCSharedUtils.certificatePassword() == password else {
            ScarletDiagnosticRecorder.shared.record("guest", "certificate_bridge_not_persisted",
                status: "error", fields: ["reason": "app_group_write_failed"])
            return
        }
        ScarletDiagnosticRecorder.shared.record("guest", "certificate_bridge_imported",
            status: "success", fields: ["reason": "same_team_verified_readback"])
    }

    // The original LCTabView initializes LC extension bookmarks and team
    // identity in .task. The independent Scarlet root replaces that tab view;
    // preserve its nonvisual bootstrap before launching any guest.
    private func ensureOriginalLCGuestBootstrap() -> Bool {
        if sharedModel.multiLCStatus == 2 {
            let scheme = UserDefaults.lcAppUrlScheme() ?? ""
            LCUtils.appGroupUserDefault.set(Bundle.main.bundleIdentifier,
                forKey: "LCBundleID.\(scheme)")
        } else if LCUtils.appGroupUserDefault.object(forKey: "LCLaunchExtensionPrivateDocBookmark") == nil {
            guard let bookmark = LCUtils.bookmark(for: LCPath.docPath) else {
                ScarletDiagnosticRecorder.shared.record("guest", "bootstrap_failed",
                    status: "error", fields: ["reason": "private_docs_bookmark"])
                showOriginalError = "LiveContainer 개인 저장소 접근 정보를 생성하지 못했습니다. 설치된 앱 데이터는 유지됩니다."
                return false
            }
            LCUtils.appGroupUserDefault.set(bookmark,
                forKey: "LCLaunchExtensionPrivateDocBookmark")
            ScarletDiagnosticRecorder.shared.record("guest", "private_docs_bookmark_created",
                status: "success")
        }

        if UserDefaults.standard.string(forKey: "LCCertificateTeamId") == nil,
           let team = LCSharedUtils.teamIdentifier() {
            UserDefaults.standard.set(team, forKey: "LCCertificateTeamId")
            ScarletDiagnosticRecorder.shared.record("guest", "team_identity_initialized",
                status: "info")
        }
        ScarletDiagnosticRecorder.shared.record("guest", "bootstrap_checked",
            status: "success")
        return true
    }

    private func runGuest(_ key: String) {
        let guestRef = ScarletDiagnosticRecorder.shared.guestReference(key)
        ScarletDiagnosticRecorder.shared.record("guest", "launch_requested",
            fields: ["guest_ref": guestRef])
        guard let app = sharedModel.apps.first(where: {
            ($0.appInfo.relativeBundlePath ?? $0.bundleIdentifier) == key
        }) else {
            ScarletDiagnosticRecorder.shared.record("guest", "launch_missing",
                status: "error", fields: ["guest_ref": guestRef])
            showOriginalError = "선택한 앱이 기존 LiveContainer에 등록되어 있지 않습니다."
            return
        }
        Task { @MainActor in
            // A double tap must not start overlapping LC sign/launch attempts.
            guard launchingGuestKeys.insert(key).inserted else {
                ScarletDiagnosticRecorder.shared.record("guest", "launch_duplicate_ignored",
                    fields: ["guest_ref": guestRef])
                return
            }
            defer { launchingGuestKeys.remove(key) }
            do {
                guard ensureOriginalLCGuestBootstrap() else { return }
                // The removed LCAppListView normally owns the JIT delegate.
                // Do not silently claim a JIT guest launched when no delegate
                // can display/complete the original JIT enablement process.
                if (app.appInfo.isJITNeeded || app.appInfo.is32bit),
                   app.delegate == nil {
                    ScarletDiagnosticRecorder.shared.record("guest", "jit_delegate_unavailable",
                        status: "blocked", fields: ["reason": "original_ui_not_mounted"])
                    showOriginalError = "이 게스트 앱은 JIT 지원이 필요합니다. 현재 런처의 JIT 연결이 준비되지 않아 실행을 중단했습니다."
                    return
                }
                bridgeExistingSideStoreCertificateIfSafe()
                recordGuestCertificatePreflight()
                // Since iOS 26 the original LiveContainer guest JIT-less
                // launcher needs a usable signing certificate. A saved Apple
                // login or an import-complete state is not that certificate.
                // Do not attempt a launch that the pinned engine cannot sign.
                if #available(iOS 26.0, *),
                   (LCUtils.certificateData() == nil ||
                    LCSharedUtils.certificatePassword() == nil) {
                    signingRecoveryNeeded = true
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "launch_blocked", status: "blocked",
                        fields: ["reason": "jitless_signing_certificate_missing",
                                 "guest_ref": guestRef])
                    showOriginalError = "JIT-Less 실행에 필요한 LiveContainer 서명 인증서가 없습니다. 설정의 인증서 가져오기에서 인증서를 확인하세요."
                    return
                }
                // Original LC remains the owner of signature/launch/handoff.
                try await app.runApp()
                // runApp returning is NOT proof the guest scene is on-screen.
                ScarletDiagnosticRecorder.shared.record("guest", "runapp_returned",
                    fields: ["guest_ref": guestRef])
            } catch {
                ScarletDiagnosticRecorder.shared.recordError("guest", "launch_failed", error: error)
                showOriginalError = error.localizedDescription
                // The unchanged upstream screen keeps the complete
                // certificate/container diagnostics available for recovery.
                // Errors stay on this host; never open the old app-list screen.
            }
        }
    }

    private func requestGuestUninstall(_ key: String) {
        let ref = ScarletDiagnosticRecorder.shared.guestReference(key)
        guard sharedModel.apps.contains(where: {
            ($0.appInfo.relativeBundlePath ?? $0.bundleIdentifier) == key
        }) else {
            ScarletDiagnosticRecorder.shared.record(
                "guest", "uninstall_missing", status: "error",
                fields: ["guest_ref": ref])
            showOriginalError = "삭제할 게스트 앱을 찾을 수 없습니다."
            return
        }
        pendingGuestUninstallKey = key
        confirmGuestUninstall = true
        ScarletDiagnosticRecorder.shared.record(
            "guest", "uninstall_confirmation_requested",
            fields: ["guest_ref": ref])
    }

    private func uninstallConfirmedGuest() {
        guard let key = pendingGuestUninstallKey else { return }
        pendingGuestUninstallKey = nil
        let ref = ScarletDiagnosticRecorder.shared.guestReference(key)
        guard let app = sharedModel.apps.first(where: {
            ($0.appInfo.relativeBundlePath ?? $0.bundleIdentifier) == key
        }) else {
            showOriginalError = "이미 삭제되었거나 찾을 수 없는 앱입니다."
            return
        }
        guard !launchingGuestKeys.contains(key), !app.isAppRunning else {
            showOriginalError = "앱 실행 또는 서명이 진행 중입니다. 작업 종료 후 삭제하세요."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "uninstall_blocked", status: "blocked",
                fields: ["reason": "launch_in_progress"])
            return
        }
        let activeContainers = Set(ScarletGuestSceneRegistry.availableGuests().map(\.id))
        guard !app.appInfo.containers.contains(where: {
            activeContainers.contains($0.folderName)
        }) else {
            showOriginalError = "앱이 실행 중입니다. 해당 창을 종료한 뒤 삭제하세요."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "uninstall_blocked", status: "blocked",
                fields: ["reason": "guest_running"])
            return
        }
        guard let originalPath = app.appInfo.bundlePath(),
              app.appInfo.relativeBundlePath != nil else {
            showOriginalError = "앱 경로를 검증할 수 없어 삭제를 중단했습니다."
            return
        }
        // Delete only an immediate .app child of the original LC bundle root.
        // Keep Documents, Data/Application, AppGroups and all signing assets.
        let bundleURL = URL(fileURLWithPath: originalPath)
            .standardizedFileURL.resolvingSymlinksInPath()
        let root = (app.appInfo.isShared ? LCPath.lcGroupBundlePath : LCPath.bundlePath)
            .standardizedFileURL.resolvingSymlinksInPath()
        guard bundleURL.pathExtension.lowercased() == "app",
              bundleURL.deletingLastPathComponent() == root,
              FileManager.default.fileExists(atPath: bundleURL.path) else {
            showOriginalError = "LiveContainer 앱 폴더 외부 경로는 삭제할 수 없습니다."
            ScarletDiagnosticRecorder.shared.record(
                "guest", "uninstall_blocked", status: "blocked",
                fields: ["reason": "unexpected_bundle_path"])
            return
        }
        do {
            try FileManager.default.removeItem(at: bundleURL)
            sharedModel.apps.removeAll { $0 === app }
            sharedModel.hiddenApps.removeAll { $0 === app }
            ScarletDiagnosticRecorder.shared.record(
                "guest", "uninstall_bundle_completed", status: "success",
                fields: ["guest_ref": ref, "result": "data_preserved"])
        } catch {
            ScarletDiagnosticRecorder.shared.recordError(
                "guest", "uninstall_bundle_failed", error: error)
            showOriginalError = "앱 파일 삭제 실패: \(error.localizedDescription)"
        }
    }

    private func prepareDeviceIPAInstall(_ source: URL) {
        guard ["ipa", "tipa"].contains(source.pathExtension.lowercased()) else {
            showOriginalError = "IPA 또는 TIPA 파일을 선택하세요."
            return
        }
        ScarletDiagnosticRecorder.shared.record("sidestore", "device_file_selected")
        ScarletDiagnosticRecorder.shared.record("sidestore", "install_requested",
            fields: ["engine": "sidestore"])
        // Do not open SideStore's UI. Device installation requires the
        // SideStore headless install/signing engine and verified profiles.
        // The older integrated app implements IPA staging -> installSharedIPA.
        // This rebuild has not yet ported and verified that transport.
        guard UserDefaults.sideStoreExist() else {
            ScarletDiagnosticRecorder.shared.record("sidestore", "engine_missing",
                status: "blocked", fields: ["reason": "engine_missing"])
            showOriginalError = "내장 SideStore 설치 엔진을 찾지 못했습니다."
            return
        }
        ScarletDiagnosticRecorder.shared.record("sidestore", "install_blocked",
            status: "blocked", fields: ["reason": "transport_unverified"])
        showOriginalError = "iOS 앱 설치 엔진의 서명·기기 설치 연결이 아직 검증되지 않았습니다. 원본 IPA와 기존 인증서·프로파일은 변경하지 않았습니다."
    }

    // SwiftUI presents the real iOS Files document picker. Copy the
    // security-scoped original into a scratch IPA: LiveContainer's original
    // startInstallApp removes its input URL after importing; the user's Files
    // original must never be removed.
    private func stageGuestIPAFromFiles(_ source: URL) {
        let ext = source.pathExtension.lowercased()
        guard ext == "ipa" || ext == "tipa" else {
            showOriginalError = "IPA 또는 TIPA 파일을 선택하세요."
            return
        }
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        let temporary = FileManager.default.temporaryDirectory
            .appendingPathComponent("scarlet-guest-\(UUID().uuidString).\(ext)")
        do {
            try FileManager.default.copyItem(at: source, to: temporary)
            queuedGuestIPAURL = temporary
            ScarletDiagnosticRecorder.shared.record("guest_import", "file_staged")
            showGuestImportProgress = true
        } catch {
            ScarletDiagnosticRecorder.shared.recordError("guest_import", "file_stage_failed", error: error)
            showOriginalError = "파일을 가져올 수 없습니다: \(error.localizedDescription)"
        }
    }

    // Source install routes through the same original LC guest IPA importer
    // as Files, never through the unmounted upstream LCAppListView notification.
    private func installSourceGuestApp(_ downloadID: String) {
        guard !sourceIsDownloading, !showGuestImportProgress else { return }
        guard let app = originalSources.sources.compactMap({ $0.source })
                .flatMap({ $0.apps })
                .first(where: { $0.latestVersion?.downloadURL.absoluteString == downloadID }),
              let url = app.latestVersion?.downloadURL,
              url.scheme?.lowercased() == "https", url.host != nil else {
            showOriginalError = "설치할 앱의 안전한 HTTPS 다운로드 주소를 찾지 못했습니다."
            ScarletDiagnosticRecorder.shared.record("sources", "install_blocked",
                status: "blocked", fields: ["reason": "url_invalid"])
            return
        }
        sourceIsDownloading = true
        sourceDownloadError = nil
        sourceDownloadStage = "IPA 서버에 연결 중"
        showSourceDownloadSheet = true
        ScarletDiagnosticRecorder.shared.record("sources", "guest_download_started")
        sourceDownloadTask = Task { @MainActor in
            defer {
                sourceIsDownloading = false
                sourceDownloadTask = nil
            }
            let config = URLSessionConfiguration.ephemeral
            config.timeoutIntervalForRequest = 45
            config.timeoutIntervalForResource = 900
            config.waitsForConnectivity = false
            let session = URLSession(configuration: config)
            defer { session.invalidateAndCancel() }
            do {
                sourceDownloadStage = "소스에서 IPA 다운로드 중"
                let (downloaded, response) = try await session.download(from: url)
                try Task.checkCancellation()
                defer { try? FileManager.default.removeItem(at: downloaded) }
                guard let http = response as? HTTPURLResponse,
                      (200...299).contains(http.statusCode) else {
                    throw NSError(domain: "ScarletSourceImport", code: 1,
                        userInfo: [NSLocalizedDescriptionKey: "소스에서 IPA 다운로드에 실패했습니다."])
                }
                let attrs = try FileManager.default.attributesOfItem(atPath: downloaded.path)
                let size = (attrs[.size] as? NSNumber)?.int64Value ?? 0
                guard size > 0, size < 2_147_483_648 else {
                    throw NSError(domain: "ScarletSourceImport", code: 2,
                        userInfo: [NSLocalizedDescriptionKey: "다운로드 파일 크기가 올바르지 않습니다."])
                }
                let reader = try FileHandle(forReadingFrom: downloaded)
                defer { try? reader.close() }
                let magic = try reader.read(upToCount: 4)
                guard magic == Data([0x50, 0x4B, 0x03, 0x04]) else {
                    ScarletDiagnosticRecorder.shared.record("sources", "download_not_ipa",
                        status: "error", fields: ["reason": "not_zip_archive"])
                    throw NSError(domain: "ScarletSourceImport", code: 3,
                        userInfo: [NSLocalizedDescriptionKey: "다운로드한 파일이 유효한 IPA ZIP 형식이 아닙니다."])
                }
                sourceDownloadStage = "파일 형식 확인 완료 · 가져오기 준비"
                try Task.checkCancellation()
                let staged = FileManager.default.temporaryDirectory
                    .appendingPathComponent("scarlet-source-\(UUID().uuidString).ipa")
                try FileManager.default.copyItem(at: downloaded, to: staged)
                // Present the original LC import engine only AFTER this sheet
                // closes; simultaneous SwiftUI sheets can silently fail.
                sourceDownloadedIPA = staged
                ScarletDiagnosticRecorder.shared.record("sources", "guest_download_completed",
                    fields: ["route": "livecontainer", "stage": "download_only"])
                showSourceDownloadSheet = false
            } catch is CancellationError {
                ScarletDiagnosticRecorder.shared.record("sources", "guest_download_cancelled",
                    status: "info")
                sourceDownloadStage = "다운로드가 취소되었습니다."
                showSourceDownloadSheet = false
            } catch {
                ScarletDiagnosticRecorder.shared.recordError("sources", "guest_download_failed", error: error)
                sourceDownloadStage = "다운로드 실패"
                sourceDownloadError = "IPA를 가져오지 못했습니다. 네트워크 상태와 소스의 다운로드 주소를 확인하세요."
            }
        }
    }

    private func reportPreviousGuestLaunchFailure() {
        if let previousError = UserDefaults.standard.string(forKey: "error"),
           !previousError.isEmpty {
            UserDefaults.standard.removeObject(forKey: "error")
            ScarletDiagnosticRecorder.shared.record("guest", "previous_launch_error_detected",
                status: "error")
            showOriginalError = "이전 게스트 앱 실행 실패: \(previousError)"
        } else if UserDefaults.standard.bool(forKey: "SigningInProgress") {
            UserDefaults.standard.removeObject(forKey: "SigningInProgress")
            ScarletDiagnosticRecorder.shared.record("guest", "signing_interrupted",
                status: "error")
            showOriginalError = "이전 게스트 앱의 서명 작업이 중단됐습니다. 인증서 상태를 확인하세요."
        }
    }

    private func handle(_ action: ScarletControl) {
        ScarletDiagnosticRecorder.shared.record("action", "requested",
            fields: ["action": action.rawValue])
        switch action {
        case .localImportGuestIPA:
            pendingIPAInstallRoute = .guest
            ScarletDiagnosticRecorder.shared.record("guest_import", "file_picker_requested")
            showGuestFilePicker = true
        case .serviceBeginSignIn:
            ScarletDiagnosticRecorder.shared.record("auth", "login_sheet_requested")
            showScarletAppleIDLogin = true
        case .serviceInstallIPA:
            pendingIPAInstallRoute = .device
            ScarletDiagnosticRecorder.shared.record("sidestore", "file_picker_requested")
            showGuestFilePicker = true
        case .localOpenEmbeddedSideStore,
             .serviceRefreshApp, .serviceSyncAppIDs,
             .serviceSetSettings, .serviceReadSettings:
            ScarletDiagnosticRecorder.shared.record("sidestore", "action_blocked",
                status: "blocked", fields: ["action": action.rawValue,
                                            "reason": "transport_unverified"])
            // Never redirect any SideStore service button to its guest UI.
            showOriginalError = "SideStore 화면 이동은 사용하지 않습니다. 해당 기능은 Scarlet 내부 엔진 연결이 검증된 후 사용할 수 있습니다."
        case .localAppearance, .localStorageNavigation, .serviceReadLogs,
             .localTapProbe, .localClearNotifications:
            ScarletDiagnosticRecorder.shared.record("settings", "legacy_route_blocked",
                fields: ["action": action.rawValue])
            // The real LCSettingsView lives directly inside the settings tab.
            // Do not route distinct controls to one generic settings modal.
            showOriginalError = "설정 탭에서 원본 LiveContainer 설정을 직접 사용할 수 있습니다."
        }
    }

    var body: some View {
        ScarletIndependentShell(
            snapshot: ScarletHostPresentationSnapshot(
                serviceConnected: UserDefaults.sideStoreExist(),
                appleAuthenticated: appleAuthVerified,
                pairingVerified: false,
                signingVerified: false,
                installationVerified: false,
                installedProfileExpiresAt: nil,
                installedProfileVerified: false),
            guests: guestItems,
            sources: originalSources.sources.map { item in
                ScarletSourcePresentation(
                    id: item.id.absoluteString,
                    title: item.displayName,
                    detail: item.url.host ?? "",
                    icon: "link",
                    apps: (item.source?.apps ?? []).map { app in
                        ScarletSourceAppPresentation(
                            id: app.latestVersion?.downloadURL.absoluteString ?? app.bundleIdentifier,
                            name: app.name,
                            version: app.latestVersion?.version ?? "다운로드 없음",
                            hasDownload: app.latestVersion?.downloadURL != nil
                        )
                    }
                )
            },
            onAction: handle,
            onOpenGuest: runGuest,
            onDeleteGuest: requestGuestUninstall,
            onOpenSource: { _ in showNativeSources = true },
            onAddSource: {
                ScarletDiagnosticRecorder.shared.record("sources", "direct_add_requested")
                newSourceURL = ""
                sourceInputError = nil
                showSourceURLInput = true
            },
            onInstallSourceApp: installSourceGuestApp,
            preservedGlassTabBar: { tab in
                AnyView(ScarletNativeGlassTabBar(selected: tab))
            },
            nativeTweaks: {
                // Embedded real LiveContainer tweak manager; actual tweak
                // folder state, enable toggles and import are owned upstream.
                AnyView(
                    LCTweaksView()
                        .environmentObject(sharedModel)
                )
            },
            nativeSettings: {
                // Original LiveContainer Forms, pickers, certificates, JIT,
                // multitask and storage controls remain wired to real state.
                // The bottom tab is NOT inside a second presentation.
                AnyView(
                    LCSettingsView()
                        .environmentObject(sharedModel)
                        .environmentObject(LCAppSortManager.shared)
                        .environmentObject(downloadHelper)
                )
            },
            onTabChanged: recordTab,
            onSystemGlassMounted: {
                // Records which code path actually mounted on iOS 26+.
                // It deliberately does not claim optical proof from a device.
                ScarletDiagnosticRecorder.shared.record(
                    "glass", "system_tabbar_mounted",
                    status: "info",
                    fields: ["api": "SwiftUI.TabView",
                             "material_owner": "system",
                             "optical_verified": "false"])
            }
        )
        .environmentObject(downloadHelper)
        .onAppear {
            ScarletDiagnosticRecorder.shared.record("boot", "host_visible",
                fields: ["count": String(sharedModel.apps.count),
                         "engine": "livecontainer",
                         "available": UserDefaults.sideStoreExist() ? "true" : "false"])
            recordLayout()
            _ = ensureOriginalLCGuestBootstrap()
            bridgeExistingSideStoreCertificateIfSafe()
            reportPreviousGuestLaunchFailure()
            refreshStoredLoginState()
            // UIKit window creation can lag behind SwiftUI view construction.
            // The actual dock is initialized lazily and attached when ready.
            DispatchQueue.main.async {
                MultitaskDockManager.shared.scarletEnsureWindowHost()
                let mounted = MultitaskDockManager.shared.windowHostingView.superview != nil
                NSLog("[SCARLET_BOOT] phase=home-visible dock-root-attached=%d", mounted ? 1 : 0)
                ScarletDiagnosticRecorder.shared.record("boot", "dock_attachment",
                    fields: ["window_attached": mounted ? "true" : "false"])
            }
        }
        .onChange(of: scenePhase) { phase in
            ScarletDiagnosticRecorder.shared.record("lifecycle", "scene_phase",
                fields: ["state": String(describing: phase)])
            if phase == .active && !showScarletAppleIDLogin {
                refreshStoredLoginState()
            }
        }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletGuestAuthVerified"))) { _ in
            // State must come from persisted SideStore Keychain, never from
            // the success notification alone.
            refreshStoredLoginState()
            ScarletDiagnosticRecorder.shared.record("auth",
                "verified_login_recheck_requested")
        }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletGuestCertificateInvalid"))) { _ in
            signingRecoveryNeeded = true
            ScarletDiagnosticRecorder.shared.record("guest", "certificate_recovery_available",
                status: "warning")
            validateJITLessSigner()
        }
        .onReceive(NotificationCenter.default.publisher(
            for: UIApplication.didReceiveMemoryWarningNotification)) { _ in
            ScarletDiagnosticRecorder.shared.record("system", "memory_warning", status: "warning")
        }
        .onReceive(NotificationCenter.default.publisher(
            for: UIDevice.orientationDidChangeNotification)) { _ in
            recordLayout()
        }
        .onChange(of: showGuestImportProgress) { visible in
            ScarletDiagnosticRecorder.shared.record("guest_import",
                visible ? "import_progress_visible" : "import_progress_dismissed")
        }
        .onChange(of: showNativeSources) { visible in
            ScarletDiagnosticRecorder.shared.record("sources",
                visible ? "manager_visible" : "manager_dismissed")
        }
        .onChange(of: showScarletAppleIDLogin) { visible in
            ScarletDiagnosticRecorder.shared.record("auth",
                visible ? "login_visible" : "login_dismissed")
            if !visible { refreshStoredLoginState() }
        }
        .onChange(of: showOriginalError) { error in
            if error != nil {
                ScarletDiagnosticRecorder.shared.record("alert", "shown", status: "warning")
            }
        }
        .sheet(isPresented: $showScarletAppleIDLogin) {
            // Credentials remain in a Scarlet-owned ephemeral view.
            // The embedded SideStore guest authentication UI is NOT opened.
            ScarletAppleIDLoginSheet(engine: ScarletConnectedSideSignEngine())
        }
        .fileImporter(isPresented: $showGuestFilePicker,
                      allowedContentTypes: [.ipa, .tipa],
                      allowsMultipleSelection: false) { result in
            switch result {
            case .success(let files):
                if let selected = files.first {
                    switch pendingIPAInstallRoute {
                    case .guest:
                        ScarletDiagnosticRecorder.shared.record("guest_import", "file_selected")
                        stageGuestIPAFromFiles(selected)
                    case .device:
                        // Keep the selected Files original intact. No silent
                        // LC fallback or simulated successful device install.
                        prepareDeviceIPAInstall(selected)
                    }
                }
            case .failure(let error):
                ScarletDiagnosticRecorder.shared.recordError(
                    "guest_import", "file_selection_failed", error: error)
                showOriginalError = error.localizedDescription
            }
        }
        .sheet(isPresented: $showGuestImportProgress, onDismiss: {
            if let queuedGuestIPAURL {
                try? FileManager.default.removeItem(at: queuedGuestIPAURL)
            }
            queuedGuestIPAURL = nil
        }) {
            if let queuedGuestIPAURL {
                // Only the original LC installer runs here. The old app-list
                // UI branch is never constructed for Scarlet's IPA flow.
                LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,
                              scarletOnImportFinished: {
                                  showGuestImportProgress = false
                              })
                    .environmentObject(downloadHelper)
                    .environmentObject(sharedModel)
                    .environmentObject(LCAppSortManager.shared)
                    .presentationDetents([.height(340)])
                    .presentationDragIndicator(.visible)
                    .presentationBackground(Color(red: 0.065, green: 0.058, blue: 0.10))
                    .interactiveDismissDisabled()
            }
        }
        .sheet(isPresented: $showSourceURLInput) {
            NavigationStack {
                Form {
                    Section("소스 주소") {
                        TextField("https://example.com/source.json", text: $newSourceURL)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                            .autocorrectionDisabled()
                            .accessibilityIdentifier("SCARLET_DIRECT_SOURCE_URL_FIELD")
                    }
                    if let sourceInputError {
                        Text(sourceInputError).foregroundStyle(.red)
                    }
                }
                .navigationTitle("소스 추가")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("취소") { showSourceURLInput = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("추가") {
                            guard !sourceIsSaving else { return }
                            sourceIsSaving = true
                            Task { @MainActor in
                                defer { sourceIsSaving = false }
                                let error = await originalSources.addSource(from: newSourceURL)
                                if let error {
                                    sourceInputError = error
                                    ScarletDiagnosticRecorder.shared.record("sources", "direct_add_failed",
                                        status: "error")
                                } else {
                                    ScarletDiagnosticRecorder.shared.record("sources", "direct_add_completed",
                                        status: "success")
                                    showSourceURLInput = false
                                }
                            }
                        }
                        .disabled(sourceIsSaving || newSourceURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }
        }
        .sheet(isPresented: $showSourceDownloadSheet, onDismiss: {
            if let staged = sourceDownloadedIPA {
                sourceDownloadedIPA = nil
                stageGuestIPAFromFiles(staged)
                try? FileManager.default.removeItem(at: staged)
            }
        }) {
            VStack(spacing: 20) {
                Image(systemName: sourceDownloadError == nil
                      ? "arrow.down.doc.fill" : "exclamationmark.triangle.fill")
                    .font(.system(size: 31, weight: .medium))
                    .foregroundStyle(Color(red: 0.72, green: 0.63, blue: 0.99))
                    .frame(width: 58, height: 58)
                    .background(Color(red: 0.39, green: 0.32, blue: 0.60).opacity(0.24),
                                in: RoundedRectangle(cornerRadius: 19))
                VStack(spacing: 7) {
                    Text(sourceDownloadError == nil ? "게스트 앱 설치" : "다운로드 실패")
                        .font(.title3.bold())
                        .foregroundStyle(Color.white)
                    Text(sourceDownloadError ?? sourceDownloadStage)
                        .font(.subheadline)
                        .foregroundStyle(Color(red: 0.78, green: 0.75, blue: 0.85))
                        .multilineTextAlignment(.center)
                        .accessibilityIdentifier("SCARLET_SOURCE_DOWNLOAD_STAGE")
                }
                if sourceIsDownloading {
                    ProgressView()
                        .tint(Color(red: 0.72, green: 0.63, blue: 0.99))
                        .accessibilityLabel("소스 IPA 다운로드 중")
                }
                Text("다운로드 후 LiveContainer 가져오기와 서명 검증을 진행합니다.")
                    .font(.caption)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Color(red: 0.68, green: 0.65, blue: 0.75))
                Button(sourceIsDownloading ? "다운로드 취소" : "닫기") {
                    if sourceIsDownloading {
                        sourceDownloadTask?.cancel()
                        sourceIsDownloading = false
                    }
                    showSourceDownloadSheet = false
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.44, green: 0.33, blue: 0.77))
                .accessibilityIdentifier("SCARLET_SOURCE_DOWNLOAD_CANCEL")
            }
            // The system sheet IS the visible rounded surface. The former
            // extra RoundedRectangle + opaque sheet background produced two
            // concentric panels over the source list on iPhone.
            .padding(.horizontal, 24)
            .padding(.vertical, 18)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .presentationDetents([.height(340)])
            .presentationBackground(Color(red: 0.14, green: 0.12, blue: 0.22))
            .presentationDragIndicator(.hidden)
            .interactiveDismissDisabled(sourceIsDownloading)
            .accessibilityIdentifier("SCARLET_BRANDED_SOURCE_DOWNLOAD_SHEET")
        }
        .sheet(isPresented: $showNativeSources) {
            NavigationStack {
                LCSourcesView()
            }
            .environmentObject(sharedModel)
            .environmentObject(LCAppSortManager.shared)
        }
        .confirmationDialog(
            "게스트 앱 삭제",
            isPresented: $confirmGuestUninstall,
            titleVisibility: .visible
        ) {
            Button("앱만 삭제 (데이터 보존)", role: .destructive) {
                uninstallConfirmedGuest()
            }
            Button("취소", role: .cancel) {
                pendingGuestUninstallKey = nil
            }
        } message: {
            Text("게스트 앱 파일만 삭제합니다. 데이터, 키체인, 다른 앱과 인증서는 보존됩니다.")
        }
        .alert("Scarlet Crystal 진단", isPresented: Binding(
            get: { showOriginalError != nil },
            set: { if !$0 { showOriginalError = nil } }
        )) {
            if signingRecoveryNeeded {
                Button("서명 설정에서 복구") {
                    signingRecoveryNeeded = false
                    showOriginalError = nil
                    NotificationCenter.default.post(
                        name: Notification.Name("ScarletOpenSigningSettings"), object: nil)
                }
            }
            Button("확인", role: .cancel) {
                showOriginalError = nil
                signingRecoveryNeeded = false
            }
        } message: {
            if signingRecoveryNeeded {
                Text("게스트 앱 서명이 유효하지 않습니다. 설정의 'SideStore 인증서 가져오기/새로고침'과 'JIT-Less 모드 진단'을 확인하세요. 기존 앱과 인증서는 보존됩니다.")
            } else {
                Text(showOriginalError ?? "")
            }
        }
    }

}

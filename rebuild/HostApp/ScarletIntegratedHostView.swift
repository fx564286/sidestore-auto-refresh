// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI
import UIKit
import UniformTypeIdentifiers
import Security
import SideStoreSupport

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
    // V45 new architecture: one stable original-size viewport for multiple
    // resident LiveProcess scenes; disabled unless enabled in Settings.
    @StateObject private var fullscreenStack = ScarletFullscreenSceneStack()
    @AppStorage("Scarlet.Feature.FullscreenResidentPilot.V45")
    private var experimentalFullscreenResident = false
    // A single Files picker serves both explicitly selected installation routes.
    private enum IPAInstallRoute { case guest, device }
    @State private var pendingIPAInstallRoute: IPAInstallRoute = .guest
    @State private var showGuestFilePicker = false
    @State private var showGuestImportProgress = false
    @State private var queuedGuestIPAURL: URL?
    @State private var installProgressMinimized = false
    @State private var showSourceActions = false
    @State private var confirmRemoveSource = false
    @State private var selectedSourceURL: URL?
    @State private var showSourceURLInput = false
    @State private var newSourceURL = ""
    @State private var sourceIsSaving = false
    @State private var sourceIsDownloading = false
    @State private var sourceDownloadTask: Task<Void, Never>?
    @State private var showSourceDownloadSheet = false
    @State private var sourceDownloadStage = "IPA 서버에 연결 중"
    @State private var sourceDownloadError: String?
    @State private var sourceDownloadedIPA: URL?
    @State private var deviceInstallRunning = false
    @State private var deviceInstallStatus: String?
    @State private var showDeviceInstallSheet = false
    @State private var sourceInputError: String?
    @State private var showScarletAppleIDLogin = false
    @State private var showInAppDevicePairing = false
    @State private var appleAuthVerified = false
    // Ignore delayed auth readbacks after a newer foreground/login transition.
    @State private var authStateReadGeneration: UInt64 = 0
    @State private var lastLayoutSignature: String?
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
        // Use scene interface orientation (the actual guest presentation),
        // not UIDeviceOrientation's unstable faceUp / unknown descriptions.
        let orientation: String
        switch window?.windowScene?.interfaceOrientation ?? .unknown {
        case .portrait: orientation = "portrait"
        case .portraitUpsideDown: orientation = "portrait_upside_down"
        case .landscapeLeft: orientation = "landscape_left"
        case .landscapeRight: orientation = "landscape_right"
        default: orientation = "unknown"
        }
        let width = Int(window?.bounds.width ?? 0)
        let height = Int(window?.bounds.height ?? 0)
        let top = Int(window?.safeAreaInsets.top ?? 0)
        let bottom = Int(window?.safeAreaInsets.bottom ?? 0)
        let signature = "\(orientation):\(width):\(height):\(top):\(bottom)"
        // Avoid repeated identical readings from SwiftUI lifecycle/rotation
        // notifications. Keep ALL actual safe-area and geometry changes.
        guard signature != lastLayoutSignature else { return }
        lastLayoutSignature = signature
        ScarletDiagnosticRecorder.shared.record(
            "layout", "orientation_observed",
            fields: [
                "orientation": orientation,
                "width_pt": String(width),
                "height_pt": String(height),
                "safe_top_pt": String(top),
                "safe_bottom_pt": String(bottom)
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
            LCUtils.validateJITLessSetup { verified, validationError in
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "jitless_probe_finished",
                    status: verified ? "success" : "error",
                    fields: ["result": verified ? "signature_valid" : "signature_invalid"])
                // The pinned LC callback distinguishes a zsign failure from
                // a successful write that fails its code-signature postcheck.
                // Record only a safe NSError category/code, not payloads.
                if !verified, let validationError {
                    let nsError = validationError as NSError
                    let category = nsError.code == 2 &&
                        nsError.domain == Bundle.main.bundleIdentifier
                        ? "signature_postcheck_invalid" : "signer_operation_failed"
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "jitless_probe_failure_classified",
                        status: "error", fields: ["reason": category])
                    ScarletDiagnosticRecorder.shared.recordError(
                        "guest", "jitless_probe_underlying_error",
                        error: validationError)
                }
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
                    let signature = ScarletSigningReadiness.inspect()
                    // The installed Apple signature must grant the group.
                    // No repeated Apple login, Keychain rewrite or P12 picker
                    // can restore an entitlement missing from that signature.
                    let groupBlocked = !signature.sideStoreAppGroupEntitled ||
                        !signature.sideStoreAppGroupAccessible
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "launch_blocked", status: "blocked",
                        fields: ["reason": groupBlocked ?
                                    signature.safeBlockCategory :
                                    "jitless_signing_certificate_missing",
                                 "guest_ref": guestRef])
                    showOriginalError = groupBlocked
                        ? "설치된 앱의 Apple 서명에 SideStore App Group 권한이 없습니다. 인증서 재가져오기나 Apple 재로그인으로 복구할 수 없습니다. App Group 권한이 포함된 프로비저닝 프로파일로 현재 앱을 다시 서명해야 합니다."
                        : "JIT-Less 실행에 필요한 LiveContainer 서명 인증서가 없습니다. 설정의 인증서 가져오기에서 인증서를 확인하세요."
                    return
                }
                // V14 registered AFTER await runApp, but classic
                // launchToGuestApp can transfer the process without returning.
                // Persist A before the handoff so A->Home->B retains A in the
                // menu, even if the current scene is replaced. A failed
                // throwing runApp restores the previous list transactionally.
                let guestFolderForHistory = app.appInfo.relativeBundlePath
                let historyBeforeLaunch = ScarletGuestSessionLedger.recent()
                if let folder = guestFolderForHistory {
                    ScarletGuestSessionLedger.noteLaunch(
                        folder: folder,
                        title: app.displayName,
                        dataUUID: app.uiSelectedContainer?.folderName)
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "session_history_pre_handoff",
                        fields: ["result": "persisted_before_bootstrap"])
                }
                // Third path (V45 opt-in): each guest is one original LC
                // LiveProcess hosted inside ONE real full-screen viewport.
                // No UIWindow.resize, native window decorations, virtual
                // multitask app windows, zoom or process-killing cold swap.
                // The old latching logic silently kept the pilot ON after
                // user explicitly switched it OFF. The toggle is authoritative.
                let residentSessionActive = fullscreenStack.hasResidentSession
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "guest_launch_mode_routed",
                    fields: ["new_mode": experimentalFullscreenResident ? "on" : "off",
                             "live_session": residentSessionActive ? "true" : "false",
                             "result": experimentalFullscreenResident
                                 ? "pilot_requested" : "original_lc_requested"])
                if experimentalFullscreenResident,
                   UIDevice.current.userInterfaceIdiom == .phone,
                   #available(iOS 27.0, *),
                   app.appInfo.defaultClassicMode == 0,
                   !app.appInfo.isJITNeeded, !app.appInfo.is32bit,
                   app.uiSelectedContainer != nil {
                    do {
                        if let folder = app.appInfo.relativeBundlePath,
                           let livingPID = fullscreenStack.livePID(folder: folder) {
                            // Re-signing an already live guest can reactivate
                            // or disturb it. A->B->A must reuse the owned PID
                            // before performing ANY signing or LC bootstrap.
                            guard fullscreenStack.activate(folder: folder) else {
                                throw NSError(domain: "scarlet.guest", code: 4,
                                    userInfo: [NSLocalizedDescriptionKey:
                                        "기존 게스트로 전환하지 못했습니다."])
                            }
                            ScarletDiagnosticRecorder.shared.record(
                                "guest", "fullscreen_scene_reopened_without_resign",
                                status: "success",
                                fields: ["process_pid": String(livingPID),
                                         "result": "same_live_scene"])
                            return
                        }
                        try await app.signApp(force: false)
                        try fullscreenStack.enqueueSignedGuest(app)
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "fullscreen_scene_pilot_launched",
                            fields: ["memory": "not_verified"])
                    } catch {
                        ScarletGuestSessionLedger.restore(historyBeforeLaunch)
                        throw error
                    }
                    return
                }
                // Never fall through to the original cold bootstrap while
                // the resident engine still owns LiveProcess requests. The
                // fallback previously returned without displaying a guest and
                // users could tap the same entry dozens of times.
                if residentSessionActive && experimentalFullscreenResident {
                    // A pilot-compatible guest may fall back to classic only
                    // when no existing pilot owns an active live scene.
                    // noteLaunch() was intentionally called before native
                    // handoff, but an incompatible guest never reaches that
                    // handoff. Undo its provisional entry; otherwise the
                    // switcher shows apps that were blocked from launching.
                    ScarletGuestSessionLedger.restore(historyBeforeLaunch)
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "blocked_launch_history_reverted",
                        fields: ["reason": "requires_original_lc_runtime",
                                 "count": String(ScarletGuestSessionLedger.recent().count)])
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "resident_incompatible_launch_blocked",
                        status: "blocked",
                        fields: ["reason": "requires_original_lc_runtime"])
                    showOriginalError = "현재 실행 중인 RAM 유지 게스트와 실행 방식이 다른 앱입니다. 현재 세션을 종료한 뒤 기존 실행 방식으로 실행할 수 있습니다."
                    return
                }
                if !experimentalFullscreenResident {
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "v48_original_launch_mode_selected",
                        fields: ["result": "classic_mode_after_pilot_disabled",
                                 "memory": "not_preserved"])
                }
                // Native scene path, where genuinely supported, retains each
                // guest's RAM without changing the guest UIWindow geometry.
                // On devices lacking multi-scene support retain the original
                // full-screen LC bootstrap; never force a resized virtual dock.
                if #available(iOS 16.1, *),
                   UIDevice.current.userInterfaceIdiom == .pad,
                   UIApplication.shared.supportsMultipleScenes,
                   app.appInfo.defaultClassicMode == 0 {
                    let previousMode = LCUtils.appGroupUserDefault.integer(
                        forKey: "LCMultitaskMode")
                    LCUtils.appGroupUserDefault.set(MultitaskMode.nativeWindow.rawValue,
                                                    forKey: "LCMultitaskMode")
                    do {
                        try await app.runApp(multitask: true)
                    } catch {
                        LCUtils.appGroupUserDefault.set(previousMode,
                                                        forKey: "LCMultitaskMode")
                        ScarletGuestSessionLedger.restore(historyBeforeLaunch)
                        throw error
                    }
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "native_multiscene_launch_requested",
                        fields: ["result": "native_window"])
                } else {
                    do {
                        if UIDevice.current.userInterfaceIdiom == .phone {
                            // Explicit false bypasses persisted LC multitask
                            // preferences and preserves original guest geometry.
                            try await app.runApp(multitask: false)
                        } else {
                            try await app.runApp()
                        }
                    } catch {
                        ScarletGuestSessionLedger.restore(historyBeforeLaunch)
                        throw error
                    }
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "legacy_fullscreen_launch_requested",
                        fields: ["reason": "original_fullscreen_only",
                                 "virtual_window": "disabled",
                                 "process_pid": String(
                                     ProcessInfo.processInfo.processIdentifier),
                                 "memory": "not_preserved"])
                }
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
            if let folder = app.appInfo.relativeBundlePath {
            ScarletGuestSessionLedger.remove(folder: folder)
        }
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
        guard source.pathExtension.lowercased() == "ipa" else {
            showOriginalError = "기기 직접 설치에는 .ipa 파일이 필요합니다. .tipa는 게스트 앱으로 가져올 수 있습니다."
            return
        }
        guard !deviceInstallRunning, !guestImportActivity.isRunning,
              !sourceIsDownloading else {
            showOriginalError = "다른 앱 설치가 진행 중입니다."
            return
        }
        guard UserDefaults.sideStoreExist() else {
            ScarletDiagnosticRecorder.shared.record("sidestore", "engine_missing",
                status: "blocked", fields: ["reason": "engine_missing"])
            showOriginalError = "내장 SideStore 설치 엔진을 찾지 못했습니다."
            return
        }
        let readiness = ScarletSigningReadiness.inspect()
        guard readiness.canRequestNativeRefresh else {
            ScarletDiagnosticRecorder.shared.record("sidestore", "install_blocked",
                status: "blocked", fields: ["reason": readiness.safeBlockCategory])
            showOriginalError = "서명된 App Group 권한이나 개발팀이 일치하지 않아 기기 설치가 차단됐습니다."
            return
        }
        deviceInstallRunning = true
        deviceInstallStatus = "설치 파일 준비 중"
        showDeviceInstallSheet = true
        ScarletDiagnosticRecorder.shared.record("sidestore", "install_requested",
            fields: ["engine": "headless_appmanager", "route": "device"])
        Task { @MainActor in
            defer { deviceInstallRunning = false }
            let authenticated = await ScarletConnectedSideSignEngine().storedAuthenticated()
            guard authenticated else {
                deviceInstallStatus = "SideStore 로그인 확인이 필요합니다."
                ScarletDiagnosticRecorder.shared.record("sidestore", "install_blocked",
                    status: "blocked", fields: ["reason": "auth_unavailable"])
                return
            }
            let groupID = "group.com.SideStore.SideStore.P8EZT3U5N4"
            guard let containerURL = FileManager.default.containerURL(
                      forSecurityApplicationGroupIdentifier: groupID) else {
                deviceInstallStatus = "App Group 저장소에 접근할 수 없습니다."
                ScarletDiagnosticRecorder.shared.record("sidestore", "install_blocked",
                    status: "blocked", fields: ["reason": "app_group_unavailable"])
                return
            }
            // Do not let a previous request's stage contaminate this attempt.
            let stageDefaults = UserDefaults(suiteName: groupID)
            let stageKey = "Scarlet.Install.LastStage.V44"
            stageDefaults?.removeObject(forKey: stageKey)
            let directory = containerURL.appendingPathComponent(
                "ScarletDeviceInstall", isDirectory: true)
            let staged = directory.appendingPathComponent(
                "scarlet-device-\(UUID().uuidString).ipa")
            // Filename is a random UUID; only the matching installer worker
            // is allowed to open files from this one group container.
            do {
                deviceInstallStatus = "IPA 파일 준비 중"
                try FileManager.default.createDirectory(at: directory,
                    withIntermediateDirectories: true)
                let copied: Bool = await Task.detached(priority: .userInitiated) {
                    let scoped = source.startAccessingSecurityScopedResource()
                    defer { if scoped { source.stopAccessingSecurityScopedResource() } }
                    do {
                        try FileManager.default.copyItem(at: source, to: staged)
                        return true
                    } catch { return false }
                }.value
                guard copied else {
                    deviceInstallStatus = "IPA 파일을 읽을 수 없습니다."
                    ScarletDiagnosticRecorder.shared.record("sidestore", "install_failed",
                        status: "error", fields: ["reason": "staging_failed"])
                    return
                }
                defer { try? FileManager.default.removeItem(at: staged) }
                deviceInstallStatus = "내장 SideStore에서 서명·설치 중"
                // Original SideStore AppManager installs through its own
                // signing/provisioning/pairing engine. No SideInstaller UI.
                try await ScarletDeviceInstaller.install(stagedIPA: staged)
                deviceInstallStatus = "설치 엔진 반환 · 실제 iPhone 설치 결과 확인 필요"
                let finalStage = stageDefaults?.string(forKey: stageKey) ??
                    "stage_not_reported"
                ScarletDiagnosticRecorder.shared.record("sidestore",
                    "install_operation_returned",
                    fields: ["result": "appmanager_callback_completed",
                             "stage": finalStage,
                             "installation_verified": "false"])
            } catch {
                let nsError = error as NSError
                // SideStoreSupport wraps its worker error into the
                // SideStore NSError domain. Parse only known, non-secret
                // categorical codes rather than exposing Apple responses.
                let categoryText = nsError.domain + " " + nsError.localizedDescription
                let knownReasons = ["certificate_missing", "certificate_unavailable",
                    "pairing_unavailable", "pairing_invalid",
                    "pairing_file_missing", "rppairing_file_missing",
                    "rppairing_record_invalid", "profile_unavailable",
                    "app_group_unavailable", "staged_ipa_missing", "staged_ipa_invalid",
                    "worker_missing", "team_unavailable", "team_mismatch",
                    "auth_unavailable", "vpn_unavailable", "network_unavailable",
                    "device_network_unavailable", "device_endpoint_unavailable",
                    "device_identifier_unavailable", "minimuxer_not_started",
                    "certificate_expired", "certificate_revoked",
                    "device_operation_timed_out", "invalid_parameters",
                    "file_io_failure", "preflight_unclassified",
                    "transport_unclassified", "appmanager_unclassified",
                    "anisette_unavailable", "signing_failed",
                    "native_install_failed"]
                // SideStoreSupport may wrap the original XPC failure in
                // NSError(domain: "SideStore", code: 1). Search a FIXED
                // marker, never serialize the potentially private message.
                let marker = "scarlet.install."
                let normalized = categoryText.lowercased()
                let exactReason: String
                if let range = normalized.range(of: marker) {
                    exactReason = String(normalized[range.upperBound...]
                        .prefix(while: { $0.isLetter || $0.isNumber ||
                                         $0 == "_" || $0 == "-" }))
                } else {
                    exactReason = ""
                }
                let typedAppManagerCode = exactReason.hasPrefix("appmanager_error_code_") &&
                    exactReason.count <= 34 &&
                    exactReason.dropFirst("appmanager_error_code_".count)
                        .allSatisfy({ $0.isNumber || $0 == "-" })
                let reason = knownReasons.contains(exactReason) || typedAppManagerCode
                    ? exactReason : "install_transport_or_worker_unclassified"
                let stage: String
                if reason.hasPrefix("appmanager_") || reason == "signing_failed" ||
                   reason == "profile_unavailable" {
                    stage = "appmanager"
                } else if reason == "team_unavailable" ||
                          reason == "team_mismatch" || reason == "auth_unavailable" {
                    stage = "team"
                } else if reason == "certificate_missing" ||
                          reason == "certificate_unavailable" {
                    stage = "certificate"
                } else {
                    stage = "transport_or_preflight"
                }
                let lastWorkerStage = stageDefaults?.string(forKey: stageKey) ??
                    "stage_not_reported"
                ScarletDiagnosticRecorder.shared.record("sidestore",
                    "install_failed", status: "error",
                    fields: ["reason": reason, "stage": stage,
                             "worker_stage": lastWorkerStage,
                             "installation_verified": "false"])
                switch reason {
                case "team_unavailable", "team_mismatch", "auth_unavailable":
                    deviceInstallStatus = "SideStore 활성 개발팀 또는 로그인 복원이 필요합니다."
                case "minimuxer_not_started", "transport_unclassified",
                     "device_network_unavailable", "device_endpoint_unavailable",
                     "device_operation_timed_out", "vpn_unavailable":
                    deviceInstallStatus = "기기 연결 엔진을 준비하지 못했습니다. 페어링·전송 상태를 확인해야 합니다."
                case "network_unavailable":
                    deviceInstallStatus = "SideStore 네트워크 요청에 실패했습니다."
                case "certificate_missing", "certificate_unavailable":
                    deviceInstallStatus = "기존 서명 인증서를 찾을 수 없습니다. 인증서 발급·동기화가 필요합니다."
                case "rppairing_file_missing", "pairing_file_missing":
                    deviceInstallStatus = "기기의 RemoteRP 페어링 파일을 SideStore에서 찾지 못했습니다."
                case "rppairing_record_invalid":
                    deviceInstallStatus = "RemoteRP 페어링 파일 형식이 올바르지 않습니다."
                case "pairing_unavailable", "pairing_invalid":
                    deviceInstallStatus = "SideStore 페어링 데이터를 확인해야 합니다."
                case "profile_unavailable":
                    deviceInstallStatus = "Apple 프로비저닝 프로파일을 확인해야 합니다."
                default:
                    deviceInstallStatus = "기기 설치에 실패했습니다. 진단 로그에서 상태를 확인하세요."
                }
            }
        }
    }

    // SwiftUI presents the real iOS Files document picker. Copy the
    // security-scoped original into a scratch IPA: LiveContainer's original
    // startInstallApp removes its input URL after importing; the user's Files
    // original must never be removed.
    private func stageGuestIPAFromFiles(_ source: URL, presentProgress: Bool = true) {
        guard !guestImportActivity.isRunning, queuedGuestIPAURL == nil else {
            showOriginalError = "다른 게스트 앱 가져오기가 진행 중입니다."
            return
        }
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
            guestImportActivity.start()
            queuedGuestIPAURL = temporary
            installProgressMinimized = !presentProgress
            ScarletDiagnosticRecorder.shared.record("guest_import", "file_staged")
            showGuestImportProgress = presentProgress
        } catch {
            ScarletDiagnosticRecorder.shared.recordError("guest_import", "file_stage_failed", error: error)
            showOriginalError = "파일을 가져올 수 없습니다: \(error.localizedDescription)"
        }
    }

    // The hidden worker calls this ONLY when the original importer returns.
    // A sheet dismissal must never delete a file that the importer still owns.
    private func guestImportWorkerFinished() {
        if let staged = queuedGuestIPAURL {
            try? FileManager.default.removeItem(at: staged)
        }
        queuedGuestIPAURL = nil
    }

    private func handoffDownloadedSourceIfReady() {
        guard let staged = sourceDownloadedIPA else { return }
        sourceDownloadedIPA = nil
        stageGuestIPAFromFiles(staged, presentProgress: !installProgressMinimized)
        try? FileManager.default.removeItem(at: staged)
    }

    private func openActiveInstallProgress() {
        if deviceInstallRunning || deviceInstallStatus != nil {
            showDeviceInstallSheet = true
        } else if sourceIsDownloading || sourceDownloadedIPA != nil || sourceDownloadError != nil {
            showSourceDownloadSheet = true
        } else if guestImportActivity.hasActivity {
            showGuestImportProgress = true
        }
    }

    // R6P19: Source download -1005 was reproduced across archived and
    // current iPhone sessions, regardless of guest engine or root geometry.
    // Retry ONLY transient network-connection-loss (not HTTP 403/404,
    // untrusted URL, cancellation, IPA validation or other failures).
    // Use server-provided resume bytes if available. If that single resume
    // fails (except cancellation), make one ordinary HTTPS attempt; all
    // retries remain bounded and never weaken ATS or ZIP validation.
    private func downloadSourceWithConnectionRecovery(
        from url: URL, using session: URLSession
    ) async throws -> (URL, URLResponse) {
        var resumeData: Data?
        for attempt in 1...3 {
            try Task.checkCancellation()
            do {
                if let resumeData {
                    do {
                        return try await session.download(resumeFrom: resumeData)
                    } catch {
                        try Task.checkCancellation()
                        let ns = error as NSError
                        // `NSURLErrorCannotResume` does NOT exist in the
                        // pinned Xcode 27.2 Foundation SDK. Fall back only
                        // after an actual URL-loading error; a user cancel
                        // never restarts a download.
                        guard ns.domain == NSURLErrorDomain &&
                              ns.code != NSURLErrorCancelled else {
                            throw error
                        }
                        ScarletDiagnosticRecorder.shared.record(
                            "sources", "guest_download_resume_rejected",
                            fields: ["count": String(attempt)])
                        return try await session.download(from: url)
                    }
                }
                return try await session.download(from: url)
            } catch {
                try Task.checkCancellation()
                let ns = error as NSError
                guard ns.domain == NSURLErrorDomain &&
                      ns.code == NSURLErrorNetworkConnectionLost &&
                      attempt < 3 else { throw error }
                resumeData = ns.userInfo[NSURLSessionDownloadTaskResumeData] as? Data
                if resumeData?.isEmpty == true { resumeData = nil }
                ScarletDiagnosticRecorder.shared.record(
                    "sources", "guest_download_connection_retry",
                    fields: ["count": String(attempt),
                             "result": resumeData == nil ? "fresh" : "resume"])
                sourceDownloadStage = "연결이 끊겨 다운로드 재시도 중 (\(attempt)/2)"
                try await Task.sleep(for: .milliseconds(attempt == 1 ? 400 : 1000))
            }
        }
        throw URLError(.networkConnectionLost)
    }

    // Source install routes through the same original LC guest IPA importer
    // as Files, never through the unmounted upstream LCAppListView notification.
    private func installSourceGuestApp(_ downloadID: String) {
        guard !sourceIsDownloading, !guestImportActivity.isRunning,
              queuedGuestIPAURL == nil else {
            showOriginalError = "다른 게스트 앱 가져오기가 진행 중입니다."
            return
        }
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
        installProgressMinimized = false
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
                let (downloaded, response) = try await
                    downloadSourceWithConnectionRecovery(from: url, using: session)
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
                // A sheet may have been swiped away minutes earlier. Stage
                // immediately if already minimized; otherwise onDismiss
                // transfers after SwiftUI has closed the first native sheet.
                sourceDownloadedIPA = staged
                ScarletDiagnosticRecorder.shared.record("sources", "guest_download_completed",
                    fields: ["route": "livecontainer", "stage": "download_only"])
                if showSourceDownloadSheet {
                    showSourceDownloadSheet = false
                } else {
                    handoffDownloadedSourceIfReady()
                }
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
                            hasDownload: app.latestVersion?.downloadURL != nil,
                            iconURL: app.iconURL
                        )
                    }
                )
            },
            onAction: handle,
            onOpenGuest: runGuest,
            onDeleteGuest: requestGuestUninstall,
            onOpenSource: { raw in
                guard let source = originalSources.sources.first(where: {
                    $0.id.absoluteString == raw
                }) else { return }
                selectedSourceURL = source.id
                showSourceActions = true
                ScarletDiagnosticRecorder.shared.record(
                    "sources", "source_actions_opened")
            },
            onAddSource: {
                ScarletDiagnosticRecorder.shared.record("sources", "direct_add_requested")
                newSourceURL = ""
                sourceInputError = nil
                showSourceURLInput = true
            },
            onInstallSourceApp: installSourceGuestApp,
            activeInstallText: deviceInstallRunning ? (deviceInstallStatus ?? "기기 설치 중") :
                (sourceIsDownloading ? sourceDownloadStage :
                 (sourceDownloadError != nil ? "다운로드 실패" :
                  (guestImportActivity.hasActivity ? guestImportActivity.title : deviceInstallStatus))),
            onShowActiveInstall: openActiveInstallProgress,
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
                        .safeAreaInset(edge: .top) {
                            Toggle(isOn: $experimentalFullscreenResident) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("실험적 전체화면 RAM 유지")
                                        .font(.subheadline.weight(.medium))
                                    Text("창 크기를 바꾸지 않는 LiveProcess 장면 전환 · 기기 검증 전")
                                        .font(.caption2).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(.regularMaterial)
                            // Always allow OFF without restarting Scarlet.
                            // Preserve existing LiveProcess objects; only stop
                            // new pilot dispatch and hide its UI on OFF.
                            .onChange(of: experimentalFullscreenResident) { oldMode, newMode in
                                ScarletDiagnosticRecorder.shared.record(
                                    "guest", "pilot_setting_changed",
                                    fields: ["old_mode": oldMode ? "on" : "off",
                                             "new_mode": newMode ? "on" : "off",
                                             "live_session": fullscreenStack.hasResidentSession ? "true" : "false",
                                             "result": "setting_applied_without_restart"])
                                if !newMode {
                                    fullscreenStack.goHome()
                                    ScarletDiagnosticRecorder.shared.record(
                                        "guest", "pilot_mode_disabled_immediately",
                                        fields: ["result": "classic_launch_selected_next",
                                                 "memory": "existing_liveprocess_not_terminated"])
                                }
                            }
                            .accessibilityHint("실험 모드는 앱 재실행 없이 켜거나 끌 수 있습니다.")
                        }
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
        // V48 recovery: OFF means truly OFF. The previous unconditional
        // ignoresSafeArea compositor stayed mounted even in classic mode and
        // stale ledger slots could keep forcing the pilot engine.
        // Never mount its UIKit subtree for an ordinary original-LC launch.
        .overlay {
            if experimentalFullscreenResident || fullscreenStack.hasResidentSession {
                ScarletFullscreenSceneViewportRepresentable(
                    stack: fullscreenStack, installedApps: sharedModel.apps)
                    .ignoresSafeArea(.all, edges: .all)
                    .statusBarHidden(fullscreenStack.isVisible &&
                        fullscreenStack.nativeStatusBarCollisionShield)
                    .opacity(fullscreenStack.isVisible ? 1 : 0)
                    .allowsHitTesting(fullscreenStack.isVisible)
                    .accessibilityIdentifier("SCARLET_V45_NATIVE_FULLSCREEN_VIEWPORT")
            }
        }
        .statusBarHidden(fullscreenStack.isVisible &&
            fullscreenStack.nativeStatusBarCollisionShield)
        // P49: this view is hosted by the *key host UIWindow*; changing the
        // non-key resident overlay owner's preferred style in P47 could not
        // affect UIStatusBarManager. Use the actual guest background tone as
        // a temporary root presentation preference only while resident.
        // P51: do not force presentation-wide appearance if native
        // status icons were withheld due to a proven unsafe guest header.
        .preferredColorScheme(fullscreenStack.isVisible &&
            !fullscreenStack.nativeStatusBarCollisionShield
            ? fullscreenStack.hostStatusBarScheme : nil)
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletPilotRemoteSafeAreaChanged"))) { note in
            let stage = note.userInfo?["stage"] as? String ?? "unknown"
            let top = (note.userInfo?["top"] as? NSNumber)?.intValue ?? -1
            let bottom = (note.userInfo?["bottom"] as? NSNumber)?.intValue ?? -1
            ScarletDiagnosticRecorder.shared.record(
                "layout", "pilot_remote_safearea_applied",
                status: top > 0 ? "success" : "warning",
                fields: ["stage": stage,
                         "safe_top_pt": String(top),
                         "safe_bottom_pt": String(bottom),
                         "result": top > 0 ? "nonzero_remote_scene_safearea"
                                           : "zero_remote_scene_safearea"])
        }
        // Keep the real LiveContainer importer mounted OUTSIDE the sheet.
        // The sheet is a read-only view of host-owned progress, so swiping
        // it down cannot cancel work or delete its staged input IPA.
        .background(alignment: .topLeading) {
            if let queuedGuestIPAURL {
                LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,
                              scarletActivity: guestImportActivity,
                              scarletOnImportFinished: guestImportWorkerFinished)
                    .environmentObject(downloadHelper)
                    .environmentObject(sharedModel)
                    .environmentObject(LCAppSortManager.shared)
                    .frame(width: 1, height: 1)
                    .clipped()
                    .opacity(0)
                    .allowsHitTesting(false)
                    .accessibilityHidden(true)
                    .accessibilityIdentifier("SCARLET_HIDDEN_GUEST_IMPORT_WORKER")
            }
        }
        .onAppear {
            // A new host entry must NOT display tabs from a previous user
            // session. A guest->Scarlet app-list return carries a short
            // one-use continuation ticket, so A->host->B still shows A,B.
            ScarletGuestSessionLedger.prepareForHostAppearance()
            ScarletInstalledProfileReadback.verifyNewProcess()
            // Disable the V34 maximized virtual-window experiment on iPhone.
            // Only presentation preferences are touched; never guest data,
            // certificates, pairing or installed application bundles.
            if UIDevice.current.userInterfaceIdiom == .phone {
                UserDefaults.standard.set(false, forKey: "LCLaunchInMultitaskMode")
                UserDefaults.standard.set(false, forKey: "LCLaunchMultitaskMaximized")
                LCUtils.appGroupUserDefault.set(false, forKey: "LCMaxOneAppOnStage")
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "original_fullscreen_policy", status: "success",
                    fields: ["virtual_window": "disabled",
                             "guest_geometry": "original"])
            }
            // Guest apps virtualize Application Support. Collect the previous
            // guest's anonymous switcher trace before showing host diagnostics.
            ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()
            ScarletDiagnosticRecorder.shared.record("boot", "host_visible",
                fields: ["count": String(sharedModel.apps.count),
                         "engine": "livecontainer",
                         "available": UserDefaults.sideStoreExist() ? "true" : "false"])
            recordLayout()
            _ = ensureOriginalLCGuestBootstrap()
            bridgeExistingSideStoreCertificateIfSafe()
            reportPreviousGuestLaunchFailure()
            refreshStoredLoginState()
            if #available(iOS 27.0, *) {
                ScarletDevicePairingModel.shared.refreshStoredState()
            }
            // UIKit window creation can lag behind SwiftUI view construction.
            // The actual dock is initialized lazily and attached when ready.
            Task { @MainActor in
                await ScarletAutomaticRenewal.shared.foregroundCatchUp()
            }
            // V36: legacy LC dock renderer is absent from the binary.
            NSLog("[SCARLET_BOOT] phase=home-visible legacy-dock-source-removed=1")
            ScarletDiagnosticRecorder.shared.record(
                "boot", "legacy_dock_source_removed",
                status: "success", fields: ["owner": "scarlet_guest_switcher"])
        }
        .onChange(of: scenePhase) { phase in
            ScarletDiagnosticRecorder.shared.record("lifecycle", "scene_phase",
                fields: ["state": String(describing: phase)])
            if phase == .active && !showScarletAppleIDLogin {
                ScarletGuestSessionLedger.reconcileHostForeground()
                ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()
                refreshStoredLoginState()
                if #available(iOS 27.0, *) {
                    ScarletDevicePairingModel.shared.refreshStoredState()
                }
                Task { @MainActor in
                    await ScarletAutomaticRenewal.shared.foregroundCatchUp()
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletCertificateAutoBridgeRequested"))) { _ in
            bridgeExistingSideStoreCertificateIfSafe()
            NotificationCenter.default.post(
                name: Notification.Name("ScarletCertificateAutoBridgeFinished"),
                object: nil)
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
        .onChange(of: showSourceActions) { visible in
            ScarletDiagnosticRecorder.shared.record("sources",
                visible ? "source_actions_visible" : "source_actions_dismissed")
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
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletPresentDevicePairing"))) { _ in
            guard !showInAppDevicePairing else { return }
            showInAppDevicePairing = true
            ScarletDiagnosticRecorder.shared.record("pairing", "sheet_presented")
        }
        .sheet(isPresented: $showInAppDevicePairing) {
            if #available(iOS 27.0, *) {
                ScarletDevicePairingSheet()
                    .presentationDetents([.large])
                    .presentationBackground(
                        Color(red: 0.104, green: 0.079, blue: 0.147))
                    .presentationDragIndicator(.visible)
                    .accessibilityIdentifier("SCARLET_STABLE_DEVICE_PAIRING_SHEET")
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
            if guestImportActivity.isRunning {
                installProgressMinimized = true
                ScarletDiagnosticRecorder.shared.record("guest_import",
                    "sheet_minimized", fields: ["worker_kept_alive": "true"])
            }
        }) {
            VStack(spacing: 13) {
                if #available(iOS 26.0, *) {
                    Image(systemName: guestImportActivity.phase == .signingUnverified
                          ? "exclamationmark.shield.fill" : "shippingbox.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                        .frame(width: 58, height: 58)
                        .glassEffect()
                } else {
                    Image(systemName: "shippingbox.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                }
                Text(guestImportActivity.title)
                    .font(.title3.bold())
                    .foregroundStyle(.white)
                Text(guestImportActivity.detail)
                    .font(.subheadline)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Color(red: 0.78, green: 0.75, blue: 0.85))
                    .accessibilityIdentifier("SCARLET_GUEST_IMPORT_STAGE")
                if guestImportActivity.isRunning {
                    ProgressView(value: guestImportActivity.progress, total: 1)
                        .tint(Color(red: 0.76, green: 0.67, blue: 1))
                        .accessibilityIdentifier("SCARLET_GUEST_IMPORT_ACTUAL_PROGRESS")
                }
                // During import, swipe down the sheet to minimize it; no
                // redundant '내리기' button competes with the system gesture.
                if !guestImportActivity.isRunning {
                    Button("닫기") {
                        showGuestImportProgress = false
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(red: 0.44, green: 0.33, blue: 0.77))
                    .accessibilityIdentifier("SCARLET_IMPORT_PROGRESS_CLOSE")
                }
            }
            .padding(.horizontal, 26)
            .padding(.vertical, 16)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .presentationDetents([.height(325)])
            .presentationDragIndicator(.visible)
            .presentationBackground(Color(red: 0.14, green: 0.12, blue: 0.22))
            .accessibilityIdentifier("SCARLET_BRANDED_GUEST_IMPORT_CARD")
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
        .sheet(isPresented: $showDeviceInstallSheet) {
            // Presentation only. The XPC install task is owned by the host
            // and can continue while the user browses Scarlet's other tabs.
            VStack(spacing: 12) {
                Image(systemName: "iphone.gen3")
                    .font(.system(size: 27))
                    .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                Text("앱 설치")
                    .font(.title3.bold())
                    .foregroundStyle(.white)
                Text(deviceInstallStatus ?? "내장 SideStore 처리 중")
                    .font(.subheadline)
                    .foregroundStyle(Color(red: 0.82, green: 0.78, blue: 0.89))
                    .multilineTextAlignment(.center)
                    .accessibilityIdentifier("SCARLET_DEVICE_INSTALL_STATUS")
                if deviceInstallRunning {
                    ProgressView()
                        .tint(Color(red: 0.76, green: 0.67, blue: 1))
                    Text("창을 내려도 앱 내부에서 설치 작업이 계속됩니다.")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.secondary)
                } else {
                    Button("닫기") { showDeviceInstallSheet = false }
                        .buttonStyle(.borderedProminent)
                        .accessibilityIdentifier("SCARLET_DEVICE_INSTALL_DONE")
                }
            }
            .padding(.horizontal, 24)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .presentationDetents([.height(300)])
            .presentationDragIndicator(.visible)
            .presentationBackground(Color(red: 0.14, green: 0.12, blue: 0.22))
            .accessibilityIdentifier("SCARLET_NATIVE_DEVICE_INSTALL_SHEET")
        }
        .sheet(isPresented: $showSourceDownloadSheet, onDismiss: {
            if sourceIsDownloading && sourceDownloadedIPA == nil {
                installProgressMinimized = true
                ScarletDiagnosticRecorder.shared.record("sources", "sheet_minimized",
                    fields: ["download_kept_alive": "true"])
            }
            handoffDownloadedSourceIfReady()
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
                HStack(spacing: 12) {
                    if sourceIsDownloading {
                        Button("다운로드 취소") {
                            sourceDownloadTask?.cancel()
                            showSourceDownloadSheet = false
                        }
                        .accessibilityIdentifier("SCARLET_SOURCE_DOWNLOAD_CANCEL")
                    }
                    if !sourceIsDownloading {
                        Button("닫기") {
                            showSourceDownloadSheet = false
                        }
                        .accessibilityIdentifier("SCARLET_SOURCE_DOWNLOAD_CLOSE")
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.44, green: 0.33, blue: 0.77))
            }
            // The system sheet IS the visible rounded surface. The former
            // extra RoundedRectangle + opaque sheet background produced two
            // concentric panels over the source list on iPhone.
            .padding(.horizontal, 24)
            .padding(.vertical, 18)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .presentationDetents([.height(340)])
            .presentationBackground(Color(red: 0.14, green: 0.12, blue: 0.22))
            .presentationDragIndicator(.visible)
            .accessibilityIdentifier("SCARLET_BRANDED_SOURCE_DOWNLOAD_SHEET")
        }
        .confirmationDialog(
            "소스 관리", isPresented: $showSourceActions,
            titleVisibility: .visible
        ) {
            if let selectedSourceURL,
               let item = originalSources.sources.first(where: { $0.id == selectedSourceURL }) {
                Button("소스 새로고침") {
                    Task { @MainActor in
                        await originalSources.refreshSource(item)
                        ScarletDiagnosticRecorder.shared.record(
                            "sources", "single_source_refresh_requested")
                    }
                }
                .accessibilityIdentifier("SCARLET_SINGLE_SOURCE_REFRESH")
                Button("소스 삭제", role: .destructive) {
                    confirmRemoveSource = true
                }
                .accessibilityIdentifier("SCARLET_SINGLE_SOURCE_REMOVE")
            }
            Button("취소", role: .cancel) { selectedSourceURL = nil }
        } message: {
            Text("이 소스만 관리합니다. 추가는 화면 아래 소스 추가 버튼에서 진행합니다.")
        }
        .confirmationDialog(
            "선택한 소스를 삭제하시겠습니까?",
            isPresented: $confirmRemoveSource,
            titleVisibility: .visible
        ) {
            Button("소스만 삭제", role: .destructive) {
                if let selectedSourceURL,
                   let item = originalSources.sources.first(where: { $0.id == selectedSourceURL }) {
                    originalSources.removeSource(item)
                    ScarletDiagnosticRecorder.shared.record(
                        "sources", "single_source_removed")
                }
                selectedSourceURL = nil
            }
            Button("취소", role: .cancel) { selectedSourceURL = nil }
        } message: {
            Text("등록된 소스와 캐시만 삭제하며 이미 설치한 게스트 앱과 앱 데이터는 유지합니다.")
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

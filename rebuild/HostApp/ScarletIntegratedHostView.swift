// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI
import UIKit
import UniformTypeIdentifiers
import Security

@available(iOS 17.0, *)
struct ScarletIntegratedHostView: View {
    @Environment(\.scenePhase) private var scenePhase
    @EnvironmentObject private var sharedModel: SharedModel
    // Guest window enumeration is sourced lazily from the live scene registry.
    // Avoid initializing the dock before UIWindow and its view tree exist.
    @StateObject private var downloadHelper = DownloadHelper()
    @StateObject private var originalSources = AltStoreSourcesViewModel()
    // A single Files picker serves both explicitly selected installation routes.
    private enum IPAInstallRoute { case guest, device }
    @State private var pendingIPAInstallRoute: IPAInstallRoute = .guest
    @State private var showGuestFilePicker = false
    @State private var showGuestImportProgress = false
    @State private var queuedGuestIPAURL: URL?
    @State private var showNativeSources = false
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
                lastOpenedAt: app.appInfo.lastLaunched
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
        ScarletDiagnosticRecorder.shared.record("guest", "certificate_preflight",
            fields: ["certificate_present": cert == nil ? "false" : "true",
                     "password_present": password == nil ? "false" : "true",
                     "team_match": teamMatch])
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
                // Record host/certificate compatibility without modifying it.
                recordGuestCertificatePreflight()
                // Delegates and guest bundle identity remain original LC.
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
                    icon: "link"
                )
            },
            onAction: handle,
            onOpenGuest: runGuest,
            onDeleteGuest: requestGuestUninstall,
            onOpenSource: { _ in showNativeSources = true },
            onAddSource: {
                sharedModel.selectedTab = .sources
                showNativeSources = true
            },
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
            onTabChanged: recordTab
        )
        .environmentObject(downloadHelper)
        .onAppear {
            ScarletDiagnosticRecorder.shared.record("boot", "host_visible",
                fields: ["count": String(sharedModel.apps.count),
                         "engine": "livecontainer",
                         "available": UserDefaults.sideStoreExist() ? "true" : "false"])
            recordLayout()
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
                    .presentationDetents([.medium])
                    .interactiveDismissDisabled()
            }
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

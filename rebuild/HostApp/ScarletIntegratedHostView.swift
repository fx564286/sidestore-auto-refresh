// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI

@available(iOS 17.0, *)
struct ScarletIntegratedHostView: View {
    @EnvironmentObject private var sharedModel: SharedModel
    // Guest window enumeration is sourced lazily from the live scene registry.
    // Avoid initializing the dock before UIWindow and its view tree exist.
    @StateObject private var downloadHelper = DownloadHelper()
    @StateObject private var originalSources = AltStoreSourcesViewModel()
    @State private var showNativeAppLibrary = false
    @State private var showNativeSources = false
    @State private var showNativeSettings = false
    @State private var showScarletAppleIDLogin = false
    @State private var showOriginalError: String?

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

    private func runGuest(_ key: String) {
        guard let app = sharedModel.apps.first(where: {
            ($0.appInfo.relativeBundlePath ?? $0.bundleIdentifier) == key
        }) else {
            showOriginalError = "선택한 앱이 기존 LiveContainer에 등록되어 있지 않습니다."
            return
        }
        Task { @MainActor in
            do {
                // Delegates and guest bundle identity remain original LC.
                try await app.runApp()
            } catch {
                showOriginalError = error.localizedDescription
                // The unchanged upstream screen keeps the complete
                // certificate/container diagnostics available for recovery.
                showNativeAppLibrary = true
            }
        }
    }

    private func prepareDeviceIPAInstall() {
        // Do not open SideStore's UI. Device installation requires the
        // SideStore headless install/signing engine and verified profiles.
        // The older integrated app implements IPA staging -> installSharedIPA.
        // This rebuild has not yet ported and verified that transport.
        guard UserDefaults.sideStoreExist() else {
            showOriginalError = "내장 SideStore 설치 엔진을 찾지 못했습니다."
            return
        }
        showOriginalError = "iOS 앱 설치 엔진의 서명·기기 설치 연결이 아직 검증되지 않았습니다. 원본 IPA와 기존 인증서·프로파일은 변경하지 않았습니다."
    }

    private func handle(_ action: ScarletControl) {
        switch action {
        case .localImportGuestIPA:
            sharedModel.selectedTab = .apps
            showNativeAppLibrary = true
        case .serviceBeginSignIn:
            showScarletAppleIDLogin = true
        case .serviceInstallIPA:
            prepareDeviceIPAInstall()
        case .localOpenEmbeddedSideStore,
             .serviceRefreshApp, .serviceSyncAppIDs,
             .serviceSetSettings, .serviceReadSettings:
            // Never redirect any SideStore service button to its guest UI.
            showOriginalError = "SideStore 화면 이동은 사용하지 않습니다. 해당 기능은 Scarlet 내부 엔진 연결이 검증된 후 사용할 수 있습니다."
        case .localAppearance, .localStorageNavigation, .serviceReadLogs,
             .localTapProbe, .localClearNotifications:
            showNativeSettings = true
        }
    }

    var body: some View {
        ScarletIndependentShell(
            snapshot: ScarletHostPresentationSnapshot(
                serviceConnected: UserDefaults.sideStoreExist(),
                appleAuthenticated: false,
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
            onOpenSource: { _ in showNativeSources = true },
            onAddSource: {
                sharedModel.selectedTab = .sources
                showNativeSources = true
            },
            preservedGlassTabBar: { tab in
                AnyView(ScarletNativeGlassTabBar(selected: tab))
            }
        )
        .environmentObject(downloadHelper)
        .onAppear {
            // UIKit window creation can lag behind SwiftUI view construction.
            // The actual dock is initialized lazily and attached when ready.
            DispatchQueue.main.async {
                MultitaskDockManager.shared.scarletEnsureWindowHost()
                NSLog("[SCARLET_BOOT] phase=home-visible dock-root-attached=%d",
                      MultitaskDockManager.shared.windowHostingView.superview != nil ? 1 : 0)
            }
        }
        .sheet(isPresented: $showScarletAppleIDLogin) {
            // Credentials remain in a Scarlet-owned ephemeral view.
            // The embedded SideStore guest authentication UI is NOT opened.
            ScarletAppleIDLoginSheet(engine: ScarletPendingSideStoreEngineBridge())
        }
        .sheet(isPresented: $showNativeAppLibrary) {
            NavigationStack {
                // ORIGINAL LC guest IPA importer, including file/URL import,
                // container selection, per-app signature and error feedback.
                LCAppListView()
                    .environmentObject(downloadHelper)
            }
            .environmentObject(sharedModel)
            .environmentObject(LCAppSortManager.shared)
        }
        .sheet(isPresented: $showNativeSources) {
            NavigationStack {
                LCSourcesView()
            }
            .environmentObject(sharedModel)
            .environmentObject(LCAppSortManager.shared)
        }
        .sheet(isPresented: $showNativeSettings) {
            NavigationStack {
                LCSettingsView()
            }
            .environmentObject(sharedModel)
            .environmentObject(LCAppSortManager.shared)
        }
        .alert("Scarlet Crystal 진단", isPresented: Binding(
            get: { showOriginalError != nil },
            set: { if !$0 { showOriginalError = nil } }
        )) {
            Button("확인", role: .cancel) { showOriginalError = nil }
        } message: {
            Text(showOriginalError ?? "")
        }
    }

}

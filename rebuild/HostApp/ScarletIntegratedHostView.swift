// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI

@available(iOS 17.0, *)
struct ScarletIntegratedHostView: View {
    @EnvironmentObject private var sharedModel: SharedModel
    @ObservedObject private var guestDock = MultitaskDockManager.shared
    @StateObject private var downloadHelper = DownloadHelper()
    @StateObject private var originalSources = AltStoreSourcesViewModel()
    @State private var showNativeAppLibrary = false
    @State private var showNativeSources = false
    @State private var showNativeSettings = false
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

    private func openEmbeddedSideStore() {
        guard UserDefaults.sideStoreExist() else {
            showOriginalError = "내장 SideStore 실행 파일이 없습니다. 통합 IPA를 검사하세요."
            return
        }
        LCUtils.openSideStore(delegate: nil)
    }

    private func handle(_ action: ScarletControl) {
        switch action {
        case .localImportGuestIPA:
            sharedModel.selectedTab = .apps
            showNativeAppLibrary = true
        case .localOpenEmbeddedSideStore,
             .serviceBeginSignIn,
             .serviceRefreshApp,
             .serviceSyncAppIDs,
             .serviceInstallIPA,
             .serviceSetSettings,
             .serviceReadSettings:
            openEmbeddedSideStore()
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

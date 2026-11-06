// Scarlet Crystal new integrated LiveContainer host (engineering candidate).
// This file is compiled INTO the upstream LiveContainerSwiftUI framework.
// The native engine owns guest paths and SideStore operations; this view
// does not replace either engine, credentials, profiles or guest storage.
import SwiftUI

@available(iOS 17.0, *)
struct ScarletIntegratedHostView: View {
    @EnvironmentObject private var sharedModel: SharedModel
    @StateObject private var downloadHelper = DownloadHelper()
    @State private var showNativeAppLibrary = false
    @State private var showNativeSources = false
    @State private var showNativeSettings = false
    @State private var showWindowManager = false
    @State private var showOriginalError: String?
    @State private var panelSelection = 0

    private var guestItems: [ScarletGuestPresentation] {
        sharedModel.apps.map { app in
            ScarletGuestPresentation(
                id: app.appInfo.relativeBundlePath ?? app.bundleIdentifier,
                title: app.displayName,
                detail: app.isAppRunning ? "실행 요청 중" : "설치됨",
                isRunning: app.isAppRunning,
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
            sources: [],
            onAction: handle,
            onOpenGuest: runGuest,
            onOpenSource: { _ in showNativeSources = true },
            onAddSource: {
                sharedModel.selectedTab = .sources
                showNativeSources = true
            },
            preservedGlassSwitchControl: AnyView(
                ScarletNativeGlassSwitcher {
                    showWindowManager = true
                }
            ),
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
        .overlay {
            if showWindowManager {
                ZStack {
                    Color.black.opacity(0.16)
                        .ignoresSafeArea()
                        .contentShape(Rectangle())
                        .onTapGesture { showWindowManager = false }
                        .accessibilityIdentifier("SCARLET_GLASS_OUTSIDE_DISMISS")
                    windowPanel
                }
            }
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

    private var windowPanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 2) {
                Button {
                    panelSelection = 0
                } label: {
                    Text("최근 앱")
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(panelSelection == 0 ? Color.purple.opacity(0.55)
                                                        : Color.clear, in: Capsule())
                }
                Button {
                    panelSelection = 1
                } label: {
                    Text("창 관리")
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(panelSelection == 1 ? Color.purple.opacity(0.55)
                                                        : Color.clear, in: Capsule())
                }
            }
            .buttonStyle(.plain)
            Text(panelSelection == 0 ? "최근 실행 앱" : "현재 창")
                .font(.headline)
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(guestItems.filter { $0.lastOpenedAt != nil }) { guest in
                        Button {
                            showWindowManager = false
                            runGuest(guest.id)
                        } label: {
                            Label(guest.title, systemImage: guest.icon)
                                .frame(maxWidth: .infinity, minHeight: 44,
                                       alignment: .leading)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .frame(maxHeight: 220)
            if panelSelection == 1 {
                // The source-backed original LC APIs are required here.
                // Without a verified selected window owner, destructive
                // per-window controls stay disabled instead of lying.
                HStack(spacing: 8) {
                    Button("최소화") {
                        if #available(iOS 16, *) {
                            MultitaskDockManager.shared.minimizeAllWindows()
                        }
                    }
                    Button("최대화") {}
                        .disabled(true)
                    Button("닫기") {}
                        .disabled(true)
                }
                .buttonStyle(.plain)
                .frame(maxWidth: .infinity)
                .font(.footnote.weight(.semibold))
                .accessibilityHint("최대화 및 닫기는 원본 창 소유권 연결 전 비활성화")
            }
        }
        .padding(17)
        .foregroundStyle(.white)
        .frame(maxWidth: 346)
        .background {
            SCNativeLiquidGlassSurface(cornerRadius: 24,
                                        selectedIndex: panelSelection)
                .clipShape(RoundedRectangle(cornerRadius: 24))
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24)
                .stroke(.white.opacity(0.22), lineWidth: 1)
        }
        .padding(.horizontal, 20)
        .accessibilityIdentifier("SCARLET_NATIVE_GLASS_WINDOW_PANEL")
    }
}

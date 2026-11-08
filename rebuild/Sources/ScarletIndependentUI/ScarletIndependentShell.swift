// Scarlet Crystal — independent presentation layer.
// Native Liquid Glass, LiveContainer, SideStore and SideSign are injected via
// host adapters. This file owns NO engine, glass renderer, credential or profile.
import SwiftUI
import UIKit

public struct ScarletGuestPresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let icon: String
    // Derived only from the actual LiveContainer guest registry; never infer
    // running state from a static Figma example or an installation timestamp.
    public let isRunning: Bool
    public let lastOpenedAt: Date?
    public let iconPNG: Data?

    public init(id: String, title: String, detail: String,
                icon: String = "app.fill",
                isRunning: Bool = false,
                lastOpenedAt: Date? = nil,
                iconPNG: Data? = nil) {
        self.id = id
        self.title = title
        self.detail = detail
        self.icon = icon
        self.isRunning = isRunning
        self.lastOpenedAt = lastOpenedAt
        self.iconPNG = iconPNG
    }
}

public struct ScarletSourceAppPresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let name: String
    public let version: String
    public let hasDownload: Bool

    public init(id: String, name: String, version: String, hasDownload: Bool) {
        self.id = id
        self.name = name
        self.version = version
        self.hasDownload = hasDownload
    }
}

public struct ScarletSourcePresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let icon: String
    public let apps: [ScarletSourceAppPresentation]

    public init(id: String, title: String, detail: String,
                icon: String = "square.stack.fill",
                apps: [ScarletSourceAppPresentation] = []) {
        self.id = id
        self.title = title
        self.detail = detail
        self.icon = icon
        self.apps = apps
    }
}

public struct ScarletHostPresentationSnapshot: Equatable, Sendable {
    public let serviceConnected: Bool
    public let appleAuthenticated: Bool
    public let pairingVerified: Bool
    public let installationVerified: Bool
    public let signingVerified: Bool
    // Only the installed app's verified profile may be used here.
    // The published GitHub IPA's profile is not the phone's profile.
    public let installedProfileExpiresAt: Date?
    public let installedProfileVerified: Bool
    public let upstreamCandidateAvailable: Bool

    public init(serviceConnected: Bool = false, appleAuthenticated: Bool = false,
                pairingVerified: Bool = false, signingVerified: Bool = false,
                installationVerified: Bool = false,
                installedProfileExpiresAt: Date? = nil,
                installedProfileVerified: Bool = false,
                upstreamCandidateAvailable: Bool = false) {
        self.serviceConnected = serviceConnected
        self.appleAuthenticated = appleAuthenticated
        self.pairingVerified = pairingVerified
        self.signingVerified = signingVerified
        self.installationVerified = installationVerified
        self.installedProfileExpiresAt = installedProfileExpiresAt
        self.installedProfileVerified = installedProfileVerified
        self.upstreamCandidateAvailable = upstreamCandidateAvailable
    }
}

private enum ScarletPresentationColor {
    static let background = Color(red: 0.051, green: 0.051, blue: 0.094)
    static let surface = Color(red: 36.0/255, green: 35.0/255, blue: 58.0/255)
    static let stroke = Color(red: 69.0/255, green: 66.0/255, blue: 93.0/255)
    static let accent = Color(red: 0.667, green: 0.588, blue: 1.0)
    static let purple = Color(red: 0.39, green: 0.30, blue: 0.89)
    static let text = Color(red: 0.988, green: 0.98, blue: 1.0)
    static let muted = Color(red: 0.72, green: 0.70, blue: 0.77)
    static let warning = Color(red: 1.0, green: 0.73, blue: 0.48)
    static let success = Color(red: 0.49, green: 0.85, blue: 0.78)
}

// The independent presentation target typechecks without the LC host.
// Keep scroll-edge styling self-contained instead of referring to host
// NativeGlass extensions that aren't linked into the standalone target.
private extension View {
    @ViewBuilder
    func scarletIndependentScrollEdge() -> some View {
        if #available(iOS 26.0, *) {
            self.scrollEdgeEffectHidden(true, for: .all)
        } else {
            self
        }
    }
}

private struct ScarletPanel<Content: View>: View {
    @ViewBuilder let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .padding(17)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
    }
}

private struct ScarletActionRow: View {
    let title: String
    let detail: String
    let icon: String
    let enabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 36, height: 36, alignment: .center)
                    .background(ScarletPresentationColor.stroke.opacity(0.4),
                                in: RoundedRectangle(cornerRadius: 11))
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.system(size: 16, weight: .semibold))
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if !detail.isEmpty {
                        Text(detail)
                            .font(.system(size: 13))
                            .foregroundStyle(ScarletPresentationColor.muted)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(ScarletPresentationColor.muted)
                    .frame(width: 20, alignment: .center)
            }
            .foregroundStyle(ScarletPresentationColor.text)
            .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityHint(enabled ? detail : "현재 연결 또는 권한 상태에서 사용할 수 없습니다.")
    }
}

private struct ScarletStatusBadge: View {
    let title: String
    let color: Color

    var body: some View {
        Text(title)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(color)
            .fixedSize(horizontal: true, vertical: false)
            .padding(.horizontal, 12)
            .frame(height: 27)
            .background(ScarletPresentationColor.surface, in: Capsule())
    }
}

/// Rows and separators are based on REAL guest records. No trailing
/// divider is rendered below the final app (fixes the Figma lone line).
private struct ScarletGuestActionRow: View {
    let guest: ScarletGuestPresentation
    let onDelete: () -> Void
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: guest.icon)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 36, height: 36, alignment: .center)
                    .background(ScarletPresentationColor.stroke.opacity(0.4),
                                in: RoundedRectangle(cornerRadius: 11))
                Text(guest.title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.text)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
            .padding(.horizontal, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(guest.title)
        .accessibilityHint(guest.isRunning ? "실행 중인 앱으로 전환" : "앱 실행")
        .accessibilityIdentifier("SCARLET_GUEST_ACTION_ROW")
        .contextMenu {
            Button(role: .destructive) {
                onDelete()
            } label: {
                Label("앱 삭제", systemImage: "trash")
            }
            .accessibilityIdentifier("SCARLET_GUEST_UNINSTALL_MENU")
        }
    }
}

// iPhone-style launcher: one independent icon per guest, no enclosing list card.
private struct ScarletGuestLauncherTile: View {
    let guest: ScarletGuestPresentation
    let onDelete: () -> Void
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 7) {
                ZStack(alignment: .bottomTrailing) {
                    Group {
                        if let data = guest.iconPNG, let image = UIImage(data: data) {
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFit()
                        } else {
                            Image(systemName: guest.icon)
                                .resizable()
                                .scaledToFit()
                                .padding(18)
                                .foregroundStyle(ScarletPresentationColor.accent)
                                .background(ScarletPresentationColor.surface)
                        }
                    }
                    .frame(width: 66, height: 66)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(ScarletPresentationColor.stroke.opacity(0.65), lineWidth: 0.75)
                    }
                    if guest.isRunning {
                        Circle()
                            .fill(ScarletPresentationColor.success)
                            .frame(width: 10, height: 10)
                            .overlay(Circle().stroke(ScarletPresentationColor.background, lineWidth: 2))
                    }
                }
                Text(guest.title)
                    .font(.system(size: 11.5, weight: .medium))
                    .foregroundStyle(ScarletPresentationColor.text)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, minHeight: 30, alignment: .top)
            }
            .frame(maxWidth: .infinity, alignment: .top)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(guest.title)
        .accessibilityHint(guest.isRunning ? "실행 중인 게스트로 전환" : "게스트 앱 실행")
        .accessibilityIdentifier("SCARLET_GUEST_LAUNCHER_TILE")
        .contextMenu {
            Button(role: .destructive, action: onDelete) {
                Label("앱 삭제", systemImage: "trash")
            }
        }
    }
}

private struct ScarletGuestListCard: View {
    let guests: [ScarletGuestPresentation]
    let emptyText: String
    let onOpen: (String) -> Void
    let onDelete: (String) -> Void

    var body: some View {
        VStack(spacing: 0) {
            if guests.isEmpty {
                Text(emptyText)
                    .font(.footnote)
                    .foregroundStyle(ScarletPresentationColor.muted)
                    .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
                    .padding(.horizontal, 8)
            } else {
                ForEach(guests) { item in
                    ScarletGuestActionRow(
                        guest: item,
                        onDelete: { onDelete(item.id) },
                        action: { onOpen(item.id) }
                    )
                    if item.id != guests.last?.id {
                        Rectangle()
                            .fill(ScarletPresentationColor.stroke.opacity(0.55))
                            .frame(height: 1)
                            .padding(.horizontal, 8)
                    }
                }
            }
        }
        .padding(7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ScarletPresentationColor.surface,
                    in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
        }
    }
}

@available(iOS 16.0, *)
public struct ScarletIndependentShell: View {
    // User-selected tab order and labels, WITHOUT importing the example
    // screenshot's theme, dimensions or container layout.
    // The original UIKit Liquid Glass renderer remains unmodified.
    public enum Tab: String, CaseIterable {
        case sources = "소스"
        case apps = "앱"
        case tweaks = "트윅"
        case settings = "설정"

        public var icon: String {
            switch self {
            case .sources: "books.vertical"
            case .apps: "square.grid.2x2"
            case .tweaks: "wrench.and.screwdriver"
            case .settings: "gearshape"
            }
        }
    }

    public let snapshot: ScarletHostPresentationSnapshot
    public let guests: [ScarletGuestPresentation]
    public let sources: [ScarletSourcePresentation]
    public let onOpenSource: (String) -> Void
    public let onAddSource: () -> Void
    public let onInstallSourceApp: (String) -> Void
    public let onAction: (ScarletControl) -> Void
    public let onOpenGuest: (String) -> Void
    public let onDeleteGuest: (String) -> Void
    // The container's four tabs remain native Liquid Glass.
    // The one round switch control belongs to a running guest scene ONLY.
    // Keep the original interactive Liquid Glass tab-bar renderer. The host
    // binds the four destination tabs to this shell selection; no duplicated
    // material or synthetic glassEffect is introduced here.
    public let preservedGlassTabBar: (Binding<Tab>) -> AnyView
    // Original LC tweak file/enable/sign manager embedded directly in the tab.
    public let nativeTweaks: () -> AnyView
    // Direct embedded original LiveContainer settings, not a modal.
    public let nativeSettings: () -> AnyView
    // Only presentation state is emitted, no titles/guest IDs/credentials.
    public let onTabChanged: (String) -> Void
    // A mounted native TabView is observable without drawing a second bar.
    public let onSystemGlassMounted: () -> Void

    @State private var selected: Tab
    @State private var searchText = ""
    @ScaledMetric(relativeTo: .largeTitle) private var screenTitleSize: CGFloat = 28

    public init(snapshot: ScarletHostPresentationSnapshot,
                guests: [ScarletGuestPresentation],
                sources: [ScarletSourcePresentation],
                onAction: @escaping (ScarletControl) -> Void,
                onOpenGuest: @escaping (String) -> Void,
                onDeleteGuest: @escaping (String) -> Void = { _ in },
                onOpenSource: @escaping (String) -> Void,
                onAddSource: @escaping () -> Void,
                onInstallSourceApp: @escaping (String) -> Void = { _ in },
                preservedGlassTabBar: @escaping (Binding<Tab>) -> AnyView,
                nativeTweaks: @escaping () -> AnyView = { AnyView(EmptyView()) },
                nativeSettings: @escaping () -> AnyView = { AnyView(EmptyView()) },
                onTabChanged: @escaping (String) -> Void = { _ in },
                onSystemGlassMounted: @escaping () -> Void = {},
                initialTab: Tab = .apps) {
        self.snapshot = snapshot
        self.guests = guests
        self.sources = sources
        self.onAction = onAction
        self.onOpenGuest = onOpenGuest
        self.onDeleteGuest = onDeleteGuest
        self.onOpenSource = onOpenSource
        self.onAddSource = onAddSource
        self.onInstallSourceApp = onInstallSourceApp
        self.preservedGlassTabBar = preservedGlassTabBar
        self.nativeTweaks = nativeTweaks
        self.nativeSettings = nativeSettings
        self.onTabChanged = onTabChanged
        self.onSystemGlassMounted = onSystemGlassMounted
        self._selected = State(initialValue: initialTab)
    }

    public var body: some View {
        // iOS 26+ owns the complete native Liquid Glass tab hierarchy.
        // A custom ZStack overlay cannot teach a pushed NavigationView Form
        // about its occluded bottom, and can flatten the sampled glass.
        Group {
            if #available(iOS 26.0, *) {
                systemLiquidGlassTabs
            } else {
                legacyGlassTabs
            }
        }
        .background(ScarletPresentationColor.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .onAppear { onTabChanged(selected.rawValue) }
        .onChange(of: selected) { tab in onTabChanged(tab.rawValue) }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletOpenSigningSettings"))) { _ in
            // Navigate to the original LC certificate import / JIT-Less diagnose.
            // Do not present an unrelated or duplicated settings modal.
            selected = .settings
        }
    }

    private func heading(_ overline: String, _ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            if !overline.isEmpty {
                Text(overline.uppercased())
                    .font(.caption2.weight(.semibold))
                    .tracking(0.8)
                    .foregroundStyle(ScarletPresentationColor.accent)
            }
            Text(title)
                .font(.system(size: screenTitleSize, weight: .bold, design: .default))
                .foregroundStyle(ScarletPresentationColor.text)
            if !subtitle.isEmpty {
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // Apps displays only its heading, search and actual LiveContainer guests.
    // One title-leading menu owns both installation routes on a single tap.
    // The selected route opens the same native Files picker, without an app list.

    @available(iOS 26.0, *)
    private var systemLiquidGlassTabs: some View {
        // Apple TabView supplies its own floating iOS 26+ Liquid Glass,
        // safe-area integration, scroll underlap, native interactions and
        // automatic navigation-stack inset. No custom painted capsule overlays.
        TabView(selection: $selected) {
            ForEach(Tab.allCases, id: \.self) { tab in
                screen(for: tab)
                    .tabItem {
                        Label(tab.rawValue, systemImage: tab.icon)
                    }
                    .tag(tab)
            }
        }
        .tabBarMinimizeBehavior(.onScrollDown)
        .onAppear(perform: onSystemGlassMounted)
        .accessibilityIdentifier("SCARLET_IOS26_NATIVE_SYSTEM_GLASS_TABS")
    }

    private var legacyGlassTabs: some View {
        // Only old iOS uses the previous independent overlay bar.
        ZStack(alignment: .bottom) {
            ScarletPresentationColor.background.ignoresSafeArea()
            screen(for: selected)
            preservedGlassTabBar($selected)
                .frame(maxWidth: .infinity, alignment: .center)
                .frame(height: 62)
                .padding(.horizontal, 19)
                .padding(.bottom, 6)
                .zIndex(1)
                .accessibilityIdentifier("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR")
        }
    }

    @ViewBuilder
    private func screen(for tab: Tab) -> some View {
        Group {
            if tab == .settings {
                nativeSettings()
                    .scarletIndependentScrollEdge()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityIdentifier("SCARLET_INLINE_NATIVE_LC_SETTINGS")
            } else if tab == .tweaks {
                nativeTweaks()
                    .scarletIndependentScrollEdge()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityIdentifier("SCARLET_INLINE_NATIVE_LC_TWEAKS")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 17) {
                        if tab == .sources {
                            sourcesScreen
                        } else {
                            home
                        }
                        Color.clear
                            .frame(height: 140)
                            .accessibilityHidden(true)
                            .accessibilityIdentifier("SCARLET_SCROLL_END_CLEARANCE")
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 18)
                    .frame(maxWidth: 650, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .center)
                }
                .scrollIndicators(.hidden)
                .scarletIndependentScrollEdge()
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var home: some View {
        Group {
            HStack(spacing: 10) {
                Menu {
                    Button {
                        // User chooses one of two installation targets in a
                        // single tap, then the native iPhone Files importer.
                        onAction(.serviceInstallIPA)
                    } label: {
                        Label("IPA 설치하기", systemImage: "square.and.arrow.down")
                    }
                    .accessibilityIdentifier("SCARLET_INSTALL_CHOICE_DEVICE_IPA")

                    Button {
                        onAction(.localImportGuestIPA)
                    } label: {
                        Label("게스트 앱 설치하기", systemImage: "square.stack.3d.up.badge.a")
                    }
                    .accessibilityIdentifier("SCARLET_INSTALL_CHOICE_GUEST_APP")
                } label: {
                    Image(systemName: "doc.badge.plus")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(ScarletPresentationColor.accent)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .accessibilityLabel("앱 설치")
                .accessibilityHint("한 번 탭하여 IPA 설치 또는 게스트 앱 설치 선택")
                .accessibilityIdentifier("SCARLET_INSTALLED_APPS_ADD_FILE")
                heading("", "설치된 앱", "")
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(ScarletPresentationColor.accent)
                TextField("설치된 앱 검색", text: $searchText)
                    .font(.system(size: 14))
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .tint(ScarletPresentationColor.accent)
                    .accessibilityIdentifier("SCARLET_APP_SEARCH")
            }
            .padding(.horizontal, 14)
            .frame(height: 44)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20))
            .overlay {
                RoundedRectangle(cornerRadius: 20)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
            if visibleGuests.isEmpty {
                Text("설치된 앱이 없습니다.")
                    .font(.subheadline)
                    .foregroundStyle(ScarletPresentationColor.muted)
                    .frame(maxWidth: .infinity, minHeight: 120)
            } else {
                LazyVGrid(
                    columns: Array(repeating: GridItem(.flexible(minimum: 58), spacing: 12), count: 4),
                    alignment: .center, spacing: 18
                ) {
                    ForEach(visibleGuests) { guest in
                        ScarletGuestLauncherTile(
                            guest: guest,
                            onDelete: { onDeleteGuest(guest.id) },
                            action: { onOpenGuest(guest.id) }
                        )
                    }
                }
                .padding(.top, 12)
                .accessibilityIdentifier("SCARLET_APPS_FOUR_COLUMN_LAUNCHER")
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private var visibleGuests: [ScarletGuestPresentation] {
        guests.filter {
            searchText.isEmpty || $0.title.localizedCaseInsensitiveContains(searchText)
        }
    }

    private var sourcesScreen: some View {
        Group {
            heading("", "소스", "")
            if sources.isEmpty {
                ScarletPanel {
                    Text("소스를 추가해 앱 목록을 확인하세요.")
                        .font(.footnote)
                        .foregroundStyle(ScarletPresentationColor.muted)
                }
            } else {
                ForEach(sources) { source in
                    ScarletPanel {
                        HStack {
                            Image(systemName: source.icon)
                                .foregroundStyle(ScarletPresentationColor.accent)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(source.title).font(.headline)
                                Text(source.detail).font(.caption)
                                    .foregroundStyle(ScarletPresentationColor.muted)
                            }
                            Spacer()
                            Button { onOpenSource(source.id) } label: {
                                Image(systemName: "ellipsis.circle")
                            }
                            .accessibilityLabel("소스 관리")
                        }
                        if source.apps.isEmpty {
                            Text("앱 목록이 비어 있거나 소스를 불러오는 중입니다.")
                                .font(.footnote)
                                .foregroundStyle(ScarletPresentationColor.muted)
                        }
                        ForEach(source.apps) { app in
                            HStack(spacing: 10) {
                                Image(systemName: "app.fill")
                                    .foregroundStyle(ScarletPresentationColor.accent)
                                    .frame(width: 38, height: 38)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(app.name).font(.subheadline.weight(.medium))
                                        .lineLimit(1)
                                    Text(app.version).font(.caption2)
                                        .foregroundStyle(ScarletPresentationColor.muted)
                                }
                                Spacer(minLength: 6)
                                Button("게스트 설치") { onInstallSourceApp(app.id) }
                                    .font(.caption.weight(.semibold))
                                    .disabled(!app.hasDownload)
                                    .accessibilityIdentifier("SCARLET_SOURCE_APP_INSTALL")
                            }
                            .frame(minHeight: 49)
                        }
                    }
                }
            }
            Button(action: onAddSource) {
                Label("소스 추가", systemImage: "plus")
                    .font(.headline)
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .foregroundStyle(ScarletPresentationColor.text)
                    .background(ScarletPresentationColor.purple,
                                in: RoundedRectangle(cornerRadius: 13))
            }
            .buttonStyle(.plain)
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }


}

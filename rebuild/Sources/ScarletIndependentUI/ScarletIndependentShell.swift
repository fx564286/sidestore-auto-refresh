// Scarlet Crystal — independent presentation layer.
// Native Liquid Glass, LiveContainer, SideStore and SideSign are injected via
// host adapters. This file owns NO engine, glass renderer, credential or profile.
import SwiftUI

public struct ScarletGuestPresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let icon: String
    // Derived only from the actual LiveContainer guest registry; never infer
    // running state from a static Figma example or an installation timestamp.
    public let isRunning: Bool
    public let lastOpenedAt: Date?

    public init(id: String, title: String, detail: String,
                icon: String = "app.fill",
                isRunning: Bool = false,
                lastOpenedAt: Date? = nil) {
        self.id = id
        self.title = title
        self.detail = detail
        self.icon = icon
        self.isRunning = isRunning
        self.lastOpenedAt = lastOpenedAt
    }
}

public struct ScarletSourcePresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let icon: String

    public init(id: String, title: String, detail: String,
                icon: String = "square.stack.fill") {
        self.id = id
        self.title = title
        self.detail = detail
        self.icon = icon
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
    static let surface = Color(red: 0.125, green: 0.121, blue: 0.19)
    static let stroke = Color(red: 0.27, green: 0.25, blue: 0.36)
    static let accent = Color(red: 0.667, green: 0.588, blue: 1.0)
    static let purple = Color(red: 0.39, green: 0.30, blue: 0.89)
    static let text = Color(red: 0.988, green: 0.98, blue: 1.0)
    static let muted = Color(red: 0.72, green: 0.70, blue: 0.77)
    static let warning = Color(red: 1.0, green: 0.73, blue: 0.48)
    static let success = Color(red: 0.49, green: 0.85, blue: 0.78)
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
    }
}

private struct ScarletGuestListCard: View {
    let guests: [ScarletGuestPresentation]
    let emptyText: String
    let onOpen: (String) -> Void

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
                    ScarletGuestActionRow(guest: item) { onOpen(item.id) }
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
    public let onAction: (ScarletControl) -> Void
    public let onOpenGuest: (String) -> Void
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

    @State private var selected: Tab
    @State private var searchText = ""
    @ScaledMetric(relativeTo: .largeTitle) private var screenTitleSize: CGFloat = 28

    public init(snapshot: ScarletHostPresentationSnapshot,
                guests: [ScarletGuestPresentation],
                sources: [ScarletSourcePresentation],
                onAction: @escaping (ScarletControl) -> Void,
                onOpenGuest: @escaping (String) -> Void,
                onOpenSource: @escaping (String) -> Void,
                onAddSource: @escaping () -> Void,
                preservedGlassTabBar: @escaping (Binding<Tab>) -> AnyView,
                nativeTweaks: @escaping () -> AnyView = { AnyView(EmptyView()) },
                nativeSettings: @escaping () -> AnyView = { AnyView(EmptyView()) },
                initialTab: Tab = .apps) {
        self.snapshot = snapshot
        self.guests = guests
        self.sources = sources
        self.onAction = onAction
        self.onOpenGuest = onOpenGuest
        self.onOpenSource = onOpenSource
        self.onAddSource = onAddSource
        self.preservedGlassTabBar = preservedGlassTabBar
        self.nativeTweaks = nativeTweaks
        self.nativeSettings = nativeSettings
        self._selected = State(initialValue: initialTab)
    }

    public var body: some View {
        VStack(spacing: 0) {
            if selected == .settings {
                // The real original LCSettingsView is the tab content itself.
                // No "화면 설정" or "저장소" button opens a duplicate sheet.
                VStack(spacing: 0) {
                    HStack(spacing: 12) {
                        Text("설정")
                            .font(.system(size: screenTitleSize, weight: .bold))
                            .foregroundStyle(ScarletPresentationColor.text)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Button {
                            onAction(.serviceBeginSignIn)
                        } label: {
                            Label("Apple ID 로그인", systemImage: "person.crop.circle")
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .buttonStyle(.bordered)
                        .tint(ScarletPresentationColor.accent)
                        .accessibilityIdentifier("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN")
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 18)
                    .padding(.bottom, 10)
                    Text(snapshot.serviceConnected
                         ? "SideStore 엔진 감지 · Apple 로그인 검증 필요"
                         : "SideStore 인증 연결 확인 필요")
                        .font(.caption)
                        .foregroundStyle(ScarletPresentationColor.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 8)
                    nativeSettings()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .accessibilityIdentifier("SCARLET_INLINE_NATIVE_LC_SETTINGS")
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if selected == .tweaks {
                // Do not create a fake tweak-management card or a sheet.
                // The original LiveContainer LCTweaksView controls actual
                // tweak folders, dylib/framework imports and enable state.
                nativeTweaks()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityIdentifier("SCARLET_INLINE_NATIVE_LC_TWEAKS")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 17) {
                        switch selected {
                        case .sources: sourcesScreen
                        case .apps: home
                        case .tweaks, .settings: EmptyView()
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 18)
                    .padding(.bottom, 24)
                    .frame(maxWidth: 650, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .center)
                }
                .scrollIndicators(.hidden)
            }

            preservedGlassTabBar($selected)
                .frame(maxWidth: .infinity, alignment: .center)
                .frame(height: 62)
                .padding(.horizontal, 19)
                .padding(.bottom, 6)
                .accessibilityIdentifier("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR")
        }
        .background(ScarletPresentationColor.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
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

    // The Apps tab directly displays installed apps; Settings and Tweaks
    // render original LiveContainer managers. Preserve the custom Scarlet UI.
    // No stats, recent-app section, fake settings or duplicate navigation.
    // One Apps screen, two DISTINCT install targets, no SideStore guest UI.
    // The original guest importer handles LiveContainer-contained apps.
    // Device IPA signing and installation uses SideStore/SideSign only after
    // the embedded engine transport and Apple provisioning are verified.
    // Unified Home: both install engines and all real installed guest apps.
    // Home/Apps are one destination, not competing screens or overlay sheets.
    private var home: some View {
        Group {
            HStack(spacing: 10) {
                // Opens the genuine original LiveContainer app-manager screen
                // (the user's second screenshot), not a SideStore guest UI.
                Button {
                    onAction(.localImportGuestIPA)
                } label: {
                    Image(systemName: "doc.badge.plus")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(ScarletPresentationColor.accent)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("설치된 앱 관리 및 IPA 파일 추가")
                .accessibilityHint("원본 LiveContainer 앱 관리 화면 열기")
                .accessibilityIdentifier("SCARLET_INSTALLED_APPS_ADD_FILE")
                heading("", "설치된 앱", "")
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: 10) {
                installPathRow("SideStore 앱 설치",
                               icon: "plus",
                               detail: "SideStore 기기 IPA 설치",
                               identifier: "SCARLET_HOME_DEVICE_IPA_INSTALL") {
                    onAction(.serviceInstallIPA)
                }
                installPathRow("게스트 앱 설치",
                               icon: "plus",
                               detail: "LiveContainer 게스트 IPA 가져오기",
                               identifier: "SCARLET_HOME_GUEST_IPA_INSTALL") {
                    onAction(.localImportGuestIPA)
                }
            }
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
            ScarletGuestListCard(
                guests: visibleGuests,
                emptyText: "설치된 앱이 없습니다.",
                onOpen: onOpenGuest
            )
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private func installPathRow(_ title: String,
                                icon: String,
                                detail: String,
                                identifier: String,
                                action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 25, height: 36)
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.text)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 11)
            .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
            .contentShape(Rectangle())
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 16))
            .overlay {
                RoundedRectangle(cornerRadius: 16)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity)
        .accessibilityLabel(title)
        .accessibilityHint(detail)
        .accessibilityIdentifier(identifier)
    }

    private var visibleGuests: [ScarletGuestPresentation] {
        guests.filter {
            searchText.isEmpty || $0.title.localizedCaseInsensitiveContains(searchText)
        }
    }

    private var sourcesScreen: some View {
        Group {
            heading("", "소스", "")
            ScarletPanel {
                ForEach(sources) { source in
                    ScarletActionRow(title: source.title, detail: source.detail,
                                     icon: source.icon, enabled: true) {
                        onOpenSource(source.id)
                    }
                }
                if sources.isEmpty {
                    Text("소스를 추가해 앱 목록을 확인하세요.")
                        .font(.footnote)
                        .foregroundStyle(ScarletPresentationColor.muted)
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

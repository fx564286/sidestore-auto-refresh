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
    // Preserves the existing Scarlet Crystal bottom tab destinations exactly.
    // Window management remains exclusively in the circular app switcher.
    public enum Tab: String, CaseIterable {
        case home = "Home"
        case apps = "Apps"
        case sources = "Sources"
        case settings = "Settings"

        public var icon: String {
            switch self {
            case .home: "house"
            case .apps: "square.grid.3x3"
            case .sources: "books.vertical"
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

    @State private var selected: Tab
    @State private var searchText = ""
    @State private var showConnectionDetails: Bool
    @ScaledMetric(relativeTo: .largeTitle) private var screenTitleSize: CGFloat = 28

    public init(snapshot: ScarletHostPresentationSnapshot,
                guests: [ScarletGuestPresentation],
                sources: [ScarletSourcePresentation],
                onAction: @escaping (ScarletControl) -> Void,
                onOpenGuest: @escaping (String) -> Void,
                onOpenSource: @escaping (String) -> Void,
                onAddSource: @escaping () -> Void,
                preservedGlassTabBar: @escaping (Binding<Tab>) -> AnyView,
                initialTab: Tab = .home,
                initialConnectionDetails: Bool = false) {
        self.snapshot = snapshot
        self.guests = guests
        self.sources = sources
        self.onAction = onAction
        self.onOpenGuest = onOpenGuest
        self.onOpenSource = onOpenSource
        self.onAddSource = onAddSource
        self.preservedGlassTabBar = preservedGlassTabBar
        self._selected = State(initialValue: initialTab)
        self._showConnectionDetails = State(initialValue: initialConnectionDetails)
    }

    public var body: some View {
        ZStack(alignment: .bottomLeading) {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 17) {
                        switch selected {
                        case .home: home
                        case .apps: apps
                        case .sources: sourcesScreen
                        case .settings:
                        if showConnectionDetails {
                            connection
                        } else {
                            settings
                        }
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 18)
                    // Container screen intentionally has NO guest-only round switcher.
                    .padding(.bottom, 24)
                    .frame(maxWidth: 650, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .center)
                }
                .scrollIndicators(.hidden)

                // Restore pre-inline-settings native Liquid Glass navigation.
                // Original settings remains reachable and its engine intact.
                preservedGlassTabBar($selected)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .frame(height: 62)
                    .padding(.horizontal, 19)
                    .padding(.bottom, 6)
                    .accessibilityIdentifier("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR")
            }

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

    private func sectionTitle(_ label: String, trailing: String? = nil) -> some View {
        HStack {
            Text(label).font(.headline)
                .foregroundStyle(ScarletPresentationColor.text)
            Spacer()
            if let trailing {
                Text(trailing).font(.caption.weight(.semibold))
                    .foregroundStyle(ScarletPresentationColor.accent)
            }
        }
    }

    // Initial screen: Home and Settings are both visible WITHOUT a tab.
    // No stats, recent-app section, fake settings or duplicate navigation.
    private var home: some View {
        Group {
            heading("", "내 컨테이너", "")
            engineEntry("SideStore", icon: "square.and.arrow.down") {
                onAction(.localOpenEmbeddedSideStore)
            }
            .accessibilityIdentifier("SCARLET_HOME_SIDESTORE_ENGINE")
            engineEntry("가상 앱", icon: "square.stack.3d.up") {
                onAction(.localImportGuestIPA)
            }
            .accessibilityIdentifier("SCARLET_HOME_LIVECONTAINER_ENGINE")

        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private func engineEntry(_ title: String, icon: String,
                             action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 36, height: 36)
                    .background(ScarletPresentationColor.stroke.opacity(0.4),
                                in: RoundedRectangle(cornerRadius: 11))
                Text(title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.text)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity, minHeight: 78, alignment: .leading)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
            .contentShape(RoundedRectangle(cornerRadius: 20))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
    }

    // Virtual Apps: no recent/running/total filters or duplicate app statuses.
    // Original LiveContainer library remains available from the initial screen.
    private var visibleGuests: [ScarletGuestPresentation] {
        guests.filter {
            searchText.isEmpty || $0.title.localizedCaseInsensitiveContains(searchText)
        }
    }

    private var apps: some View {
        Group {
            heading("", "가상 앱", "")
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 20, height: 20)
                TextField("앱 검색", text: $searchText)
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
            Button {
                onAction(.localImportGuestIPA)
            } label: {
                Text("＋  앱 추가")
                    .font(.system(size: 16, weight: .semibold))
                    .frame(maxWidth: .infinity)
                    .frame(height: 47)
                    .foregroundStyle(ScarletPresentationColor.text)
                    .background(ScarletPresentationColor.purple,
                                in: RoundedRectangle(cornerRadius: 13))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("SCARLET_NATIVE_GUEST_IMPORT")
            ScarletGuestListCard(
                guests: visibleGuests,
                emptyText: "앱이 없습니다.",
                onOpen: onOpenGuest
            )
        }
        .foregroundStyle(ScarletPresentationColor.text)
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

    private var renewalAssessment: ScarletRefreshAssessment {
        ScarletRefreshPolicy().assess(
            now: Date(),
            profileExpiresAt: snapshot.installedProfileVerified
                ? snapshot.installedProfileExpiresAt : nil
        )
    }

    private var renewalSummary: String {
        guard snapshot.installedProfileVerified else {
            return "아이폰에 설치된 앱의 프로파일 확인 필요"
        }
        switch renewalAssessment.decision {
        case .healthy:
            guard let remaining = renewalAssessment.remainingSeconds else {
                return "유효기간 확인 필요"
            }
            return "만료까지 약 \(max(1, Int(remaining / 3600)))시간"
        case .refreshDue:
            return "서명 갱신 필요"
        case .alreadyExpired:
            return "서명 유효기간 만료"
        case .profileUnavailable:
            return "유효기간 확인 필요"
        }
    }

    private var renewalReady: Bool {
        snapshot.serviceConnected &&
        snapshot.appleAuthenticated &&
        snapshot.pairingVerified &&
        snapshot.installedProfileVerified
    }

    // 6:136 · Figma Settings: three left-anchored panels, centered CTA.
    // Row icon + title anchors: card X + 17 / + 65 pt respectively.
    private func compactSettingsCard<Content: View>(
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 0, content: content)
            .padding(9)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20))
            .overlay {
                RoundedRectangle(cornerRadius: 20)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
    }

    private var settings: some View {
        Group {
            heading("", "설정", "")
            compactSettingsCard {
                Text("컨테이너")
                    .font(.system(size: 18, weight: .semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .frame(height: 22)
                    .padding(.leading, 8)
                ScarletActionRow(title: "화면 설정",
                                 detail: "",
                                 icon: "circle.lefthalf.filled", enabled: true) {
                    onAction(.localAppearance)
                }
                .padding(.horizontal, 8)
                .frame(height: 62)
                Divider()
                ScarletActionRow(title: "저장소",
                                 detail: "",
                                 icon: "folder", enabled: true) {
                    onAction(.localStorageNavigation)
                }
                .padding(.horizontal, 8)
                .frame(height: 62)
            }
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 12) {
                    Text("계정 및 서명")
                        .font(.system(size: 18, weight: .semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Button("관리") {
                        showConnectionDetails = true
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("SCARLET_SIGNING_MANAGEMENT")
                }
                .frame(height: 22)
                Text(snapshot.serviceConnected ? "SideStore 인증" : "내장 SideStore 확인 필요")
                    .font(.system(size: 13))
                    .foregroundStyle(ScarletPresentationColor.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .frame(height: 16)
                Button {
                    onAction(.serviceBeginSignIn)
                } label: {
                    Text("Apple ID 로그인")
                        .font(.system(size: 15, weight: .semibold))
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .frame(height: 43)
                        .background(ScarletPresentationColor.purple,
                                    in: RoundedRectangle(cornerRadius: 13))
                }
                .buttonStyle(.plain)
                .disabled(!snapshot.serviceConnected)
                .accessibilityIdentifier("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN")
                .accessibilityHint("Scarlet의 Apple ID 로그인 입력 화면을 엽니다.")
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 17)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20))
            .overlay {
                RoundedRectangle(cornerRadius: 20)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
            compactSettingsCard {
                ScarletActionRow(title: "진단 로그",
                                 detail: "",
                                 icon: "waveform.path.ecg", enabled: true) {
                    onAction(.serviceReadLogs)
                }
                .padding(.horizontal, 8)
                .frame(height: 62)
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private var connection: some View {
        Group {
            HStack(spacing: 8) {
                Button {
                    showConnectionDetails = false
                } label: {
                    Label("설정", systemImage: "chevron.left")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(ScarletPresentationColor.accent)
                        .frame(minHeight: 44)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("SCARLET_CONNECTION_BACK")
                Spacer()
            }
            heading("", "연결 및 서명", "")
            ScarletPanel {
                Text("연결 상태")
                    .font(.title3.bold())
                Text(snapshot.serviceConnected ? "내장 SideStore 발견 · 로그인 상태 미검증" : "SideStore 실행 파일 없음")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
            Button {
                onAction(.serviceReadSettings)
            } label: {
                Label("연결 상태 확인", systemImage: "arrow.clockwise")
                    .font(.headline)
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .foregroundStyle(ScarletPresentationColor.text)
                    .background(ScarletPresentationColor.surface,
                                in: RoundedRectangle(cornerRadius: 13))
            }
            .buttonStyle(.plain)
            sectionTitle("설정 단계")
            ScarletPanel {
                statusRow("01", "기기 페어링", verified: snapshot.pairingVerified)
                Divider()
                statusRow("02", "Apple ID 로그인", verified: snapshot.appleAuthenticated)
                Divider()
                statusRow("03", "IPA 서명", verified: snapshot.signingVerified)
                Divider()
                statusRow("04", "기기 설치", verified: snapshot.installationVerified)
            }
            Button {
                onAction(.serviceBeginSignIn)
            } label: {
                Text("Apple ID 로그인 시작")
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .foregroundStyle(ScarletPresentationColor.text)
                    .background(ScarletPresentationColor.purple,
                                in: RoundedRectangle(cornerRadius: 13))
            }
            .disabled(!snapshot.serviceConnected)
            .accessibilityHint(snapshot.serviceConnected
                ? "Scarlet의 Apple ID 인증 화면을 엽니다."
                : "먼저 SideStore 서비스 연결을 복구해야 합니다.")
            Text("로그인 시 2단계 인증이 필요할 수 있습니다.")
                .font(.caption)
                .foregroundStyle(ScarletPresentationColor.muted)
            ScarletPanel {
                ScarletActionRow(title: "SideStore 열기",
                                 detail: "iOS 앱 설치 및 서명 갱신",
                                 icon: "square.and.arrow.down", enabled: true) {
                    onAction(.localOpenEmbeddedSideStore)
                }
            }
            ScarletPanel {
                Text("자동 갱신")
                    .font(.headline)
                Text(renewalSummary)
                    .font(.footnote)
                    .foregroundStyle(ScarletPresentationColor.muted)
                if snapshot.upstreamCandidateAvailable {
                    Text("원본 업데이트 후보 확인됨")
                        .font(.footnote)
                        .foregroundStyle(ScarletPresentationColor.accent)
                }
                if renewalAssessment.decision == .refreshDue ||
                   renewalAssessment.decision == .alreadyExpired {
                    Button {
                        onAction(.serviceRefreshApp)
                    } label: {
                        Text("서명 갱신")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 48)
                            .background(ScarletPresentationColor.purple,
                                        in: RoundedRectangle(cornerRadius: 13))
                    }
                    .buttonStyle(.plain)
                    .disabled(!renewalReady)
                    .accessibilityHint(renewalReady
                        ? "기기 설치 결과를 별도로 확인해야 합니다."
                        : "페어링, Apple 로그인 및 설치 프로파일 확인이 필요합니다.")
                }
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private func statusRow(_ number: String, _ title: String,
                           verified: Bool) -> some View {
        HStack {
            Text(number).font(.caption.weight(.bold))
                .foregroundStyle(ScarletPresentationColor.accent)
            Text(title).font(.subheadline.weight(.medium))
            Spacer()
            Text(verified ? "확인됨" : "확인 필요")
                .font(.caption)
                .foregroundStyle(verified
                                 ? ScarletPresentationColor.success
                                 : ScarletPresentationColor.warning)
        }
        .frame(minHeight: 44)
    }

}

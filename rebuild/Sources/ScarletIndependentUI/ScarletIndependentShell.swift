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
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(width: 36, height: 36)
                    .background(ScarletPresentationColor.stroke.opacity(0.4),
                                in: RoundedRectangle(cornerRadius: 10))
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.headline)
                    Text(detail).font(.footnote)
                        .foregroundStyle(ScarletPresentationColor.muted)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
            .foregroundStyle(ScarletPresentationColor.text)
            .frame(minHeight: 48)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityHint(enabled ? detail : "현재 연결 또는 권한 상태에서 사용할 수 없습니다.")
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
            case .apps: "square.stack.3d.up"
            case .sources: "square.stack"
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
    // The host MUST inject its EXISTING interactive circular Liquid Glass
    // app-switch button (including original tap/long-press gestures).
    // This new UI does not emulate the material or create a second button.
    public let preservedGlassSwitchControl: AnyView
    // Keep the original interactive Liquid Glass tab-bar renderer. The host
    // binds the four destination tabs to this shell selection; no duplicated
    // material or synthetic glassEffect is introduced here.
    public let preservedGlassTabBar: (Binding<Tab>) -> AnyView

    @State private var selected: Tab
    @State private var searchText = ""
    private enum AppFilter: String, CaseIterable {
        case all = "전체"
        case recent = "최근"
        case running = "실행 중"
    }
    @State private var appFilter: AppFilter = .all
    @State private var showLocalAppearance = false
    @State private var showLocalStorage = false
    @State private var showConnectionDetails: Bool
    @ScaledMetric(relativeTo: .largeTitle) private var screenTitleSize: CGFloat = 28

    public init(snapshot: ScarletHostPresentationSnapshot,
                guests: [ScarletGuestPresentation],
                sources: [ScarletSourcePresentation],
                onAction: @escaping (ScarletControl) -> Void,
                onOpenGuest: @escaping (String) -> Void,
                onOpenSource: @escaping (String) -> Void,
                onAddSource: @escaping () -> Void,
                preservedGlassSwitchControl: AnyView,
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
        self.preservedGlassSwitchControl = preservedGlassSwitchControl
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
                    // Keep the circular switcher's hit region accessible
                    // without covering local setting controls or final rows.
                    .padding(.bottom, 98)
                    .frame(maxWidth: 650)
                    .frame(maxWidth: .infinity)
                }
                .scrollIndicators(.hidden)

                // Native host tab bar: four destinations only, with the
                // original Scarlet Crystal Liquid Glass materials/gestures.
                // Do not add a Window Manager tab to this navigation bar.
                preservedGlassTabBar($selected)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .frame(height: 62)
                    .padding(.horizontal, 19)
                    .padding(.bottom, 6)
                    .accessibilityIdentifier("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR")
            }

            // The existing ONE circular guest app switcher opens the
            // original recent-apps/window-manager overlay (outside-tap
            // dismiss is the host's responsibility), not a new tab.
            preservedGlassSwitchControl
                .frame(width: 62, height: 62)
                .accessibilityLabel("앱 전환 및 창 관리")
                .accessibilityIdentifier("SCARLET_SINGLE_ROUND_APP_SWITCHER")
                .padding(.leading, 22)
                .padding(.bottom, 78)
        }
        .background(ScarletPresentationColor.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .sheet(isPresented: $showLocalAppearance) {
            NavigationStack {
                VStack(alignment: .leading, spacing: 12) {
                    Text("화면 및 인터페이스").font(.title2.bold())
                    Text("이 화면은 SideStore 연결 없이 열립니다.")
                    Text("실제 설정값은 기존 앱의 로컬 설정 저장소에 연결해야 합니다.")
                        .foregroundStyle(.secondary)
                    Spacer()
                }
                .padding()
                .navigationTitle("로컬 인터페이스")
            }
        }
        .sheet(isPresented: $showLocalStorage) {
            NavigationStack {
                VStack(alignment: .leading, spacing: 12) {
                    Text("컨테이너 데이터").font(.title2.bold())
                    Text("저장소 열람과 기존 데이터 보호를 위한 독립 경로입니다.")
                    Text("파괴적인 삭제나 마이그레이션은 제공하지 않습니다.")
                        .foregroundStyle(.secondary)
                    Spacer()
                }
                .padding()
                .navigationTitle("저장소")
            }
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
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(ScarletPresentationColor.muted)
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

    private var home: some View {
        Group {
            heading("Scarlet Crystal", "내 컨테이너", "앱 실행과 창 관리")
            ScarletPanel {
                Text("실행 가능")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(ScarletPresentationColor.success)
                Text("앱")
                    .font(.title2.bold())
                Text("설치된 앱")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
                HStack {
                    Text("\(guests.count)  설치 앱").font(.headline)
                    Spacer()
                    Text("컨테이너").font(.caption.weight(.semibold))
                        .foregroundStyle(ScarletPresentationColor.success)
                }
            }
            .background(ScarletPresentationColor.purple.opacity(0.28),
                        in: RoundedRectangle(cornerRadius: 20))
            sectionTitle("빠른 작업")
            HStack(spacing: 10) {
                quickAction("앱 추가", icon: "plus.app",
                            detail: "IPA 가져오기") {
                    onAction(.localImportGuestIPA)
                }
                quickAction("설정", icon: "gearshape",
                            detail: "환경설정") {
                    selected = .settings
                }
            }
            sectionTitle("최근 앱")
            ScarletPanel {
                ForEach(guests.prefix(3)) { guest in
                    ScarletActionRow(title: guest.title, detail: guest.detail,
                                     icon: guest.icon, enabled: true) {
                        onOpenGuest(guest.id)
                    }
                }
                if guests.isEmpty {
                    Text("등록된 앱이 없습니다.")
                        .font(.subheadline)
                        .foregroundStyle(ScarletPresentationColor.muted)
                }
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private func quickAction(_ title: String, icon: String, detail: String,
                             action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .center, spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(ScarletPresentationColor.accent)
                    .frame(maxWidth: .infinity, alignment: .center)
                Text(title)
                    .font(.headline)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, alignment: .center)
                Text(detail)
                    .font(.footnote)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(ScarletPresentationColor.muted)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
            .foregroundStyle(ScarletPresentationColor.text)
            .frame(maxWidth: .infinity, minHeight: 104, alignment: .center)
            .padding(15)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 20))
            .overlay {
                RoundedRectangle(cornerRadius: 20)
                    .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity)
    }

    private var visibleGuests: [ScarletGuestPresentation] {
        let matching = guests.filter {
            searchText.isEmpty || $0.title.localizedCaseInsensitiveContains(searchText)
        }
        switch appFilter {
        case .all:
            return matching
        case .recent:
            // "Recent" is not a fabricated running list. The real host must
            // populate lastOpenedAt based on actual guest activity.
            return matching.filter { $0.lastOpenedAt != nil }
                .sorted { ($0.lastOpenedAt ?? .distantPast) >
                          ($1.lastOpenedAt ?? .distantPast) }
        case .running:
            return matching.filter(\.isRunning)
        }
    }

    private var apps: some View {
        Group {
            heading("", "내 앱", "앱을 검색하거나 실행하세요.")
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(ScarletPresentationColor.accent)
                TextField("앱 검색", text: $searchText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .tint(ScarletPresentationColor.accent)
                    .accessibilityIdentifier("SCARLET_APP_SEARCH")
            }
            .padding(14)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 16))

            // Figma 6:75 filter labels and equal-width targets.
            HStack(spacing: 8) {
                ForEach(AppFilter.allCases, id: \.self) { item in
                    Button {
                        appFilter = item
                    } label: {
                        Text(item.rawValue)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(ScarletPresentationColor.text)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(
                                appFilter == item
                                    ? ScarletPresentationColor.purple
                                    : ScarletPresentationColor.surface,
                                in: Capsule()
                            )
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(appFilter == item ? .isSelected : [])
                    .accessibilityIdentifier("SCARLET_APP_FILTER_\(item.rawValue)")
                }
            }
            sectionTitle("앱", trailing: "\(visibleGuests.count)개")
            ScarletPanel {
                ForEach(visibleGuests) { guest in
                    ScarletActionRow(title: guest.title, detail: guest.detail,
                                     icon: guest.icon, enabled: true) {
                        onOpenGuest(guest.id)
                    }
                }
                if visibleGuests.isEmpty {
                    Text(appFilter == .running ? "실행 중인 앱이 없습니다."
                         : appFilter == .recent ? "최근 실행한 앱이 없습니다."
                         : "앱이 없습니다.")
                        .font(.footnote)
                        .foregroundStyle(ScarletPresentationColor.muted)
                }
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private var sourcesScreen: some View {
        Group {
            heading("", "소스", "앱 소스를 관리합니다.")
            sectionTitle("등록된 소스", trailing: "\(sources.count)개")
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

    private var settings: some View {
        Group {
            heading("", "설정", "컨테이너와 서명 설정")
            ScarletPanel {
                sectionTitle("기기 및 컨테이너")
                ScarletActionRow(title: "화면 설정",
                                 detail: "테마 및 표시",
                                 icon: "circle.lefthalf.filled", enabled: true) {
                    showLocalAppearance = true
                    onAction(.localAppearance)
                }
                Divider()
                ScarletActionRow(title: "저장소",
                                 detail: "앱 데이터 및 백업",
                                 icon: "folder", enabled: true) {
                    showLocalStorage = true
                    onAction(.localStorageNavigation)
                }
            }
            ScarletPanel {
                Text(snapshot.serviceConnected ? "SideStore 연결됨" : "SideStore 연결 필요")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(snapshot.serviceConnected
                                     ? ScarletPresentationColor.success
                                     : ScarletPresentationColor.warning)
                Text("계정 및 서명").font(.headline)
                Text("SideStore 연결 필요")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
                Button {
                    showConnectionDetails = true
                } label: {
                    Text("계정 및 서명 열기")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(ScarletPresentationColor.purple,
                                    in: RoundedRectangle(cornerRadius: 13))
                }
                .buttonStyle(.plain)
            }
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
            ScarletPanel {
                ScarletActionRow(title: "진단 로그",
                                 detail: "오류 및 동작 기록",
                                 icon: "waveform.path.ecg", enabled: true) {
                    onAction(.serviceReadLogs)
                }
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
            heading("", "연결 및 서명", "페어링 및 Apple 계정")
            ScarletPanel {
                Text(snapshot.serviceConnected ? "연결됨" : "연결 안 됨")
                    .font(.headline)
                    .foregroundStyle(snapshot.serviceConnected
                                     ? ScarletPresentationColor.success
                                     : ScarletPresentationColor.warning)
                Text("SideStore 연결 상태")
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
                ? "SideStore 로그인 요청을 시작합니다."
                : "먼저 SideStore 서비스 연결을 복구해야 합니다.")
            Text("로그인 시 2단계 인증이 필요할 수 있습니다.")
                .font(.caption)
                .foregroundStyle(ScarletPresentationColor.muted)
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

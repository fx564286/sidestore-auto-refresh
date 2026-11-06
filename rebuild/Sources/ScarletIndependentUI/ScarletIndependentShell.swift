// Scarlet Crystal — independent presentation layer.
// Native Liquid Glass, LiveContainer, SideStore and SideSign are injected via
// host adapters. This file owns NO engine, glass renderer, credential or profile.
import SwiftUI

public struct ScarletGuestPresentation: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let icon: String

    public init(id: String, title: String, detail: String, icon: String = "app.fill") {
        self.id = id; self.title = title; self.detail = detail; self.icon = icon
    }
}

public struct ScarletHostPresentationSnapshot: Equatable, Sendable {
    public let serviceConnected: Bool
    public let appleAuthenticated: Bool
    public let pairingVerified: Bool
    public let installationVerified: Bool
    public let signingVerified: Bool

    public init(serviceConnected: Bool = false, appleAuthenticated: Bool = false,
                pairingVerified: Bool = false, signingVerified: Bool = false,
                installationVerified: Bool = false) {
        self.serviceConnected = serviceConnected
        self.appleAuthenticated = appleAuthenticated
        self.pairingVerified = pairingVerified
        self.signingVerified = signingVerified
        self.installationVerified = installationVerified
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
                    Text(title).font(.subheadline.weight(.semibold))
                    Text(detail).font(.caption)
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

public struct ScarletIndependentShell: View {
    public enum Tab: String, CaseIterable {
        case home = "홈"
        case apps = "앱"
        case settings = "설정"
        case connection = "연결"

        var icon: String {
            switch self {
            case .home: "house"
            case .apps: "square.stack.3d.up"
            case .settings: "gearshape"
            case .connection: "link"
            }
        }
    }

    public let snapshot: ScarletHostPresentationSnapshot
    public let guests: [ScarletGuestPresentation]
    public let onAction: (ScarletControl) -> Void
    public let onOpenGuest: (String) -> Void
    // Host must call its ORIGINAL Liquid Glass presenter. Do not recreate
    // blur, glass material, gesture recognizers, or hit testing here.
    public let onOpenPreservedGlassWindowManager: () -> Void

    @State private var selected: Tab = .home
    @State private var searchText = ""
    @State private var showLocalAppearance = false
    @State private var showLocalStorage = false

    public init(snapshot: ScarletHostPresentationSnapshot,
                guests: [ScarletGuestPresentation],
                onAction: @escaping (ScarletControl) -> Void,
                onOpenGuest: @escaping (String) -> Void,
                onOpenPreservedGlassWindowManager: @escaping () -> Void) {
        self.snapshot = snapshot
        self.guests = guests
        self.onAction = onAction
        self.onOpenGuest = onOpenGuest
        self.onOpenPreservedGlassWindowManager = onOpenPreservedGlassWindowManager
    }

    public var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    switch selected {
                    case .home: home
                    case .apps: apps
                    case .settings: settings
                    case .connection: connection
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 18)
                .padding(.bottom, 28)
                .frame(maxWidth: 650)
                .frame(maxWidth: .infinity)
            }
            .scrollIndicators(.hidden)
            tabBar
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
            Text(overline.uppercased())
                .font(.caption2.weight(.semibold))
                .tracking(0.8)
                .foregroundStyle(ScarletPresentationColor.accent)
            Text(title)
                .font(.system(.largeTitle, design: .rounded, weight: .bold))
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
            heading("Scarlet Crystal", "나의 컨테이너",
                    "더 빠르게 실행하고, 더 명확하게 관리하세요.")
            ScarletPanel {
                Text("LIVE CONTAINER")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(ScarletPresentationColor.success)
                Text("내 작업 공간")
                    .font(.title2.bold())
                Text("기존 실행 엔진과 게스트 데이터를 유지합니다.")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
                HStack {
                    Text("\(guests.count)  설치 앱").font(.headline)
                    Spacer()
                    Text("실행 준비").font(.caption.weight(.semibold))
                        .foregroundStyle(ScarletPresentationColor.success)
                }
            }
            .background(ScarletPresentationColor.purple.opacity(0.28),
                        in: RoundedRectangle(cornerRadius: 20))
            sectionTitle("빠른 작업")
            HStack(spacing: 10) {
                quickAction("앱 추가", icon: "plus.app",
                            detail: "기존 엔진으로 가져오기") {
                    onAction(.serviceInstallIPA)
                }
                quickAction("창 관리", icon: "macwindow.on.rectangle",
                            detail: "원본 Liquid Glass 유지") {
                    onOpenPreservedGlassWindowManager()
                }
            }
            sectionTitle("최근 실행 앱", trailing: "전체")
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
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: icon).font(.title2)
                    .foregroundStyle(ScarletPresentationColor.accent)
                Text(title).font(.subheadline.weight(.semibold))
                Text(detail).font(.caption2)
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
            .foregroundStyle(ScarletPresentationColor.text)
            .frame(maxWidth: .infinity, minHeight: 104, alignment: .leading)
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

    private var apps: some View {
        Group {
            heading("LiveContainer", "내 앱", "앱을 찾고 실행하는 독립 목록입니다.")
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(ScarletPresentationColor.accent)
                TextField("앱 이름 검색", text: $searchText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .tint(ScarletPresentationColor.accent)
            }
            .padding(14)
            .background(ScarletPresentationColor.surface,
                        in: RoundedRectangle(cornerRadius: 16))
            sectionTitle("앱 라이브러리", trailing: "\(guests.count)개")
            ScarletPanel {
                ForEach(guests.filter { searchText.isEmpty ||
                    $0.title.localizedCaseInsensitiveContains(searchText) }) { guest in
                    ScarletActionRow(title: guest.title, detail: guest.detail,
                                     icon: guest.icon, enabled: true) {
                        onOpenGuest(guest.id)
                    }
                }
            }
            ScarletPanel {
                Text("게스트 실행은 기존 LiveContainer 엔진을 이용합니다.")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private var settings: some View {
        Group {
            heading("Preferences", "설정", "로컬 기능은 서비스 장애와 독립적으로 동작합니다.")
            ScarletPanel {
                sectionTitle("기기 및 컨테이너")
                ScarletActionRow(title: "화면 및 인터페이스",
                                 detail: "테마 · 레이아웃 · 접근성",
                                 icon: "circle.lefthalf.filled", enabled: true) {
                    showLocalAppearance = true
                    onAction(.localAppearance)
                }
                Divider()
                ScarletActionRow(title: "컨테이너 데이터",
                                 detail: "저장소 · 백업 · 개인정보",
                                 icon: "folder", enabled: true) {
                    showLocalStorage = true
                    onAction(.localStorageNavigation)
                }
                Divider()
                ScarletActionRow(title: "실행 및 창 관리",
                                 detail: "기존 Liquid Glass 창 제어",
                                 icon: "macwindow", enabled: true) {
                    onOpenPreservedGlassWindowManager()
                }
            }
            ScarletPanel {
                Text(snapshot.serviceConnected ? "SideStore 연결됨" : "SideStore 연결 필요")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(snapshot.serviceConnected
                                     ? ScarletPresentationColor.success
                                     : ScarletPresentationColor.warning)
                Text("SideStore & SideSign").font(.headline)
                Text("연결 상태는 로컬 설정 버튼을 비활성화하지 않습니다.")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
                Button {
                    onAction(.serviceReadSettings)
                } label: {
                    Text("상태 확인 및 다시 연결")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(ScarletPresentationColor.purple,
                                    in: RoundedRectangle(cornerRadius: 13))
                }
                .buttonStyle(.plain)
            }
            ScarletPanel {
                ScarletActionRow(title: "서비스 진단",
                                 detail: "상태와 실패 원인을 확인",
                                 icon: "waveform.path.ecg", enabled: true) {
                    onAction(.serviceReadLogs)
                }
            }
        }
        .foregroundStyle(ScarletPresentationColor.text)
    }

    private var connection: some View {
        Group {
            heading("Connection", "연결 및 서명",
                    "페어링·로그인·서명을 서로 다른 단계로 확인합니다.")
            ScarletPanel {
                Text(snapshot.serviceConnected ? "서비스 연결 확인됨" : "서비스 연결 미확인")
                    .font(.headline)
                    .foregroundStyle(snapshot.serviceConnected
                                     ? ScarletPresentationColor.success
                                     : ScarletPresentationColor.warning)
                Text("서비스 연결만으로 Apple 로그인 성공으로 표시하지 않습니다.")
                    .font(.caption)
                    .foregroundStyle(ScarletPresentationColor.muted)
            }
            sectionTitle("연결 단계")
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
            Text("6자리 2FA 코드는 실제 SideSign 요청에 따라 별도 화면에서 입력합니다.")
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

    private var tabBar: some View {
        HStack(spacing: 2) {
            ForEach(Tab.allCases, id: \.self) { tab in
                Button {
                    selected = tab
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.icon).font(.system(size: 19))
                        Text(tab.rawValue).font(.caption2)
                    }
                    .foregroundStyle(selected == tab ?
                                     ScarletPresentationColor.text :
                                     ScarletPresentationColor.muted)
                    .frame(maxWidth: .infinity, minHeight: 55)
                    .background(selected == tab ?
                                ScarletPresentationColor.stroke.opacity(0.45) :
                                Color.clear,
                                in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(7)
        .background(ScarletPresentationColor.surface,
                    in: RoundedRectangle(cornerRadius: 20))
        .overlay {
            RoundedRectangle(cornerRadius: 20)
                .stroke(ScarletPresentationColor.stroke, lineWidth: 1)
        }
        .padding(.horizontal, 20)
        .padding(.bottom, 9)
        .accessibilityIdentifier("SCARLET_INDEPENDENT_TAB_BAR")
    }
}

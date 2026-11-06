// Scarlet Crystal isolated screenshot preview ONLY.
// This is NOT the installable app or the original Liquid Glass runtime.
// The mock controls below are intentionally matte and carry a watermark.
import SwiftUI

@main
struct ScarletScreenshotPreviewApp: App {
    private let startTab: ScarletIndependentShell.Tab

    init() {
        let args = ProcessInfo.processInfo.arguments
        let index = args.firstIndex(of: "--screen")
        let screen = index.flatMap { i in args.indices.contains(i + 1) ? args[i + 1] : nil } ?? "home"
        switch screen {
        case "apps", "home": startTab = .apps
        case "sources": startTab = .sources
        case "tweaks": startTab = .tweaks
        case "settings", "connection": startTab = .settings
        default: startTab = .apps
        }
    }

    var body: some Scene {
        WindowGroup {
            ScarletIndependentShell(
                snapshot: ScarletHostPresentationSnapshot(
                    serviceConnected: false,
                    appleAuthenticated: false,
                    pairingVerified: false,
                    signingVerified: false,
                    installationVerified: false),
                guests: [
                    ScarletGuestPresentation(id: "fixture-one", title: "샘플 앱 A",
                        detail: "최근 사용", isRunning: true, lastOpenedAt: Date()),
                    ScarletGuestPresentation(id: "fixture-two", title: "샘플 앱 B",
                        detail: "설치됨"),
                ],
                sources: [],
                onAction: { _ in },
                onOpenGuest: { _ in },
                onOpenSource: { _ in },
                onAddSource: {},
                preservedGlassTabBar: { selected in
                    AnyView(
                        HStack(spacing: 4) {
                            ForEach(ScarletIndependentShell.Tab.allCases, id: \.self) { tab in
                                Button { selected.wrappedValue = tab } label: {
                                    VStack(spacing: 3) {
                                        Image(systemName: tab.icon)
                                            .font(.system(size: 19))
                                        Text(tab.rawValue)
                                            .font(.system(size: 11.5))
                                    }
                                    .frame(maxWidth: .infinity, minHeight: 52)
                                    .foregroundStyle(.white)
                                    .background(
                                        selected.wrappedValue == tab
                                            ? Color.gray.opacity(0.36)
                                            : Color.clear,
                                        in: Capsule()
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(5)
                        .background(Color.gray.opacity(0.2),
                                    in: Capsule())
                    )
                },
                nativeSettings: {
                    // Simulator-only placeholder. The installable app injects
                    // upstream LCSettingsView with real original controls.
                    AnyView(
                        NavigationStack {
                            Form {
                                Section("Scarlet Crystal") {
                                    Label("Apple ID 로그인 (미리보기)", systemImage: "person.crop.circle")
                                    Label("진단 로그 보기 및 공유 (미리보기)", systemImage: "ladybug")
                                }
                                Section("LiveContainer (미리보기)") {
                                    Label("인증서·JIT·멀티태스킹 설정", systemImage: "gearshape")
                                    Label("원본 설정 Form은 실기기에서 사용", systemImage: "info.circle")
                                }
                            }
                            .navigationTitle("설정")
                        }
                    )
                },
                initialTab: startTab
            )
            .overlay(alignment: .topTrailing) {
                Text("SIMULATOR UI PREVIEW · NOT LIQUID GLASS")
                    .font(.system(size: 8, weight: .medium))
                    .foregroundStyle(.yellow.opacity(0.75))
                    .padding(.trailing, 8)
                    .padding(.top, 1)
                    .allowsHitTesting(false)
            }
        }
    }
}

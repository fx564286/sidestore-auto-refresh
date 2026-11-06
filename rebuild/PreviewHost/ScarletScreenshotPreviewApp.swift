// Scarlet Crystal isolated screenshot preview ONLY.
// This is NOT the installable app or the original Liquid Glass runtime.
// The mock controls below are intentionally matte and carry a watermark.
import SwiftUI

@main
struct ScarletScreenshotPreviewApp: App {
    private let startTab: ScarletIndependentShell.Tab
    private let startAccountDetails: Bool

    init() {
        let args = ProcessInfo.processInfo.arguments
        let index = args.firstIndex(of: "--screen")
        let screen = index.flatMap { i in args.indices.contains(i + 1) ? args[i + 1] : nil } ?? "home"
        switch screen {
        case "apps": startTab = .apps
        case "sources": startTab = .sources
        case "settings": startTab = .home
        case "connection": startTab = .settings
        default: startTab = .home
        }
        startAccountDetails = screen == "connection"
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
                initialTab: startTab,
                initialConnectionDetails: startAccountDetails
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

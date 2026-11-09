// Scarlet PR48: a guest-only controller overlay. Do NOT alter the host shell,
// LCAppModel.runApp() or the guest's bounds, orientation and UI hierarchy.
// PR48 can run exactly one foreground guest process at a time; the panel must
// not mislabel unlaunched apps as concurrently running.
import Foundation
import SwiftUI
import UIKit

@available(iOS 17.0, *)
struct ScarletFullscreenGuestFloatingTab: View {
    let guestTitle: String
    let onPanel: (Bool) -> Void
    let onExit: () -> Void
    @State private var isOpen = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if isOpen {
                VStack(alignment: .leading, spacing: 12) {
                    Label("실행 중인 앱", systemImage: "square.stack.3d.up")
                        .font(.headline)
                    HStack(spacing: 12) {
                        Image(systemName: "app.fill")
                            .font(.title2)
                            .frame(width: 46, height: 46)
                            .background(.white.opacity(0.12),
                                        in: RoundedRectangle(cornerRadius: 12))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(guestTitle)
                                .font(.subheadline.weight(.semibold))
                                .lineLimit(1)
                            Text("현재 실행 중 · 전체화면")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 0)
                    }
                    Button {
                        isOpen = false
                        onPanel(false)
                        onExit()
                    } label: {
                        Label("게스트 종료 · 홍수정으로", systemImage: "rectangle.portrait.and.arrow.right")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("SCARLET_PR48_GUEST_EXIT")
                    Text("다른 앱은 홍수정에서 선택할 수 있습니다.")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .padding(16)
                .frame(maxWidth: 326, alignment: .leading)
                .background {
                    if #available(iOS 26.0, *),
                       !UIAccessibility.isReduceTransparencyEnabled {
                        RoundedRectangle(cornerRadius: 23)
                            .glassEffect(.regular, in: .rect(cornerRadius: 23))
                    } else {
                        SCNativeLiquidGlassSurface(cornerRadius: 23)
                            .clipShape(RoundedRectangle(cornerRadius: 23))
                    }
                }
                .accessibilityIdentifier("SCARLET_PR48_GUEST_PANEL")
            }
            ScarletNativeGlassSwitcher(openManager: {
                isOpen.toggle()
                onPanel(isOpen)
            })
            .accessibilityIdentifier("SCARLET_PR48_GUEST_ROUND_TAB")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }
}

// The normal full-screen guest runs a completely separate UIApplicationMain
// path, so do not attach to the guest's root controller or alter its size.
// A small non-key UIWindow drawn above it stays visible even when the guest
// replaces its own root controller (e.g. after login).
@available(iOS 17.0, *)
@MainActor
@objc(ScarletFullscreenGuestTabInstaller)
final class ScarletFullscreenGuestTabInstaller: NSObject {
    private static var floatingWindow: UIWindow?
    private static weak var guestWindow: UIWindow?
    private static var width: CGFloat = 72
    private static var height: CGFloat = 72
    private static var rotationObserver: NSObjectProtocol?
    private static var lastFailure: String?

    private static func frame(in window: UIWindow) -> CGRect {
        let scene = window.windowScene
        let bounds = scene?.coordinateSpace.bounds ?? window.bounds
        let inset = window.safeAreaInsets
        return CGRect(x: max(8, inset.left + 12),
                      y: max(0, bounds.height - max(12, inset.bottom + 9) - height),
                      width: min(width, max(64, bounds.width - 16)),
                      height: min(height, max(64, bounds.height - 16)))
    }

    private static func placeFloatingWindow() {
        guard let guestWindow, let floatingWindow else { return }
        let target = frame(in: guestWindow)
        if floatingWindow.frame != target {
            floatingWindow.frame = target
        }
    }

    @objc(installForGuestName:)
    static func installForGuestName(_ rawName: NSString) {
        guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive ||
                                $0.activationState == .foregroundInactive }),
              let original = scene.windows.first(where: { $0.isKeyWindow }),
              original.rootViewController?.viewIfLoaded?.window != nil else {
            if lastFailure != "window_not_ready" {
                lastFailure = "window_not_ready"
                NSLog("[SCARLET_GUEST_TAB] window_not_ready")
            }
            return
        }

        if let floatingWindow, floatingWindow.windowScene === scene,
           !floatingWindow.isHidden {
            guestWindow = original
            placeFloatingWindow()
            return
        }
        floatingWindow?.isHidden = true
        floatingWindow = nil
        guestWindow = original
        width = 72
        height = 72

        let name = (rawName as String).isEmpty ? "현재 게스트" : rawName as String
        let content = ScarletFullscreenGuestFloatingTab(
            guestTitle: name,
            onPanel: { shown in
                // Expand ONLY this transparent floating UIWindow, not the
                // guest UIWindow, UIViewController or safe-area constraints.
                let bounds = original.windowScene?.coordinateSpace.bounds ?? original.bounds
                width = shown ? min(340, max(72, bounds.width - 16)) : 72
                height = shown ? min(262, max(72, bounds.height - 16)) : 72
                placeFloatingWindow()
                ScarletDiagnosticRecorder.shared.record(
                    "guest", shown ? "fullscreen_tab_opened" : "fullscreen_tab_closed")
            },
            onExit: {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "fullscreen_tab_exit_requested")
                // Re-launch PR48's original host via its existing sentinel
                // without deleting guest data, P12, or altering orientation.
                guard let defaults = UserDefaults.lc() else { return }
                defaults.set("ui", forKey: "selected")
                defaults.removeObject(forKey: "selectedContainer")
                _ = LCSharedUtils.launchToGuestApp(withClassicMode: 0)
            }
        )

        let overlay = UIWindow(windowScene: scene)
        overlay.windowLevel = UIWindow.Level.alert + 1
        overlay.backgroundColor = .clear
        overlay.isOpaque = false
        let controller = UIHostingController(rootView: content)
        controller.view.backgroundColor = .clear
        controller.view.isOpaque = false
        overlay.rootViewController = controller
        overlay.frame = frame(in: original)
        // Do not makeKeyAndVisible(): stealing the key window breaks the guest
        // keyboard, scrolling and presentation stack.
        overlay.isHidden = false
        floatingWindow = overlay
        if rotationObserver == nil {
            rotationObserver = NotificationCenter.default.addObserver(
                forName: UIDevice.orientationDidChangeNotification,
                object: nil, queue: .main) { _ in
                Task { @MainActor in
                    placeFloatingWindow()
                    try? await Task.sleep(for: .milliseconds(200))
                    placeFloatingWindow()
                }
            }
        }
        lastFailure = nil
        NSLog("[SCARLET_GUEST_TAB] mounted_nonkey_window")
        ScarletDiagnosticRecorder.shared.record(
            "guest", "fullscreen_tab_mounted",
            fields: ["api": "UIKit.UIWindow", "material_owner": "system"])
    }
}

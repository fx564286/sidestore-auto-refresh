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

@available(iOS 17.0, *)
@MainActor
@objc(ScarletFullscreenGuestTabInstaller)
final class ScarletFullscreenGuestTabInstaller: NSObject {
    private static weak var installedRoot: UIViewController?
    private static var hosting: UIHostingController<ScarletFullscreenGuestFloatingTab>?
    private static var wrapper: UIView?
    private static var widthConstraint: NSLayoutConstraint?
    private static var heightConstraint: NSLayoutConstraint?
    private static var expanded = false

    // Invoked by the existing guest TweakLoader after UIApplication becomes
    // active. No swizzle of supportedInterfaceOrientations or guest view size.
    @objc(installForGuestName:)
    static func installForGuestName(_ rawName: NSString) {
        guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive }),
              let window = scene.windows.first(where: { $0.isKeyWindow }),
              let root = window.rootViewController,
              root.viewIfLoaded?.window != nil else { return }
        if installedRoot === root, wrapper?.superview != nil { return }

        // An application may rebuild its root VC after login/rotation. Clean
        // only our own independent overlay, never the guest application tree.
        wrapper?.removeFromSuperview()
        hosting?.willMove(toParent: nil)
        hosting?.removeFromParent()
        hosting = nil
        wrapper = nil
        installedRoot = root
        expanded = false

        let container = UIView()
        container.backgroundColor = .clear
        container.translatesAutoresizingMaskIntoConstraints = false
        root.view.addSubview(container)
        let w = container.widthAnchor.constraint(equalToConstant: 72)
        let h = container.heightAnchor.constraint(equalToConstant: 72)
        NSLayoutConstraint.activate([
            w, h,
            container.leadingAnchor.constraint(
                equalTo: root.view.safeAreaLayoutGuide.leadingAnchor,
                constant: 12),
            container.bottomAnchor.constraint(
                equalTo: root.view.safeAreaLayoutGuide.bottomAnchor,
                constant: -9),
            container.widthAnchor.constraint(
                lessThanOrEqualTo: root.view.safeAreaLayoutGuide.widthAnchor),
            container.heightAnchor.constraint(
                lessThanOrEqualTo: root.view.safeAreaLayoutGuide.heightAnchor)
        ])
        widthConstraint = w
        heightConstraint = h
        wrapper = container

        let title = (rawName as String).isEmpty ? "현재 게스트" : rawName as String
        let view = ScarletFullscreenGuestFloatingTab(
            guestTitle: title,
            onPanel: { shown in
                expanded = shown
                // Only our 72pt floating control changes size. Never resize
                // the underlying guest UIWindow, VC, view, or root safe area.
                let bounds = root.view.safeAreaLayoutGuide.layoutFrame
                widthConstraint?.constant = shown ? min(340, max(72, bounds.width - 12)) : 72
                heightConstraint?.constant = shown ? min(262, max(72, bounds.height - 12)) : 72
                UIView.animate(withDuration: 0.23) { root.view.layoutIfNeeded() }
            },
            onExit: {
                // The LC launcher recognizes the "ui" sentinel and returns
                // to PR48 host on a fresh process launch. Guest files, P12,
                // installed bundles and native orientation masks are untouched.
                guard let defaults = UserDefaults.lcUserDefaults() else { return }
                defaults.set("ui", forKey: "selected")
                defaults.removeObject(forKey: "selectedContainer")
                _ = LCSharedUtils.launchToGuestApp(withClassicMode: 0)
            }
        )
        let vc = UIHostingController(rootView: view)
        vc.view.backgroundColor = .clear
        vc.view.translatesAutoresizingMaskIntoConstraints = false
        root.addChild(vc)
        container.addSubview(vc.view)
        NSLayoutConstraint.activate([
            vc.view.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            vc.view.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            vc.view.topAnchor.constraint(equalTo: container.topAnchor),
            vc.view.bottomAnchor.constraint(equalTo: container.bottomAnchor)
        ])
        vc.didMove(toParent: root)
        hosting = vc
    }
}

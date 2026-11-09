// Scarlet Crystal guest-only app switcher.
// Mounted over an actual LiveContainer guest AppSceneViewController, NEVER the
// container's Home/Apps/Sources/Settings host shell.
// Thumbnails are captured only from owned active guest UIView instances.
// They are ephemeral, not copied from Figma or saved to app storage.
import SwiftUI
import UIKit

@MainActor
private final class ScarletWeakGuestController {
    weak var controller: UIViewController?
    init(_ controller: UIViewController) { self.controller = controller }
}

struct ScarletGuestTarget: Identifiable {
    let id: String
    let title: String
}

@available(iOS 16.1, *)
@MainActor
enum ScarletGuestSceneRegistry {
    private static var scenes: [String: ScarletWeakGuestController] = [:]

    static func register(_ controller: UIViewController, dataUUID: String) {
        scenes[dataUUID] = ScarletWeakGuestController(controller)
    }

    static func unregister(_ dataUUID: String) {
        scenes.removeValue(forKey: dataUUID)
    }

    static func availableGuests() -> [ScarletGuestTarget] {
        var found: [String: ScarletGuestTarget] = [:]
        for app in MultitaskDockManager.shared.apps {
            guard let view = app.view, view.superview != nil, view.window != nil else { continue }
            found[app.appUUID] = ScarletGuestTarget(id: app.appUUID, title: app.appName)
        }
        for (uuid, info) in MultitaskWindowManager.appDict {
            guard let controller = scenes[uuid]?.controller,
                  controller.viewIfLoaded?.window != nil else { continue }
            found[uuid] = ScarletGuestTarget(id: uuid, title: info.displayName)
        }
        return found.values.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
    }

    static func screenshot(dataUUID: String) -> UIImage? {
        var eligible: UIView?
        if let controller = scenes[dataUUID]?.controller,
           let view = controller.viewIfLoaded,
           view.window != nil && !view.isHidden {
            eligible = view
        } else if let dock = MultitaskDockManager.shared.apps.first(where: {
            $0.appUUID == dataUUID
        }), let view = dock.view, view.window != nil && !view.isHidden {
            eligible = view
        }
        guard let view = eligible, view.bounds.width >= 20, view.bounds.height >= 20 else {
            return nil
        }

        // Draw the owned guest's real UIView pixels before opening the switcher.
        // Remote/secure rendering may refuse capture: display unavailable, never
        // substitute a fabricated stock photo.
        let bounds = view.bounds
        // The panel displays a 116pt thumbnail. Limit capture resolution so
        // switching among many apps does not allocate full-screen bitmaps.
        let scale = min(CGFloat(1), CGFloat(256) / bounds.width)
        let output = CGSize(width: bounds.width * scale,
                            height: bounds.height * scale)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        return UIGraphicsImageRenderer(size: output, format: format).image { context in
            context.cgContext.scaleBy(x: scale, y: scale)
            if !view.drawHierarchy(in: bounds, afterScreenUpdates: false) {
                view.layer.render(in: context.cgContext)
            }
        }
    }

    static func activate(_ dataUUID: String) -> Bool {
        if MultitaskDockManager.shared.bringMultitaskViewToFront(uuid: dataUUID) {
            return true
        }
        return MultitaskWindowManager.openExistingAppWindow(dataUUID: dataUUID)
    }
}

@available(iOS 17.0, *)
struct ScarletGuestSwitcherOverlay: View {
    let dataUUID: String
    let displayName: String
    let exitGuest: () -> Void
    var panelVisibilityChanged: (Bool) -> Void = { _ in }

    @State private var isOpen = false
    @State private var targets: [ScarletGuestTarget] = []
    @State private var previews: [String: UIImage] = [:]

    private func openSwitcher() {
        let active = ScarletGuestSceneRegistry.availableGuests()
        targets = active.isEmpty
            ? [ScarletGuestTarget(id: dataUUID, title: displayName)]
            : active
        previews = [:]
        for item in targets {
            if let image = ScarletGuestSceneRegistry.screenshot(dataUUID: item.id) {
                previews[item.id] = image
            }
        }
        isOpen = true
        panelVisibilityChanged(true)
        ScarletDiagnosticRecorder.shared.record("guest", "switcher_opened",
            fields: ["running_count": String(targets.count)])
    }

    private func closeSwitcher() {
        isOpen = false
        previews.removeAll(keepingCapacity: false)
        panelVisibilityChanged(false)
    }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Color.black.opacity(isOpen ? 0.17 : 0)
                .ignoresSafeArea()
                .allowsHitTesting(isOpen)
                .contentShape(Rectangle())
                .onTapGesture { closeSwitcher() }
                .accessibilityIdentifier("SCARLET_GUEST_OUTSIDE_TAP_DISMISS")

            VStack(alignment: .leading, spacing: 12) {
                if isOpen {
                    windowPanel
                }
                ScarletNativeGlassSwitcher(openManager: {
                    if isOpen { closeSwitcher() } else { openSwitcher() }
                })
                .padding(.leading, 4)
                .accessibilityIdentifier("SCARLET_GUEST_ONLY_ROUND_SWITCHER")
            }
            .padding(.leading, 18)
            .padding(.bottom, 5)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }

    // Only actual running guests are listed.  Closing a guest destroys its
    // runtime scene; user Documents, App Groups and certificates are untouched.
    private var windowPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "square.stack.3d.up.fill")
                Text("실행 중인 앱")
                    .font(.headline.weight(.semibold))
                Spacer()
                Text("\(targets.count)")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.white.opacity(0.7))
            }
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(targets) { item in
                        Button {
                            if item.id == dataUUID {
                                closeSwitcher()
                            } else if ScarletGuestSceneRegistry.activate(item.id) {
                                closeSwitcher()
                            }
                        } label: {
                            HStack(spacing: 12) {
                                Group {
                                    if let image = previews[item.id] {
                                        Image(uiImage: image).resizable().scaledToFill()
                                    } else {
                                        Image(systemName: "app.fill")
                                            .font(.system(size: 25))
                                            .foregroundStyle(.white.opacity(0.7))
                                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                                    }
                                }
                                .frame(width: 74, height: 58)
                                .background(.black.opacity(0.25))
                                .clipShape(RoundedRectangle(cornerRadius: 11))
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.title)
                                        .font(.subheadline.weight(.semibold))
                                        .lineLimit(1)
                                    if item.id == dataUUID {
                                        Text("현재 실행 중")
                                            .font(.caption2)
                                            .foregroundStyle(.white.opacity(0.72))
                                    }
                                }
                                Spacer(minLength: 0)
                                Image(systemName: "chevron.right")
                                    .font(.caption.weight(.semibold))
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("SCARLET_LIVE_GUEST_PREVIEW_ROW")
                    }
                }
            }
            .frame(maxHeight: 228)
            Button {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "exit_requested",
                    fields: ["guest_ref":
                        ScarletDiagnosticRecorder.shared.guestReference(dataUUID)])
                closeSwitcher()
                exitGuest()
            } label: {
                Label("앱 종료 · 홍수정으로", systemImage: "rectangle.portrait.and.arrow.right")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .contentShape(RoundedRectangle(cornerRadius: 15))
            }
            .buttonStyle(.plain)
            .background {
                if #available(iOS 26.0, *),
                   !UIAccessibility.isReduceTransparencyEnabled {
                    RoundedRectangle(cornerRadius: 15)
                        .glassEffect(.regular.tint(.purple.opacity(0.28)).interactive(),
                                     in: .rect(cornerRadius: 15))
                } else {
                    RoundedRectangle(cornerRadius: 15).fill(.white.opacity(0.16))
                }
            }
            .accessibilityIdentifier("SCARLET_GUEST_EXIT_TO_SCARLET")
        }
        .padding(16)
        .foregroundStyle(.white)
        .frame(maxWidth: 354)
        .background {
            if #available(iOS 26.0, *),
               !UIAccessibility.isReduceTransparencyEnabled {
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .glassEffect(.regular, in: .rect(cornerRadius: 24))
                    .accessibilityIdentifier("SCARLET_GUEST_PANEL_NATIVE_GLASS_MATERIAL")
            } else {
                SCNativeLiquidGlassSurface(cornerRadius: 24)
                    .clipShape(RoundedRectangle(cornerRadius: 24))
            }
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24)
                .stroke(.white.opacity(0.22), lineWidth: 1)
        }
        .accessibilityIdentifier("SCARLET_GUEST_LIVE_PREVIEW_PANEL")
    }
}

// The upstream default virtual-window mode is implemented in Objective-C,
// not MultitaskAppWindow.  Install the same SwiftUI control directly inside
// the genuine DecoratedAppSceneViewController after its guest view is mounted.
// The hosting view starts at 96×90pt and expands only when the user opens it:
// guest touches outside the control remain available.
@available(iOS 17.0, *)
@MainActor
@objc(ScarletGuestOverlayInstaller)
final class ScarletGuestOverlayInstaller: NSObject {
    @objc(installOnController:dataUUID:displayName:)
    static func install(onController owner: UIViewController,
                        dataUUID: String, displayName: String) {
        let wrapper = UIView()
        wrapper.backgroundColor = .clear
        wrapper.translatesAutoresizingMaskIntoConstraints = false
        owner.view.addSubview(wrapper)
        let width = wrapper.widthAnchor.constraint(equalToConstant: 96)
        let height = wrapper.heightAnchor.constraint(equalToConstant: 90)
        NSLayoutConstraint.activate([
            width, height,
            wrapper.leadingAnchor.constraint(equalTo: owner.view.leadingAnchor, constant: 6),
            wrapper.bottomAnchor.constraint(equalTo: owner.view.safeAreaLayoutGuide.bottomAnchor,
                                            constant: -6)
        ])
        let content = ScarletGuestSwitcherOverlay(
            dataUUID: dataUUID,
            displayName: displayName,
            exitGuest: { [weak owner] in
                let exitSelector = NSSelectorFromString("scarletExitToHost")
                if let owner, owner.responds(to: exitSelector) {
                    owner.perform(exitSelector)
                }
            },
            panelVisibilityChanged: { [weak owner] expanded in
                guard let owner else { return }
                width.constant = expanded ? min(376, max(250, owner.view.bounds.width - 12)) : 96
                height.constant = expanded ? min(480, max(340, owner.view.bounds.height - 8)) : 90
                UIView.animate(withDuration: 0.26) { owner.view.layoutIfNeeded() }
            }
        )
        let hosting = UIHostingController(rootView: content)
        hosting.view.backgroundColor = .clear
        hosting.view.translatesAutoresizingMaskIntoConstraints = false
        owner.addChild(hosting)
        wrapper.addSubview(hosting.view)
        NSLayoutConstraint.activate([
            hosting.view.leadingAnchor.constraint(equalTo: wrapper.leadingAnchor),
            hosting.view.trailingAnchor.constraint(equalTo: wrapper.trailingAnchor),
            hosting.view.topAnchor.constraint(equalTo: wrapper.topAnchor),
            hosting.view.bottomAnchor.constraint(equalTo: wrapper.bottomAnchor)
        ])
        hosting.didMove(toParent: owner)
        ScarletDiagnosticRecorder.shared.record("guest", "virtual_switcher_mounted",
            fields: ["api": "SwiftUI.UIHostingController"])
    }
}

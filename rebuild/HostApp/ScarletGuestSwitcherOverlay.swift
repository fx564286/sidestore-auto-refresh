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
            guard let view = app.view, view.window != nil, !view.isHidden else { continue }
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

    @State private var isOpen = false
    @State private var selectedSegment = 0
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
        selectedSegment = 0
        isOpen = true
    }

    private func closeSwitcher() {
        isOpen = false
        previews.removeAll(keepingCapacity: false)
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
                .accessibilityIdentifier("SCARLET_GUEST_ONLY_ROUND_SWITCHER")
            }
            .padding(.leading, 22)
            .padding(.bottom, 76)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }

    private var windowPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                ForEach(0..<2, id: \.self) { index in
                    Button {
                        selectedSegment = index
                    } label: {
                        Text(index == 0 ? "최근 앱" : "창 관리")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 36)
                            .background(selectedSegment == index
                                ? Color(red: 0.39, green: 0.30, blue: 0.89)
                                : Color.clear, in: Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(7)
            .frame(maxWidth: .infinity)
            .background(Color.black.opacity(0.25), in: Capsule())
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(targets) { item in
                        Button {
                            guard item.id != dataUUID else {
                                closeSwitcher()
                                return
                            }
                            if ScarletGuestSceneRegistry.activate(item.id) {
                                closeSwitcher()
                            }
                        } label: {
                            HStack(alignment: .center, spacing: 12) {
                                Group {
                                    if let image = previews[item.id] {
                                        Image(uiImage: image)
                                            .resizable()
                                            .scaledToFill()
                                    } else {
                                        VStack(spacing: 4) {
                                            Image(systemName: "photo.on.rectangle.angled")
                                            Text("미리보기 없음")
                                                .font(.system(size: 10))
                                        }
                                        .foregroundStyle(.white.opacity(0.65))
                                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                                    }
                                }
                                .frame(width: 116, height: 86)
                                .background(Color.black.opacity(0.32))
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(item.title)
                                        .font(.subheadline.weight(.semibold))
                                        .lineLimit(2)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                Spacer(minLength: 2)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("SCARLET_LIVE_GUEST_PREVIEW_ROW")
                    }
                }
            }
            .frame(maxHeight: 224)
            if selectedSegment == 1 {
                HStack(spacing: 8) {
                    Button("최소화") {
                        MultitaskDockManager.shared.minimizeAllWindows()
                        closeSwitcher()
                    }
                    Button("최대화") {}.disabled(true)
                    Button("닫기") {}.disabled(true)
                }
                .font(.footnote.weight(.semibold))
                .buttonStyle(.plain)
                .frame(maxWidth: .infinity)
                .accessibilityHint("창별 소유권 연결 전에는 최대화와 닫기를 실행할 수 없습니다.")
            }
        }
        .padding(16)
        .foregroundStyle(.white)
        .frame(maxWidth: 354)
        .background {
            SCNativeLiquidGlassSurface(cornerRadius: 24,
                                        selectedIndex: selectedSegment)
                .clipShape(RoundedRectangle(cornerRadius: 24))
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24)
                .stroke(.white.opacity(0.22), lineWidth: 1)
        }
        .accessibilityIdentifier("SCARLET_GUEST_LIVE_PREVIEW_PANEL")
    }
}

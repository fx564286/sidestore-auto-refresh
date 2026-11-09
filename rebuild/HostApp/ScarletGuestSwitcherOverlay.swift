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
    let isLive: Bool
    init(id: String, title: String, isLive: Bool = true) {
        self.id = id
        self.title = title
        self.isLive = isLive
    }
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
    @Namespace private var guestGlassSelection
    @State private var targets: [ScarletGuestTarget] = []
    @State private var previews: [String: UIImage] = [:]
    @State private var feedback: String?
    @Environment(\.openWindow) private var openWindow

    private func openSwitcher() {
        let active = ScarletGuestSceneRegistry.availableGuests()
        var combined = active
        var ids = Set(active.map(\.id))
        // Native LiveProcess window is necessarily alive even if registry
        // registration races with the first overlay appearance.
        if ids.insert(dataUUID).inserted {
            combined.insert(ScarletGuestTarget(id: dataUUID, title: displayName),
                            at: 0)
        }
        // A->Home->B must list A even when it has been terminated by iOS.
        // A cold entry is NEVER a promise of retained in-memory state.
        for entry in ScarletGuestSessionLedger.recent() {
            let id = entry.dataUUID ?? entry.folder
            if ids.insert(id).inserted {
                combined.append(ScarletGuestTarget(
                    id: id, title: entry.title ?? entry.folder, isLive: false))
            }
        }
        targets = combined
        feedback = nil
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
                .padding(.leading, 4)
                .accessibilityIdentifier("SCARLET_GUEST_ONLY_ROUND_SWITCHER")
            }
            .padding(.leading, 18)
            .padding(.bottom, 76)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
    }

    private var windowPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                ForEach(0..<2, id: \.self) { index in
                    Button {
                        withAnimation(.spring(response: 0.34, dampingFraction: 0.78)) {
                            selectedSegment = index
                        }
                    } label: {
                        Text(index == 0 ? "최근 앱" : "창 관리")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 36)
                            .background {
                                if selectedSegment == index {
                                    if #available(iOS 26.0, *),
                                       !UIAccessibility.isReduceTransparencyEnabled {
                                        Capsule()
                                            .glassEffect(
                                                .regular.tint(Color.purple.opacity(0.24)).interactive(),
                                                in: .capsule
                                            )
                                            .glassEffectID("guest-segment", in: guestGlassSelection)
                                            .matchedGeometryEffect(id: "guest-selection",
                                                                   in: guestGlassSelection)
                                    } else {
                                        Capsule()
                                            .fill(Color(red: 0.39, green: 0.30, blue: 0.89))
                                    }
                                }
                            }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(7)
            .frame(maxWidth: .infinity)
            .background {
                if #available(iOS 26.0, *),
                   !UIAccessibility.isReduceTransparencyEnabled {
                    Capsule()
                        .glassEffect(.regular.interactive(), in: .capsule)
                } else {
                    Capsule().fill(Color.black.opacity(0.25))
                }
            }
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(targets) { item in
                        Button {
                            guard item.id != dataUUID else {
                                closeSwitcher()
                                return
                            }
                            guard item.isLive else {
                                feedback = "종료된 앱은 목록에서 다시 실행해야 합니다. 작업 상태 복원은 앱 자체 저장 기능에 따라 달라집니다."
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
                                    Text(item.isLive ? "실행 중 · 작업 유지" : "최근 실행 · 재시작 필요")
                                        .font(.caption2).foregroundStyle(.secondary)
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
            if let feedback {
                Text(feedback)
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }
            Button {
                // Open the existing LC host scene without terminating a
                // resident native LiveProcess guest or resetting its UIWindow.
                openWindow(id: "Main")
                closeSwitcher()
            } label: {
                Label("앱 목록", systemImage: "rectangle.portrait.and.arrow.right")
                    .frame(maxWidth: .infinity, minHeight: 36)
            }
            .accessibilityIdentifier("SCARLET_NATIVE_GUEST_RETURN_TO_HOST")
            if selectedSegment == 1 {
                HStack(spacing: 7) {
                    guestWindowCommand("최소화", symbol: "minus") {
                        MultitaskDockManager.shared.minimizeAllWindows()
                        closeSwitcher()
                    }
                    guestWindowCommand("최대화",
                                       symbol: "arrow.up.left.and.arrow.down.right",
                                       isEnabled: false) {}
                    guestWindowCommand("닫기", symbol: "xmark", isEnabled: false) {}
                }
                .frame(maxWidth: .infinity)
                .accessibilityHint("창별 소유권 연결 전에는 최대화와 닫기를 실행할 수 없습니다.")
            }
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
                SCNativeLiquidGlassSurface(cornerRadius: 24,
                                            selectedIndex: selectedSegment)
                    .clipShape(RoundedRectangle(cornerRadius: 24))
            }
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24)
                .stroke(.white.opacity(0.22), lineWidth: 1)
        }
        .accessibilityIdentifier("SCARLET_GUEST_LIVE_PREVIEW_PANEL")
    }

    // Centered 320pt three-column window actions; unavailable actions
    // remain disabled until the original window owner can be verified.
    private func guestWindowCommand(_ title: String, symbol: String,
                                    isEnabled: Bool = true,
                                    action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 2) {
                Image(systemName: symbol)
                    .font(.system(size: 16, weight: .semibold))
                    .frame(height: 23, alignment: .center)
                Text(title)
                    .font(.system(size: 12, weight: .semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.85)
            }
            .frame(maxWidth: .infinity, minHeight: 55, alignment: .center)
            .background(Color.black.opacity(0.26),
                        in: RoundedRectangle(cornerRadius: 12))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity)
        .disabled(!isEnabled)
    }
}

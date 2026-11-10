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
        return UIDevice.current.userInterfaceIdiom == .pad &&
            MultitaskWindowManager.openExistingAppWindow(dataUUID: dataUUID)
    }
}

// Resolve installed guest artwork from the original LC Applications roots.
// Never use the host icon as a guest placeholder or persist decoded bitmaps.
@available(iOS 17.0, *)
@MainActor
enum ScarletGuestIconCatalog {
    static func icon(for item: ScarletGuestTarget,
                     history: [ScarletGuestSessionLedger.Entry]) -> UIImage? {
        guard let folder = history.first(where: {
            $0.dataUUID == item.id || $0.folder == item.id
        })?.folder else { return nil }
        return icon(forFolder: folder)
    }

    static func icon(forFolder folder: String) -> UIImage? {
        guard folder.hasSuffix(".app"), folder != ".app",
              !folder.contains("/"), !folder.contains("\\") else { return nil }

        let home = getenv("LC_HOME_PATH").map {
            URL(fileURLWithPath: String(cString: $0))
        } ?? URL(fileURLWithPath: NSHomeDirectory())
        var roots = [home.appendingPathComponent("Documents", isDirectory: true)
                             .appendingPathComponent("Applications", isDirectory: true)]
        if let shared = LCSharedUtils.appGroupPath() {
            roots.append(shared.appendingPathComponent("LiveContainer", isDirectory: true)
                               .appendingPathComponent("Applications", isDirectory: true))
        }
        for root in roots {
            let appURL = root.appendingPathComponent(folder, isDirectory: true)
            guard FileManager.default.fileExists(
                atPath: appURL.appendingPathComponent("Info.plist").path)
            else { continue }
            for cached in ["LCAppIconLight.png", "LCAppIconDark.png"] {
                if let icon = UIImage(contentsOfFile:
                    appURL.appendingPathComponent(cached).path) {
                    return icon
                }
            }
            // LC may not have generated its thumbnail yet. Use only literal,
            // path-safe icon names from this exact installed app's Info.plist.
            guard let info = NSDictionary(contentsOf:
                appURL.appendingPathComponent("Info.plist")) as? [String: Any],
                let icons = info["CFBundleIcons"] as? [String: Any],
                let primary = icons["CFBundlePrimaryIcon"] as? [String: Any],
                let filenames = primary["CFBundleIconFiles"] as? [String] else {
                continue
            }
            for name in filenames.reversed() where
                !name.isEmpty && !name.contains("/") && !name.contains("\\") {
                for suffix in [".png", "@3x.png", "@2x.png"] {
                    let filename = name.hasSuffix(".png") ? name : name + suffix
                    if let icon = UIImage(contentsOfFile:
                        appURL.appendingPathComponent(filename).path) {
                        return icon
                    }
                }
            }
        }
        return nil
    }
}

@available(iOS 17.0, *)
struct ScarletGuestSwitcherOverlay: View {
    let dataUUID: String
    let displayName: String

    @State private var isOpen = false
    @State private var targets: [ScarletGuestTarget] = []
    @State private var previews: [String: UIImage] = [:]
    @State private var guestIcons: [String: UIImage] = [:]
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
        let history = ScarletGuestSessionLedger.recent()
        for entry in history {
            let id = entry.dataUUID ?? entry.folder
            if ids.insert(id).inserted {
                combined.append(ScarletGuestTarget(
                    id: id, title: entry.title ?? entry.folder, isLive: false))
            }
        }
        targets = combined
        ScarletGuestSessionLedger.traceSwitcher("native_panel_opened", count: combined.count)
        feedback = nil
        previews = [:]
        guestIcons = [:]
        for item in targets {
            if let icon = ScarletGuestIconCatalog.icon(for: item, history: history) {
                guestIcons[item.id] = icon
            }
            if let image = ScarletGuestSceneRegistry.screenshot(dataUUID: item.id) {
                previews[item.id] = image
            }
        }
        withAnimation(.spring(response: 0.34, dampingFraction: 0.87)) {
            isOpen = true
        }
    }

    private func closeSwitcher() {
        withAnimation(.spring(response: 0.34, dampingFraction: 0.87)) {
            isOpen = false
        }
        previews.removeAll(keepingCapacity: false)
        guestIcons.removeAll(keepingCapacity: false)
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
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(targets) { item in
                        Button {
                            ScarletGuestSessionLedger.traceSwitcher("native_switch_tapped")
                            guard item.id != dataUUID else {
                                closeSwitcher()
                                return
                            }
                            guard item.isLive else {
                                ScarletGuestSessionLedger.traceSwitcher("native_switch_rejected")
                                feedback = "종료된 앱은 목록에서 다시 실행해야 합니다. 작업 상태 복원은 앱 자체 저장 기능에 따라 달라집니다."
                                return
                            }
                            if ScarletGuestSceneRegistry.activate(item.id) {
                                ScarletGuestSessionLedger.traceSwitcher("native_switch_activated")
                                closeSwitcher()
                            } else {
                                ScarletGuestSessionLedger.traceSwitcher("native_switch_rejected")
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
                                    HStack(spacing: 8) {
                                        Group {
                                            if let icon = guestIcons[item.id] {
                                                Image(uiImage: icon)
                                                    .resizable()
                                                    .scaledToFit()
                                            } else {
                                                Image(systemName: "app.fill")
                                                    .resizable()
                                                    .scaledToFit()
                                                    .padding(8)
                                            }
                                        }
                                        .frame(width: 36, height: 36)
                                        .background(Color.white.opacity(0.12),
                                                    in: RoundedRectangle(cornerRadius: 9))
                                        .clipShape(RoundedRectangle(cornerRadius: 9))
                                        .accessibilityIdentifier("SCARLET_GUEST_APP_ICON")
                                        Text(item.title)
                                            .font(.subheadline.weight(.semibold))
                                            .lineLimit(2)
                                    }
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
                                            selectedIndex: 0)
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

#!/usr/bin/env python3
"""V56: no-new-App-ID, safe-area-adjacent guest control capsule.

This is an in-app overlay below the system Dynamic Island, NOT an ActivityKit
Live Activity or an attempt to intercept Apple's protected Island UI.
Keep the existing host + three extensions, signing, JIT and guest data intact.
Apply after V39 and V55 on the pinned LiveContainer tree.
"""
from pathlib import Path
import sys

TARGET = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "NRG_V56_NOTCH_ADJACENT_CONTROLS"

MANAGER = r'''
    // NRG_V56_NOTCH_ADJACENT_CONTROLS: same host app and existing three extensions.
    // The overlay is below the protected system Dynamic Island; no Widget App ID.
    @Published var nrgV56IslandHidden = true
    @Published var nrgV56IslandExpanded = false
    private var nrgV56IslandHost: UIHostingController<AnyView>?

    @objc public func nrgV56RelayoutIsland() {
        // Do not block FrontBoard/scene-update from a background callback.
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV56RelayoutIsland() }
            return
        }
        guard let window = keyWindow else { return }
        if nrgV56IslandHost == nil {
            let content = AnyView(NRGV56IslandBar().environmentObject(self))
            let host = UIHostingController(rootView: content)
            host.view.backgroundColor = .clear
            host.view.isOpaque = false
            nrgV56IslandHost = host
        }
        guard let host = nrgV56IslandHost else { return }
        if host.view.superview !== window {
            host.view.removeFromSuperview()
            window.addSubview(host.view)
        }
        let portrait = window.bounds.height > window.bounds.width
        let visible = portrait && !nrgV56IslandHidden && !apps.isEmpty
        host.view.isHidden = !visible
        if !visible { return }
        // Avoid painting or intercepting touches over the hardware island.
        let width = min(340.0, max(180.0, window.bounds.width - 24.0))
        let y = max(10.0, window.safeAreaInsets.top + 3.0)
        let height: CGFloat = nrgV56IslandExpanded ? 143.0 : 48.0
        let frame = CGRect(x: (window.bounds.width - width) / 2,
                           y: y, width: width, height: height)
        if host.view.frame != frame { host.view.frame = frame }
        window.bringSubviewToFront(host.view)
        NSLog("[NRG_V56_ISLAND_UI] style=adjacent overlay=visible app_count=%ld expanded=%d",
              apps.count, nrgV56IslandExpanded ? 1 : 0)
    }

    @objc public func nrgV56ShowGuestControls() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV56ShowGuestControls() }
            return
        }
        nrgV56IslandHidden = false
        nrgV56RelayoutIsland()
    }

    @objc public func nrgV56ReturnHome() {
        nrgV56IslandExpanded = false
        nrgV56IslandHidden = true
        nrgV56RelayoutIsland()
        minimizeAllWindows()
    }
'''

BAR = r'''
// NRG_V56_NOTCH_ADJACENT_CONTROLS: uses an existing app window, not a
// protected system Dynamic Island surface. Native Island content requires a
// separately provisioned WidgetKit/ActivityKit extension and Apple App ID.
@available(iOS 16.0, *)
private struct NRGV56IslandBar: View {
    @EnvironmentObject var dockManager: MultitaskDockManager

    private var count: Int { dockManager.apps.count }

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 9) {
                Button(action: dockManager.nrgV56ReturnHome) {
                    Image(systemName: "house.fill")
                        .font(.system(size: 15, weight: .semibold))
                        .frame(width: 32, height: 32)
                        .background(.white.opacity(0.16), in: Circle())
                }
                .accessibilityLabel("Return to LiveContainer")
                .accessibilityIdentifier("nrgV56IslandHome")

                Spacer(minLength: 0)

                Text("\(count)")
                    .font(.system(size: 16, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .accessibilityLabel("\(count) running guest apps")

                ForEach(Array(dockManager.apps.suffix(2)), id: \.appUUID) { app in
                    NRGV56IslandIcon(app: app)
                }

                Button {
                    dockManager.nrgV56IslandExpanded.toggle()
                    dockManager.nrgV56RelayoutIsland()
                } label: {
                    Image(systemName: dockManager.nrgV56IslandExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 12, weight: .semibold))
                        .frame(width: 27, height: 32)
                }
                .accessibilityIdentifier("nrgV56IslandExpand")
            }
            .padding(.horizontal, 10)
            .frame(height: 44)
            .foregroundStyle(.white)
            .background(.black, in: Capsule())
            .overlay(Capsule().stroke(.white.opacity(0.18), lineWidth: 1))

            if dockManager.nrgV56IslandExpanded {
                HStack(spacing: 7) {
                    Button {
                        dockManager.nrgV56ReturnHome()
                    } label: {
                        NRGV56IslandMenuItem(symbol: "house.fill", text: "메인 복귀")
                    }
                    .accessibilityIdentifier("nrgV56MenuHome")

                    Menu {
                        ForEach(dockManager.apps, id: \.appUUID) { app in
                            Button(app.appName) {
                                _ = dockManager.bringMultitaskViewToFront(uuid: app.appUUID)
                                dockManager.nrgV56IslandExpanded = false
                                dockManager.nrgV56RelayoutIsland()
                            }
                        }
                    } label: {
                        NRGV56IslandMenuItem(symbol: "square.grid.2x2", text: "\(count)개 앱")
                    }
                    .accessibilityIdentifier("nrgV56MenuApps")

                    Button {
                        if let app = dockManager.apps.last {
                            _ = dockManager.bringMultitaskViewToFront(uuid: app.appUUID)
                        }
                        dockManager.nrgV56IslandExpanded = false
                        dockManager.nrgV56RelayoutIsland()
                    } label: {
                        NRGV56IslandMenuItem(symbol: "app.fill", text: "현재 앱")
                    }
                    .accessibilityIdentifier("nrgV56MenuCurrent")

                    Button {
                        dockManager.nrgV56IslandExpanded = false
                        dockManager.nrgV56RelayoutIsland()
                    } label: {
                        NRGV56IslandMenuItem(symbol: "xmark.circle.fill", text: "닫기")
                    }
                    .accessibilityIdentifier("nrgV56MenuDismiss")
                }
                .buttonStyle(.plain)
                .padding(8)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22))
                .overlay(RoundedRectangle(cornerRadius: 22)
                    .stroke(.white.opacity(0.13), lineWidth: 1))
            }
            Spacer(minLength: 0)
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity, alignment: .top)
    }
}

@available(iOS 16.0, *)
private struct NRGV56IslandMenuItem: View {
    let symbol: String
    let text: String
    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: symbol).font(.system(size: 19, weight: .medium))
                .frame(height: 28)
            Text(text).font(.system(size: 10, weight: .medium))
                .lineLimit(1).minimumScaleFactor(0.8)
        }
        .foregroundStyle(.primary)
        .frame(maxWidth: .infinity)
        .frame(height: 68)
        .contentShape(Rectangle())
    }
}

@available(iOS 16.0, *)
private struct NRGV56IslandIcon: View {
    let app: DockAppModel
    @State private var icon: UIImage?

    var body: some View {
        Group {
            if let icon {
                Image(uiImage: icon).resizable().scaledToFill()
            } else {
                Image(systemName: "app.fill").resizable().scaledToFit()
                    .foregroundStyle(.white.opacity(0.8))
                    .padding(5)
            }
        }
        .frame(width: 26, height: 26)
        .clipShape(RoundedRectangle(cornerRadius: 7))
        .onAppear {
            let cacheKey = "\(app.appName)_\(app.appUUID)"
            if let cached = IconCacheManager.shared.getIcon(for: cacheKey) {
                icon = cached
                return
            }
            DispatchQueue.global(qos: .userInitiated).async {
                let value = app.appInfo?.iconIsDarkIcon(false)
                DispatchQueue.main.async {
                    guard let value else { return }
                    icon = value
                    IconCacheManager.shared.setIcon(value, for: cacheKey)
                }
            }
        }
    }
}

'''

def replace_one(s: str, old: str, new: str, label: str) -> str:
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"V56 {label}: wanted one anchor; got {n}")
    return s.replace(old, new, 1)


def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK) < 3 or "nrgV56IslandHome" not in s or "nrgDockReturnHome" in s:
            raise RuntimeError("partial V56 UI overlay")
        return s
    if "NRG_V55_ROTATION_GEOMETRY" not in s or "NRG_V42_DOCK_GLASS_HOME" not in s:
        raise RuntimeError("V56 requires V39/V55 patched dock")
    # Move Home from the dock into the top capsule; the right dock is apps only.
    start = s.index("                        // NRG_V42_DOCK_GLASS_HOME:")
    end = s.index("                        ForEach(dockManager.apps) { app in", start)
    s = s[:start] + "                        // V56: app-switch-only dock; Home moved to notch-adjacent capsule.\n" + s[end:]

    s = replace_one(s,
        "    internal var hostingController: UIHostingController<AnyView>?\n",
        "    internal var hostingController: UIHostingController<AnyView>?\n" + MANAGER,
        "manager overlay state")
    s = replace_one(s,
        "            if self.isVisible {\n                self.updateDockFrame()\n            }\n        }\n    }\n    \n    @objc private func userDefaultsDidChange()",
        "            if self.isVisible {\n                self.updateDockFrame()\n            }\n            self.nrgV56RelayoutIsland()\n        }\n    }\n    \n    @objc private func userDefaultsDidChange()",
        "orientation observer")
    s = replace_one(s,
        "            self.apps.removeAll { $0.appUUID == appUUID }\n",
        "            self.apps.removeAll { $0.appUUID == appUUID }\n            self.nrgV56RelayoutIsland()\n",
        "guest removal")
    s = replace_one(s,
        "            self.apps.append(appModel)\n",
        "            self.apps.append(appModel)\n"
        "            self.nrgV56ShowGuestControls()\n",
        "guest launch")
    s = replace_one(s,
        "        DispatchQueue.main.async {\n            self.apps.forEach { app in\n",
        "        DispatchQueue.main.async {\n"
        "            if except == nil {\n"
        "                self.nrgV56IslandHidden = true\n"
        "                self.nrgV56IslandExpanded = false\n"
        "                self.nrgV56RelayoutIsland()\n"
        "            }\n"
        "            self.apps.forEach { app in\n",
        "return home")
    s = replace_one(s,
        "                animateViewAppearance(targetView, from: center, in: window)\n"
        "                return true",
        "                animateViewAppearance(targetView, from: center, in: window)\n"
        "                nrgV56ShowGuestControls()\n"
        "                return true",
        "guest foreground")
    old = "// MARK: - Collapsed Dock View\n"
    s = replace_one(s, old, BAR + old, "overlay view code")
    return s


def main(root: Path) -> None:
    p = root / TARGET
    before = p.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise RuntimeError("V56 patch not idempotent")
    if after != before:
        p.write_text(after, encoding="utf-8")
    print("[PASS] V56 notch-adjacent guest controls; zero new App IDs/extensions")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v56_notch_ui.py <pinned LiveContainer source>")
    main(Path(sys.argv[1]))

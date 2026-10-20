#!/usr/bin/env python3
"""V58 native Dynamic Island via the pre-existing SideStore WidgetKit target.

Exactly one extra packaged extension (LiveWidget). No fake Island overlays;
the existing right floating dock becomes noninteractive while an Activity is
running. Reuse the previously known com.kdt.livecontainer.LiveWidget ID.
"""
from pathlib import Path
import plistlib
import sys

MARK="NRG_V58_NATIVE_ISLAND_ACTIVITY"
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
HOST_INFO=Path("LiveContainer/Info.plist")
SIDESTORE_BUNDLE=Path("AltWidget/AltWidgetBundle.swift")

SHARED_ATTRS = r'''
// NRG_V58_NATIVE_ISLAND_ACTIVITY: ActivityKit attributes mirrored byte-for-byte
// in host and widget extension; Codable schema must remain compatible.
struct NRGGuestActivityAttributes: ActivityAttributes {
    public struct Guest: Codable, Hashable {
        var name: String
        var launchURL: String
        var running: Bool
    }
    public struct ContentState: Codable, Hashable {
        var runningCount: Int
        var installedCount: Int
        var activeName: String
        var guests: [Guest]
    }
    var purpose: String
}
'''

MANAGER = r'''
    // NRG_V58_NATIVE_ISLAND_ACTIVITY: one system-managed activity per NRG
    // installation. No alternate UI view consumes the guest viewport.
    // NRG_V191_STARTUP_HOST_ATTACH: an iOS 27 first launch can trigger
    // SwiftUI.onAppear before the root controller has any child views. The
    // pinned upstream init() force-unwraps root.subviews.first and SIGTRAPs.
    // Reconcile lazily on launch, Island refresh, and scene activation.
    @objc public func nrgV191AttachGuestWindowHostIfReady() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV191AttachGuestWindowHostIfReady() }
            return
        }
        let window = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first(where: { $0.isKeyWindow }) ?? keyWindow
        guard let root = window?.rootViewController?.view else { return }
        // The root itself is a safe early anchor. Reparent to its first real
        // child after UIKit constructs one; never attach a view to itself.
        let anchor = root.subviews.first(where: { $0 !== windowHostingView }) ?? root
        if windowHostingView.superview !== anchor {
            windowHostingView.removeFromSuperview()
            anchor.addSubview(windowHostingView)
            windowHostingView.frame = anchor.bounds
        }
    }

    // NRG_V194_FOREGROUND_ONLY_ISLAND: Live Activities otherwise persist after
    // leaving the app because refresh is not called on scene deactivation.
    private static var nrgIslandLifecycleObserversInstalled = false

    @objc private func nrgV194EndIslandWhenInactive() {
        guard #available(iOS 16.2, *) else { return }
        for activity in Activity<NRGGuestActivityAttributes>.activities {
            Task { await activity.end(nil, dismissalPolicy: .immediate) }
        }
    }

    @objc private func nrgV194ResumeIslandWhenActive() {
        // Activation notifications can precede retained guest restoration.
        // Reconcile again on the next main-loop turn after the host is active.
        DispatchQueue.main.async { [weak self] in
            self?.nrgV58RefreshNativeIsland()
        }
    }

    private func nrgV194InstallIslandLifecycleObservers() {
        guard !Self.nrgIslandLifecycleObserversInstalled else { return }
        Self.nrgIslandLifecycleObserversInstalled = true
        NotificationCenter.default.addObserver(
            self, selector: #selector(nrgV194EndIslandWhenInactive),
            name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(
            self, selector: #selector(nrgV194EndIslandWhenInactive),
            name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(
            self, selector: #selector(nrgV194ResumeIslandWhenActive),
            name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    @objc public func nrgV58RefreshNativeIsland() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV58RefreshNativeIsland() }
            return
        }
        nrgV194InstallIslandLifecycleObservers()
        // The SwiftUI tab can appear before UIKit has populated root.subviews.
        nrgV191AttachGuestWindowHostIfReady()
        nrgV56IslandHidden = true
        nrgV56IslandExpanded = false
        nrgV56RelayoutIsland()

        if #available(iOS 16.2, *), UIDevice.current.userInterfaceIdiom == .phone {
            // Keep the old dock model for retained guest scene switching,
            // but do not overlay a floating bar on top of the game screen.
            let systemIslandEnabled = ActivityAuthorizationInfo().areActivitiesEnabled
            // Do not suppress the in-app guest switcher until the system
            // activity is actually available and the app is foregrounded.
            hostingController?.view.isHidden = systemIslandEnabled && UIApplication.shared.applicationState == .active
            // NRG_V193_RUNNING_ONLY_ISLAND: never list dormant installed apps.
            // The Island is a switcher for retained, running guest sessions only.
            let installed = DataManager.shared.model.apps
            let runningCount = apps.count
            let name = String((apps.last?.appName ?? "NRG").prefix(32))
            let catalog: [(model: LCAppModel, running: Bool)] = installed.compactMap { model in
                let active = apps.contains { dock in
                    dock.appInfo?.relativeBundlePath == model.appInfo.relativeBundlePath ||
                    model.uiContainers.contains(where: { $0.folderName == dock.appUUID })
                }
                return active ? (model: model, running: true) : nil
            }
            // The Island has finite space: prioritize active guests.
            let guests = catalog.prefix(6).compactMap { item -> NRGGuestActivityAttributes.Guest? in
                guard let bundle = item.model.appInfo.relativeBundlePath,
                      bundle.hasSuffix(".app"), bundle.utf8.count <= 180 else { return nil }
                var route = URLComponents()
                route.scheme = "livecontainer"
                route.host = "livecontainer-launch"
                var query = [URLQueryItem(name: "bundle-name", value: bundle),
                             URLQueryItem(name: "nrg-multitask", value: "1")]
                if let container = item.model.uiSelectedContainer?.folderName,
                   !container.isEmpty {
                    query.append(URLQueryItem(name: "container-folder-name", value: container))
                }
                route.queryItems = query
                guard let launchURL = route.url?.absoluteString else { return nil }
                return NRGGuestActivityAttributes.Guest(
                    name: String(item.model.appInfo.displayName().prefix(24)),
                    launchURL: launchURL, running: item.running)
            }
            let state = NRGGuestActivityAttributes.ContentState(
                runningCount: runningCount, installedCount: runningCount,
                activeName: name, guests: guests)
            let existing = Activity<NRGGuestActivityAttributes>.activities
            // End when no guest is running, or NRG is no longer foreground.
            if runningCount == 0 || UIApplication.shared.applicationState == .background {
                for activity in existing {
                    Task { await activity.end(nil, dismissalPolicy: .immediate) }
                }
                return
            }
            guard systemIslandEnabled else {
                NSLog("[NRG_V58_ACTIVITY] available=0 count=%ld", runningCount)
                return
            }
            if let active = existing.first {
                Task { await active.update(ActivityContent(state: state, staleDate: nil)) }
            } else {
                do {
                    let attrs = NRGGuestActivityAttributes(purpose: "guest-switcher")
                    _ = try Activity<NRGGuestActivityAttributes>.request(
                        attributes: attrs,
                        content: ActivityContent(state: state, staleDate: nil),
                        pushType: nil
                    )
                    NSLog("[NRG_V58_ACTIVITY] started=1 count=%ld", runningCount)
                } catch {
                    NSLog("[NRG_V58_ACTIVITY] request_failed=1 count=%ld", runningCount)
                }
            }
        }
    }
'''

WIDGET = r'''import SwiftUI
import WidgetKit
import ActivityKit

// NRG_V58_NATIVE_ISLAND_ACTIVITY: one extra extension is required for the
// genuine system Dynamic Island. Never present an app-owned overlay there.
'''+SHARED_ATTRS+r'''
@available(iOS 16.1, *)
struct NRGGuestIslandWidget: Widget {
    private let homeURL = URL(string: "livecontainer://nrg-apps")!

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: NRGGuestActivityAttributes.self) { context in
            HStack(spacing: 12) {
                Image(systemName: "square.stack.3d.up.fill")
                VStack(alignment: .leading, spacing: 3) {
                    Text("Scarlet & Crystal").font(.caption.weight(.semibold)).lineLimit(1)
                    Text(context.state.activeName).font(.caption).lineLimit(1)
                }
                Spacer(minLength: 2)
                Text(String(context.state.installedCount)).monospacedDigit()
            }
            .padding(12)
            .activityBackgroundTint(.black)
            .activitySystemActionForegroundColor(.white)
            .widgetURL(homeURL)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Label("Scarlet & Crystal", systemImage: "square.stack.3d.up.fill")
                        .font(.headline)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(String(context.state.runningCount) + "개 실행")
                        .font(.caption).monospacedDigit()
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.activeName)
                        .lineLimit(1)
                        .font(.subheadline)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    // NRG_V60_ISLAND_GUEST_SWITCH: open exactly the selected
                    // guest, retaining LiveContainer's ordinary sign/JIT path.
                    VStack(spacing: 6) {
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())],
                                  spacing: 6) {
                            ForEach(context.state.guests, id: \.launchURL) { guest in
                                Link(destination: URL(string: guest.launchURL) ?? homeURL) {
                                    HStack(spacing: 5) {
                                        Image(systemName: guest.running ? "circle.fill" : "app.fill")
                                            .font(.system(size: 9))
                                        Text(guest.name)
                                            .font(.caption.weight(.medium))
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.8)
                                    }
                                    .frame(maxWidth: .infinity, minHeight: 30)
                                    .background(.white.opacity(0.16), in: Capsule())
                                }
                            }
                        }
                    }
                    .tint(.white)
                    // NRG_V195_HOST_REENTRY: always allow returning to the host.
                    Link(destination: homeURL) {
                        Label("Scarlet & Crystal 열기", systemImage: "house.fill")
                            .font(.caption.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 30)
                    }
                    .tint(.white)
                }
            } compactLeading: {
                Image(systemName: "square.stack.3d.up.fill")
            } compactTrailing: {
                Text(String(context.state.runningCount))
                    .monospacedDigit()
            } minimal: {
                Image(systemName: "square.stack.3d.up.fill")
            }
        }
    }
}

@main
struct AltWidgetBundle: WidgetBundle {
    var body: some Widget {
        if #available(iOS 16.1, *) {
            NRGGuestIslandWidget()
        }
    }
}
'''

def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise RuntimeError(f"V58 {label}: expected one anchor got {n}")
    return s.replace(a,b,1)

def patch_dock(s):
    if MARK in s:
        if s.count(MARK)!=2 or "nrgV58RefreshNativeIsland()" not in s:
            raise RuntimeError("partial V58 activity manager")
        if "NRG_V191_STARTUP_HOST_ATTACH" not in s:
            raise RuntimeError("V58 source is from an old build without V191 startup guard")
        if "keyWindow!.rootViewController!.view.subviews.first!" in s:
            raise RuntimeError("V191 unsafe singleton initializer remains")
        return s
    if "NRG_V56_NOTCH_ADJACENT_CONTROLS" not in s:raise RuntimeError("V58 requires V56")
    s=one(s,"import Combine\n","import Combine\nimport ActivityKit\n"+SHARED_ATTRS,"ActivityKit model")
    s=one(s,"    internal var hostingController: UIHostingController<AnyView>?\n",
          "    internal var hostingController: UIHostingController<AnyView>?\n"+MANAGER,
          "activity update manager")
    s=one(s,
          '''        nrgV56IslandHidden = false
        nrgV56RelayoutIsland()
    }

    @objc public func nrgV56ReturnHome()''',
          '''        // Native Island replaces the screen-occluding adjacent capsule.
        nrgV56IslandHidden = true
        nrgV56RelayoutIsland()
        nrgV58RefreshNativeIsland()
    }

    @objc public func nrgV56ReturnHome()''',
          "guest show controls")
    # V3 guest-return rewrites removeRunningApp; upstream fallback is async.
    for indent in ("        ", "            "):
        needle = (indent+"self.apps.removeAll { $0.appUUID == appUUID }\n"
                  +indent+"self.nrgV56RelayoutIsland()\n")
        if needle in s:
            s=one(s, needle, needle+indent+"self.nrgV58RefreshNativeIsland()\n", "removed guest state")
            break
    else:
        raise RuntimeError("V58 removed guest hook not found")
    # NRG_V191_STARTUP_HOST_ATTACH: never dereference a root child before
    # UIKit finishes constructing its first SwiftUI scene. The app crashed in
    # MultitaskDockManager.init() with SIGTRAP on the main thread (~150ms).
    s=one(s,
          "        keyWindow!.rootViewController!.view.subviews.first!.addSubview(self.windowHostingView)",
          "        nrgV191AttachGuestWindowHostIfReady()",
          "startup safe UIKit host attachment")
    # Ensure the first guest cannot re-display the floating right dock
    # after the native activity is requested during apps.append().
    s=one(s,
          "                self.showDock()\n            } else if self.isVisible {\n",
          "                self.showDock()\n                self.nrgV58RefreshNativeIsland()\n            } else if self.isVisible {\n",
          "post-launch floating dock suppression")
    return s

def main(root,side):
    dock=root/DOCK
    orig=dock.read_text()
    out=patch_dock(orig)
    if patch_dock(out)!=out:raise RuntimeError("V58 ActivityKit patch is not idempotent")
    widget=side/SIDESTORE_BUNDLE
    previous=widget.read_text()
    if previous != WIDGET:
        if MARK in previous:raise RuntimeError("unexpected earlier V58 widget source")
        if "struct AltWidgetBundle: WidgetBundle" not in previous:
            raise RuntimeError("missing pinned SideStore Widget target")
    info=root/HOST_INFO
    data=plistlib.loads(info.read_bytes())
    if data.get("NSSupportsLiveActivities") not in (None, True):
        raise RuntimeError("unexpected incompatible Live Activities setting")
    data["NSSupportsLiveActivities"]=True
    if orig!=out:dock.write_text(out)
    if previous!=WIDGET:widget.write_text(WIDGET)
    info.write_bytes(plistlib.dumps(data))
    print("[PASS] V58 native Island host ActivityKit + SideStore widget target + host Info.plist")

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: patch_v58_native_activity.py <LiveContainer> <EmbeddedSideStore>")
    main(Path(sys.argv[1]),Path(sys.argv[2]))

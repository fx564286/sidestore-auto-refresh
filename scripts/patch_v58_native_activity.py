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
    // NRG_V61_MRU_ISLAND: the switcher must show running guests in last-used
    // order, not installed-app order. Session IDs are never persisted or logged.
    private var nrgV61RecentGuestIDs: [String] = []
    private var nrgV61LastActivityState: NRGGuestActivityAttributes.ContentState?

    private func nrgV61NoteGuestUse(_ id: String) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self] in self?.nrgV61NoteGuestUse(id) }
            return
        }
        guard apps.contains(where: { $0.appUUID == id }) else { return }
        nrgV61RecentGuestIDs.removeAll { $0 == id }
        nrgV61RecentGuestIDs.insert(id, at: 0)
        nrgV61RecentGuestIDs = Array(nrgV61RecentGuestIDs.prefix(12))
        nrgV58RefreshNativeIsland()
    }

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
        // Do not end the Live Activity on willResignActive: tapping the Island,
        // opening Control Center, or transient guest scene changes also fire it.
        // NRG_V63_BACKGROUND_CONTINUITY: Live Activity is intentionally
        // visible while the guest process runs. Do NOT end on background:
        // a classic/LiveProcess guest launch backgrounds the host itself.
        // End only when there are no recent guest routes or on explicit reset.
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
            // Never hide the only functional guest switcher before ActivityKit
            // has actually created a Live Activity. Permission is not success.
            hostingController?.view.isHidden = systemIslandEnabled &&
                !Activity<NRGGuestActivityAttributes>.activities.isEmpty &&
                UIApplication.shared.applicationState == .active
            // NRG_V193_RUNNING_ONLY_ISLAND: never list dormant installed apps.
            // The Island is a switcher for retained, running guest sessions only.
            let installed = DataManager.shared.model.apps
            let runningCount = apps.count
            nrgV61RecentGuestIDs.removeAll { id in
                !apps.contains(where: { $0.appUUID == id })
            }
            let running = apps.sorted { a, b in
                let ai = nrgV61RecentGuestIDs.firstIndex(of: a.appUUID) ?? Int.max
                let bi = nrgV61RecentGuestIDs.firstIndex(of: b.appUUID) ?? Int.max
                return ai == bi ? a.appUUID < b.appUUID : ai < bi
            }
            // NRG_V197_SESSION_IDENTITY: derive links from the *running dock*
            // rather than uiSelectedContainer, which may point to a different
            // instance of the same guest app.
            let runningCatalog: [(model: LCAppModel, containerUUID: String)] = running.compactMap { dock in
                guard let model = installed.first(where: { model in
                    model.uiContainers.contains(where: { $0.folderName == dock.appUUID }) ||
                    (model.appInfo.relativeBundlePath == dock.appInfo?.relativeBundlePath &&
                     model.uiSelectedContainer?.folderName == dock.appUUID)
                }) else { return nil }
                return (model: model, containerUUID: dock.appUUID)
            }
            // NRG_V63_RECENT_GUEST_CATALOG: virtual-window Dock is not a
            // complete guest inventory. Classic and LiveProcess launches
            // bypass it. appInfo.lastLaunched is set by the real runApp path.
            // Never include external iOS apps or unlaunched installed guests.
            let recentCatalog: [(model: LCAppModel, containerUUID: String)] = installed
                .filter { model in
                    guard let used = model.appInfo.lastLaunched else { return false }
                    return Date().timeIntervalSince(used) >= 0 &&
                        Date().timeIntervalSince(used) < 48 * 60 * 60
                }
                .sorted { ($0.appInfo.lastLaunched ?? .distantPast) >
                          ($1.appInfo.lastLaunched ?? .distantPast) }
                .compactMap { model in
                    guard let folder = model.uiSelectedContainer?.folderName ??
                            model.uiContainers.first?.folderName,
                          !folder.isEmpty else { return nil }
                    return (model: model, containerUUID: folder)
                }
            let catalog = runningCatalog + recentCatalog.filter { item in
                !runningCatalog.contains { runningItem in
                    runningItem.containerUUID == item.containerUUID &&
                    runningItem.model.appInfo.relativeBundlePath == item.model.appInfo.relativeBundlePath
                }
            }
            let name = String((catalog.first?.model.appInfo.displayName() ??
                "Scarlet Crystal").prefix(32))
            // The Island has finite space: active scenes first, then MRU guests.
            let guests = catalog.prefix(6).compactMap { item -> NRGGuestActivityAttributes.Guest? in
                guard let bundle = item.model.appInfo.relativeBundlePath,
                      bundle.hasSuffix(".app"), bundle.utf8.count <= 180 else { return nil }
                var route = URLComponents()
                // NRG_V63_EXCLUSIVE_SCHEME: route back to this exact app,
                // not another LiveContainer installation claiming the generic scheme.
                route.scheme = "scarletcrystal251"
                route.host = "livecontainer-launch"
                var query = [URLQueryItem(name: "bundle-name", value: bundle),
                             URLQueryItem(name: "nrg-multitask", value: "1")]
                guard !item.containerUUID.isEmpty else { return nil }
                query.append(URLQueryItem(name: "container-folder-name", value: item.containerUUID))
                route.queryItems = query
                guard let launchURL = route.url?.absoluteString else { return nil }
                return NRGGuestActivityAttributes.Guest(
                    name: String(item.model.appInfo.displayName().prefix(24)),
                    launchURL: launchURL,
                    running: apps.contains(where: { $0.appUUID == item.containerUUID }))
            }
            NSLog("[NRG_V61_ISLAND_SNAPSHOT] running=%ld matched=%ld links=%ld authorized=%d active=%d",
                  runningCount, catalog.count, guests.count, systemIslandEnabled ? 1 : 0,
                  UIApplication.shared.applicationState == .active ? 1 : 0)
            guard !guests.isEmpty else {
                hostingController?.view.isHidden = false
                nrgV61LastActivityState = nil
                for activity in Activity<NRGGuestActivityAttributes>.activities {
                    Task { await activity.end(nil, dismissalPolicy: .immediate) }
                }
                NSLog("[NRG_V61_ISLAND] guest_links_missing=1 fallback_dock=1")
                return
            }
            let state = NRGGuestActivityAttributes.ContentState(
                runningCount: runningCount, installedCount: guests.count,
                activeName: name, guests: guests)
            let existing = Activity<NRGGuestActivityAttributes>.activities
            // End when no guest is running, or NRG is no longer foreground.
            if guests.isEmpty {
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
                guard nrgV61LastActivityState != state else { return }
                nrgV61LastActivityState = state
                Task {
                    await active.update(ActivityContent(state: state, staleDate: nil))
                    NSLog("[NRG_V61_ISLAND] updated=1 running=%ld links=%ld", runningCount, guests.count)
                }
            } else {
                do {
                    let attrs = NRGGuestActivityAttributes(purpose: "guest-switcher")
                    _ = try Activity<NRGGuestActivityAttributes>.request(
                        attributes: attrs,
                        content: ActivityContent(state: state, staleDate: nil),
                        pushType: nil
                    )
                    nrgV61LastActivityState = state
                    hostingController?.view.isHidden = UIApplication.shared.applicationState == .active
                    NSLog("[NRG_V61_ISLAND] started=1 running=%ld links=%ld", runningCount, guests.count)
                } catch {
                    let ns = error as NSError
                    nrgV61LastActivityState = nil
                    hostingController?.view.isHidden = false
                    NSLog("[NRG_V61_ISLAND] request_failed=1 domain=%@ code=%ld fallback_dock=1",
                          ns.domain, ns.code)
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
    private let homeURL = URL(string: "scarletcrystal251://nrg-apps")!

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: NRGGuestActivityAttributes.self) { context in
            HStack(spacing: 12) {
                Image(systemName: "square.stack.3d.up.fill")
                VStack(alignment: .leading, spacing: 3) {
                    Text("Scarlet Crystal").font(.caption.weight(.semibold)).lineLimit(1)
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
                    Label("Scarlet Crystal", systemImage: "square.stack.3d.up.fill")
                        .font(.headline)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(String(context.state.installedCount) + "개 최근")
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
                        Label("Scarlet Crystal 열기", systemImage: "house.fill")
                            .font(.caption.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 30)
                    }
                    .tint(.white)
                }
            } compactLeading: {
                Image(systemName: "square.stack.3d.up.fill")
            } compactTrailing: {
                Text(String(context.state.installedCount))
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
    # Notify the activity when a guest is launched or becomes most-recently
    # foregrounded. appUUID is LiveContainer's data/container session UUID.
    s=one(s,
          "            self.apps.append(appModel)\n            self.nrgV56ShowGuestControls()\n",
          "            self.apps.append(appModel)\n"
          "            self.nrgV61NoteGuestUse(appModel.appUUID)\n"
          "            self.nrgV56ShowGuestControls()\n",
          "last-used guest on launch")
    s=one(s,
          "    func bringMultitaskViewToFront(uuid: String, from center: CGPoint? = nil) -> Bool {\n",
          "    func bringMultitaskViewToFront(uuid: String, from center: CGPoint? = nil) -> Bool {\n"
          "        nrgV61NoteGuestUse(uuid)\n",
          "last-used guest on foreground")
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
    # Only the genuine Scarlet Crystal host owns these ActivityKit URLs.
    # Preserve original livecontainer:// handlers for other app features.
    types=data.get("CFBundleURLTypes", [])
    if not isinstance(types,list):raise RuntimeError("invalid URL types list")
    match=[entry for entry in types if isinstance(entry,dict) and
           "livecontainer" in entry.get("CFBundleURLSchemes",[])]
    if len(match)!=1:raise RuntimeError("canonical LiveContainer scheme missing")
    schemes=match[0]["CFBundleURLSchemes"]
    if "scarletcrystal251" not in schemes:
        schemes.append("scarletcrystal251")
    data["CFBundleURLTypes"]=types
    if "NRG_V61_MRU_ISLAND" not in out:
        raise RuntimeError("V61 Island MRU patch was not applied")
    if orig!=out:dock.write_text(out)
    if previous!=WIDGET:widget.write_text(WIDGET)
    info.write_bytes(plistlib.dumps(data))
    print("[PASS] V58 native Island host ActivityKit + SideStore widget target + host Info.plist")

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: patch_v58_native_activity.py <LiveContainer> <EmbeddedSideStore>")
    main(Path(sys.argv[1]),Path(sys.argv[2]))

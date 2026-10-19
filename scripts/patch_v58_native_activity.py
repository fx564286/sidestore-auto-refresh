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
    public struct ContentState: Codable, Hashable {
        var runningCount: Int
        var activeName: String
    }
    var purpose: String
}
'''

MANAGER = r'''
    // NRG_V58_NATIVE_ISLAND_ACTIVITY: one system-managed activity per NRG
    // installation. No alternate UI view consumes the guest viewport.
    @objc public func nrgV58RefreshNativeIsland() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV58RefreshNativeIsland() }
            return
        }
        nrgV56IslandHidden = true
        nrgV56IslandExpanded = false
        nrgV56RelayoutIsland()

        if #available(iOS 16.2, *), UIDevice.current.userInterfaceIdiom == .phone {
            // Keep the old dock model for retained guest scene switching,
            // but do not overlay a floating bar on top of the game screen.
            hostingController?.view.isHidden = true
            let runningCount = apps.count
            let name = String((apps.last?.appName ?? "NRG").prefix(32))
            let state = NRGGuestActivityAttributes.ContentState(
                runningCount: runningCount, activeName: name)
            let existing = Activity<NRGGuestActivityAttributes>.activities
            if runningCount == 0 {
                for activity in existing {
                    Task { await activity.end(nil, dismissalPolicy: .immediate) }
                }
                return
            }
            guard ActivityAuthorizationInfo().areActivitiesEnabled else {
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
    private let homeURL = URL(string: "livecontainer://")!

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: NRGGuestActivityAttributes.self) { context in
            HStack(spacing: 12) {
                Image(systemName: "square.stack.3d.up.fill")
                VStack(alignment: .leading, spacing: 3) {
                    Text("NRG").font(.headline)
                    Text(context.state.activeName).font(.caption).lineLimit(1)
                }
                Spacer(minLength: 2)
                Text(String(context.state.runningCount)).monospacedDigit()
            }
            .padding(12)
            .activityBackgroundTint(.black)
            .activitySystemActionForegroundColor(.white)
            .widgetURL(homeURL)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Label("NRG", systemImage: "square.stack.3d.up.fill")
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
                    Link(destination: homeURL) {
                        Label("앱으로 돌아가기 · 전환", systemImage: "arrow.uturn.backward")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
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
            .widgetURL(homeURL)
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
    # The earlier patch inserts the above line for removeRunningApp only.
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

#!/usr/bin/env python3
"""V71: restore in-guest switching after V58/V60 suppressed the V56 surface.

The system Island remains owned by ActivityKit outside Scarlet Crystal. In a
visible retained guest scene only, show a small safe-area-adjacent trigger
and route recent guests via the same verified ActivityKit guest catalog.
Never modify the signed host identity, bundle entitlements or landscape frame.
"""
from pathlib import Path
import sys

TARGET = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'NRG_V71_FOREGROUND_GUEST_SWITCHER'

UI = r'''
// NRG_V71_FOREGROUND_GUEST_SWITCHER: tiny portrait-only in-guest trigger.
// Does not spoof or claim ownership of Apple's protected Dynamic Island.
@available(iOS 16.0, *)
private struct NRGV56IslandBar: View {
    @EnvironmentObject var dockManager: MultitaskDockManager
    private let columns = [GridItem(.flexible(), spacing: 7), GridItem(.flexible(), spacing: 7)]

    var body: some View {
        VStack(spacing: 6) {
            Button {
                dockManager.nrgV56IslandExpanded.toggle()
                dockManager.nrgV56RelayoutIsland()
            } label: {
                HStack(spacing: 5) {
                    Image(systemName: "square.stack.3d.up.fill")
                    Text("\\(dockManager.nrgV71Guests.count)").monospacedDigit()
                    Image(systemName: dockManager.nrgV56IslandExpanded ? "chevron.up" : "chevron.down")
                }
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 86, height: 30)
                .background(.black.opacity(0.92), in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.22), lineWidth: 1))
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Scarlet Crystal 게스트 전환")
            .accessibilityIdentifier("nrgV71GuestSwitcherTrigger")
            if dockManager.nrgV56IslandExpanded {
                VStack(spacing: 8) {
                    Text("최근 게스트 전환")
                        .font(.caption.weight(.semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ScrollView {
                        LazyVGrid(columns: columns, spacing: 7) {
                            ForEach(dockManager.nrgV71Guests, id: \\.launchURL) { guest in
                                Button {
                                    dockManager.nrgV71SelectGuest(guest.launchURL)
                                } label: {
                                    HStack(spacing: 5) {
                                        Image(systemName: guest.running ? "circle.fill" : "app.fill")
                                            .font(.system(size: 9))
                                        Text(guest.name).lineLimit(1).minimumScaleFactor(0.7)
                                    }
                                    .font(.system(size: 12))
                                    .frame(maxWidth: .infinity, minHeight: 34)
                                    .background(.white.opacity(0.13), in: Capsule())
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("nrgV71GuestSwitchAction")
                            }
                        }
                    }
                    .frame(maxHeight: 122)
                    Button {
                        dockManager.nrgV56ReturnHome()
                    } label: {
                        Label("Scarlet Crystal로 돌아가기", systemImage: "house.fill")
                            .font(.system(size: 12, weight: .medium))
                            .frame(maxWidth: .infinity, minHeight: 30)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("nrgV71ReturnHome")
                }
                .padding(10)
                .foregroundStyle(.white)
                .background(.black.opacity(0.94), in: RoundedRectangle(cornerRadius: 20))
                .frame(maxWidth: .infinity)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .top)
    }
}
'''
# UI is a raw string: remove escaped interpolation / keypath introduced solely
# for shell transfer, not from Swift formatting requirements.
UI = UI.replace(r'\\(', r'\(').replace(r'\\.launchURL', r'\.launchURL')

HELPER = r'''
    // NRG_V71_FOREGROUND_GUEST_SWITCHER: same filtered guest routes that
    // ActivityKit exposes, including classic guest sessions not in the Dock.
    @Published var nrgV71Guests: [NRGGuestActivityAttributes.Guest] = []

    private func nrgV71HasVisibleGuestScene() -> Bool {
        guard UIApplication.shared.applicationState == .active else { return false }
        return apps.contains { app in
            guard let guestView = app.view, guestView.window != nil,
                  !guestView.bounds.isEmpty else { return false }
            var ancestor: UIView? = guestView
            while let candidate = ancestor {
                if candidate.isHidden || candidate.alpha < 0.05 { return false }
                ancestor = candidate.superview
            }
            return true
        }
    }

    @objc public func nrgV71SelectGuest(_ route: String) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { self.nrgV71SelectGuest(route) }
            return
        }
        // A route MUST originate from the currently verified in-container
        // snapshot. Never treat arbitrary or external iOS bundle URLs as apps.
        guard nrgV71Guests.contains(where: { $0.launchURL == route }),
              let targetURL = URL(string: route),
              let components = URLComponents(url: targetURL, resolvingAgainstBaseURL: false),
              components.scheme == "scarletcrystal251",
              components.host == "livecontainer-launch" else {
            NSLog("[NRG_V71_SWITCH] result=rejected invalid_or_stale_guest=1")
            return
        }
        nrgV56IslandExpanded = false
        nrgV56RelayoutIsland()
        let folder = components.queryItems?.first(where: { $0.name == "container-folder-name" })?.value
        if let folder, apps.contains(where: { $0.appUUID == folder }),
           bringMultitaskViewToFront(uuid: folder) {
            NSLog("[NRG_V71_SWITCH] route=retained result=presented")
            return
        }
        UIApplication.shared.open(targetURL, options: [:]) { success in
            NSLog("[NRG_V71_SWITCH] route=guest-deeplink open_accepted=%d", success ? 1 : 0)
        }
    }
'''


def one(s, a, b, label):
    count=s.count(a)
    if count != 1: raise RuntimeError(f'V71 {label}: anchor count {count}')
    return s.replace(a,b,1)


def patch(src):
    if MARK in src:
        if src.count(MARK) != 2 or 'nrgV71SelectGuest' not in src or 'nrgV71GuestSwitcherTrigger' not in src:
            raise RuntimeError('V71 incomplete/duplicate patch')
        return src
    for key in ('NRG_V62_EXCLUSIVE_UI_SURFACES', 'NRG_V58_NATIVE_ISLAND_ACTIVITY',
                'NRG_V56_NOTCH_ADJACENT_CONTROLS', 'NRG_V63_RECENT_GUEST_CATALOG'):
        if key not in src: raise RuntimeError(f'V71 prerequisite missing {key}')
    # Old V62 code removed the entire V56 capsule on every iPhone refresh.
    old = '''        // NRG_V62_EXCLUSIVE_UI_SURFACES: ActivityKit owns the system Island.
        // Do not keep a legacy hosting view attached below the notch on iPhone.
        if #available(iOS 16.2, *), UIDevice.current.userInterfaceIdiom == .phone {
            if !nrgV56IslandHidden { nrgV56IslandHidden = true }
            if nrgV56IslandExpanded { nrgV56IslandExpanded = false }
            nrgV56IslandHost?.view.removeFromSuperview()
            nrgV56IslandHost = nil
            return
        }
        guard let window = keyWindow else { return }
'''
    src=one(src,old,'''        // V71: system ActivityKit remains available outside retained guests;
        // use the active UIWindow rather than the first registered window.
        let window = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first(where: { $0.isKeyWindow }) ?? keyWindow
        guard let window else { return }
''','remove blanket foreground suppression')
    # Minimize footprint, preserve physical hardware exclusion. No screen-wide
    # transparent hit-test surface in the collapsed state.
    old = '''        let portrait = window.bounds.height > window.bounds.width
        let visible = portrait && !nrgV56IslandHidden && !apps.isEmpty
        host.view.isHidden = !visible
        if !visible { return }
        // Avoid painting or intercepting touches over the hardware island.
        let width = min(340.0, max(180.0, window.bounds.width - 24.0))
        let y = max(10.0, window.safeAreaInsets.top + 3.0)
        let height: CGFloat = nrgV56IslandExpanded ? 143.0 : 48.0
'''
    new = '''        let portrait = window.bounds.height > window.bounds.width
        let visible = portrait && !nrgV56IslandHidden &&
            nrgV71HasVisibleGuestScene() && !nrgV71Guests.isEmpty
        host.view.isHidden = !visible
        if !visible { return }
        // NRG_V71: 86x30 pt passive footprint in the guest. Keep clear of
        // the protected Island/status-bar and preserve guest's top buttons.
        let width: CGFloat = nrgV56IslandExpanded
            ? min(338.0, window.bounds.width - 24.0) : 86.0
        let y = max(10.0, window.safeAreaInsets.top + 3.0)
        let height: CGFloat = nrgV56IslandExpanded ? 218.0 : 30.0
'''
    src=one(src,old,new,'compact geometry and actual retained guest visibility')
    src=one(src,'    internal var hostingController: UIHostingController<AnyView>?\n',
           '    internal var hostingController: UIHostingController<AnyView>?\n'+HELPER,
           'shared guest catalog and switch dispatch')
    old='''        nrgV191AttachGuestWindowHostIfReady()
        nrgV56IslandHidden = true
        nrgV56IslandExpanded = false
        nrgV56RelayoutIsland()
'''
    new='''        nrgV191AttachGuestWindowHostIfReady()
        nrgV56IslandHidden = !nrgV71HasVisibleGuestScene()
        if nrgV56IslandHidden { nrgV56IslandExpanded = false }
'''
    src=one(src,old,new,'guest foreground refresh')
    old='''            NSLog("[NRG_V61_ISLAND_SNAPSHOT] running=%ld matched=%ld links=%ld authorized=%d active=%d",'''
    new='''            // V71: use exactly the same filtered URLs as the native Island.
            // Do not depend on Live Activities being granted or foregrounded.
            nrgV71Guests = guests
            nrgV56RelayoutIsland()
            NSLog("[NRG_V61_ISLAND_SNAPSHOT] running=%ld matched=%ld links=%ld authorized=%d active=%d",'''
    src=one(src,old,new,'share ActivityKit guest snapshot')
    old='''        // Native Island replaces the screen-occluding adjacent capsule.
        nrgV56IslandHidden = true
        nrgV56RelayoutIsland()
        nrgV58RefreshNativeIsland()
'''
    new='''        // V71: retained scenes require their own tiny in-guest trigger.
        // Classic/LiveProcess scenes continue to use the system Island.
        nrgV56IslandHidden = false
        nrgV58RefreshNativeIsland()
'''
    src=one(src,old,new,'restored on-guest arrival')
    # The original V56 SwiftUI top bar embeds running Dock apps only, which
    # doesn't include classic/LiveProcess recent sessions. Replace its
    # presentation; keep shared DockAppModel and menu helpers intact.
    start=src.index('// NRG_V56_NOTCH_ADJACENT_CONTROLS: uses an existing app window, not a')
    end=src.index('@available(iOS 16.0, *)\nprivate struct NRGV56IslandMenuItem:',start)
    src=src[:start]+UI+'\n'+src[end:]
    return src


def main(root):
    file=root/TARGET
    before=file.read_text(encoding='utf8')
    after=patch(before)
    if patch(after)!=after: raise RuntimeError('V71 patch not idempotent')
    if before!=after: file.write_text(after,encoding='utf8')
    print('[PASS] V71 in-guest switching; native Island outside; no extra App IDs')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: patch_v71_in_guest_switcher.py <LiveContainer>')
    main(Path(sys.argv[1]))

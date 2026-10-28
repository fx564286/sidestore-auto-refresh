#!/usr/bin/env python3
"""V155 one guest execution path: LiveProcess only; preserve user data.

Source-level deletion of Direct's alternate floating window, host URL
handoff, alternate picker/restart branch, app context launch toggle.
No silent fallback to Direct if LiveProcess cannot start.
Also completes two still-open V154 issues: recent list optical height
and backdrop-owned hit testing; never change the known-good top tabs.
"""
from pathlib import Path
import sys

def one(s,old,new,why):
    n=s.count(old)
    if n!=1: raise ValueError(f"V155 {why}: anchor occurrences={n}")
    return s.replace(old,new,1)

def section(s,a,b,replacement,why):
    x=s.find(a)
    if x<0:raise ValueError(f"V155 {why} start absent")
    y=s.find(b,x+len(a))
    if y<0:raise ValueError(f"V155 {why} end absent")
    if s.find(a,x+1)>=0:raise ValueError(f"V155 {why} multiple starts")
    return s[:x]+replacement+s[y:]

def model(s):
    if "SCARLET_V155_ONLY_LIVEPROCESS" in s:return s
    s=one(s,'''        let classicMode = appInfo.defaultClassicMode
        let multitask = classicMode == 0 ? (multitask ?? shouldLaunchInMultitaskMode) : false''',
    '''        // SCARLET_V155_ONLY_LIVEPROCESS: exactly one guest execution path.
        // Existing per-app Classic settings are preserved on disk, NOT used.
        // LiveProcess failures are surfaced, never silently rerouted to Direct.
        let classicMode = appInfo.defaultClassicMode
        guard #available(iOS 16.0, *) else {
            throw "Scarlet Crystal requires iOS 16 or later for LiveProcess guests."
        }
        let multitask = true
        NSLog("[SCARLET_V155_SINGLE] stage=guest_launch route=LiveProcess previous_classic=%lu",
              classicMode)''','model route')
    # Explicitly prevent either legacy fallback from being reached.
    s=one(s,'''        if jitNeeded {
            if multitask, #available(iOS 17.4, *) {''',
    '''        if jitNeeded {
            guard #available(iOS 17.4, *) else {
                throw "LiveProcess JIT launch requires iOS 17.4 or later."
            }
            if multitask, #available(iOS 17.4, *) {''','JIT legacy guard')
    # Classic launch in the final path is physically removed, not dormant.
    a='''        } else {
            if #available(iOS 26.0, *), FileManager.default.fileExists(atPath: "\\(appInfo.bundlePath()!)/Frameworks/MetalANGLE.framework/MetalANGLE") {'''
    b='''        // Record the launch time'''
    s=section(s,a,b,'''        } else {
            throw "LiveProcess extension is unavailable. Direct launch has been retired."
        }

''','classic fallback removal')
    # A guarded else in older JIT path is retained solely to satisfy older iOS
    # API compile, but runtime guard prevents it from being taken.
    return s

def banner(s):
    if "SCARLET_V155_MENU_SINGLE_LIVEPROCESS" in s:return s
    a='''        // Multitask Toggle
        if #available(iOS 16.0, *) {'''
    b='''        let addToHomeScreenMenu = UIMenu('''
    return section(s,a,b,'''        // SCARLET_V155_MENU_SINGLE_LIVEPROCESS: the app's normal
        // Run action uses LiveProcess. The old Classic/Multitask toggle
        // gave users a second path that no longer exists.

''','second mode menu toggle')

def bootstrap(s):
    if "SCARLET_V155_NO_DIRECT_PRESENTER" in s:return s
    a='// SCARLET_V105_DIRECT_UNIFIED_MORPH:'
    b='extern char **environ;'
    s=section(s,a,b,'''// SCARLET_V155_NO_DIRECT_PRESENTER: removed the fallback UIWindow,
// its button, gesture interceptors and scheme-based host handoff.
// Installed guest containers and signing identities are unchanged.

''','Direct presenter deletion')
    a='''    // Install before guest UIApplication/scene creation, never inside LiveProcess.
    // SCARLET_V138_FUNCTIONAL_OWNER: virtual LiveProcess uses native V73
        // to reach the live host window manager; Direct uses shared fallback.
        if (!isLiveProcess && !isSideStore) {
        scGuestMorphPresenter = [SCGuestMorphPresenter new];
    }'''
    b='''    // SCARLET_V155_ONLY_LIVEPROCESS: do not install an alternative guest
    // UI or silently start a Direct guest. SideStore is exempt.
    if (!isLiveProcess && !isSideStore) {
        NSLog(@"[SCARLET_V155_SINGLE] stage=bootstrap result=direct_rejected");
        return @"Direct guest launch is disabled; use LiveProcess in Scarlet Crystal.";
    }'''
    return one(s,a,b,"guest bootstrap fallback removal")

def shell(s):
    if "SCARLET_V155_NO_DIRECT_URL_ROUTE" in s:return s
    a='''        // SCARLET_V147_DIRECT_HOST_ROUTING:'''
    b='''        if ["https", "http"].contains(url.scheme?.lowercased() ?? "") {'''
    return section(s,a,b,'''        // SCARLET_V155_NO_DIRECT_URL_ROUTE: no duplicate host
        // picker handoff. All guest controls are owned by LiveProcess.

''','Direct URL handoff removal')

def dock(s):
    if "SCARLET_V155_DOCK_SINGLE_MODE" in s:return s
    a='''    // SCARLET_V112_SHARED_GUEST_UI: Direct and LiveProcess invoke one renderer.'''
    b='''    @objc(nrgV102PresentWindowActionsFrom:sourceView:)'''
    s=section(s,a,b,'''    // SCARLET_V155_DOCK_SINGLE_MODE: only the existing LiveProcess
    // native picker remains, not the Direct restart/window mode.

''','Direct method removal')
    s=one(s,'''        let directMode = nrgV112DirectGuestRequest
        var windowActions = nrgV102WindowActionRequest ||
            (directMode && nrgV114DirectWindowActionsRequest)''',
        '''        var windowActions = nrgV102WindowActionRequest''','mode flag')
    s=one(s,'        let models = directMode ? [] : DataManager.shared.model.apps','        let models = DataManager.shared.model.apps','models')
    s=one(s,'if #available(iOS 16.1, *), !directMode {','if #available(iOS 16.1, *) {','native apps')
    s=one(s,'              endedEditing ? 1 : 0, directMode ? 1 : 0)',
             '              endedEditing ? 1 : 0, 0)','keyboard log')
    s=one(s,'directMode ? 1 : 0, windowActions ? 1 : 0)',
             '0, windowActions ? 1 : 0)','resilience log')
    s=one(s,'''        subtitle.text = windowActions ? "현재 게스트 창"
            : directMode ? "현재 게스트 · 다른 앱으로 전환하려면 재시작 필요"
            : "Scarlet Crystal 내부 · 최근 활성화 순"''',
        '''        subtitle.text = windowActions ? "현재 게스트 창"
            : "Scarlet Crystal 내부 · 최근 활성화 순"''','subtitle')
    s=one(s,'''        tabPicker.setEnabled(directMode ||
            (controller is DecoratedAppSceneViewController), forSegmentAt: 1)''',
        '''        tabPicker.setEnabled(controller is DecoratedAppSceneViewController,
                             forSegmentAt: 1)''','tab mode')
    # Replace the identical initial and tab-switch clip policy.
    s=s.replace('scroll.clipsToBounds = windowActions || directMode',
                'scroll.clipsToBounds = windowActions')
    s=s.replace('rows.isLayoutMarginsRelativeArrangement = !windowActions && !directMode',
                'rows.isLayoutMarginsRelativeArrangement = !windowActions')
    a='''        let listHeight = min(CGFloat(max(1, directMode ? 2
            : (windowActions ? actionsCount : recent.count))) * 54, maxListHeight)'''
    b='''        // SCARLET_V155_RECENT_OPTICAL_HEIGHT: V154 added 6pt top and
        // bottom to each native glass row without increasing the list's 54pt
        // viewport. The lower optical bloom was therefore still clipped.
        let listHeight = min(
            CGFloat(max(1, windowActions ? actionsCount : recent.count)) * 54 +
                (windowActions ? 0 : 12),
            maxListHeight)'''
    s=one(s,a,b,'recent height')
    s=one(s,'''            subtitle.text = windowActions ? "현재 게스트 창"
                : directMode ? "현재 게스트 · 다른 앱으로 전환하려면 재시작 필요"
                : "Scarlet Crystal 내부 · 최근 활성화 순"''',
        '''            subtitle.text = windowActions ? "현재 게스트 창"
                : "Scarlet Crystal 내부 · 최근 활성화 순"''','rebuilt subtitle')
    s=one(s,'''            let count = directMode ? 2 : (windowActions ? actionsCount : recent.count)
            tabListHeightConstraint.constant =
                min(CGFloat(max(1, count)) * 54, maxListHeight)''',
        '''            let count = windowActions ? actionsCount : recent.count
            tabListHeightConstraint.constant =
                min(CGFloat(max(1, count)) * 54 + (windowActions ? 0 : 12),
                    maxListHeight)''','rebuilt optical height')
    s=one(s,'if recent.isEmpty && !windowActions && !directMode {',
             'if recent.isEmpty && !windowActions {','empty fallback')
    a='''        if directMode {
            // The same V100 row style and collapse animation for either mode.'''
    b='''        for guest in recent {'''
    # block contains "} else if !windowActions {" at end; replace all with
    # a straight if !windowActions list.
    s=section(s,a,b,'''        if !windowActions {
''','Direct row/restart removal')
    s=one(s,'''            if directMode {
                self.nrgV114DirectWindowActionsRequest = targetWindowActions
            }
''','',"tab Direct state")
    s=one(s,'targetWindowActions ? "windows" : "recent", directMode ? 1 : 0)',
             'targetWindowActions ? "windows" : "recent", 0)','tab log')
    # Drop bridge that advertised a Direct-only secondary entry point.
    a='''@objc(SCUnifiedGuestUIBridge)'''
    if a in s:
        start=s.index(a)
        # class at end of file; need verify next anchor for safe trim
        end=s.index('\n}', start)+2
        section_text=s[start:end]
        if 'nrgV112PresentDirectGuestUI' not in section_text:
            raise ValueError("bridge class changed")
        pre = s.rfind("// One bridge to the ONE picker.", 0, start)
        if pre < 0:raise ValueError("bridge prefix missing")
        s=s[:pre]+"// SCARLET_V155_REMOVED_DIRECT_BRIDGE\n"+s[end:]
    # The V154 overlay's generic UIControl hit testing was competing with
    # guest UIWindow hit testing. Claim only background pixels in the SAME
    # existing overlay; allow every panel child to own its touches.
    s=one(s,
        """    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
""",
        """    // SCARLET_V155_OUTSIDE_HITTEST: outside pixels belong to the
    // existing backdrop; inside controls pass through untouched.
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        guard !isHidden, isUserInteractionEnabled, alpha > 0.01 else { return nil }
        if let panel = activePanel, !panel.frame.contains(point) {
            return self
        }
        return super.hitTest(point, with: event)
    }
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
""",
        "backdrop hit testing")
    # ensure no active Direct paths in picker
    if 'directMode' in s or 'nrgV112DirectGuestRequest' in s:
        raise ValueError("Direct mode token remains in picker")
    return s

FILES=[
 ('LiveContainerSwiftUI/Models/LCAppModel.swift',model),
 ('LiveContainerSwiftUI/Views/AppList/LCAppBanner/LCAppBannerViewController.swift',banner),
 ('LiveContainer/LCBootstrap.m',bootstrap),
 ('LiveContainerSwiftUI/Views/V3UnifiedShell.swift',shell),
 ('MultitaskSupport/MultitaskDockView.swift',dock),
]
def apply(root):
    changes=[]
    for path,fn in FILES:
        f=root/path
        if not f.is_file():raise ValueError("missing "+str(f))
        old=f.read_text();new=fn(old)
        if fn(new)!=new:raise ValueError("not idempotent: "+path)
        changes.append((f,old,new))
    for f,old,new in changes:
        if old!=new:f.write_text(new)
    print("[PASS] V155 one LiveProcess guest route; no Direct presenter, picker or URL; recent optical height")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v155_single_liveprocess.py <LiveContainer>")
    apply(Path(sys.argv[1]))

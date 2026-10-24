#!/usr/bin/env python3
"""V72: remove all compiled native/adjacent Island UI and route window overflow hold to guests.

Keep original window overflow single tap Minimize/Maximize/Close, guest
identity, signed app and extensions other than unused LiveWidget. Apple
system gestures stay untouched; long-press is attached only to the NRG V37
window's own top-right UIButton. Apply AFTER V60, V192 and V70.
"""
from pathlib import Path
import plistlib
import sys

DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
WINDOW = Path('MultitaskSupport/DecoratedAppSceneViewController.m')
SHELL = Path('LiveContainerSwiftUI/Views/V3UnifiedShell.swift')
MODEL = Path('LiveContainerSwiftUI/Models/LCAppModel.swift')
INFO = Path('LiveContainer/Info.plist')
MARK = 'NRG_V72_OVERFLOW_LONGPRESS'

SWIFT_SWITCHER = r'''
    // NRG_V72_OVERFLOW_LONGPRESS / SCARLET_V91_ORIGINAL_DOCK_LONGPRESS
    // The original right-edge swipe already exposed the live Dock.apps view.
    // Reuse that exact view/model; do NOT build a separate recent-app sheet.
    @objc(nrgV72PresentGuestSwitcherFrom:sourceView:)
    public func nrgV72PresentGuestSwitcher(from controller: UIViewController,
                                           sourceView: UIView) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self] in
                self?.nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)
            }
            return
        }
        guard sourceView.window != nil else {
            NSLog("[SCARLET_V91_DOCK] denied=button_not_visible")
            return
        }
        nrgV91RevealOriginalRunningDock(source: "button_hold")
    }

    // The Direct round control posts the same host-only request. It never
    // calls the old classic-mode restart on a long hold.
    @objc private func nrgV91DirectControlHold(_ note: Notification) {
        nrgV91RevealOriginalRunningDock(source: "direct_hold")
    }

    @objc public func nrgV91RevealOriginalRunningDock(source: String) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self] in
                self?.nrgV91RevealOriginalRunningDock(source: source)
            }
            return
        }
        // The upstream dock only represents independently running virtual
        // guests. Never invent a running session or cold-launch a saved guest.
        guard isDockEnabled(), !apps.isEmpty else {
            NSLog("[SCARLET_V91_DOCK] result=unavailable mode=not_virtual_or_no_running_guests source=%@", source)
            return
        }
        if !isVisible { showDock() }
        // showDock() commits on the main queue; after it mounts, reuse the
        // same visibility and expansion methods that edge swipe used.
        DispatchQueue.main.async { [weak self] in
            guard let self, self.isVisible else {
                NSLog("[SCARLET_V91_DOCK] result=unavailable reason=host_dock_not_mounted")
                return
            }
            if self.isDockHidden { self.showDockFromHidden() }
            if self.isCollapsed { self.toggleDockCollapse() }
            NSLog("[SCARLET_V91_DOCK] result=reveal_original_dock source=%@ running=%ld", source, self.apps.count)
        }
    }
'''

OBJC_HANDLER = r'''
// NRG_V72_OVERFLOW_LONGPRESS: preserve the primary tap's original UIMenu.
- (void)nrgV72WindowOverflowLongPress:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan) return;
    if (!self.nrgWindowOverflow || !self.nrgWindowOverflow.window) return;
    UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
    [feedback impactOccurred];
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self sourceView:self.nrgWindowOverflow];
}

'''

def replace_one(s, old, new, why):
    count=s.count(old)
    if count!=1: raise RuntimeError(f'V72 {why}: expected 1 anchor, found {count}')
    return s.replace(old,new,1)


def cut_between(s, left, right, why, keep_right=True):
    if s.count(left)!=1 or s.count(right)!=1:
        raise RuntimeError(f'V72 {why}: missing/duplicate delimiters {s.count(left)}:{s.count(right)}')
    a=s.index(left);b=s.index(right,a+len(left))
    return s[:a]+s[b:] if keep_right else s[:a]+s[b+len(right):]


def patch_dock(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'ActivityKit' in s or 'nrgV56' in s or 'nrgV58' in s or 'UIScreenEdgePanGestureRecognizer' in s:
            raise RuntimeError('V72 incomplete/double dock transformation')
        if any(s.count(name)!=1 for name in ('enum LCMultitaskDockRenderedMode',
                   'struct LCMultitaskDockPresentationState',
                   'struct LCMultitaskDockSessionState')):
            raise RuntimeError('V74 missing/duplicate dock session model')
        return s
    for required in ('NRG_V58_NATIVE_ISLAND_ACTIVITY','NRG_V62_EXCLUSIVE_UI_SURFACES',
                     'NRG_V56_NOTCH_ADJACENT_CONTROLS','NRG_V192_SCARLET_STARTUP'):
        if required not in s:raise RuntimeError(f'V72 prior patch missing: {required}')
    s=replace_one(s,'import ActivityKit\n','', 'ActivityKit import')
    s=cut_between(s,'// NRG_V58_NATIVE_ISLAND_ACTIVITY: ActivityKit attributes mirrored byte-for-byte',
                  '// MARK: - App Info Provider','native activity declarations')
    # V74 compiler repair: V58's broad removal region can include the V3
    # dock first-frame/session model types. Those models are still consumed by
    # MultitaskDockManager and its SwiftUI root; never discard them with the
    # superseded ActivityKit attributes. Restore only missing complete types.
    models=('enum LCMultitaskDockRenderedMode',
            'struct LCMultitaskDockPresentationState',
            'struct LCMultitaskDockSessionState')
    model_hits=[s.count(name) for name in models]
    if model_hits == [0, 0, 0]:
        template=(Path(__file__).with_name('templates') / 'multitask_dock_session_state.swift').read_text()
        if not all(template.count(name)==1 for name in models):
            raise RuntimeError('V74 dock session template mismatch')
        template=template.removeprefix('import Foundation\n').strip()
        s=replace_one(s,'// MARK: - App Info Provider',template+'\n\n// MARK: - App Info Provider',
                      'restore V3 dock session types')
    elif model_hits != [1, 1, 1]:
        raise RuntimeError(f'V74 partial/duplicated dock session model: {model_hits}')
    nrg_v191_start=s.index('    @objc public func nrgV191AttachGuestWindowHostIfReady()')
    nrg_v191_end=s.index('    // NRG_V194_FOREGROUND_ONLY_ISLAND:',nrg_v191_start)
    safe_host_attach=s[nrg_v191_start:nrg_v191_end]
    nrg_start=s.index('    // NRG_V58_NATIVE_ISLAND_ACTIVITY: one system-managed activity')
    nrg_end=s.index('    public struct Constants {',nrg_start)
    s=s[:nrg_start]+safe_host_attach+'\n'+SWIFT_SWITCHER+'\n'+s[nrg_end:]
    s=cut_between(s,
        '// NRG_V56_NOTCH_ADJACENT_CONTROLS: uses an existing app window, not a',
        '// MARK: - Collapsed Dock View','legacy view and SwiftUI overlay')
    # V91 replaces the *entry gesture*, not the Dock presentation. Delete the
    # original edge handlers and their registration, rather than disabling them.
    swipe_registration = 'self.setupEdgeGestureRecognizers()'
    if s.count(swipe_registration) != 3:
        raise RuntimeError('V91 edge registration changed unexpectedly')
    s = s.replace(swipe_registration, '/* SCARLET_V91_ORIGINAL_DOCK_LONGPRESS: hold only */')
    start = '    // Add edge gesture recognition areas when dock is hidden\n'
    stop = '    // MARK: - Multitask Mode Check\n'
    s = cut_between(s, start, stop, 'remove retired edge-pan listener')
    s = replace_one(s, '        static let edgeSwipeThreshold: CGFloat = 30.0\n', '', 'remove retired edge threshold')
    # Single original manager instance listens for the Direct button hold,
    # where direct bootstrap cannot statically link to a Swift class.
    s = replace_one(s, '        setupDockView()\n',
        '        setupDockView()\n'
        '        NotificationCenter.default.addObserver(self, selector: #selector(nrgV91DirectControlHold(_:)), '
        'name: Notification.Name("ScarletOriginalDockLongHold"), object: nil)\n',
        'direct guest bridge observer')
    if 'UIScreenEdgePanGestureRecognizer' in s or 'handleEdgeSwipe(' in s:
        raise RuntimeError('V91 old edge gesture survived')
    for line in (
        '            self.nrgV56RelayoutIsland()\n',
        '        self.nrgV56RelayoutIsland()\n',
        '        self.nrgV58RefreshNativeIsland()\n',
        '        nrgV61NoteGuestUse(uuid)\n',
        '        nrgV56ShowGuestControls()\n',
        '            self.nrgV61NoteGuestUse(appModel.appUUID)\n',
        '            self.nrgV56ShowGuestControls()\n',
        '                self.nrgV58RefreshNativeIsland()\n',
        '                self.nrgV56IslandHidden = true\n',
        '                self.nrgV56IslandExpanded = false\n',
        '                self.nrgV56RelayoutIsland()\n'):
        s=s.replace(line,'')
    # Old "else if" was conditioned by suppressed live Activity; now Dock
    # remains an ordinary existing container control, never the system Island.
    if any(token in s for token in ('nrgV56','nrgV58','nrgV61','NRGGuestActivityAttributes','ActivityKit','NativeIsland')):
        raise RuntimeError('V72 residual native/adjacent Island manager code')
    return s


def patch_window(s):
    if MARK in s:
        if s.count(MARK)!=2:raise RuntimeError('V72 incomplete/double window transformation')
        return s
    if 'NRG_V37_WINDOW_ONLY_OVERFLOW' not in s:raise RuntimeError('Missing existing 1-o’clock overflow')
    needle='''    overflow.showsMenuAsPrimaryAction = YES;
    [self.view addSubview:overflow];'''
    replacement='''    // NRG_V72_OVERFLOW_LONGPRESS: tap opens window actions; hold opens guests.
    // Gesture cancellation avoids a second tap firing after the long press.
    overflow.showsMenuAsPrimaryAction = YES;
    UILongPressGestureRecognizer *nrgV72Hold = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(nrgV72WindowOverflowLongPress:)];
    nrgV72Hold.minimumPressDuration = 0.55;
    nrgV72Hold.cancelsTouchesInView = YES;
    [overflow addGestureRecognizer:nrgV72Hold];
    [self.view addSubview:overflow];'''
    s=replace_one(s,needle,replacement,'overflow long press')
    s=replace_one(s,'- (void)setupDecoratedView {',OBJC_HANDLER+'- (void)setupDecoratedView {',
                  'overflow handler method')
    # One comment-only marker in gesture, one in handler.
    assert s.count(MARK)==2
    return s


def patch_shell(s):
    if 'NRG_V72_NO_ISLAND' in s:
        if 'nrgV192RefreshIslandIfReady' in s: raise RuntimeError('Residual shell callback')
        return s
    s=replace_one(s,'''        // NRG_V192_SCARLET_STARTUP: SwiftUI first commit precedes UIKit root.
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                nrgV192RefreshIslandIfReady()
            }
        }
        .onReceive(sharedModel.$apps) { _ in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                nrgV192RefreshIslandIfReady()
            }
        }
''','''        // NRG_V72_NO_ISLAND: no native Live Activity or host overlay refresh.
''','remove island startup observers')
    s=cut_between(s,
        '// V192: ignore native-Island refresh during the uncommitted first scene.',
        '// V192: ignore native-Island refresh during the uncommitted first scene.',
        'unused host helper',keep_right=False) if False else s
    # Function appended as final Swift declaration in the known pinned patch.
    intro='// V192: ignore native-Island refresh during the uncommitted first scene.'
    if s.count(intro)!=1:raise RuntimeError('Missing V192 appended helper')
    s=s[:s.index(intro)].rstrip()+'\n'
    return s


def patch_model(s):
    if 'NRG_V72_NO_PREARM' in s:return s
    old='''        // NRG_V63_NOTIFY_GUEST_LAUNCH: ActivityKit request must precede
        // switching to a classic/LiveProcess guest (host may background).
        appInfo.lastLaunched = Date()
        if #available(iOS 16.2, *) {
            await MainActor.run {
                MultitaskDockManager.shared.nrgV58RefreshNativeIsland()
            }
        }
'''
    s=replace_one(s,old,'''        // NRG_V72_NO_PREARM: keep last-used metadata for the long-press
        // picker without starting system Live Activities or new extensions.
        appInfo.lastLaunched = Date()
''','guest launch timestamp')
    return s


def patch_info(data):
    if data.get('NSSupportsLiveActivities') not in (None,True,False):
        raise RuntimeError('Unexpected host Live Activities setting')
    data.pop('NSSupportsLiveActivities',None)
    # The exclusive URL scheme remains required for guest selection, and the
    # long-press selector uses no entitlement or new bundle registration.
    assert any('scarletcrystal251' in v.get('CFBundleURLSchemes',[]) for v in data.get('CFBundleURLTypes',[]))
    return data


def main(root):
    staged=[]
    for rel, fn in ((DOCK,patch_dock),(WINDOW,patch_window),(SHELL,patch_shell),(MODEL,patch_model)):
        p=root/rel;before=p.read_text();after=fn(before)
        if fn(after)!=after:raise RuntimeError(f'V72 non-idempotence: {rel}')
        staged.append((p,after))
    info=root/INFO;data=plistlib.loads(info.read_bytes())
    data=patch_info(data)
    for path,content in staged:path.write_text(content)
    info.write_bytes(plistlib.dumps(data))
    print('[PASS] V72 no ActivityKit/adjacent Island, original tap retained, long press guest picker')
    print('[PASS] host identity untouched, original window controls and JIT/Share extensions retained')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v72_overflow_longpress.py <LiveContainer>')
    main(Path(sys.argv[1]))

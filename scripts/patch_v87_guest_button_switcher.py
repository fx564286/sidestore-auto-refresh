#!/usr/bin/env python3
"""V87: make the floating Return hold open the installed-guest switcher.

Fixes two demonstrated gaps in V76+V72:
* a visible Return button can have no usable AppSceneViewController.view.window,
  so present on the owning button window's visible root controller.
* V72 labels only Dock.apps guests as running and omits retained native windows.

Changes no app identity, Apple login, JIT, container lifetime or existing taps.
Must run AFTER V76, V72 and V73 have been applied.
"""
from pathlib import Path
import sys

OBJC = Path('MultitaskSupport/AppSceneViewController.m')
DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'SCARLET_V87_HOST_GUEST_PICKER'
SWIFT_MARK = 'SCARLET_V87_NATIVE_RUNNING_GUESTS'

OLD_OBJC = r'''// V76: this presenter belongs to Scarlet Crystal's host, not LiveProcess.
// Guest data is never enumerated in an untrusted guest process.
- (void)lcV76ShowInstalledGuestSwitcher {
    if (!NSThread.isMainThread) {
        dispatch_async(dispatch_get_main_queue(), ^{ [self lcV76ShowInstalledGuestSwitcher]; });
        return;
    }
    if (self.isAppTerminationCleanUpCalled || !self.isAppRunning ||
        !self.lcReturnControl || !self.lcReturnControl.window ||
        UIApplication.sharedApplication.applicationState != UIApplicationStateActive) {
        NSLog(@"[LC_GUEST_SWITCH_V76] ignored=guest_inactive");
        return;
    }
    // Use the visible owner for UIKit action-sheet presentation. The virtual
    // window's V73 ellipsis owns its own picker and is unaffected.
    UIViewController *presenter = self;
    if ([self.delegate isKindOfClass:DecoratedAppSceneViewController.class]) {
        presenter = (DecoratedAppSceneViewController *)self.delegate;
    }
    if (!presenter.view.window) {
        NSLog(@"[LC_GUEST_SWITCH_V76] ignored=presenter_has_no_window");
        return;
    }
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:presenter
                                                     sourceView:self.lcReturnControl.button];
    NSLog(@"[LC_GUEST_SWITCH_V76] route=host_recent_guests");
}
'''
NEW_OBJC = r'''// SCARLET_V87_HOST_GUEST_PICKER: visible host-window ownership is the
// reliable presenter anchor, even while the remote guest scene is initializing.
// No home-screen app enumeration or LiveProcess-owned presentation.
- (void)lcV76ShowInstalledGuestSwitcher {
    if (!NSThread.isMainThread) {
        dispatch_async(dispatch_get_main_queue(), ^{ [self lcV76ShowInstalledGuestSwitcher]; });
        return;
    }
    UIButton *source = self.lcReturnControl.button;
    UIWindow *owner = source.window;
    if (_isAppTerminationCleanUpCalled || !source || !owner || !owner.windowScene) {
        NSLog(@"[SCARLET_V87_SWITCH] result=refused reason=no_visible_host_window");
        return;
    }
    UIViewController *presenter = self;
    if (presenter.view.window != owner) {
        if ([self.delegate isKindOfClass:DecoratedAppSceneViewController.class] &&
            [(DecoratedAppSceneViewController *)self.delegate view].window == owner) {
            presenter = (DecoratedAppSceneViewController *)self.delegate;
        } else {
            presenter = owner.rootViewController;
        }
    }
    if (!presenter || presenter.view.window != owner) {
        NSLog(@"[SCARLET_V87_SWITCH] result=refused reason=host_presenter_missing");
        return;
    }
    // Follow currently visible host presentation instead of presenting from
    // a detached remote AppSceneViewController.
    while (presenter.presentedViewController &&
           !presenter.presentedViewController.isBeingDismissed) {
        presenter = presenter.presentedViewController;
    }
    if (presenter.isBeingDismissed || !presenter.view.window) {
        NSLog(@"[SCARLET_V87_SWITCH] result=refused reason=transitioning");
        return;
    }
    NSLog(@"[SCARLET_V87_SWITCH] event=long_hold presenter=visible_host");
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:presenter
                                                     sourceView:source];
}
'''
# Rewrite Swift using exact pre-V87 snippets from V72.
SWIFT_CHANGES = (
    (
      '        let activeFolders = Set(apps.map { $0.appUUID })\n',
      '''        // SCARLET_V87_NATIVE_RUNNING_GUESTS: the Dock only owns virtual
        // guest views. Include retained native LiveProcess windows too.
        // Never count a stale/unbound window as running.
        let nativeFolders = Set(MultitaskWindowManager.appDict.values.compactMap { entry -> String? in
            guard let controller = entry.controller, controller.isAppRunning else { return nil }
            return entry.dataUUID
        })
        let activeFolders = Set(apps.map { $0.appUUID }).union(nativeFolders)
'''
    ),
    (
      '                if guest.running && self.bringMultitaskViewToFront(uuid: guest.folder) {\n                    NSLog("[NRG_V72_SWITCH] route=retained result=presented")\n                    return\n                }\n',
      '''                // Native and virtual windows have independent presentation
                // ownership. Restore an existing native scene before asking
                // the Dock or starting another guest process.
                if guest.running {
                    if #available(iOS 16.1, *),
                       MultitaskWindowManager.openExistingAppWindow(dataUUID: guest.folder) {
                        NSLog("[SCARLET_V87_SWITCH] route=native_existing result=requested")
                        return
                    }
                    if self.bringMultitaskViewToFront(uuid: guest.folder) {
                        NSLog("[SCARLET_V87_SWITCH] route=virtual_existing result=presented")
                        return
                    }
                    NSLog("[SCARLET_V87_SWITCH] result=retained_window_unavailable fallback=guarded_route")
                }
'''
    ),
    (
      '        let menu = UIAlertController(title: "최근 게스트 전환",',
      '        let menu = UIAlertController(title: "홍수정 내부 앱 전환",'
    )
)

def replace_one(text: str, before: str, after: str, why: str) -> str:
    if text.count(before) != 1:
        raise ValueError(f'V87 {why}: expected exactly one pinned anchor, found {text.count(before)}')
    return text.replace(before, after, 1)

def objc(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or 'presenter=visible_host' not in source:
            raise ValueError('V87 partially installed Objective-C switcher')
        return source
    if 'LC_GUEST_SWITCH_V76_PATCHED' not in source:
        raise ValueError('V87 needs V76 native long-hold button')
    return replace_one(source, OLD_OBJC, NEW_OBJC, 'host scene presenter')

def swift(source: str) -> str:
    if SWIFT_MARK in source:
        for field in ('nativeFolders', 'route=native_existing', 'route=virtual_existing',
                      '홍수정 내부 앱 전환'):
            if field not in source:
                raise ValueError('V87 partially installed Swift switcher')
        if source.count(SWIFT_MARK) != 1:
            raise ValueError('V87 duplicated Swift marker')
        return source
    if 'NRG_V72_OVERFLOW_LONGPRESS' not in source:
        raise ValueError('V87 needs V72 recent guest chooser')
    for old, new in SWIFT_CHANGES:
        source = replace_one(source, old, new, 'native guest picker')
    return source

def apply(root: Path) -> None:
    # Validate both files and replay before writing either.
    proposed = []
    for relative, fn in ((OBJC, objc), (DOCK, swift)):
        file = root / relative
        before = file.read_text(encoding='utf-8')
        after = fn(before)
        if fn(after) != after:
            raise ValueError('V87 non-idempotent patch ' + str(relative))
        proposed.append((file, before, after))
    for file, before, after in proposed:
        if before != after:
            file.write_text(after, encoding='utf-8')
    print('[PASS] V87 visible-host hold and native/virtual installed guest routing; identity unchanged')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_v87_guest_button_switcher.py <LiveContainer checkout>')
    apply(Path(sys.argv[1]))

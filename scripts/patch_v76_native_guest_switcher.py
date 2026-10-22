#!/usr/bin/env python3
"""V76: full-screen LiveProcess guest long-press opens V72 recent guest picker.

Virtual-window guests already own the V73 native-material movable ellipsis.
Their second Return overlay is suppressed, not removed. Native-window guests
use the existing movable Return control with a long press mapped to the same
host-installed-app switcher. This patch is applied after patch_guest_return.
It does not alter process identity, launch container registration or JIT.
"""
from pathlib import Path
import sys

TARGET=Path('MultitaskSupport/AppSceneViewController.m')
MARKER='LC_GUEST_SWITCH_V76_PATCHED'

def one(s,old,new,label):
    if s.count(old)!=1:raise ValueError(f'V76 {label}: expected 1, got {s.count(old)}')
    return s.replace(old,new,1)

LONG_PRESS=r'''
    // LC_GUEST_SWITCH_V76_PATCHED: long press is reserved for guest switching.
    // The primary tap remains Return, pan remains move-to-uncover guest UI.
    UILongPressGestureRecognizer *v76Hold = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(lcV76HoldToSwitch:)];
    v76Hold.minimumPressDuration = 0.55;
    v76Hold.cancelsTouchesInView = YES;
    [self.button addGestureRecognizer:v76Hold];
'''

METHODS=r'''
- (void)lcV76HoldToSwitch:(UILongPressGestureRecognizer *)recognizer {
    if (recognizer.state != UIGestureRecognizerStateBegan || self.collapsed) return;
    if (self.switchAction) {
        UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc]
            initWithStyle:UIImpactFeedbackStyleLight];
        [feedback impactOccurred];
        self.switchAction();
    }
}
- (void)lcV76CollapseControl {
    [self collapse];
}
'''

SWITCH_METHOD=r'''
// V76: this presenter belongs to Scarlet Crystal's host, not LiveProcess.
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

MATERIAL=r'''
    // Use the same iOS adaptive system material as the V73 floating ellipsis.
    // Custom color preferences can still override it; native control is 44pt.
    self.button.backgroundColor = UIColor.clearColor;
    UIVisualEffectView *v76Material = [[UIVisualEffectView alloc]
        initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemThinMaterial]];
    v76Material.frame = self.button.bounds;
    v76Material.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    v76Material.userInteractionEnabled = NO;
    v76Material.layer.cornerRadius = 22;
    v76Material.clipsToBounds = YES;
    [self.button insertSubview:v76Material atIndex:0];
'''

LAYOUT=r'''
    // LCReturnControl default position is left-of-center; saved gestures win.
    // Suppress the extra overlay for virtual windows: V73 already provides
    // the draggable window menu and its V72 long-press guest switcher.
    self.lcReturnControl.hidden = LCReturnShouldHide(self.isAppRunning, decorated, maximized) || decorated;
'''

def patch(s):
    if MARKER in s:
        for x in ('lcV76ShowInstalledGuestSwitcher','lcV76HoldToSwitch:',
                  'nrgV72PresentGuestSwitcherFrom:presenter','|| decorated;',
                  'UIBlurEffectStyleSystemThinMaterial'):
            if x not in s:raise ValueError('V76 partial existing patch: '+x)
        if s.count(MARKER)!=1:raise ValueError('V76 unexpected marker count')
        return s
    for needed in ('LC_GUEST_RETURN_V3','nrgV72PresentGuestSwitcherFrom',):
        if needed=='nrgV72PresentGuestSwitcherFrom':continue # linked Swift method, not yet in .m
        if needed not in s:raise ValueError('V76 missing guest return prerequisite')
    s=one(s,'@property(nonatomic, copy) void (^action)(void);\n@property(nonatomic) CGPoint position;',
          '@property(nonatomic, copy) void (^action)(void);\n@property(nonatomic, copy) void (^switchAction)(void);\n@property(nonatomic) CGPoint position;',
          'switch action property')
    s=one(s,'    self.position = CGPointMake(0.95, 0.25);',
          '    self.position = CGPointMake(0.06, 0.60); // V76 default avoids in-app top-right buttons',
          'left-of-center default')
    s=one(s,'    self.button.layer.cornerRadius = 22;\n',
          '    self.button.layer.cornerRadius = 22;\n'+MATERIAL,
          'native UIKit material')
    # UIButton's implicit long-press UIMenu competes with the explicitly
    # requested gesture; move collapse into the switcher action sheet.
    old='''    self.button.menu = [UIMenu menuWithTitle:@"" children:@[
        [UIAction actionWithTitle:@"Collapse Return Button" image:[UIImage systemImageNamed:@"sidebar.right"] identifier:nil handler:^(__kindof UIAction *action) {
            [weakControl collapse];
        }]
    ]];
'''
    s=one(s,old,'    // V76: collapse remains in recent-guest action sheet and settings.\n',
          'remove conflicting implicit longpress menu')
    s=one(s,'    __weak typeof(self) weakControl = self;\n','',
          'unused former native menu capture')
    s=one(s,'    [self.button addTarget:self action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];\n',
          '    [self.button addTarget:self action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];\n'+LONG_PRESS,
          'explicit hold to switch')
    s=one(s,'- (void)tapped {\n    if (self.collapsed)',METHODS+'- (void)tapped {\n    if (self.collapsed)',
          'native control hold implementation')
    s=one(s,'    self.button.backgroundColor = self.collapsed ? UIColor.clearColor : background;',
          '    self.button.backgroundColor = self.collapsed ? UIColor.clearColor : (customColors ? background : UIColor.clearColor);\n'
          '    for (UIView *child in self.button.subviews) {\n'
          '        if ([child isKindOfClass:UIVisualEffectView.class]) child.hidden = self.collapsed || customColors;\n'
          '    }',
          'system material on default color')
    s=one(s,'        self.lcReturnControl.action = ^{ [weakSelf lcReturnToHost]; };',
          '        self.lcReturnControl.action = ^{ [weakSelf lcReturnToHost]; };\n'
          '        self.lcReturnControl.switchAction = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };',
          'register guest picker action')
    s=one(s,'    self.lcReturnControl.hidden = LCReturnShouldHide(self.isAppRunning, decorated, maximized);',
          LAYOUT.rstrip('\n'), 'remove redundant decorated overlay')
    s=one(s,'- (void)lcReturnToHost {',SWITCH_METHOD+'- (void)lcReturnToHost {',
          'guest host picker presenter')
    if s.count(MARKER)!=1:raise ValueError(f'V76 marker count: {s.count(MARKER)}')
    return s

def main(root):
    file=root/TARGET
    original=file.read_text(encoding='utf-8')
    updated=patch(original)
    if patch(updated)!=updated:raise ValueError('V76 not idempotent')
    if updated!=original:file.write_text(updated,encoding='utf-8')
    print('[PASS] V76 native LiveProcess hold opens host guest picker; virtual uses V73 ellipsis')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v76_native_guest_switcher.py <LiveContainer source>')
    main(Path(sys.argv[1]))

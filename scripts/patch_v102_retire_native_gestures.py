#!/usr/bin/env python3
"""V102: remove inactive V76 gesture, stale callback, and native UIMenu.

LiveProcess uses same guest morph on tap and same window-actions morph on hold.
Does not change Direct/LiveProcess ownership, credential or signing.
"""
from pathlib import Path
import sys
FILE=Path('MultitaskSupport/AppSceneViewController.m')
MARK='SCARLET_V102_NATIVE_GESTURE_CLEANUP'
def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'v76Hold.enabled = NO' in s or 'lcV76HoldToSwitch:' in s:
            raise ValueError('Native V102 partial or stale code')
        return s
    for marker in ('SCARLET_V100_LIVEPROCESS_MORPH','LC_GUEST_SWITCH_V76_PATCHED',
                   'SCARLET_V87_HOST_GUEST_PICKER'):
        if marker not in s:raise ValueError('Missing native prerequisite '+marker)
    n='        self.lcReturnControl.button.menu = [UIMenu menuWithChildren:@['
    if s.count(n)!=1: raise ValueError('unexpected V100 menu count')
    a=s.index(n);b=s.index('        ]];',a)+len('        ]];')
    if 'Return to Scarlet Crystal' not in s[a:b] or 'lcV76CollapseControl' not in s[a:b]:
        raise ValueError('unknown V100 native menu body')
    s=s[:a]+'''        // SCARLET_V102_NATIVE_GESTURE_CLEANUP: same morph surface as
        // virtual guests. Remove old separate native popup completely.
        self.lcReturnControl.button.menu = nil;
        UILongPressGestureRecognizer *nrgV102NativeHold = [[UILongPressGestureRecognizer alloc]
            initWithTarget:self action:@selector(lcV102NativeHoldActions:)];
        nrgV102NativeHold.minimumPressDuration = 0.55;
        nrgV102NativeHold.cancelsTouchesInView = YES;
        [self.lcReturnControl.button addGestureRecognizer:nrgV102NativeHold];'''+s[b:]
    start=s.find('    UILongPressGestureRecognizer *v76Hold = [[UILongPressGestureRecognizer alloc]')
    if start<0 or s.count('    v76Hold.enabled = NO;')!=1:
        raise ValueError('missing disabled V76 gesture')
    end=s.index('    v76Hold.enabled = NO;',start)+len('    v76Hold.enabled = NO;')
    s=s[:start]+s[end:]
    start=s.find('- (void)lcV76HoldToSwitch:(UILongPressGestureRecognizer *)recognizer {')
    if start<0 or s.count('- (void)lcV76HoldToSwitch:')!=1:
        raise ValueError('missing dead V76 hold selector')
    end=s.find('- (void)lcV76CollapseControl {',start)
    if end<0:raise ValueError('could not isolate legacy method')
    s=s[:start]+s[end:]
    for old in (
       '@property(nonatomic, copy) void (^switchAction)(void);\n',
       '        self.lcReturnControl.switchAction = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };\n',
    ):
        if s.count(old)!=1:raise ValueError('missing unused V76 callback')
        s=s.replace(old,'',1)
    marker='- (void)lcV76ShowInstalledGuestSwitcher {'
    if s.count(marker)!=1:raise ValueError('unexpected native host picker selector')
    methods='''// V102: the same in-window material/rounded renderer backs both gestures.
- (void)lcV102NativeHoldActions:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan ||
        _isAppTerminationCleanUpCalled || !self.lcReturnControl ||
        self.lcReturnControl.hidden || !self.lcReturnControl.button.window) return;
    UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc]
        initWithStyle:UIImpactFeedbackStyleLight];
    [feedback impactOccurred];
    [MultitaskDockManager.shared nrgV102PresentWindowActionsFrom:self
                                                     sourceView:self.lcReturnControl.button];
}
- (void)lcV102CollapseFloatingButton {
    [self.lcReturnControl lcV76CollapseControl];
}

'''
    s=s.replace(marker,methods+marker,1)
    return s

def apply(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError('missing pinned AppScene source')
    before=p.read_text()
    after=patch(before)
    if patch(after)!=after:raise ValueError('not idempotent')
    if before!=after:p.write_text(after)
    print('[PASS] Native V76 legacy gesture/callback and V100 native menu removed')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v102_retire_native_gestures.py <LiveContainer>')
    apply(Path(sys.argv[1]))

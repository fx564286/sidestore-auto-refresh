#!/usr/bin/env python3
"""V99: one native floating button, tap guest switch, hold original window options.

Uses V72/V73 host-owned UIKit control. Leaves guest rendering, JIT, identity,
container ownership and existing iOS system Dynamic Island unchanged.
"""
from pathlib import Path
import sys

TARGET=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V99_UNIFIED_FLOATING_GUEST_CONTROL"
DEFAULT_OLD='CGFloat fraction = [stored isKindOfClass:NSNumber.class] ? [stored doubleValue] : 0.60;'
DEFAULT_NEW='CGFloat fraction = [stored isKindOfClass:NSNumber.class] ? [stored doubleValue] : 0.50;'
RIGHT_OLD='BOOL onRight = [prefs boolForKey:sideKey];'
RIGHT_NEW='BOOL onRight = [prefs objectForKey:sideKey] ? [prefs boolForKey:sideKey] : YES;'
TAP_OLD='    overflow.showsMenuAsPrimaryAction = YES;\n    UILongPressGestureRecognizer *nrgV72Hold'
TAP_NEW='''    // SCARLET_V99_UNIFIED_FLOATING_GUEST_CONTROL: primary tap is the
    // retained guest picker. Hold reveals original minimize/maximize/close.
    overflow.showsMenuAsPrimaryAction = NO;
    [overflow addTarget:self action:@selector(nrgV99OpenRecentGuests:)
      forControlEvents:UIControlEventTouchUpInside];
    UILongPressGestureRecognizer *nrgV72Hold'''
HANDLER_OLD='''    UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
    [feedback impactOccurred];
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self sourceView:self.nrgWindowOverflow];
}'''
HANDLER_NEW='''    UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
    [feedback impactOccurred];
    [self nrgV99ShowWindowActionsFrom:self.nrgWindowOverflow];
}'''
NEW_METHODS=r'''
// The fixed 1-o'clock overflow is gone: this same movable host-owned button
// exposes both actions without inserting a bar across the guest safe area.
- (void)nrgV99OpenRecentGuests:(UIButton *)source {
    if (!source || !source.window || self.isBeingDismissed) return;
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self sourceView:source];
    NSLog(@"[SCARLET_V99_FLOATING] action=recent_guests origin=tap");
}
- (void)nrgV99ShowWindowActionsFrom:(UIButton *)source {
    if (!source || !source.window || self.isBeingDismissed ||
        self.presentedViewController) return;
    UIAlertController *sheet =
        [UIAlertController alertControllerWithTitle:@"창 관리"
                                            message:nil
                                     preferredStyle:UIAlertControllerStyleActionSheet];
    __weak typeof(self) weakSelf = self;
    [sheet addAction:[UIAlertAction actionWithTitle:@"최소화"
                                            style:UIAlertActionStyleDefault
                                          handler:^(UIAlertAction *action) {
        [weakSelf minimizeWindow];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"최대화 / 복원"
                                            style:UIAlertActionStyleDefault
                                          handler:^(UIAlertAction *action) {
        [weakSelf maximizeWindow];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"닫기"
                                            style:UIAlertActionStyleDestructive
                                          handler:^(UIAlertAction *action) {
        [weakSelf closeWindow];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"취소"
                                            style:UIAlertActionStyleCancel
                                          handler:nil]];
    UIPopoverPresentationController *popover=sheet.popoverPresentationController;
    if (popover) {
        popover.sourceView=source;
        popover.sourceRect=source.bounds;
    }
    [self presentViewController:sheet animated:YES completion:nil];
    NSLog(@"[SCARLET_V99_FLOATING] action=window_controls origin=hold");
}

'''
def one(s,a,b,label):
    count=s.count(a)
    if count!=1: raise ValueError(f"V99 {label}: expected one anchor, got {count}")
    return s.replace(a,b,1)
def patch(s):
    if MARK in s:
        for requirement in ("nrgV99OpenRecentGuests:", "nrgV99ShowWindowActionsFrom:",
                            "SCARLET_V99_FLOATING", "overflow.showsMenuAsPrimaryAction = NO;"):
            if requirement not in s:raise ValueError("V99 partially applied: "+requirement)
        if s.count(MARK)!=1: raise ValueError("duplicate V99 markers")
        return s
    for prerequisite in ("NRG_V73_APPLE_FLOATING_CONTROL","NRG_V72_OVERFLOW_LONGPRESS",
                         "nrgV73RestoreFloatingPosition", "nrgV72WindowOverflowLongPress:"):
        if prerequisite not in s: raise ValueError("missing previously tested prerequisite "+prerequisite)
    s=one(s,DEFAULT_OLD,DEFAULT_NEW,"symmetric height")
    s=one(s,RIGHT_OLD,RIGHT_NEW,"default right edge")
    s=one(s,TAP_OLD,TAP_NEW,"tap switch mapping")
    s=one(s,HANDLER_OLD,HANDLER_NEW,"hold window actions")
    s=one(s,"- (void)nrgV72WindowOverflowLongPress:",NEW_METHODS+"- (void)nrgV72WindowOverflowLongPress:","window sheet methods")
    s=one(s,'overflow.accessibilityHint = @"Tap for window options. Hold to switch guests. Drag to move.";',
          'overflow.accessibilityHint = @"Tap to switch recent container guests. Hold for window actions. Drag to move.";',
          "accessibility")
    return s

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v99_floating_guest_control.py <LiveContainer>")
    p=Path(sys.argv[1])/TARGET
    before=p.read_text(encoding="utf-8")
    after=patch(before)
    assert patch(after)==after
    if before!=after:p.write_text(after,encoding="utf-8")
    print("SCARLET_V99_FLOATING_OK tap_switch=1 hold_window_menu=1 default_right=1")

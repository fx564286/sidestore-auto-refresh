#!/usr/bin/env python3
"""V144: make both existing native guest buttons deform under the finger.

One UIKit UIButton in each exclusive host/Direct runtime; this augments
their existing V139 gradient, never creates another handle or action route.
"""
from pathlib import Path
import sys
BOOT=Path('LiveContainer/LCBootstrap.m')
HOST=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
MARK='SCARLET_V144_BUTTON_LENS'

MORPH='''    // SCARLET_V144_BUTTON_LENS: the existing button is stationary for hit
    // testing; only its interactive native UIGlassEffect surface deforms.
    CGPoint glassPoint = [touch locationInView:button];
    CGFloat glassWidth = MAX(1.0, CGRectGetWidth(button.bounds));
    CGFloat glassHeight = MAX(1.0, CGRectGetHeight(button.bounds));
    BOOL released = touch.phase == UITouchPhaseEnded ||
                    touch.phase == UITouchPhaseCancelled;
    for (UIView *glassSurface in button.subviews) {
        if (![glassSurface isKindOfClass:UIVisualEffectView.class]) continue;
        if (released || UIAccessibilityIsReduceMotionEnabled()) {
            [UIView animateWithDuration:0.23 animations:^{
                glassSurface.transform = CGAffineTransformIdentity;
            }];
        } else {
            CGFloat fx = glassPoint.x / glassWidth - 0.5;
            CGFloat fy = glassPoint.y / glassHeight - 0.5;
            glassSurface.transform = CGAffineTransformScale(
                CGAffineTransformMakeTranslation(fx * 5.0, fy * 5.0),
                1.065, 1.065);
        }
    }
'''

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:raise ValueError(f'V144 button {label}: expected one target, got {n}')
    return s.replace(a,b,1)

def boot(s):
    if MARK in s:
        if s.count(MARK)!=1:raise ValueError('duplicate Direct marker')
        return s
    if 'SCARLET_V139_GLASS' not in s or 'reactToGlassTouch:' not in s:
        raise ValueError('missing V139 Direct button touch route')
    needle='''    [self updateDirectGlass:button atPoint:[touch locationInView:button]];
    NSLog(@"[SCARLET_V139_GLASS] surface=direct finger=tracked phase=%ld", (long)touch.phase);'''
    return once(s,needle,
                '''    [self updateDirectGlass:button atPoint:[touch locationInView:button]];
'''+MORPH+'''    NSLog(@"[SCARLET_V139_GLASS] surface=direct finger=tracked phase=%ld", (long)touch.phase);''',
                'Direct existing touch handler')

def host(s):
    if MARK in s:
        if s.count(MARK)!=1:raise ValueError('duplicate native host marker')
        return s
    if 'SCARLET_V139_GLASS' not in s or 'nrgV139HostedGlassTouch:' not in s:
        raise ValueError('missing V139 hosted button touch route')
    needle='''    [self nrgV139UpdateHostedGlassAt:[touch locationInView:button] inButton:button];
    NSLog(@"[SCARLET_V139_GLASS] surface=hosted finger=tracked phase=%ld", (long)touch.phase);'''
    return once(s,needle,
                '''    [self nrgV139UpdateHostedGlassAt:[touch locationInView:button] inButton:button];
'''+MORPH+'''    NSLog(@"[SCARLET_V139_GLASS] surface=hosted finger=tracked phase=%ld", (long)touch.phase);''',
                'host existing touch handler')

def apply(root):
    edits=[]
    for relative,patch in ((BOOT,boot),(HOST,host)):
        p=root/relative
        if not p.is_file() or p.is_symlink():raise ValueError('missing pinned button source')
        before=p.read_text(encoding='utf-8')
        after=patch(before)
        if patch(after)!=after:raise ValueError('not idempotent: '+str(relative))
        edits.append((p,before,after))
    for p,old,new in edits:
        if old!=new:p.write_text(new,encoding='utf-8')
    print('[PASS] V144 native Direct/hosted buttons follow the finger with one existing control each')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v144_button_glass.py <LiveContainer>')
    apply(Path(sys.argv[1]))

#!/usr/bin/env python3
"""V137: ONE guest-control implementation for Direct and LiveProcess.

Run after existing V137 glass/rotation patch. Delete the native V73 button
source (rather than temporarily hiding it), preserve shared bootstrap
presenter and its one UIWindow per active guest scene. No signing/JIT changes.
"""
from pathlib import Path
import sys

DECORATED = Path('MultitaskSupport/DecoratedAppSceneViewController.m')
BOOT = Path('LiveContainer/LCBootstrap.m')
MARK = 'SCARLET_V137_UNIFIED_GUEST_ENTRY'


def replace_one(s, old, new, reason):
    n = s.count(old)
    if n != 1:
        raise ValueError(f'V137 {reason} expected one anchor; observed {n}')
    return s.replace(old, new, 1)


def erase_span(s, a, b, replacement, reason):
    if s.count(a) != 1 or s.count(b) != 1 or s.index(a) >= s.index(b):
        raise ValueError(f'V137 {reason}: ambiguous source boundary {s.count(a)}/{s.count(b)}')
    return s[:s.index(a)] + replacement + s[s.index(b):]


def decorated(s):
    if MARK in s:
        if s.count(MARK) != 1 or 'nrgWindowOverflow' in s:
            raise ValueError('partial V137 decorated unified owner')
        return s
    for required in ('SCARLET_V136_ROTATION_ATOMIC', 'NRG_V73_APPLE_FLOATING_CONTROL'):
        if required not in s:
            raise ValueError('V137 missing decorated prerequisite '+required)
    s = erase_span(s, '@property(nonatomic, strong) UIButton *nrgWindowOverflow;',
                   '@property(nonatomic) bool isAppTerminationRequested;',
                   '', 'old native button properties')
    # Retain only the rotation/hit-area synchronization. No V73 UIWindow
    # handle, event recognizers, position constraints, tap/hold handlers.
    s = erase_span(s, '- (NSString *)nrgV73PreferenceSuffix {',
                   '- (void)setupDecoratedView {',
                   '''// SCARLET_V137_UNIFIED_GUEST_ENTRY / SCARLET_V137_TOUCH_SETTLE: the only edge entry is owned
// by the shared bootstrap presenter in both guest execution modes.
- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    UIWindow *host = self.view.window;
    if (self.isMaximized && self.appSceneVC.isAppRunning &&
        [self nrgV136GeometryStable:host]) {
        CGSize finalSize = host.bounds.size;
        UIInterfaceOrientation orientation = host.windowScene.interfaceOrientation;
        if (!CGSizeEqualToSize(finalSize, self.nrgV55LastHostSize) ||
            orientation != self.nrgV55LastHostOrientation) {
            NSLog(@"[SCARLET_V137_TOUCH] stage=settled width=%.1f height=%.1f",
                  finalSize.width, finalSize.height);
            [self nrgV55ReconcileRotationGeometry];
        }
    }
}

''', 'old button geometry and gestures')
    s = erase_span(s, '    // NRG: overlay is independent of the navigation bar and adds no layout row.',
                   '    self.view.layer.borderWidth = _isMaximized ?',
                   '    // V137: shared bootstrap morph owns all floating gesture input.\n',
                   'old native button instance and its constraints')
    for old in ('nrgWindowOverflow','nrgV73Floating','nrgV73RestoreFloatingPosition',
                'nrgV73DragFloatingOverflow','nrgV100TapMorph:','nrgV102HoldWindowActions:'):
        if old in s:
            raise ValueError('V137 old native button survived: '+old)
    return s


def boot(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'nativeAvailableInScene:' in s:
            raise ValueError('partial V137 unified bootstrap')
        return s
    for required in ('SCARLET_V137_SCENE_OWNER','SCARLET_V132_ONE_HANDLE',
                     'SCARLET_V105_DIRECT_UNIFIED_MORPH'):
        if required not in s:
            raise ValueError('V137 missing bootstrap prerequisite '+required)
    # Abolish the fallback-vs-native negotiation, rather than add more retire
    # logic. This presenter is the one code path for both execution modes.
    s = erase_span(s, '- (BOOL)containsVirtualHandle:(UIView *)view {',
                   '- (void)show:(NSNotification *)notice {',
                   '// SCARLET_V137_UNIFIED_GUEST_ENTRY: no competing native owner.\n',
                   'cross-scene native ownership and retirement methods')
    s = replace_one(s,
'''    // SCARLET_V129_SINGLE_OWNER: native V73 can appear *after* the
    // fallback was created. Retire the latter as soon as V73 is attached.
    [center addObserver:self selector:@selector(virtualReady:) name:@"SCScarletVirtualHandleReady" object:nil];
''', '', 'obsolete native-ready observer')
    s = erase_span(s,
                   '    // SCARLET_V132_ONE_HANDLE: V73 takes priority across all foreground',
                   '    NSString *idKey = scene.session.persistentIdentifier;',
                   '', 'speculative native suppressor')
    s = replace_one(s, '    [self retireAllFallbacks:@"new_active_scene"];\n', '',
                    'delete cross-scene retire-on-create')
    # Old delayed callback can hide a working button when another scene
    # momentarily reports ready. Remove both callback and timer entirely.
    s = erase_span(s, '    // SCARLET_V132_ONE_HANDLE: reconcile delayed native V73 attachment.',
                   '    NSLog(@"[SCARLET_V132_ONE_HANDLE] fallback_created=1");',
                   '', 'deferred competing owner')
    s = replace_one(s,
'''    handle.accessibilityIdentifier = @"scarlet.v105.direct.morph";''',
'''    handle.accessibilityIdentifier = @"scarlet.v137.shared.guest.control";''',
                    'one shared accessible button')
    s = replace_one(s,
'''    handle.accessibilityLabel = @"Scarlet Crystal guest switching";''',
'''    handle.accessibilityLabel = @"Scarlet Crystal window and app switching";''',
                    'shared access label')
    s = replace_one(s,
'''    // Visually identical native thin-material ellipsis entry control.''',
'''    // V137 one shared entry control for Direct AND LiveProcess.''',
                    'shared entry comment')
    # One native glass surface for all guest modes. Keep the UIButton
    # as the sole hit-testing owner and use the original UIPanGestureRecognizer.
    s = replace_one(s, "    handle.clipsToBounds = YES;",
        """    handle.clipsToBounds = YES;
    handle.layer.borderWidth = 0.8;
    handle.layer.borderColor = [UIColor.whiteColor colorWithAlphaComponent:0.66].CGColor;
    // SCARLET_V137_FINGER_GLASS: shared organic glass, never an extra button.
""", "one glass rim")
    s = replace_one(s,
        "    UIVisualEffectView *material = [[UIVisualEffectView alloc] initWithEffect:effect];",
        """    UIVisualEffectView *material = [[UIVisualEffectView alloc] initWithEffect:effect];
    CAGradientLayer *glint = [CAGradientLayer layer];
    glint.name = @"scarlet.v137.finger.glint";
    glint.frame = handle.bounds;
    glint.colors = @[(id)[UIColor.whiteColor colorWithAlphaComponent:0.38].CGColor,
                     (id)[UIColor.whiteColor colorWithAlphaComponent:0.02].CGColor,
                     (id)[UIColor.whiteColor colorWithAlphaComponent:0.20].CGColor];
    glint.locations = @[@0.0, @0.48, @1.0];
    glint.startPoint = CGPointMake(0.15, 0.0);
    glint.endPoint = CGPointMake(0.85, 1.0);
    [material.contentView.layer addSublayer:glint];""",
        "single moving rim highlight")
    s = replace_one(s,
        """    CGPoint delta = [gesture translationInView:container];
    CGFloat x = MAX(22, MIN(container.bounds.size.width-22, button.center.x+delta.x));""",
        """    CGPoint delta = [gesture translationInView:container];
    if (gesture.state == UIGestureRecognizerStateBegan ||
        gesture.state == UIGestureRecognizerStateChanged) {
        CGPoint speed = [gesture velocityInView:container];
        CGFloat tilt = MAX(-0.12, MIN(0.12, speed.x / 2300.0));
        CGFloat stretch = MAX(-0.10, MIN(0.10, speed.y / 3800.0));
        if (!UIAccessibilityIsReduceMotionEnabled()) {
            button.transform = CGAffineTransformRotate(
                CGAffineTransformMakeScale(1.10 + fabs(stretch) * 0.30,
                                           0.92 + fabs(stretch) * 0.40), tilt);
        }
        CGPoint touch = [gesture locationInView:button];
        for (UIView *child in button.subviews) {
            if (![child isKindOfClass:UIVisualEffectView.class]) continue;
            UIVisualEffectView *material = (UIVisualEffectView *)child;
            for (CALayer *layer in material.contentView.layer.sublayers) {
                if (![layer isKindOfClass:CAGradientLayer.class] ||
                    ![layer.name isEqualToString:@"scarlet.v137.finger.glint"]) continue;
                CAGradientLayer *shine = (CAGradientLayer *)layer;
                CGFloat progress = MAX(0.05, MIN(0.95, touch.x / MAX(1.0, button.bounds.size.width)));
                [CATransaction begin];
                [CATransaction setDisableActions:YES];
                shine.startPoint = CGPointMake(progress, 0);
                shine.endPoint = CGPointMake(progress, 1);
                [CATransaction commit];
            }
        }
    }
    CGFloat x = MAX(22, MIN(container.bounds.size.width-22, button.center.x+delta.x));""",
        "true finger-position follow")
    s = replace_one(s,
        "        [UIView animateWithDuration:.18 animations:^{ button.center = CGPointMake(edge, y); }];",
        """        [UIView animateWithDuration:0.36 delay:0.0
              usingSpringWithDamping:0.76 initialSpringVelocity:0.55
              options:UIViewAnimationOptionAllowUserInteraction animations:^{
            button.center = CGPointMake(edge, y);
            button.transform = CGAffineTransformIdentity;
        } completion:nil];
        UISelectionFeedbackGenerator *haptic = [UISelectionFeedbackGenerator new];
        [haptic selectionChanged];
        NSLog(@"[SCARLET_V137_FINGER_GLASS] phase=snap right=%d", right);""",
        "springy snap back")

    # Do not create a second controller/window when the same scene gets
    # multiple activate/visible events. Existing guard remains authoritative.
    if s.count('SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];') != 1:
        raise ValueError('more than one entry creation path')
    # CI source may normalize this conditional during earlier bootstrap patch.
    # The existing single static presenter must remain initialized once.
    if s.count('scGuestMorphPresenter = [SCGuestMorphPresenter new];') != 1:
        raise ValueError('boot presenter not initialized exactly once')
    for old in ('retireAllFallbacks:', 'nativeAvailableInForeground',
                'nativeAvailableInScene:', 'virtualReady:',
                'SCScarletVirtualHandleReady'):
        if old in s:
            raise ValueError('obsolete competing owner remains: '+old)
    return s


def apply(root):
    changes=[]
    for rel,fn in ((DECORATED,decorated),(BOOT,boot)):
        p=root/rel
        if not p.is_file() or p.is_symlink():
            raise ValueError('V137 missing pinned source '+str(rel))
        old=p.read_text()
        new=fn(old)
        if fn(new)!=new:
            raise ValueError('V137 non-idempotent '+str(rel))
        changes.append((p,old,new))
    for p,old,new in changes:
        if old!=new:p.write_text(new)
    print('[PASS] V137 one shared Direct/LiveProcess entry path; V73 button source deleted')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v137_single_glass_entry.py <LiveContainer>')
    apply(Path(sys.argv[1]))

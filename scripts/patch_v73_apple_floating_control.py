#!/usr/bin/env python3
"""V73: native-material movable guest window control; no fixed top-right overlay.

Apply after V72. Only touches DecoratedAppSceneViewController; guest view,
V70 viewport geometry, LiveProcess, JIT and signing stay unchanged.
"""
from pathlib import Path
import sys

FILE = Path('MultitaskSupport/DecoratedAppSceneViewController.m')
MARK = 'NRG_V73_APPLE_FLOATING_CONTROL'

PROPERTY = '''@property(nonatomic, strong) NSLayoutConstraint *nrgV73FloatingLeading;
@property(nonatomic, strong) NSLayoutConstraint *nrgV73FloatingTop;
@property(nonatomic) CGSize nrgV73LastSize;
@property(nonatomic) UIEdgeInsets nrgV73LastSafeArea;
'''

MATERIAL = '''    // NRG_V73_APPLE_FLOATING_CONTROL: native system material and SF Symbol,
    // not a black notch bar or fixed 1-o'clock overlay.
    overflow.tintColor = UIColor.labelColor;
    overflow.backgroundColor = UIColor.clearColor;
    overflow.layer.cornerRadius = 22.0;
    overflow.clipsToBounds = YES;
    UIVisualEffectView *nrgV73Material = [[UIVisualEffectView alloc]
        initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemThinMaterial]];
    nrgV73Material.translatesAutoresizingMaskIntoConstraints = NO;
    nrgV73Material.userInteractionEnabled = NO;
    [overflow insertSubview:nrgV73Material atIndex:0];
    [NSLayoutConstraint activateConstraints:@[
        [nrgV73Material.leadingAnchor constraintEqualToAnchor:overflow.leadingAnchor],
        [nrgV73Material.trailingAnchor constraintEqualToAnchor:overflow.trailingAnchor],
        [nrgV73Material.topAnchor constraintEqualToAnchor:overflow.topAnchor],
        [nrgV73Material.bottomAnchor constraintEqualToAnchor:overflow.bottomAnchor]
    ]];
    overflow.accessibilityLabel = @"Guest window controls";
    overflow.accessibilityHint = @"Tap for window options. Hold to switch guests. Drag to move.";
'''

GESTURE = '''    // Drag anywhere on the control; never steal gestures from the guest view.
    // UIControl primary menu on tap and V72 long press still work unchanged.
    UIPanGestureRecognizer *nrgV73Drag = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(nrgV73DragFloatingOverflow:)];
    nrgV73Drag.maximumNumberOfTouches = 1;
    [overflow addGestureRecognizer:nrgV73Drag];
'''

CONSTRAINTS = '''    self.nrgV73FloatingLeading = [overflow.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor constant:8];
    self.nrgV73FloatingTop = [overflow.topAnchor constraintEqualToAnchor:self.view.topAnchor constant:160];
    [NSLayoutConstraint activateConstraints:@[
        self.nrgV73FloatingLeading,
        self.nrgV73FloatingTop,
        [overflow.widthAnchor constraintEqualToConstant:44],
        [overflow.heightAnchor constraintEqualToConstant:44]
    ]];'''

METHODS = r'''
// V73 positions are per orientation, independent of fixed top-right controls.
// Viewport geometry belongs to V70 and is never modified by this overlay.
- (NSString *)nrgV73PreferenceSuffix {
    return self.view.bounds.size.width > self.view.bounds.size.height ? @"landscape" : @"portrait";
}

- (CGFloat)nrgV73MinY {
    CGFloat top = MAX(self.view.safeAreaInsets.top, self.view.window.safeAreaInsets.top);
    return MAX(12.0, top + 12.0);
}

- (CGFloat)nrgV73MaxY {
    CGFloat bottom = MAX(self.view.safeAreaInsets.bottom, self.view.window.safeAreaInsets.bottom);
    return MAX([self nrgV73MinY], CGRectGetHeight(self.view.bounds) - bottom - 56.0);
}

- (CGFloat)nrgV73Clamp:(CGFloat)value minimum:(CGFloat)minimum maximum:(CGFloat)maximum {
    return MAX(minimum, MIN(value, maximum));
}

- (void)nrgV73RestoreFloatingPosition {
    if (!self.nrgWindowOverflow || !self.nrgV73FloatingTop || !self.nrgV73FloatingLeading) return;
    CGSize size = self.view.bounds.size;
    if (size.width <= 100 || size.height <= 100) return;
    UIEdgeInsets safe = self.view.safeAreaInsets;
    safe.top = MAX(safe.top, self.view.window.safeAreaInsets.top);
    safe.bottom = MAX(safe.bottom, self.view.window.safeAreaInsets.bottom);
    if (CGSizeEqualToSize(size, self.nrgV73LastSize) &&
        UIEdgeInsetsEqualToEdgeInsets(safe, self.nrgV73LastSafeArea)) return;
    self.nrgV73LastSize = size;
    self.nrgV73LastSafeArea = safe;
    NSString *suffix = [self nrgV73PreferenceSuffix];
    NSUserDefaults *prefs = NSUserDefaults.lcUserDefaults;
    NSString *fractionKey = [@"NRGV73GuestOverflowFraction." stringByAppendingString:suffix];
    NSString *sideKey = [@"NRGV73GuestOverflowRight." stringByAppendingString:suffix];
    id stored = [prefs objectForKey:fractionKey];
    // First launch sits near the LEFT MIDDLE of the viewport, never over the
    // typical top-right in-app nav/search/actions. Users choose final location.
    CGFloat fraction = [stored isKindOfClass:NSNumber.class] ? [stored doubleValue] : 0.60;
    fraction = [self nrgV73Clamp:fraction minimum:0 maximum:1];
    CGFloat start = [self nrgV73MinY];
    CGFloat end = [self nrgV73MaxY];
    self.nrgV73FloatingTop.constant = start + (end - start) * fraction;
    BOOL onRight = [prefs boolForKey:sideKey];
    self.nrgV73FloatingLeading.constant = onRight ? MAX(8.0, size.width - 52.0) : 8.0;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    [self nrgV73RestoreFloatingPosition];
}

- (void)nrgV73DragFloatingOverflow:(UIPanGestureRecognizer *)pan {
    if (!self.nrgWindowOverflow || !self.nrgWindowOverflow.window) return;
    if (pan.state == UIGestureRecognizerStateBegan) {
        [self.nrgWindowOverflow.layer removeAllAnimations];
    }
    if (pan.state == UIGestureRecognizerStateChanged) {
        CGPoint delta = [pan translationInView:self.view];
        CGFloat maxX = MAX(8.0, CGRectGetWidth(self.view.bounds) - 52.0);
        self.nrgV73FloatingLeading.constant = [self nrgV73Clamp:self.nrgV73FloatingLeading.constant + delta.x
                                                           minimum:8.0 maximum:maxX];
        self.nrgV73FloatingTop.constant = [self nrgV73Clamp:self.nrgV73FloatingTop.constant + delta.y
                                                       minimum:[self nrgV73MinY] maximum:[self nrgV73MaxY]];
        [pan setTranslation:CGPointZero inView:self.view];
        return;
    }
    if (pan.state == UIGestureRecognizerStateEnded || pan.state == UIGestureRecognizerStateCancelled) {
        CGFloat maxX = MAX(8.0, CGRectGetWidth(self.view.bounds) - 52.0);
        BOOL right = self.nrgV73FloatingLeading.constant > (8.0 + maxX) / 2.0;
        NSString *suffix = [self nrgV73PreferenceSuffix];
        CGFloat minY = [self nrgV73MinY];
        CGFloat maxY = [self nrgV73MaxY];
        CGFloat fraction = maxY > minY ? (self.nrgV73FloatingTop.constant - minY) / (maxY - minY) : 0.60;
        NSUserDefaults *prefs = NSUserDefaults.lcUserDefaults;
        [prefs setBool:right forKey:[@"NRGV73GuestOverflowRight." stringByAppendingString:suffix]];
        [prefs setDouble:[self nrgV73Clamp:fraction minimum:0 maximum:1]
                  forKey:[@"NRGV73GuestOverflowFraction." stringByAppendingString:suffix]];
        [UIView animateWithDuration:0.32 delay:0 usingSpringWithDamping:0.82
              initialSpringVelocity:0 options:UIViewAnimationOptionAllowUserInteraction animations:^{
            self.nrgV73FloatingLeading.constant = right ? maxX : 8.0;
            [self.view layoutIfNeeded];
        } completion:nil];
        UISelectionFeedbackGenerator *feedback = [[UISelectionFeedbackGenerator alloc] init];
        [feedback selectionChanged];
        NSLog(@"[NRG_V73_FLOATING] moved=1 orientation=%@ edge=%@", suffix, right ? @"right" : @"left");
    }
}

'''

def one(src, old, new, label):
    count=src.count(old)
    if count != 1:raise RuntimeError(f'V73 {label}: expected one anchor, got {count}')
    return src.replace(old,new,1)


def patch(src):
    if MARK in src:
        for marker in ("nrgV73DragFloatingOverflow:","UIBlurEffectStyleSystemThinMaterial",
                       "nrgV73RestoreFloatingPosition","UIAccessibility",):
            if marker == "UIAccessibility":continue
            if marker not in src:raise RuntimeError('V73 partial patch: '+marker)
        if 'overflow.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-8' in src:
            raise RuntimeError('V73 still fixed in top-right')
        return src
    for previous in ('NRG_V37_WINDOW_ONLY_OVERFLOW','NRG_V72_OVERFLOW_LONGPRESS'):
        if previous not in src: raise RuntimeError('V73 prerequisite missing: '+previous)
    src=one(src,'@property(nonatomic, strong) UIButton *nrgWindowOverflow; // NRG_V37_WINDOW_ONLY_OVERFLOW',
            '@property(nonatomic, strong) UIButton *nrgWindowOverflow; // NRG_V37_WINDOW_ONLY_OVERFLOW\n'+PROPERTY,
            'private position constraints')
    old='''    overflow.tintColor = UIColor.labelColor;
    overflow.backgroundColor = [UIColor.secondarySystemBackgroundColor colorWithAlphaComponent:0.88];
    overflow.layer.cornerRadius = 17;
    overflow.accessibilityLabel = @"Window controls";
'''
    src=one(src,old,MATERIAL,'system material circle')
    anchor='''    [overflow addGestureRecognizer:nrgV72Hold];
'''
    src=one(src,anchor,anchor+GESTURE,'pan follows long-press')
    old='''    [NSLayoutConstraint activateConstraints:@[
        [overflow.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-8],
        [overflow.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:6],
        [overflow.widthAnchor constraintEqualToConstant:34],
        [overflow.heightAnchor constraintEqualToConstant:34]
    ]];'''
    src=one(src,old,CONSTRAINTS,'remove fixed top-right constraints')
    src=one(src,'- (void)nrgV72WindowOverflowLongPress:',METHODS+'- (void)nrgV72WindowOverflowLongPress:',
            'insert layout persistence and drag methods')
    if src.count(MARK)!=1:raise RuntimeError('V73 unexpected marker count')
    return src


def main(root):
    path=root/FILE
    old=path.read_text(encoding='utf-8')
    new=patch(old)
    if patch(new)!=new:raise RuntimeError('V73 not idempotent')
    if old!=new:path.write_text(new,encoding='utf-8')
    print('[PASS] V73 Apple system material, movable and edge snapping, portrait/landscape remembered, no 1-o’clock lock')

if __name__ == '__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v73_apple_floating_control.py <LiveContainer>')
    main(Path(sys.argv[1]))

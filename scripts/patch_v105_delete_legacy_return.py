#!/usr/bin/env python3
"""V105 destructive SOURCE migration of two obsolete guest control implementations.

Deletes LCReturnControl from the LiveProcess host and LCDirectReturnControl /
LCDirectReturnPresenter from bootstrap. Direct still receives exactly one
new Figma-aligned edge/morph control, with explicit user-confirmed restart;
LiveProcess only uses V73's host-owned morph. Never touches app data/signing.
"""
from pathlib import Path
import sys

SCENE = Path("MultitaskSupport/AppSceneViewController.m")
BOOT = Path("LiveContainer/LCBootstrap.m")
SCENE_MARK = "SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED"
BOOT_MARK = "SCARLET_V105_DIRECT_UNIFIED_MORPH"
BANNED = ("LCReturnControl", "lcReturnControl", "LCDirectReturnControl",
          "LCDirectReturnWindow", "LCDirectReturnPresenter",
          "LCReturnAxisCenter", "LCReturnShouldHide",
          "LCGuestReturnStartsCollapsed", "LCGuestReturnCustomColors")

DIRECT_CODE = r'''
// SCARLET_V105_DIRECT_UNIFIED_MORPH: Figma 17:2 / 17:50 single control.
// This presenter exists ONLY for a Classic/Direct guest; never LiveProcess.
// The former Direct overlay and its runtime creation path were deleted.
@interface SCGuestMorphWindow : UIWindow
@end
@implementation SCGuestMorphWindow
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return (hit == self || hit == self.rootViewController.view) ? nil : hit;
}
@end

@interface SCGuestMorphPresenter : NSObject
@property(nonatomic, strong) NSMutableDictionary<NSString *, SCGuestMorphWindow *> *windows;
@end
@implementation SCGuestMorphPresenter
- (instancetype)init {
    if (!(self = [super init])) return nil;
    self.windows = [NSMutableDictionary new];
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    [center addObserver:self selector:@selector(show:) name:UIWindowDidBecomeVisibleNotification object:nil];
    [center addObserver:self selector:@selector(show:) name:UISceneDidActivateNotification object:nil];
    [center addObserver:self selector:@selector(disconnect:) name:UISceneDidDisconnectNotification object:nil];
    return self;
}
- (void)dealloc { [NSNotificationCenter.defaultCenter removeObserver:self]; }
- (void)show:(NSNotification *)notice {
    if (!NSThread.isMainThread) {
        dispatch_async(dispatch_get_main_queue(), ^{ [self show:notice]; });
        return;
    }
    UIWindowScene *scene = nil;
    if ([notice.object isKindOfClass:UIWindow.class]) {
        UIWindow *candidate = notice.object;
        if (candidate.windowLevel != UIWindowLevelNormal) return;
        scene = candidate.windowScene;
    } else if ([notice.object isKindOfClass:UIWindowScene.class]) {
        scene = notice.object;
    }
    if (!scene || ![scene.session.role isEqualToString:UIWindowSceneSessionRoleApplication]) return;
    NSString *idKey = scene.session.persistentIdentifier;
    if (self.windows[idKey]) return;
    SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];
    UIViewController *vc = [UIViewController new];
    window.rootViewController = vc;
    vc.view.backgroundColor = UIColor.clearColor;
    window.backgroundColor = UIColor.clearColor;
    window.windowLevel = UIWindowLevelAlert + 1;
    UIButton *handle = [UIButton buttonWithType:UIButtonTypeSystem];
    handle.accessibilityIdentifier = @"scarlet.v105.direct.morph";
    handle.accessibilityLabel = @"Scarlet Crystal controls";
    handle.frame = CGRectMake(MAX(16, CGRectGetWidth(window.bounds)-64),
                              MAX(90, CGRectGetMidY(window.bounds)-24), 48, 48);
    NSArray *savedPosition = [NSUserDefaults.lcSharedDefaults arrayForKey:@"SCGuestMorphPositionV105"];
    if (savedPosition.count == 2 &&
        [savedPosition[0] isKindOfClass:NSNumber.class] &&
        [savedPosition[1] isKindOfClass:NSNumber.class]) {
        CGFloat edge = [savedPosition[0] doubleValue] < 0.5 ? 0 : 1;
        CGFloat yFraction = [savedPosition[1] doubleValue];
        if (isfinite(yFraction) && yFraction >= 0 && yFraction <= 1) {
            handle.center = CGPointMake(edge == 0 ? 24 : window.bounds.size.width-24,
                MAX(66, MIN(window.bounds.size.height-35, window.bounds.size.height*yFraction)));
        }
    }
    handle.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin |
                              UIViewAutoresizingFlexibleTopMargin |
                              UIViewAutoresizingFlexibleBottomMargin;
    handle.backgroundColor = [UIColor colorWithRed:33/255.0 green:43/255.0 blue:57/255.0 alpha:1];
    handle.tintColor = UIColor.whiteColor;
    handle.layer.cornerRadius = 24;
    handle.layer.borderWidth = 1;
    handle.layer.borderColor = [UIColor colorWithRed:58/255.0 green:70/255.0 blue:88/255.0 alpha:1].CGColor;
    [handle setImage:[UIImage systemImageNamed:@"chevron.up"] forState:UIControlStateNormal];
    [handle addTarget:self action:@selector(expand:) forControlEvents:UIControlEventTouchUpInside];
    UIPanGestureRecognizer *drag = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(dragHandle:)];
    [handle addGestureRecognizer:drag];
    UILongPressGestureRecognizer *hold = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(openOnHold:)];
    hold.minimumPressDuration = .55;
    [handle addGestureRecognizer:hold];
    [vc.view addSubview:handle];
    self.windows[idKey] = window;
    window.hidden = NO;  // never become key, never interrupt the guest keyboard
    NSLog(@"[SCARLET_V105_CONTROL] mode=direct owner=unified_morph count=1");
}
- (void)openOnHold:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan) return;
    [self expand:(UIButton *)gesture.view];
}
- (void)dragHandle:(UIPanGestureRecognizer *)gesture {
    UIView *button = gesture.view;
    UIView *container = button.superview;
    if (!container || [container viewWithTag:10501]) return;
    CGPoint delta = [gesture translationInView:container];
    CGFloat horizontal = MAX(16, MIN(container.bounds.size.width-16, button.center.x+delta.x));
    CGFloat vertical = MAX(66, MIN(container.bounds.size.height-35, button.center.y+delta.y));
    button.center = CGPointMake(horizontal, vertical);
    [gesture setTranslation:CGPointZero inView:container];
    if (gesture.state == UIGestureRecognizerStateEnded ||
        gesture.state == UIGestureRecognizerStateCancelled) {
        CGFloat edge = horizontal < CGRectGetMidX(container.bounds) ? 24 : container.bounds.size.width-24;
        [UIView animateWithDuration:.18 animations:^{ button.center = CGPointMake(edge, vertical); }];
        // Retain only position, never restore the removed legacy button.
        if (container.bounds.size.height > 100)
            [NSUserDefaults.lcSharedDefaults setObject:@[@(horizontal < CGRectGetMidX(container.bounds) ? 0 : 1),
                      @(vertical/container.bounds.size.height)] forKey:@"SCGuestMorphPositionV105"];
    }
}
- (void)expand:(UIButton *)button {
    UIView *root = button.superview;
    if (!root || [root viewWithTag:10501]) return;
    // The tap target occupies the original button; it is not visible while
    // expanded. Empty-space taps fold the same panel without launching apps.
    UIButton *scrim = [UIButton buttonWithType:UIButtonTypeCustom];
    scrim.tag = 10501;
    scrim.frame = root.bounds;
    scrim.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    scrim.backgroundColor = [UIColor colorWithWhite:0 alpha:.67];
    [scrim addTarget:self action:@selector(collapse:) forControlEvents:UIControlEventTouchUpInside];
    [root addSubview:scrim];

    CGFloat width = MIN(342, MAX(260, root.bounds.size.width - 48));
    UIView *card = [[UIView alloc] initWithFrame:CGRectMake((root.bounds.size.width-width)/2,
                 MAX(80, (root.bounds.size.height-206)/2), width, 206)];
    card.tag = 10502;
    card.backgroundColor = [UIColor colorWithRed:33/255.0 green:43/255.0 blue:57/255.0 alpha:1];
    card.layer.cornerRadius = 28;
    card.layer.borderWidth = 1;
    card.layer.borderColor = [UIColor colorWithRed:58/255.0 green:70/255.0 blue:88/255.0 alpha:1].CGColor;
    card.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin |
                            UIViewAutoresizingFlexibleRightMargin |
                            UIViewAutoresizingFlexibleTopMargin |
                            UIViewAutoresizingFlexibleBottomMargin;
    [root addSubview:card];

    UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(18, 17, width-36, 30)];
    title.text = @"Scarlet Crystal · Direct";
    title.font = [UIFont systemFontOfSize:18 weight:UIFontWeightBold];
    title.textColor = UIColor.whiteColor;
    title.textAlignment = NSTextAlignmentCenter;
    [card addSubview:title];
    UILabel *note = [[UILabel alloc] initWithFrame:CGRectMake(18, 56, width-36, 58)];
    note.text = @"이 앱은 홍수정 프로세스에서 실행 중이야.\n복귀하면 앱이 다시 시작되고 미저장 진행 상황이 사라질 수 있어.";
    note.numberOfLines = 3;
    note.textAlignment = NSTextAlignmentCenter;
    note.font = [UIFont systemFontOfSize:13 weight:UIFontWeightMedium];
    note.textColor = [UIColor colorWithRed:166/255.0 green:180/255.0 blue:200/255.0 alpha:1];
    [card addSubview:note];
    UIButton *returnButton = [UIButton buttonWithType:UIButtonTypeSystem];
    returnButton.frame = CGRectMake(18, 128, width-36, 44);
    returnButton.layer.cornerRadius = 16;
    returnButton.backgroundColor = [UIColor colorWithRed:241/255.0 green:76/255.0 blue:112/255.0 alpha:1];
    [returnButton setTitle:@"재시작 후 홍수정으로 복귀" forState:UIControlStateNormal];
    [returnButton setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [returnButton addTarget:self action:@selector(confirmRestart:) forControlEvents:UIControlEventTouchUpInside];
    [card addSubview:returnButton];
    UIButton *cancel = [UIButton buttonWithType:UIButtonTypeSystem];
    cancel.frame = CGRectMake(18, 174, width-36, 28);
    [cancel setTitle:@"취소 · 게임 유지" forState:UIControlStateNormal];
    [cancel setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [cancel addTarget:self action:@selector(collapse:) forControlEvents:UIControlEventTouchUpInside];
    [card addSubview:cancel];
    button.hidden = YES;
    scrim.alpha = 0;
    card.alpha = 0;
    card.transform = CGAffineTransformMakeScale(.88, .88);
    [UIView animateWithDuration:.23 delay:0 usingSpringWithDamping:.86
          initialSpringVelocity:0 options:UIViewAnimationOptionAllowUserInteraction animations:^{
        scrim.alpha = 1; card.alpha = 1; card.transform = CGAffineTransformIdentity;
    } completion:nil];
}
- (void)collapse:(UIView *)sender {
    UIView *root = sender;
    while (root.superview && ![root isKindOfClass:UIWindow.class]) root = root.superview;
    if ([root isKindOfClass:UIWindow.class]) root = ((UIWindow *)root).rootViewController.view;
    UIView *scrim = [root viewWithTag:10501], *card = [root viewWithTag:10502];
    [UIView animateWithDuration:.16 animations:^{
        scrim.alpha = 0; card.alpha = 0; card.transform = CGAffineTransformMakeScale(.92, .92);
    } completion:^(__unused BOOL finished) {
        [card removeFromSuperview]; [scrim removeFromSuperview];
        for (UIView *child in root.subviews) {
            if ([child isKindOfClass:UIButton.class] && child != scrim) child.hidden = NO;
        }
    }];
}
- (void)confirmRestart:(UIButton *)button {
    // This is an explicit destructive confirmation; no credentials or saved
    // guest container data are deleted. Direct process must restart to exit.
    NSLog(@"[SCARLET_V105_CONTROL] mode=direct confirmation=accepted");
    [LCSharedUtils launchToGuestAppWithClassicMode:0];
}
- (void)disconnect:(NSNotification *)notice {
    if ([notice.object isKindOfClass:UIWindowScene.class]) {
        [self.windows removeObjectForKey:((UIWindowScene *)notice.object).session.persistentIdentifier];
    }
}
@end
static SCGuestMorphPresenter *scGuestMorphPresenter;
'''

def section(s, a, b, replacement, name):
    if s.count(a) != 1 or s.count(b) != 1 or s.index(a) >= s.index(b):
        raise ValueError(f"V105 unexpected {name}: {s.count(a)}/{s.count(b)}")
    return s[:s.index(a)] + replacement + s[s.index(b):]

def native(src):
    if SCENE_MARK in src:
        if src.count(SCENE_MARK)!=1:raise ValueError("V105 native partial")
        if any(t in src for t in BANNED):raise ValueError("V105 native retained legacy symbols")
        return src
    for mark in ("SCARLET_V103_SINGLE_CONTROL_OWNER", "SCARLET_V102_NATIVE_GESTURE_CLEANUP"):
        if mark not in src:raise ValueError(f"V105 missing previous native stage {mark}")
    # Delete entire legacy class, helper functions, and Objective-C property;
    # no runtime removeFromSuperview/hide patching.
    src=section(src,"static double LCReturnAxisCenter(",
                "@interface AppSceneViewController()\n@property(nonatomic, strong) LCReturnControl *lcReturnControl;",
                f"// {SCENE_MARK}\n\n",
                "legacy class and helpers")
    src=src.replace("@property(nonatomic, strong) LCReturnControl *lcReturnControl;\n", "", 1)
    src=section(src,"- (void)viewDidLayoutSubviews {",
                "- (instancetype)initWithBundleId:", "", "legacy callbacks and return button setup")
    src=src.replace("    self.lcReturnControl.hidden = YES;\n    [self.lcReturnControl removeFromSuperview];\n","")
    if any(t in src for t in BANNED):raise ValueError("V105 native cleanup incomplete")
    return src

def direct(src):
    if BOOT_MARK in src:
        if src.count(BOOT_MARK)!=1:raise ValueError("V105 direct partial")
        if any(t in src for t in BANNED):raise ValueError("V105 direct retained legacy symbol")
        return src
    if "LCDirectReturnPresenter" not in src:
        raise ValueError("V105 needs V90 direct consent runtime")
    if "static double LCReturnAxisCenter(" in src:
        src=section(src,"static double LCReturnAxisCenter(", "// LC_GUEST_RETURN_V3:",
                    "", "direct return geometry helpers")
    src=section(src,"// LC_GUEST_RETURN_V3:", "extern char **environ;",
                DIRECT_CODE+"\n", "old direct return implementation")
    src=src.replace("lcDirectReturnPresenter = [LCDirectReturnPresenter new];",
                    "scGuestMorphPresenter = [SCGuestMorphPresenter new];")
    if "scGuestMorphPresenter = [SCGuestMorphPresenter new];" not in src:
        raise ValueError("missing direct escape initialization")
    if any(t in src for t in BANNED):raise ValueError("V105 direct cleanup incomplete")
    return src

def apply(root):
    files=(root/SCENE,root/BOOT)
    if any(not f.is_file() or f.is_symlink() for f in files):
        raise ValueError("V105 pinned guest source absent")
    old=[p.read_text(encoding="utf-8") for p in files]
    new=[fn(s) for fn,s in zip((native,direct),old)]
    if any(fn(s)!=s for fn,s in zip((native,direct),new)):
        raise ValueError("V105 non-idempotent")
    for p,a,b in zip(files,old,new):
        if a != b:p.write_text(b,encoding="utf-8")
    print("[PASS] V105 deleted both obsolete controls, one Figma-based direct morph remains")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v105_delete_legacy_return.py <LiveContainer>")
    apply(Path(sys.argv[1]))

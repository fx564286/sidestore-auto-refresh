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
// SCARLET_V105_DIRECT_UNIFIED_MORPH: retain the smallest scene entry point.
// SCARLET_V112_SHARED_GUEST_UI: the actual guest picker/panel is owned only
// by MultitaskDockManager.nrgV72PresentGuestSwitcher in Swift. Direct does
// NOT implement its own alert/card/rows or compete with the shared picker.
#include <objc/message.h>
@interface SCGuestMorphWindow : UIWindow
@end
@implementation SCGuestMorphWindow
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return (hit == self || hit == self.rootViewController.view) ? nil : hit;
}
@end

@interface SCGuestMorphController : UIViewController
@end
@implementation SCGuestMorphController
- (void)nrgV112RestartDirectGuest {
    // A row explicitly labeled "restart" is the one user-confirmed escape.
    // Never close or overwrite a guest container silently.
    NSLog(@"[SCARLET_V105_CONTROL] mode=direct confirmation=accepted route=shared_guest_picker");
    [LCSharedUtils launchToGuestAppWithClassicMode:0];
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
    // SCARLET_V128_DIRECT_SCENE_RECOVERY: subscribe AND reconcile existing scenes.
    // Some guests finish scene activation before this presenter is initialized.
    dispatch_async(dispatch_get_main_queue(), ^{
        for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
            if (![candidate isKindOfClass:UIWindowScene.class]) continue;
            UIWindowScene *active = (UIWindowScene *)candidate;
            if (active.activationState != UISceneActivationStateForegroundActive) continue;
            [self show:[NSNotification notificationWithName:UISceneDidActivateNotification object:active]];
        }
    });
    return self;
}
- (void)dealloc { [NSNotificationCenter.defaultCenter removeObserver:self]; }
- (BOOL)containsVirtualHandle:(UIView *)view {
    if ([view.accessibilityIdentifier isEqualToString:@"scarlet.v103.virtual.guest.control"]) return YES;
    for (UIView *child in view.subviews) {
        if ([self containsVirtualHandle:child]) return YES;
    }
    return NO;
}
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
    // SCARLET_V128_NO_DUPLICATE_LIVE_CONTROL: decorated scenes own their V73.
    for (UIWindow *candidate in scene.windows) {
        if ([self containsVirtualHandle:candidate]) return;
    }
    NSString *idKey = scene.session.persistentIdentifier;
    if (scene.activationState != UISceneActivationStateForegroundActive) return;
    SCGuestMorphWindow *existing = self.windows[idKey];
    if (existing && existing.windowScene == scene) {
        if (existing.isHidden) existing.hidden = NO;
        return;
    }
    if (existing) [self.windows removeObjectForKey:idKey];
    SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];
    SCGuestMorphController *vc = [SCGuestMorphController new];
    window.rootViewController = vc;
    vc.view.backgroundColor = UIColor.clearColor;
    window.backgroundColor = UIColor.clearColor;
    window.windowLevel = UIWindowLevelAlert + 1;

    // Visually identical native thin-material ellipsis entry control.
    // This host-controlled entry point is the only extra Direct UI;
    // the popup itself is rendered by the existing shared Swift picker.
    UIButton *handle = [UIButton buttonWithType:UIButtonTypeSystem];
    handle.accessibilityIdentifier = @"scarlet.v105.direct.morph";
    handle.accessibilityLabel = @"Scarlet Crystal guest switching";
    handle.accessibilityHint = @"Tap to open the shared guest controls. Drag to move.";
    // Default to the right edge; respect the user's saved drag position.
    handle.frame = CGRectMake(MAX(8, CGRectGetWidth(window.bounds)-52),
                              MAX(66, CGRectGetMidY(window.bounds)-22), 44, 44);
    NSArray *savedPosition = [NSUserDefaults.lcSharedDefaults arrayForKey:@"SCGuestMorphPositionV105"];
    if (savedPosition.count == 2 &&
        [savedPosition[0] isKindOfClass:NSNumber.class] &&
        [savedPosition[1] isKindOfClass:NSNumber.class]) {
        CGFloat right = [savedPosition[0] doubleValue] >= 0.5;
        CGFloat yFraction = [savedPosition[1] doubleValue];
        if (isfinite(yFraction) && yFraction >= 0 && yFraction <= 1) {
            handle.center = CGPointMake(right ? window.bounds.size.width-22 : 22,
                MAX(66, MIN(window.bounds.size.height-35, window.bounds.size.height*yFraction)));
        }
    }
    handle.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin |
                              UIViewAutoresizingFlexibleTopMargin |
                              UIViewAutoresizingFlexibleBottomMargin;
    [handle setImage:[UIImage systemImageNamed:@"ellipsis"] forState:UIControlStateNormal];
    handle.tintColor = UIColor.labelColor;
    handle.backgroundColor = UIColor.clearColor;
    handle.layer.cornerRadius = 22;
    handle.clipsToBounds = YES;
    // SCARLET_V128_DIRECT_NATIVE_GLASS: native UI material needs no JIT.
    UIVisualEffect *effect = [UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemThinMaterial];
    if (@available(iOS 26.0, *)) {
        if (!UIAccessibilityIsReduceTransparencyEnabled()) {
            effect = [[UIGlassEffect alloc] init];
        }
    }
    UIVisualEffectView *material = [[UIVisualEffectView alloc] initWithEffect:effect];
    material.userInteractionEnabled = NO;
    material.frame = handle.bounds;
    material.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [handle insertSubview:material atIndex:0];
    [handle addTarget:self action:@selector(openShared:) forControlEvents:UIControlEventTouchUpInside];
    UIPanGestureRecognizer *drag = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(dragHandle:)];
    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];
    self.windows[idKey] = window;
    window.hidden = NO; // never become key, never interrupt the guest keyboard
    NSLog(@"[SCARLET_V112_UI] mode=direct renderer=common_morph trigger=native_glass_ellipsis");
}
- (void)dragHandle:(UIPanGestureRecognizer *)gesture {
    UIView *button = gesture.view;
    UIView *container = button.superview;
    if (!container) return;
    CGPoint delta = [gesture translationInView:container];
    CGFloat x = MAX(22, MIN(container.bounds.size.width-22, button.center.x+delta.x));
    CGFloat y = MAX(66, MIN(container.bounds.size.height-35, button.center.y+delta.y));
    button.center = CGPointMake(x, y);
    [gesture setTranslation:CGPointZero inView:container];
    if (gesture.state == UIGestureRecognizerStateEnded ||
        gesture.state == UIGestureRecognizerStateCancelled) {
        BOOL right = x >= CGRectGetMidX(container.bounds);
        CGFloat edge = right ? container.bounds.size.width-22 : 22;
        [UIView animateWithDuration:.18 animations:^{ button.center = CGPointMake(edge, y); }];
        if (container.bounds.size.height > 100)
            [NSUserDefaults.lcSharedDefaults setObject:@[@(right ? 1 : 0),
                @(y/container.bounds.size.height)] forKey:@"SCGuestMorphPositionV105"];
    }
}
- (void)openShared:(UIButton *)sourceView {
    // SCARLET_V114_DIRECT_PICKER_REPAIR: a visible control must not become
    // inert when UIKit launches a Classic guest before its Swift bridge is
    // registered. Resolve the existing shared framework once on demand.
    UIWindow *sourceWindow = sourceView.window;
    UIViewController *controller = sourceWindow.rootViewController;
    if (!controller || !sourceView.superview) {
        NSLog(@"[SCARLET_V114_UI] tap=1 result=detached_control");
        return;
    }
    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");
    SEL route = NSSelectorFromString(@"presentFrom:sourceView:");
    Class bridge = NSClassFromString(@"SCUnifiedGuestUIBridge");
    if (!bridge || ![bridge respondsToSelector:route]) {
        NSMutableArray<NSString *> *frameworkDirectories = [NSMutableArray array];
        NSString *primary = NSBundle.mainBundle.privateFrameworksPath;
        if (primary.length) [frameworkDirectories addObject:primary];
        NSBundle *host = [NSBundle bundleForClass:LCSharedUtils.class];
        NSString *hostParent = [host.bundlePath stringByDeletingLastPathComponent];
        if (hostParent.length && ![frameworkDirectories containsObject:hostParent]) {
            [frameworkDirectories addObject:hostParent];
        }
        for (NSString *directory in frameworkDirectories) {
            NSString *candidate = [[directory stringByAppendingPathComponent:@"LiveContainerSwiftUI.framework"]
                stringByStandardizingPath];
            NSBundle *framework = [NSBundle bundleWithPath:candidate];
            if (!framework) continue;
            NSError *loadError = nil;
            BOOL loaded = [framework loadAndReturnError:&loadError];
            NSLog(@"[SCARLET_V114_UI] framework_loaded=%d error_code=%ld",
                  loaded ? 1 : 0, (long)(loadError ? loadError.code : 0));
            bridge = NSClassFromString(@"SCUnifiedGuestUIBridge");
            if (bridge && [bridge respondsToSelector:route]) break;
        }
    }
    if (bridge && [bridge respondsToSelector:route]) {
        NSLog(@"[SCARLET_V114_UI] common_router=bridge");
        ((void (*)(id, SEL, UIViewController *, UIView *))objc_msgSend)(
            bridge, route, controller, sourceView);
        return;
    }
    // MultitaskDockManager already owns the same picker; call it directly
    // when the extra bridge class is unavailable. No duplicate panel/UI.
    Class managerClass = NSClassFromString(@"MultitaskDockManager");
    if (!managerClass) {
        // Swift @objc classes may be module-qualified unless explicitly
        // renamed, unlike the SCUnifiedGuestUIBridge above.
        managerClass = NSClassFromString(@"LiveContainerSwiftUI.MultitaskDockManager");
    }
    SEL getShared = NSSelectorFromString(@"shared");
    SEL present = NSSelectorFromString(@"nrgV112PresentDirectGuestUIFrom:sourceView:");
    if (managerClass && [managerClass respondsToSelector:getShared]) {
        id manager = ((id (*)(id, SEL))objc_msgSend)(managerClass, getShared);
        if (manager && [manager respondsToSelector:present]) {
            NSLog(@"[SCARLET_V114_UI] common_router=manager");
            ((void (*)(id, SEL, UIViewController *, UIView *))objc_msgSend)(
                manager, present, controller, sourceView);
            return;
        }
    }
    NSLog(@"[SCARLET_V114_UI] common_router_unavailable=1 framework_loaded=0");
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
    # SCARLET_V128_LIVEPROCESS_FALLBACK: add an escape handle for
    # non-decorated LiveProcess guests while avoiding duplicate V73 buttons.
    condition = "if (!isLiveProcess && !isSideStore) {"
    if src.count(condition) != 1:
        raise ValueError("V128 guest mode condition changed")
    src=src.replace(condition, "if (!isSideStore) {", 1)
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
    print("[PASS] V105 deleted both obsolete controls, one Direct morph owner remains")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v105_delete_legacy_return.py <LiveContainer>")
    apply(Path(sys.argv[1]))

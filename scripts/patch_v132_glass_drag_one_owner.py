#!/usr/bin/env python3
"""V132: continuous interactive Liquid Glass tab tracking and one guest handle.

Keep V131 panel and V130 transport unchanged. Do not add UIWindow/buttons.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
BOOT = Path("LiveContainer/LCBootstrap.m")
MARK = "SCARLET_V132_GLASS_DRAG"
OWNER = "SCARLET_V132_ONE_HANDLE"

def one(s: str, old: str, new: str, reason: str) -> str:
    n = s.count(old)
    if n != 1:
        raise ValueError(f"V132 {reason}: expected 1 anchor, saw {n}")
    return s.replace(old, new, 1)

TRACKER = '''// SCARLET_V132_GLASS_DRAG: the rim moves continuously under a finger,
// and the original UISegmentedControl remains the sole selection owner.
// No global hit-test interception, extra window, or guest JIT dependency.
@available(iOS 26.0, *)
private final class SCNativeGlassFingerTracker: NSObject {
    weak var picker: UISegmentedControl?
    weak var rim: SCNativeGlassRimView?
    private var lastIndex: Int = -1

    init(picker: UISegmentedControl, rim: SCNativeGlassRimView) {
        self.picker = picker
        self.rim = rim
        super.init()
        lastIndex = picker.selectedSegmentIndex
    }

    @objc func drag(_ pan: UIPanGestureRecognizer) {
        guard let picker, let rim, picker.numberOfSegments == 2,
              picker.bounds.width > 0 else { return }
        let point = pan.location(in: picker)
        let fraction = min(1, max(0, point.x / picker.bounds.width))
        switch pan.state {
        case .began, .changed:
            // Track physical finger position, not a final binary tap.
            rim.followFinger(fraction)
            let index = fraction < 0.5 ? 0 : 1
            if picker.isEnabledForSegment(at: index) && picker.selectedSegmentIndex != index {
                picker.selectedSegmentIndex = index
                picker.sendActions(for: .valueChanged)
                if lastIndex != index {
                    UISelectionFeedbackGenerator().selectionChanged()
                }
                lastIndex = index
                NSLog("[SCARLET_V132_GLASS_DRAG] event=changed selection=%ld", index)
            }
        case .ended, .cancelled, .failed:
            rim.select(picker.selectedSegmentIndex)
            NSLog("[SCARLET_V132_GLASS_DRAG] event=settled selection=%ld", picker.selectedSegmentIndex)
        default: break
        }
    }
}

'''

def dock_patch(s: str) -> str:
    if MARK in s:
        if s.count("private final class SCNativeGlassFingerTracker") != 1:
            raise ValueError("V132 duplicated tracker definition")
        return s
    for token in ("SCARLET_V131_REFERENCE_LIQUID_GLASS",
                  "SCARLET_V131_VISIBLE_GLASS_ACTIVATION",
                  "SCARLET_V129_PICKER_RESILIENCE"):
        if token not in s: raise ValueError("V132 missing prerequisite: "+token)
    # Preserve reduction of motion: disabling animation does not disable
    # direct location feedback while the user's finger is touching.
    s=one(s, '''    func select(_ index: Int) {
        guard !UIAccessibility.isReduceMotionEnabled else { return }''',
    '''    func followFinger(_ fraction: CGFloat) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        highlight.startPoint = CGPoint(x: min(0.85, max(0.15, fraction)), y: 0)
        CATransaction.commit()
    }

    func select(_ index: Int) {
        guard !UIAccessibility.isReduceMotionEnabled else { return }''',
    "continuous optical tracking")
    s=one(s, '''        let heading = UILabel()''', TRACKER + '''        let heading = UILabel()''', "tracker class")
    # Tracker must be a top-level class, NOT nested within an instance method.
    # Pull tracker source to top-level after RIM class ends, before main public manager.
    s=s.replace(TRACKER+"        let heading = UILabel()", "        let heading = UILabel()",1)
    begin=s.index("private final class SCNativeGlassRimView: UIView")
    after=s.index("\n}\n",begin)+3
    s=s[:after]+"\n"+TRACKER+s[after:]
    # Associate action object with the recognizer's retained target.
    # UIKit keeps its target, and the tracker only weakly owns its picker/rim.
    s=one(s,
'''            tabPicker.setBackgroundImage(UIImage(), for: .normal, barMetrics: .default)
        }

        let scroll = UIScrollView()''',
'''            tabPicker.setBackgroundImage(UIImage(), for: .normal, barMetrics: .default)
            let glassTracking = SCNativeGlassFingerTracker(picker: tabPicker, rim: tabRim)
            let glassPan = UIPanGestureRecognizer(target: glassTracking,
                                                   action: #selector(SCNativeGlassFingerTracker.drag(_:)))
            glassPan.minimumNumberOfTouches = 1
            glassPan.maximumNumberOfTouches = 1
            glassPan.cancelsTouchesInView = false
            // Retain tracker by an associated object on the owning control.
            objc_setAssociatedObject(tabPicker,
                UnsafeRawPointer(bitPattern: 0x132)!,
                glassTracking, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
            tabPicker.addGestureRecognizer(glassPan)
            NSLog("[SCARLET_V132_GLASS_DRAG] installed=1 touch_region=tabs")
        }

        let scroll = UIScrollView()''',
    "glass tab drag hook")
    s=one(s,"import Combine\n","import Combine\nimport ObjectiveC\n", "objc associated tracker import")
    return s

def boot_patch(s: str) -> str:
    if OWNER in s:
        if s.count(OWNER) < 3:
            raise ValueError("V132 partial one-owner application")
        return s
    if "SCARLET_V129_SINGLE_OWNER" not in s or "SCARLET_V105_DIRECT_UNIFIED_MORPH" not in s:
        raise ValueError("V132 missing fallback source")
    # Stronger source-side ownership over all visible foreground scenes,
    # not only the scene where the V73 ready notification happened.
    s=one(s,
'''- (void)virtualReady:(NSNotification *)notice {
    if (![NSThread isMainThread])''',
'''// SCARLET_V132_ONE_HANDLE: scanning all active scene windows matters when
// a guest app's fallback window was created before native V73 activation.
- (BOOL)nativeAvailableInForeground {
    for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
        if (![candidate isKindOfClass:UIWindowScene.class] ||
            candidate.activationState != UISceneActivationStateForegroundActive) continue;
        UIWindowScene *active = (UIWindowScene *)candidate;
        for (UIWindow *window in active.windows) {
            if ([self containsVirtualHandle:window]) return YES;
        }
    }
    return NO;
}
- (void)retireAllFallbacks:(NSString *)reason {
    for (SCGuestMorphWindow *window in self.windows.allValues) {
        window.hidden = YES;
    }
    [self.windows removeAllObjects];
    NSLog(@"[SCARLET_V132_ONE_HANDLE] fallback_retired_all=1 reason=%@",reason);
}
- (void)virtualReady:(NSNotification *)notice {
    if (![NSThread isMainThread])''',
    "all scenes owner check")
    s=one(s,
'''    UIWindowScene *scene = [notice.object isKindOfClass:UIWindowScene.class] ? notice.object : nil;
    if (!scene) return;
    // Verify the actual button, not just a speculative host notification.
    for (UIWindow *window in scene.windows) {
        if ([self containsVirtualHandle:window]) {
            [self retireFallbackInScene:scene reason:@"native_V73_ready"];
            return;
        }
    }
}''',
'''    // SCARLET_V132_ONE_HANDLE: never trust a speculative notification.
    // Cross-scene native handles also own the sole visible edge affordance.
    if ([self nativeAvailableInForeground])
        [self retireAllFallbacks:@"native_V73_ready"];
}''',
    "global retirement")
    s=one(s,
'''    // SCARLET_V129_SINGLE_OWNER: never keep the fallback after a visible
    // native V73 button attaches, regardless of UIKit event order.
    for (UIWindow *candidate in scene.windows) {
        if ([self containsVirtualHandle:candidate]) {
            [self retireFallbackInScene:scene reason:@"native_V73_exists"];
            return;
        }
    }''',
'''    // SCARLET_V132_ONE_HANDLE: V73 takes priority across all foreground
    // windows, not just the current startup window notification.
    if ([self nativeAvailableInForeground]) {
        [self retireAllFallbacks:@"native_exists_before_fallback"];
        return;
    }''',
    "never make fallback while native exists")
    # A second fallback for another foreground UIWindowScene must not survive.
    s=one(s,
'''    SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];''',
'''    // SCARLET_V132_ONE_HANDLE: a single fallback across foreground scenes.
    [self retireAllFallbacks:@"new_active_scene"];
    SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc] initWithWindowScene:scene];''',
    "one fallback window")
    # Avoid a race where fallback is created just before native appears.
    # V73 sends notification on layout; deferred check reconciles event order.
    s=one(s,
'''    window.hidden = NO; // never become key, never interrupt the guest keyboard
    NSLog(@"[SCARLET_V112_UI] mode=direct renderer=common_morph trigger=native_glass_ellipsis");''',
'''    window.hidden = NO; // never become key, never interrupt the guest keyboard
    // SCARLET_V132_ONE_HANDLE: reconcile delayed native V73 attachment.
    __weak typeof(self) weakPresenter = self;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.45*NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        if ([weakPresenter nativeAvailableInForeground]) {
            [weakPresenter retireAllFallbacks:@"deferred_native_attached"];
        }
    });
    NSLog(@"[SCARLET_V132_ONE_HANDLE] fallback_created=1");''',
    "race-safe deferred ownership")
    return s

def apply(root: Path):
    for rel,fn in ((DOCK,dock_patch),(BOOT,boot_patch)):
        p=root/rel
        if not p.is_file() or p.is_symlink(): raise ValueError("V132 missing source "+str(rel))
        original=p.read_text()
        transformed=fn(original)
        if fn(transformed)!=transformed: raise ValueError("V132 non-idempotent "+str(rel))
        if transformed!=original:p.write_text(transformed)
    print("[PASS] V132 native glass tracks finger; one guest handle per foreground process")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: script <LiveContainer root>")
    apply(Path(sys.argv[1]))

#!/usr/bin/env python3
"""V137: restore post-rotation touch geometry, visible single edge handle, contrastful glass.

Apply AFTER V136. Preserve JIT, signing, profile, keychain, guest container
storage, and previously saved placement preferences.
"""
from pathlib import Path
import sys

DECO=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
BOOT=Path("LiveContainer/LCBootstrap.m")
MARK="SCARLET_V137_TOUCH_SETTLE"
OWNER="SCARLET_V137_SCENE_OWNER"
GLASS="SCARLET_V137_REGULAR_GLASS"

def replace(s, old, new, why):
    n=s.count(old)
    if n!=1: raise ValueError(f"V137 {why}: expected unique anchor, got {n}")
    return s.replace(old,new,1)

def decorated(s):
    # V137 shared entry is now installed by patch_v137_single_glass_entry.py.
    # Do not patch V73 viewDidLayoutSubviews here: its entire button and
    # gesture implementation is deleted at source by the unified stage.
    for marker in ("SCARLET_V136_ROTATION_ATOMIC", "NRG_V73_APPLE_FLOATING_CONTROL"):
        if marker not in s:raise ValueError("V137 decorated prerequisite "+marker)
    return s


def dock(s):
    if GLASS in s:
        if s.count(GLASS)!=1: raise ValueError("V137 partial glass patch")
        return s
    for required in ("SCARLET_V131_VISIBLE_GLASS_ACTIVATION","SCARLET_V132_GLASS_DRAG","SCARLET_V136_ROTATION_ATOMIC"):
        if required not in s:raise ValueError("missing prerequisite "+required)
    # Under moving video .clear is almost invisible, irrespective of the rim;
    # Apple documents regular as the standard glass material for legibility.
    s=replace(s,'let glass = UIGlassEffect(style: .clear)',
       '''// SCARLET_V137_REGULAR_GLASS: standard native refraction,
                // dynamic system tint, not unbounded background transparency.
                let glass = UIGlassEffect(style: .regular)
                glass.tintColor = UIColor.systemBackground.withAlphaComponent(0.16)''',
       "regular system glass")
    s=replace(s,'''overlay.backgroundColor = UIColor.black.withAlphaComponent(0.08)''',
       '''overlay.backgroundColor = UIColor.black.withAlphaComponent(0.19)''',
       "dim content just enough for readable text")
    s=replace(s,'''tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.04)''',
       '''tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.12)''',
       "tab outline")
    s=replace(s,'''tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.26)''',
       '''tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.48)''',
       "stronger active segment")
    # Two regular rows and one action row are intentionally from one shared
    # UI routine; retained buttons remain actual UIControls (not inert layers).
    if s.count('item.backgroundColor = UIColor.white.withAlphaComponent(0.10)') != 3:
        raise ValueError("V137 expected three transparent row backings")
    s=s.replace('item.backgroundColor = UIColor.white.withAlphaComponent(0.10)',
                'item.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.56)')
    if s.count('item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor') != 3:
        raise ValueError("V137 expected three cell border treatments")
    s=s.replace('item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor',
                'item.layer.borderColor = UIColor.separator.withAlphaComponent(0.42).cgColor')
    return s

def boot(s):
    if OWNER in s:
        if s.count(OWNER)!=1:raise ValueError("V137 partial scene owner")
        return s
    for required in ("SCARLET_V132_ONE_HANDLE","SCARLET_V129_SINGLE_OWNER"):
        if required not in s:raise ValueError("missing prerequisite "+required)
    original='''- (BOOL)nativeAvailableInForeground {
    for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
        if (![candidate isKindOfClass:UIWindowScene.class] ||
            candidate.activationState != UISceneActivationStateForegroundActive) continue;
        UIWindowScene *active = (UIWindowScene *)candidate;
        for (UIWindow *window in active.windows) {
            if ([self containsVirtualHandle:window]) return YES;
        }
    }
    return NO;
}'''
    scoped='''// SCARLET_V137_SCENE_OWNER: only the same foreground scene may replace
// its fallback handle. Another guest's native handle must never suppress it.
- (BOOL)nativeAvailableInScene:(UIWindowScene *)scene {
    if (!scene || scene.activationState != UISceneActivationStateForegroundActive) return NO;
    for (UIWindow *window in scene.windows) {
        if (window.hidden || window.alpha < 0.05) continue;
        if ([self containsVirtualHandle:window]) return YES;
    }
    return NO;
}'''
    s=replace(s,original,scoped,"scope actual native handle to guest scene")
    # Keep the legacy cross-scene retirement method unused? No: remove it,
    # because hiding a fallback from an unrelated scene causes missing buttons.
    start=s.index('- (void)retireAllFallbacks:(NSString *)reason {')
    end=s.index('\n- (void)virtualReady:(NSNotification *)notice {',start)
    s=s[:start]+s[end+1:]
    s=replace(s,'''    // SCARLET_V132_ONE_HANDLE: never trust a speculative notification.
    // Cross-scene native handles also own the sole visible edge affordance.
    if ([self nativeAvailableInForeground])
        [self retireAllFallbacks:@"native_V73_ready"];''',
    '''    // Only this native scene can replace this scene's Direct fallback.
    UIWindowScene *scene = [notice.object isKindOfClass:UIWindowScene.class] ? notice.object : nil;
    if ([self nativeAvailableInScene:scene])
        [self retireFallbackInScene:scene reason:@"native_V73_ready"];''',
    "notification retains scene ownership")
    s=replace(s,'''    if ([self nativeAvailableInForeground]) {
        [self retireAllFallbacks:@"native_exists_before_fallback"];
        return;
    }''',
    '''    if ([self nativeAvailableInScene:scene]) {
        [self retireFallbackInScene:scene reason:@"native_exists_before_fallback"];
        return;
    }''',
    "no cross-guest suppression")
    s=replace(s,'''        if ([weakPresenter nativeAvailableInForeground]) {
            [weakPresenter retireAllFallbacks:@"deferred_native_attached"];
        }''',
    '''        if ([weakPresenter nativeAvailableInScene:scene]) {
            [weakPresenter retireFallbackInScene:scene reason:@"deferred_native_attached"];
        }''',
    "deferred on same scene")
    # This method already checks ancestors' hidden state. Also ensure a view
    # outside the final portrait bounds is not considered an on-screen handle.
    s=replace(s,'''        return view.userInteractionEnabled && view.window != nil;''',
    '''        return view.userInteractionEnabled && view.window != nil &&
            CGRectIntersectsRect([view convertRect:view.bounds toView:view.window],
                                 view.window.bounds);''',
    "offscreen native doesn't suppress fallback")
    return s

def apply(root):
    updates=[]
    for rel,fn in ((DECO,decorated),(DOCK,dock),(BOOT,boot)):
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError("V137 pinned source missing "+str(rel))
        old=p.read_text()
        new=fn(old)
        if fn(new)!=new:raise ValueError("V137 non-idempotent "+str(rel))
        updates.append((p,old,new))
    for p,old,new in updates:
        if old!=new:p.write_text(new)
    print("[PASS] V137 portrait layout settle / native regular glass / one scene handle")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v137_rotation_glass_owner.py <pinned LiveContainer root>")
    apply(Path(sys.argv[1]))

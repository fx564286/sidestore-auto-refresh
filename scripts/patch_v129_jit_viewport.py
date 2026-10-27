#!/usr/bin/env python3
"""V129: iOS 27 JIT handoff preflight, reliable shared picker, and per-guest viewport.

Applied after the V128/V127 final canonical patches; strictly fail-closed and
idempotent. Never alters user guest files, Apple IDs, signing or pairing state.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V129_JIT_VIEWPORT"
APP = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")
DECO = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
INFO = Path("LiveContainer/Info.plist")
UTIL = Path("LiveContainerSwiftUI/Utilities/LCUtilsExtensions.swift")

def replace_once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise ValueError(f"V129 {label}: expected one anchor, got {n}")
    return s.replace(old, new, 1)

def jit(s):
    if "SCARLET_V129_JIT_PREFLIGHT" in s:
        if s.count("SCARLET_V129_JIT_PREFLIGHT") != 1:
            raise ValueError("V129 JIT partial/duplicate")
        return s
    marker = '                if jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {'
    addition = '''                // SCARLET_V129_JIT_PREFLIGHT: normalize unsupported
                // StosDebug PID requests to the external StikDebug transport
                // on modern iOS, without changing the saved user preference.
                var effectiveEnabler = jitEnabler
                if #available(iOS 26.0, *),
                   jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {
                    effectiveEnabler = .StikJIT
                    NSLog("[SCARLET_V129_JIT] stage=preflight legacy_provider=stosdebug fallback=stikdebug")
                }
                if #available(iOS 26.0, *), (script?.isEmpty ?? true) {
                    // A15+/M2+ TXM may need a developer-provided JIT script.
                    // Absence of a script is not proof that all apps must fail.
                    NSLog("[SCARLET_V129_JIT] stage=preflight script=absent txm=unknown runtime_jit_unverified=1")
                }
'''
    s = replace_once(s, marker, addition + marker, "JIT helper preflight")
    helper_preflight = '''                if #available(iOS 26.0, *), effectiveEnabler == .StikJIT,
                   let helperURL = URL(string: "stikdebug://enable-jit"),
                   !UIApplication.shared.canOpenURL(helperURL) {
                    NSLog("[SCARLET_V129_JIT] stage=helper_check result=missing_stikdebug")
                    errorInfo = "StikDebug 앱이 발견되지 않았습니다. 공식 StikDebug를 설치하고 페어링·DDI·LocalDevVPN을 설정하세요."
                    errorShow = true
                    return
                }
'''
    s = replace_once(s, '                if jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {',
        helper_preflight + '                if effectiveEnabler == .StosDebug || effectiveEnabler == .StosDebugLC {',
        "modern transport or legacy routing")
    # Retarget subsequent branching and URL scheme to the actual selected
    # transport. The saved user preference remains unchanged.
    s = replace_once(s,
        '                components.scheme = jitEnabler == .StikJITLC ? "stikjit" : "stikdebug"',
        '                components.scheme = effectiveEnabler == .StikJITLC ? "stikjit" : "stikdebug"',
        "real helper URL scheme")
    s = replace_once(s,
        '                    if jitEnabler == .StikJITLC {',
        '                    if effectiveEnabler == .StikJITLC {',
        "actual embedded helper branch")
    s = replace_once(s,
        '                    if effectiveEnabler == .StikJITLC {\n                        if let app = sharedModel.apps.first(where: { app in',
        '                    if effectiveEnabler == .StikJITLC {\n                        NSLog("[SCARLET_V129_JIT] handoff=embedded_stikdebug pid=%d accepted=unverified", pid)\n                        if let app = sharedModel.apps.first(where: { app in',
        "embedded helper handoff proof")
    return s

def jit_classic(s):
    # Classic/JIT-on-host launch uses LCUtils.askForJIT, not the LiveProcess
    # PID method. Normalize modern iOS requests in BOTH call paths.
    marker = "SCARLET_V129_CLASSIC_JIT_ROUTE"
    if marker in s:
        return s
    begin = "    public static func askForJIT(withScript script:"
    start = s.index(begin)
    guard = '        if(jitEnabler == .SideJITServer){'
    a=s.index(guard,start)
    # Scope rewrite to this method only.
    b=s.find("\n    public static func ",a+len(guard))
    if b<0:
        b=len(s)
    section=s[a:b]
    if section.count('jitEnabler ==') != 10:
        raise ValueError(f"V129 classic JIT branch drift {section.count('jitEnabler ==')}")
    section=section.replace('jitEnabler ==','effectiveEnabler ==')
    preflight = '''        // SCARLET_V129_CLASSIC_JIT_ROUTE: reroute obsolete StosDebug
        // to current external StikDebug on modern iOS; never change the
        // saved selection or claim that opening its URL proves JIT.
        var effectiveEnabler = jitEnabler
        if #available(iOS 26.0, *),
           jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {
            effectiveEnabler = .StikJIT
            onServerMessage?("[SCARLET_V129_JIT] fallback=external_stikdebug classic=1")
        }
        if #available(iOS 26.0, *), effectiveEnabler == .StikJIT,
           let helperURL = URL(string: "stikdebug://enable-jit"),
           !UIApplication.shared.canOpenURL(helperURL) {
            onServerMessage?("StikDebug not installed: configure StikDebug pairing/DDI/LocalDevVPN.")
            return false
        }
'''
    return s[:a]+preflight+section+s[b:]


def decorated(s):
    if MARK in s:
        if s.count(MARK) != 1 or "nrgV129ToggleViewportMode" not in s:
            raise ValueError("V129 viewport partial")
        return s
    if "NRG_V64_PORTRAIT_TOUCH_FRAME" not in s:
        raise ValueError("V129 requires complete V128 fullscreen pipeline")
    # Only the final maximized-guest viewport changes; keep windowed and
    # landscape geometry, user gestures and guest registration unchanged.
    s = replace_once(
        s,
        '    if (portraitPhone) {\n        UIEdgeInsets physicalInsets = window.safeAreaInsets;',
        '''    // SCARLET_V129_JIT_VIEWPORT: each guest keeps its own touch-safe
    // or edge-to-edge mode. Safe mode stays the default to protect top actions.
    NSString *guestId = self.appSceneVC.bundleId ?: @"unknown";
    NSString *viewportKey = [@"ScarletGuestTouchSafe." stringByAppendingString:guestId];
    NSUserDefaults *prefs = NSUserDefaults.lcUserDefaults;
    id storedTouchSafe = [prefs objectForKey:viewportKey];
    BOOL touchSafe = storedTouchSafe == nil ? YES : [storedTouchSafe boolValue];
    if (portraitPhone) {
        UIEdgeInsets physicalInsets = window.safeAreaInsets;''',
        "guest viewport mode")
    s = replace_once(
        s,
        '''        physicalRect = UIEdgeInsetsInsetRect(physicalRect,
            UIEdgeInsetsMake(portraitTop, 0, 0, 0));
        settings.safeAreaInsetsPortrait = LCUIEdgeInsetsRotateToOrientation(
            UIEdgeInsetsMake(0, 0, portraitBottom, 0), orientation);''',
        '''        // The physical inset and scene metadata are mutually exclusive:
        // applying both to the top would make some guests half-size, while
        // applying neither would make other guests' top controls untouchable.
        physicalRect = UIEdgeInsetsInsetRect(physicalRect,
            UIEdgeInsetsMake(touchSafe ? portraitTop : 0, 0, 0, 0));
        settings.safeAreaInsetsPortrait = LCUIEdgeInsetsRotateToOrientation(
            UIEdgeInsetsMake(touchSafe ? 0 : portraitTop, 0, portraitBottom, 0), orientation);''',
        "one top inset authority")
    s = replace_once(s,
        '''    NSLog(@"[NRG_V58_VIEWPORT] orientation=%ld window=%.0fx%.0f guest=%.0fx%.0f full=1",''',
        '''    NSLog(@"[SCARLET_V129_VIEWPORT] mode=%@ touchSafe=%d physicalTop=%.1f viewport=%.0fx%.0f host=%.0fx%.0f",
          guestId, touchSafe ? 1 : 0, touchSafe ? portraitTop : 0,
          pixels.width, pixels.height, window.bounds.size.width, window.bounds.size.height);
    NSLog(@"[NRG_V58_VIEWPORT] orientation=%ld window=%.0fx%.0f guest=%.0fx%.0f full=1",''',
        "runtime viewport evidence")
    insert_at='- (void)updateWindowedFrameWithSettings:(UIMutableApplicationSceneSettings *)settings {'
    method='''// Allow the current guest to switch only its own saved viewport mode.
// This never resizes a windowed guest or erases any guest state.
- (void)nrgV129ToggleViewportMode {
    if (!self.isMaximized || !self.appSceneVC.isAppRunning) return;
    NSString *guestId = self.appSceneVC.bundleId ?: @"unknown";
    NSString *key = [@"ScarletGuestTouchSafe." stringByAppendingString:guestId];
    NSUserDefaults *prefs = NSUserDefaults.lcUserDefaults;
    id existing = [prefs objectForKey:key];
    BOOL current = existing == nil ? YES : [existing boolValue];
    [prefs setBool:!current forKey:key];
    [self.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
        [self updateMaximizedFrameWithSettings:settings];
    }];
    [self.view setNeedsLayout];
    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[SCARLET_V129_VIEWPORT] toggle=1 touchSafe=%d", !current ? 1 : 0);
}

'''
    s=replace_once(s,insert_at,method+insert_at,"viewport action selector")
    return s

def dock(s):
    if "SCARLET_V129_PICKER_RESILIENCE" in s:
        if s.count("SCARLET_V129_PICKER_RESILIENCE") != 2:
            raise ValueError("V129 picker partial")
        return s
    s=replace_once(
        s,
        '''              owner.windowScene?.activationState == .foregroundActive,
              (windowActions || controller.view.window != nil),
              sourceView.isHidden == false else {''',
        '''              // SCARLET_V129_PICKER_RESILIENCE: a guest's UIKit scene
              // can be foregroundInactive during control handoff and its
              // controller can be detached even when this button is alive.
              // The attached source UIWindow is the valid presentation owner.
              owner.windowScene != nil,
              sourceView.isHidden == false else {''',
        "attached picker source guard")
    s=replace_once(
        s,
        '''        let actionsCount = 3 // V107: virtual guest window actions only.''',
        '''        let actionsCount = 4 // V129: three window controls + per-app viewport switch.''',
        "window actions count")
    s=replace_once(s,
        '''                ("창 닫기", "closeWindow")''',
        '''                ("창 닫기", "closeWindow"),
                ("화면 표시 방식 전환", "nrgV129ToggleViewportMode")''',
        "viewport switch row")
    # No new modal, overlay or SwiftUI dock. Log one presenter entry for
    # diagnosing buttons that receive a tap but fail their owner check.
    # Preserve UIKit's real UIGlassEffect, but make its runtime choice
    # observable so screenshots can be matched to the actually installed IPA.
    s=replace_once(s,
        '            material.effect = UIGlassEffect()',
        '''            material.effect = UIGlassEffect()
            NSLog("[SCARLET_V129_GLASS] picker=native_UIGlassEffect reduceTransparency=0")''',
        "native glass runtime status")
    s=replace_once(s,
        'overlay.backgroundColor = UIColor.black.withAlphaComponent(0.16)',
        'overlay.backgroundColor = UIColor.black.withAlphaComponent(0.08)',
        "lighter scrim reveals the glass surface")
    s=replace_once(s,
        '        let overlay = UIControl(frame: owner.bounds)',
        '''        NSLog("[SCARLET_V129_PICKER_RESILIENCE] present=1 source_attached=1 direct=%d windowActions=%d", directMode ? 1 : 0, windowActions ? 1 : 0)
        let overlay = UIControl(frame: owner.bounds)''',
        "picker entry evidence")
    return s

def info(s):
    marker = "<key>ScarletBuildFeatureVersion</key>"
    if marker in s:
        if "<string>V129</string>" not in s:
            raise ValueError("V129 Info.plist partial build marker")
        return s
    if "<string>stikdebug</string>" not in s:
        anchor = "<key>LSApplicationQueriesSchemes</key>\n\t<array>"
        s = replace_once(s, anchor,
            "<key>LSApplicationQueriesSchemes</key>\n\t<array>\n\t\t<string>stikdebug</string>",
            "stikdebug scheme query permission")
    import re
    version_anchor = re.compile(r'(<key>CFBundleVersion</key>\s*<string>)[^<]+(</string>)')
    matches = list(version_anchor.finditer(s))
    if len(matches) != 1:
        raise ValueError("V129 Info.plist version anchor drift")
    s=version_anchor.sub(r'\g<1>3.8.202\g<2>',s,count=1)
    return replace_once(s, "\t<key>CFBundleVersion</key>",
        "\t<key>ScarletBuildFeatureVersion</key>\n\t<string>V129</string>\n\t<key>CFBundleVersion</key>",
        "V129 device build identification")


def apply(root):
    files=[(APP,jit),(DECO,decorated),(DOCK,dock),(INFO,info),(UTIL,jit_classic)]
    modifications=[]
    for rel,fn in files:
        file=root/rel
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"V129 missing regular source: {rel}")
        old=file.read_text()
        new=fn(old)
        if fn(new)!=new: raise ValueError(f"V129 non-idempotent {rel}")
        modifications.append((file,old,new))
    for file,old,new in modifications:
        if old!=new:file.write_text(new)
        print("[PASS] V129",file.relative_to(root))

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v129_jit_viewport.py <LiveContainer root>")
    apply(Path(sys.argv[1]))

#!/usr/bin/env python3
"""V135: restore working JIT provider choice overwritten by V129 on iOS 26+.

V129 unconditionally rerouted StosDebug/StosDebugLC into external StikDebug.
That migration defeats previously working JIT script launch paths and makes
the saved selection lie about actual provider. V135 removes that forced
conversion, preserving whichever transport the user already selected, with
no signed app, App ID, pairing, IPA data or script-content mutation.
"""
from pathlib import Path
import sys

APP = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")
UTIL = Path("LiveContainerSwiftUI/Utilities/LCUtilsExtensions.swift")
MARK = "SCARLET_V135_JIT_PROVIDER_RESTORED"

def once(s: str, old: str, new: str, context: str) -> str:
    n=s.count(old)
    if n!=1:
        raise ValueError(f"V135 {context}: expected unique anchor, found {n}")
    return s.replace(old,new,1)

def app_patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK)!=1 or "effectiveEnabler = .StikJIT" in s:
            raise ValueError("V135 duplicate/partial PID provider repair")
        return s
    if "SCARLET_V129_JIT_PREFLIGHT" not in s or "SCARLET_V134_JIT_PROTOCOL" not in s:
        raise ValueError("V135 requires V129 and V134 JIT protocol")
    old='''                // SCARLET_V129_JIT_PREFLIGHT: normalize unsupported
                // StosDebug PID requests to the external StikDebug transport
                // on modern iOS, without changing the saved user preference.
                var effectiveEnabler = jitEnabler
                if #available(iOS 26.0, *),
                   jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {
                    effectiveEnabler = .StikJIT
                    NSLog("[SCARLET_V129_JIT] stage=preflight legacy_provider=stosdebug fallback=stikdebug")
                }'''
    new='''                // SCARLET_V135_JIT_PROVIDER_RESTORED: NEVER silently reroute
                // a previously working StosDebug/LC provider to StikDebug.
                // Preserve user-saved transport and its existing URL scheme.
                // An explicitly selected StikDebug still uses V134's correct
                // script-name/script-data protocol and PID targeting.
                let effectiveEnabler = jitEnabler
                NSLog("[SCARLET_V135_JIT] stage=provider_selected selected=%@ effective=%@ forced_migration=0",
                      String(describing: jitEnabler), String(describing: effectiveEnabler))'''
    s=once(s,old,new,"LiveProcess selector")
    return s

def classic_patch(s: str) -> str:
    mark="SCARLET_V135_CLASSIC_PROVIDER_RESTORED"
    if mark in s:
        if s.count(mark)!=1 or "effectiveEnabler = .StikJIT" in s:
            raise ValueError("V135 duplicate/partial classic provider repair")
        return s
    if "SCARLET_V129_CLASSIC_JIT_ROUTE" not in s or "SCARLET_V134_CLASSIC_JIT_PROTOCOL" not in s:
        raise ValueError("V135 requires V129 and V134 classic JIT protocol")
    old='''        // SCARLET_V129_CLASSIC_JIT_ROUTE: reroute obsolete StosDebug
        // to current external StikDebug on modern iOS; never change the
        // saved selection or claim that opening its URL proves JIT.
        var effectiveEnabler = jitEnabler
        if #available(iOS 26.0, *),
           jitEnabler == .StosDebug || jitEnabler == .StosDebugLC {
            effectiveEnabler = .StikJIT
            onServerMessage?("[SCARLET_V129_JIT] fallback=external_stikdebug classic=1")
        }'''
    new='''        // SCARLET_V135_CLASSIC_PROVIDER_RESTORED: the saved JIT
        // provider remains authoritative, even on iOS 27.
        // Selecting StikDebug is explicit, never a fallback imposed here.
        let effectiveEnabler = jitEnabler
        onServerMessage?("[SCARLET_V135_JIT] classic provider=\\(String(describing: jitEnabler)) forced_migration=0")
'''
    return once(s,old,new,"classic provider selector")

def apply(root: Path):
    pairs=[]
    for rel,fn in ((APP,app_patch),(UTIL,classic_patch)):
        p=root/rel
        if not p.is_file() or p.is_symlink():
            raise ValueError("missing or unsafe source "+str(p))
        old=p.read_text(encoding="utf-8")
        new=fn(old)
        if fn(new)!=new:
            raise ValueError("V135 non-idempotent source "+str(rel))
        pairs.append((p,old,new))
    for p,old,new in pairs:
        if old!=new:p.write_text(new,encoding="utf-8")
    print("[PASS] V135 original JIT provider preserved in LiveProcess and Classic; V134 script protocol kept")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v135_restore_jit_provider.py <pinned LiveContainer root>")
    apply(Path(sys.argv[1]))

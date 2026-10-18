#!/usr/bin/env python3
"""V46: route LiveProcess guest JIT callbacks to the installed host app.

With "Use LiveContainer's Bundle ID", the pinned bootstrap derives a bundle
identifier from the running process's application-identifier entitlement.
Inside LiveProcess this is <host>.LiveProcess, which is an app extension and
cannot be foreground-launched by StikDebug's pre-script resume_app().
Only normalize the suffix for an actual LiveProcess guest. Do not modify
certificates, provisioning, user data or guest selection.
"""
from pathlib import Path
import sys

MARKER = "NRG_V46_JIT_HOST_BUNDLE_RETURN"
TARGET = Path("LiveContainer/LCBootstrap.m")
ORIGINAL = '''                NSString *expectedBundleId = [entStr substringFromIndex:dotRange.location + 1];
                if(![infoPlist[@"CFBundleIdentifier"] isEqualToString:expectedBundleId]) {'''
REPLACEMENT = '''                NSString *expectedBundleId = [entStr substringFromIndex:dotRange.location + 1];
                // NRG_V46_JIT_HOST_BUNDLE_RETURN: the hosting process here can
                // be LiveProcess.appex, whose bundle ID is NOT launchable as an
                // iOS app. StikDebug uses Madeira's Bundle.main.bundleIdentifier
                // to resume the target before running madeira-jit.js. Preserve
                // the signing-team derived host ID but strip ONLY this known
                // extension suffix, and ONLY in the LiveProcess guest.
                if (isLiveProcess && [expectedBundleId hasSuffix:@".LiveProcess"]) {
                    expectedBundleId = [expectedBundleId substringToIndex:
                        expectedBundleId.length - @".LiveProcess".length];
                    NSLog(@"[LC_JIT_HANDOFF] return_target=host_app extension_suffix_removed=true");
                }
                if(![infoPlist[@"CFBundleIdentifier"] isEqualToString:expectedBundleId]) {'''

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or REPLACEMENT not in source:
            raise RuntimeError("V46 JIT return marker present but implementation drifted")
        return source
    if source.count(ORIGINAL) != 1:
        raise RuntimeError(f"Expected one entitlement-to-guest-bundle anchor; found {source.count(ORIGINAL)}")
    return source.replace(ORIGINAL, REPLACEMENT, 1)

def main(root: Path):
    file = root / TARGET
    old = file.read_text(encoding="utf-8")
    new = patch(old)
    assert patch(new) == new, "V46 JIT return transform is not idempotent"
    if new != old:
        file.write_text(new, encoding="utf-8")
    print("[PASS] V46 LiveProcess JIT callback normalizes the host app bundle ID")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v46_jit_host_bundle.py <pinned-livecontainer-root>")
    main(Path(sys.argv[1]))

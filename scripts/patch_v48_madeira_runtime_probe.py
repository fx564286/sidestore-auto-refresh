#!/usr/bin/env python3
"""V48 diagnostic-only: inspect the actual signed *host process* of LC guests.

Madeira running inside LiveContainer inherits the currently executing host or
LiveProcess code signature, not the entitlements in Madeira's loose IPA.
LLDB's attach stop (T11) is insufficient to prove JIT executable pages work.
This probe reports CS_DEBUGGED, traced status, and the signed memory grant
at bootstrap and after returning to the foreground. It never enables JIT,
mutates an AVAudioSession, shares credentials, or alters guest storage.
"""
from pathlib import Path
import sys

TARGET = Path("LiveContainer/LCBootstrap.m")
MARK = "NRG_V48_GUEST_RUNTIME_CAPABILITIES"
INCLUDE_ANCHOR = "#include <sys/mman.h>\n"
INCLUDES = "#include <sys/mman.h>\n#include <sys/sysctl.h>\n#include <sys/proc.h>\n"
FUNCTION_ANCHOR = "static BOOL checkJITEnabled() {"
INJECT = """// NRG_V48_GUEST_RUNTIME_CAPABILITIES: the guest runs under the host's
// real code signature. Capture post-StikDebug state without treating the
// sticky CS_DEBUGGED bit as proof that a debugger is still attached.
static int nrgV48EntitlementBool(CFStringRef key) {
    void *task = SecTaskCreateFromSelf(NULL);
    if (!task) return -1;
    CFTypeRef value = SecTaskCopyValueForEntitlement(task, key, NULL);
    CFRelease(task);
    if (!value) return 0;
    int granted = CFGetTypeID(value) == CFBooleanGetTypeID()
        ? (CFBooleanGetValue((CFBooleanRef)value) ? 1 : 0) : 0;
    CFRelease(value);
    return granted;
}

static void nrgV48LogGuestRuntime(const char *stage) {
    int flags = 0;
    int csResult = csops(getpid(), 0, &flags, sizeof(flags));
    int debugged = csResult == 0 ? !!(flags & CS_DEBUGGED) : -1;
    int csAllow = csResult == 0 ? !!(flags & 0x4) : -1; // CS_GET_TASK_ALLOW
    struct kinfo_proc procInfo = {0};
    size_t procSize = sizeof(procInfo);
    int mib[4] = {CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()};
    int traced = sysctl(mib, 4, &procInfo, &procSize, NULL, 0) == 0
        ? !!(procInfo.kp_proc.p_flag & P_TRACED) : -1;
    int taskAllow = nrgV48EntitlementBool(CFSTR("get-task-allow"));
    int memory = nrgV48EntitlementBool(CFSTR("com.apple.developer.kernel.increased-memory-limit"));
    int va = nrgV48EntitlementBool(CFSTR("com.apple.developer.kernel.extended-virtual-addressing"));
    NSLog(@"[NRG_V48_GUEST_RUNTIME] stage=%s pid=%d liveprocess=%d "
          "csops=%d cs_debugged=%d cs_get_task_allow=%d traced=%d "
          "ent_get_task_allow=%d memory_granted=%d extended_va_granted=%d "
          "jit_pool_unverified=1", stage, getpid(), isLiveProcess,
          csResult, debugged, csAllow, traced, taskAllow, memory, va);
}

static void nrgV48RegisterGuestResumeProbe(void) {
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        [[NSNotificationCenter defaultCenter]
            addObserverForName:UIApplicationDidBecomeActiveNotification
            object:nil queue:nil usingBlock:^(__unused NSNotification *note) {
                nrgV48LogGuestRuntime("foreground_after_debugger");
            }];
    });
}

"""
CALL_ANCHOR = """    // Overwrite home and tmp path
    NSString *newHomePath = nil;"""
CALL_REPLACE = """    // NRG_V48_GUEST_RUNTIME_CAPABILITIES: check the *running signature*,
    // not an embedded profile or the guest's unsigned entitlement plist.
    nrgV48LogGuestRuntime("guest_bootstrap");
    nrgV48RegisterGuestResumeProbe();

    // Overwrite home and tmp path
    NSString *newHomePath = nil;"""

def patch(text: str) -> str:
    if MARK in text:
        if text.count(MARK) != 2 or "nrgV48RegisterGuestResumeProbe();" not in text:
            raise RuntimeError("partial or modified V48 probe")
        return text
    for token in ("NRG_V46_JIT_HOST_BUNDLE_RETURN", "SecTaskCopyValueForEntitlement"):
        if token not in text:
            raise RuntimeError("requires pinned V46 LC guest bootstrap with Security API: " + token)
    for old, new in ((INCLUDE_ANCHOR, INCLUDES),
                     (FUNCTION_ANCHOR, INJECT + FUNCTION_ANCHOR),
                     (CALL_ANCHOR, CALL_REPLACE)):
        if text.count(old) != 1:
            raise RuntimeError(f"V48 anchor count {text.count(old)} for {old[:36]!r}")
        text = text.replace(old, new, 1)
    return text

def main(root: Path) -> None:
    p = root / TARGET
    before = p.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise RuntimeError("V48 transform not idempotent")
    if before != after:
        p.write_text(after, encoding="utf-8")
    print("[PASS] V48 Madeira guest JIT/Memory runtime probe: signed host state and foreground resume")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v48_madeira_runtime_probe.py <pinned-LiveContainer>")
    main(Path(sys.argv[1]))

#!/usr/bin/env python3
"""V86: reconcile orphaned guest registration only for a proven dead LiveProcess.

The V75 guard keeps real LiveProcess sessions from being duplicated. However,
its bare string registry can stay occupied after a guest has exited while the
window owner was lost. V86 tracks a positive PID at registration and removes a
stale record only on the kernel's affirmative ESRCH result. A live PID, unknown
PID, EPERM, or another unexpected error MUST retain ownership.
"""
from pathlib import Path
import sys

MARKER = "SCARLET_V86_VERIFIED_DEAD_GUEST"
MANAGER = Path("MultitaskSupport/MultitaskManager.swift")
SCENE = Path("MultitaskSupport/AppSceneViewController.m")
MODEL = Path("LiveContainerSwiftUI/Models/LCAppModel.swift")

ORIGINAL_MANAGER = """    static private var usingMultitaskContainers : [String] = []
    
    @objc class func registerMultitaskContainer(container: String) {
        usingMultitaskContainers.append(container)
    }
    
    @objc class func unregisterMultitaskContainer(container: String) {
        usingMultitaskContainers.removeAll(where: { c in
            return c == container
        })
    }
"""
NEW_MANAGER = """    // SCARLET_V86_VERIFIED_DEAD_GUEST: data folder ownership is not a window.
    // Track the actual LiveProcess PID to tell a dead owner from a detached
    // but still running guest. Unknown PIDs are never assumed dead.
    static private var usingMultitaskContainers : [String] = []
    static private var guestOwnerPID: [String: Int32] = [:]

    @objc class func registerMultitaskContainer(container: String, pid: Int32) {
        if !usingMultitaskContainers.contains(container) {
            usingMultitaskContainers.append(container)
        }
        if pid > 0 {
            guestOwnerPID[container] = pid
        }
    }

    @objc class func unregisterMultitaskContainer(container: String) {
        usingMultitaskContainers.removeAll(where: { c in
            return c == container
        })
        guestOwnerPID.removeValue(forKey: container)
    }

    // Only a positive kernel ESRCH result permits releasing an orphan.
    // EPERM and unknown/zero PIDs are deliberately NOT treated as dead.
    @objc class func reconcileVerifiedDeadContainer(container: String) -> Bool {
        guard isUsing(container: container),
              let owner = guestOwnerPID[container], owner > 0 else { return false }
        errno = 0
        let processGroup = getpgid(pid_t(owner))
        guard processGroup == -1 && errno == ESRCH else { return false }
        unregisterMultitaskContainer(container: container)
        NSLog("[SCARLET_V86_GUEST] verified_dead_pid=1 registration_released=1")
        return true
    }
"""
ORIGINAL_SCENE = """            [MultitaskManager registerMultitaskContainerWithContainer:self.dataUUID];
            self.identifier = identifier;
            self.pid = [self.extension pidForRequestIdentifier:self.identifier];
"""
NEW_SCENE = """            self.identifier = identifier;
            self.pid = [self.extension pidForRequestIdentifier:self.identifier];
            // SCARLET_V86: capture ownership after the real LiveProcess PID.
            // A zero or unknown PID remains protected from false stale cleanup.
            [MultitaskManager registerMultitaskContainerWithContainer:self.dataUUID pid:self.pid];
"""
ORIGINAL_MODEL = """                if stillOwned {
                    print("[LC_RETURN_V75] result=retained_owner_unresolved safe_to_cold_launch=0")
                    throw "lc.container.inUse".loc + "\\nThe guest is still registered as running, but its window could not be restored. Close the old guest window; if none is accessible, fully quit and reopen Scarlet Crystal. Do not delete the app or its data."
                }
                print("[LC_RETURN_V75] result=registration_cleared retry_cold_launch=1")
"""
NEW_MODEL = """                // SCARLET_V86: an inaccessible window is NOT proof of an
                // exited guest. Ask the kernel whether the tracked PID is
                // definitively gone. Never clear a live or unknown owner.
                var deadOwnerReleased = false
                if stillOwned {
                    deadOwnerReleased = await MainActor.run(body: {
                        MultitaskManager.reconcileVerifiedDeadContainer(container: currentDataFolder)
                    })
                }
                if stillOwned && !deadOwnerReleased {
                    print("[LC_RETURN_V75] result=retained_owner_unresolved safe_to_cold_launch=0")
                    throw "lc.container.inUse".loc + "\\nThe guest is still registered as running, but its window could not be restored. Close the old guest window; if none is accessible, fully quit and reopen Scarlet Crystal. Do not delete the app or its data."
                }
                if deadOwnerReleased {
                    print("[SCARLET_V86_GUEST] result=verified_dead_owner_cleared retry_cold_launch=1")
                } else {
                    print("[LC_RETURN_V75] result=registration_cleared retry_cold_launch=1")
                }
"""
def one(source: str, old: str, new: str, context: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"V86 {context}: expected one pinned anchor; got {source.count(old)}")
    return source.replace(old, new, 1)

def patch_manager(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or "getpgid(pid_t(owner))" not in source:
            raise ValueError("V86 partial manager patch")
        return source
    source = one(source, ORIGINAL_MANAGER, NEW_MANAGER, "MultitaskManager registry")
    if "import Darwin" not in source:
        source = "import Darwin\n" + source
    return source

def patch_scene(source: str) -> str:
    if "SCARLET_V86: capture ownership" in source:
        if source.count("SCARLET_V86: capture ownership") != 1 or NEW_SCENE not in source:
            raise ValueError("V86 partial controller patch")
        return source
    return one(source, ORIGINAL_SCENE, NEW_SCENE, "LiveProcess registration order")

def patch_model(source: str) -> str:
    if "SCARLET_V86: an inaccessible window" in source:
        if source.count("SCARLET_V86: an inaccessible window") != 1 or "deadOwnerReleased" not in source:
            raise ValueError("V86 partial launch guard")
        return source
    if "LC_RETURN_V75_BOUNDED_RESUME_RECONCILE" not in source:
        raise ValueError("V86 requires V75 bounded owner recovery first")
    return one(source, ORIGINAL_MODEL, NEW_MODEL, "V75 safe failure branch")

def apply(root: Path) -> None:
    # All files are validated before modifying any one of them.
    patches = [(MANAGER, patch_manager), (SCENE, patch_scene), (MODEL, patch_model)]
    proposed = []
    for relative, patch_fn in patches:
        file = root / relative
        original = file.read_text(encoding="utf-8")
        updated = patch_fn(original)
        if patch_fn(updated) != updated:
            raise ValueError("V86 idempotency failed for " + str(relative))
        proposed.append((file, original, updated))
    for file, before, after in proposed:
        if before != after:
            file.write_text(after, encoding="utf-8")
    print("[PASS] V86 verified-dead guest registration reconciliation; live/unknown PID protected")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v86_verified_dead_guest_reconcile.py <LiveContainer source>")
    apply(Path(sys.argv[1]))

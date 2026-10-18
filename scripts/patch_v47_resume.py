#!/usr/bin/env python3
"""V47: restore retained guest foreground scenes after iOS host activation.

A host foreground transition differs from an in-LiveContainer guest switch.
Only foreground the already-visible, running guest of the activated UIWindowScene.
Never global-resign a responder, force playback, revive a hidden guest, or
replace the guest process. All mutations are pinned, checked and idempotent.
"""
from pathlib import Path
import sys

MARK = "NRG_V47_HOST_FOREGROUND_RESUME"
DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
DELEGATE = Path("LiveContainerSwiftUI/App/AppDelegate.swift")

DOCK_ANCHOR = "    private func passURLSchemeToView(_ view: UIView) {"
DOCK_ADDITION = """    // NRG_V47_HOST_FOREGROUND_RESUME: iOS may suspend host/guest scenes while
    // another app or an offline lock screen remains active for a long time.
    // Restore only the retained, currently visible guest; do not steal a
    // keyboard responder or mutate any process-wide AVAudioSession.
    @objc public func nrgV47RestoreVisibleGuestScenes(for hostScene: UIWindowScene) {
        precondition(Thread.isMainThread)
        guard hostScene.activationState == .foregroundActive else { return }
        for app in apps {
            guard let view = app.view, !view.isHidden, view.alpha > 0.1,
                  view.window?.windowScene === hostScene,
                  let controller = view._viewDelegate() as? DecoratedAppSceneViewController,
                  controller.appSceneVC.isAppRunning,
                  PiPManager.shared?.isPiP(withDecoratedVC: controller) != true else { continue }
            controller.lcResumeMinimizedGuest()
            view.setNeedsLayout()
            NSLog("[NRG_V47_RESUME] visible_guest_restored=1 focus_forced=0 audio_forced=0")
        }
    }

"""
DELEGATE_ANCHOR = """    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        self.window = (scene as? UIWindowScene)?.keyWindow
    }
"""
DELEGATE_ADDITION = DELEGATE_ANCHOR + """
    // NRG_V47_HOST_FOREGROUND_RESUME: scene activation is not the same as
    // bringing a virtual guest to front via the dock. Reconcile on activation.
    func sceneDidBecomeActive(_ scene: UIScene) {
        guard let windowScene = scene as? UIWindowScene else { return }
        MultitaskDockManager.shared.nrgV47RestoreVisibleGuestScenes(for: windowScene)
    }
"""

def once(source: str, old: str, new: str, label: str) -> str:
    n = source.count(old)
    if n != 1:
        raise RuntimeError(f"V47 {label}: expected one anchor, found {n}")
    return source.replace(old, new, 1)

def patch_dock(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "controller.lcResumeMinimizedGuest()" not in source:
            raise RuntimeError("V47 dock patch is partial")
        return source
    for m in ("NRG_V46_GUEST_KEYBOARD_SCOPE", "lcResumeMinimizedGuest"):
        if m not in source:
            raise RuntimeError("V47 requires existing guest lifecycle: " + m)
    return once(source, DOCK_ANCHOR, DOCK_ADDITION + DOCK_ANCHOR, "dock")

def patch_delegate(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or DELEGATE_ADDITION not in source:
            raise RuntimeError("V47 scene delegate patch is partial")
        return source
    return once(source, DELEGATE_ANCHOR, DELEGATE_ADDITION, "scene delegate")

def main(root: Path) -> None:
    pending = []
    for rel, patch in ((DOCK, patch_dock), (DELEGATE, patch_delegate)):
        path = root / rel
        before = path.read_text(encoding="utf-8")
        after = patch(before)
        if patch(after) != after:
            raise RuntimeError(f"V47 not idempotent: {rel}")
        pending.append((path, before, after))
    for path, before, after in pending:
        if before != after:
            path.write_text(after, encoding="utf-8")
    print("[PASS] V47 host foreground resumes visible retained scenes, no global focus/audio side effects")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v47_resume.py <pinned-LiveContainer>")
    main(Path(sys.argv[1]))

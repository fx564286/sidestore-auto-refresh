#!/usr/bin/env python3
"""V27: focus handoff and stable geometry for retained virtual guest windows.

Applies after the pinned LiveContainer guest-return and multitask-dock patches.
Never terminates a guest, resets preferred scaling, or changes app identity.
"""
from pathlib import Path
import sys

MARKER = "NRG_V27_GUEST_SWITCH_LIFECYCLE"
PATH = "MultitaskSupport/MultitaskDockView.swift"


def one(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"V27 {label}: expected one anchor; found {count}")
    return text.replace(old, new, 1)


def patch(root: Path):
    path = root / PATH
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        if source.count(MARKER) != 2 or "NRG_V27_GEOMETRY_FADE_ONLY" not in source:
            raise SystemExit("V27 guest-switch patch incomplete")
        print("[PASS] V27 guest-switch patch already applied")
        return
    if "MULTITASK_DOCK_START_COLLAPSED_V3" not in source or "GUEST_RESUMED_EXISTING" not in source:
        raise SystemExit("Required prior guest-return/dock patches absent")

    source = one(source,
        "        passURLSchemeToView(targetView)\n        animateViewAppearance(targetView, from: center, in: window)\n",
        """        // NRG_V27_GUEST_SWITCH_LIFECYCLE: release the previous text input.
        prepareKeyboardForGuestSwitch(targetView: targetView, in: window)
        passURLSchemeToView(targetView)
        animateViewAppearance(targetView, from: center, in: window)
""", "activation path")
    helper = """    // NRG_V27_GUEST_SWITCH_LIFECYCLE: the remote keyboard's responder chain
    // belongs to the currently presented scene, not to the new guest.
    private func prepareKeyboardForGuestSwitch(targetView: UIView, in window: UIWindow) {
        precondition(Thread.isMainThread)
        var previousGuests = 0
        for app in apps {
            guard let old = app.view, old !== targetView, old.window === window else { continue }
            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
            }
            previousGuests += 1
        }
        window.endEditing(true)
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder),
                                       to: nil, from: nil, for: nil)
        NSLog("[NRG_V27_GUEST_FOCUS] previous_guests=%ld resign_requested=1", previousGuests)
    }

"""
    source = one(source, "    private func passURLSchemeToView(_ view: UIView) {\n",
                 helper + "    private func passURLSchemeToView(_ view: UIView) {\n", "keyboard helper")
    start = source.index("    private func animateViewAppearance(_ view: UIView, from center: CGPoint?, in window: UIWindow) {")
    end = source.index("    private func bringViewToFront(_ view: UIView, in window: UIWindow) {", start)
    original = source[start:end]
    if "Constants.bringToFrontScale" not in original or "PiPManager.shared!" not in original:
        raise SystemExit("V27 animation upstream changed")
    source = source[:start] + """    private func animateViewAppearance(_ view: UIView, from center: CGPoint?, in window: UIWindow) {
        // NRG_V27_GEOMETRY_FADE_ONLY: avoid transform+frame animation, which
        // can reenter with a scaled frame when guests switch rapidly.
        let wasHidden = view.isHidden || view.alpha < 0.1
        let controller = view._viewDelegate() as? DecoratedAppSceneViewController
        let isMaximized = controller?.isMaximized ?? false
        if UserDefaults.lcShared().bool(forKey: "LCMaxOneAppOnStage") && isMaximized {
            MultitaskDockManager.shared.minimizeAllWindows(except: controller)
        }
        view.layer.removeAllAnimations()
        view.transform = .identity
        if wasHidden {
            if let controller, PiPManager.shared?.isPiP(withDecoratedVC: controller) == true {
                PiPManager.shared?.stopPiP()
            }
            view.isHidden = false
            view.alpha = 0
        }
        bringViewToFront(view, in: window)
        // Preserve windowed/maximized frame and the user's chosen scale.
        UIView.animate(withDuration: wasHidden ? Constants.standardAnimationDuration :
                            Constants.shortAnimationDuration1, animations: {
            view.alpha = 1
        })
        NSLog("[NRG_V27_GUEST_GEOMETRY] identity=1 retained_frame=1 was_hidden=%d", wasHidden ? 1 : 0)
    }

""" + source[end:]
    if source.count(MARKER) != 2 or source.count("NRG_V27_GEOMETRY_FADE_ONLY") != 1:
        raise SystemExit("V27 markers mismatch")
    path.write_text(source, encoding="utf-8")
    print("[PASS] V27 keyboard focus handoff and geometry-safe guest activation")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v27_guest_switch.py <LiveContainer>")
    patch(Path(sys.argv[1]))

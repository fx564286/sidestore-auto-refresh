"""V100 morph switcher: native surface, same trigger, dismiss, and regression lock."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/patch_v100_morph_guest_switcher.py"
spec = importlib.util.spec_from_file_location("morph_v100", PATH)
v100 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v100)

DOCK = (
    "SCARLET_V97_RETAINED_GUEST_HOST_REBIND\n"
    "func nrgV72PresentGuestSwitcher(from controller: UIViewController, sourceView: UIView) {\n"
    + v100.START
    + "\nfor guest in recent { if guest.running { } }\nlet menuItem = UIAlertController(title: \"x\", message:nil, preferredStyle:.actionSheet)\n"
    + v100.END
    + "\n}"
)
WINDOW = (
    "NRG_V73_APPLE_FLOATING_CONTROL NRG_V72_OVERFLOW_LONGPRESS\n"
    + v100.WINDOW_OLD + "\n"
    + "- (void)nrgV72WindowOverflowLongPress:(UILongPressGestureRecognizer *)gesture {\n"
    + "    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self sourceView:self.nrgWindowOverflow];\n}\n"
    + 'overflow.accessibilityHint = @"Tap for window options. Hold to switch guests. Drag to move.";\n'
)


class MorphSwitchTests(unittest.TestCase):
    def test_dock_replaces_separate_popup_with_single_view(self):
        result = v100.patch_dock(DOCK)
        self.assertEqual(result.count(v100.MARK_DOCK), 1)
        self.assertNotIn(v100.START, result)
        self.assertIn('"scarlet.v100.morph.backdrop"', result)
        self.assertIn('sourceView.isHidden = true', result)
        self.assertIn('sourceView?.isHidden = false', result)
        self.assertIn('overlay.addAction(UIAction', result)
        self.assertIn('UIAccessibility.isReduceMotionEnabled', result)
        self.assertIn('material.transform = .identity', result)
        self.assertEqual(v100.patch_dock(result), result)

    def test_guard_rejects_duplicate_window_anchor(self):
        with self.assertRaises(ValueError):
            v100.patch_dock(DOCK + v100.START)
        with self.assertRaises(ValueError):
            v100.patch_dock(DOCK.replace('SCARLET_V97_RETAINED_GUEST_HOST_REBIND', ''))

    def test_window_routes_single_tap_and_keeps_long_hold_menu(self):
        result = v100.patch_window(WINDOW)
        self.assertEqual(result.count(v100.MARK_WINDOW), 1)
        self.assertIn('overflow.showsMenuAsPrimaryAction = NO;', result)
        self.assertIn('@selector(nrgV100TapMorph:)', result)
        self.assertEqual(result.count('nrgV72PresentGuestSwitcherFrom:self'), 1)
        self.assertIn('nrgV72WindowOverflowLongPress:', result)
        self.assertIn('Hold for window actions', result)
        self.assertEqual(v100.patch_window(result), result)

    def test_old_long_hold_no_longer_attaches_guest_picker(self):
        output = v100.patch_window(WINDOW)
        self.assertNotIn('addGestureRecognizer:nrgV72Hold', output)
        self.assertNotIn('overflow.showsMenuAsPrimaryAction = YES', output)

    def test_attached_production_source_if_explicitly_provided(self):
        import os
        root = os.environ.get("V100_PATCHED_LIVECONTAINER")
        if not root:
            return
        root = pathlib.Path(root)
        d = (root / v100.DOCK).read_text()
        w = (root / v100.WINDOW).read_text()
        self.assertEqual(v100.patch_dock(d), d)
        self.assertEqual(v100.patch_window(w), w)

    def test_fail_closed_cannot_half_write(self):
        with tempfile.TemporaryDirectory() as base:
            root = pathlib.Path(base)
            for rel, data in ((v100.DOCK, DOCK), (v100.WINDOW, "wrong")):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(data)
            with self.assertRaises(ValueError):
                v100.apply(root)
            self.assertEqual((root / v100.DOCK).read_text(), DOCK)


if __name__ == "__main__":
    unittest.main()

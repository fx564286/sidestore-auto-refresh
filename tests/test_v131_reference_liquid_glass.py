"""V131 native four-layer reference adoption; exactly one UIKit glass surface."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "v131", ROOT / "scripts/patch_v131_reference_liquid_glass.py")
v131 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v131)

class LiquidGlassReference(unittest.TestCase):
    def test_native_single_surface(self):
        text = (ROOT / "scripts/patch_v131_reference_liquid_glass.py").read_text()
        for marker in ("UIGlassEffect(style: .clear)", "glass.isInteractive = true",
                       "CAGradientLayer()", "UIColor.white.withAlphaComponent(0.19)",
                       "layer.borderWidth = 0.7", "CATransaction.setAnimationDuration(0.34)",
                       "UIAccessibility.isReduceMotionEnabled",
                       "UIAccessibility.isReduceTransparencyEnabled",
                       "SCARLET_V131_REFERENCE_LIQUID_GLASS"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        # Never add a new guest UIWindow or force-set reduced transparency.
        for forbidden in ("UIWindow(frame:", "UIHostingController(", "SecItemDelete",
                          "installProvisioningProfile(", "JITLaunch", "setAccessibilityReduceTransparency"):
            self.assertNotIn(forbidden, text)

    def test_real_generated_source(self):
        pinned = os.getenv("V131_PATCHED_LIVECONTAINER")
        if not pinned:
            with self.assertRaises(ValueError):
                v131.transform("unrelated source")
            return
        source = (Path(pinned) / v131.DOCK).read_text()
        self.assertEqual(v131.transform(source), source)
        self.assertEqual(source.count("UIGlassEffect(style: .clear)"), 1)
        self.assertEqual(source.count("SCARLET_V131_REFERENCE_LIQUID_GLASS"), 1)
        self.assertEqual(source.count('material.accessibilityIdentifier = "scarlet.v100.morph.panel"'), 1)
        self.assertEqual(source.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'), 1)
        self.assertEqual(source.count("tabPicker.addAction("), 1)
        self.assertEqual(source.count("item.configuration = .plain()"), 3)
        # Regression for V131 CI #40474821815: Python generated literal
        # backslash-n tokens instead of real Swift statement boundaries.
        self.assertNotIn(r"{\n                // The panel owns Liquid Glass", source)
        self.assertNotIn(r".plain()\n", source)
        self.assertNotIn(r".cornerCurve = .continuous\n", source)
        self.assertEqual(source.count("// The panel owns Liquid Glass; rows remain translucent controls."), 2)
        self.assertEqual(source.count("item.layer.cornerCurve = .continuous"), 3)
        self.assertEqual(source.count("UIButton.Configuration.glass()"), 0)
        self.assertNotIn("UIVisualEffectView(effect: UIGlassEffect())", source)
        self.assertIn("weak tabHousing", source)
        self.assertIn("SCARLET_V131_VISIBLE_GLASS_ACTIVATION", source)
        self.assertIn("status=deferred_until_visible", source)
        self.assertIn("status=materialized_after_visible", source)
        self.assertLess(source.index("overlay.alpha = 1"), source.index("material.effect = glass"))
        self.assertIn("SCARLET_V129_PICKER_RESILIENCE", source)
        self.assertIn("SCARLET_V127_COMPLETE_GLASS", source)

if __name__=="__main__":
    unittest.main()

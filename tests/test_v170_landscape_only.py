"""V170 guards: no portrait geometry changes; only stable landscape repairs."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "landscape_patch", ROOT / "scripts/patch_v170_landscape_only.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class LandscapeOnly(unittest.TestCase):
    def setUp(self):
        self.source = """// SCARLET_V169_EVENT_DRIVEN_VIEWPORT
// SCARLET_V151_UNIFIED_GUEST_GEOMETRY
// SCARLET_V136_ROTATION_ATOMIC
@property(nonatomic) BOOL nrgV169GeometryQueued;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&
        orientation == self.nrgV169LastMeasuredOrientation) return;
        owner.nrgV169GeometryQueued = NO;
        [owner nrgV55ReconcileRotationGeometry];
// portrait existing source must remain byte-identical
if (portraitPhone) { portraitTop = physicalInsets.top; }
"""

    def test_landscape_only_and_idempotent(self):
        out = mod.patch(self.source)
        self.assertEqual(out, mod.patch(out))
        self.assertIn("if (UIInterfaceOrientationIsLandscape(orientation) &&", out)
        self.assertIn("size.width > size.height + 1.0", out)
        self.assertIn("!nrgV170LandscapeNeedsRepair", out)
        self.assertIn("nrgV170LandscapeRepairAttempted", out)
        self.assertIn("if (portraitPhone) { portraitTop = physicalInsets.top; }", out)
        self.assertEqual(out.count("portraitTop = physicalInsets.top;"), 1)
        self.assertNotIn("UIInterfaceOrientationIsPortrait(orientation)", out)
        self.assertIn("SCARLET_V170_LANDSCAPE", out)

    def test_fails_closed_without_v169(self):
        with self.assertRaises(ValueError):
            mod.patch("@property(nonatomic) BOOL nrgV169GeometryQueued;")

if __name__ == "__main__":
    unittest.main()

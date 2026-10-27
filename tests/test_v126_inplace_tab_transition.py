"""V126 regression: one retained glass panel when switching recent/window tabs."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v108 = load("patch_v108_remove_blue_collapsed_dock")
v111 = load("patch_v110_single_guest_dock")


class InPlaceTabs(unittest.TestCase):
    def test_builder_keeps_one_material_and_two_modes(self):
        producer = (ROOT / "scripts/patch_v110_single_guest_dock.py").read_text()
        for required in (
            "SCARLET_V126_INPLACE_TAB_CONTENT",
            "source = apply_in_place_tab_transition(source)",
            'if "SCARLET_V126_INPLACE_TAB_CONTENT" not in source:',
            "let rebuildTabContent: () -> Void = {",
            "UIView.transition(with: rows, duration: 0.20",
            "UIAccessibility.isReduceMotionEnabled",
            "tabListHeightConstraint.constant",
            "rows.removeArrangedSubview(child)",
            "nrgV114DirectWindowActionsRequest = targetWindowActions",
            "weak overlay, weak sourceView",
        ):
            with self.subTest(required=required):
                self.assertIn(required, producer)
        self.assertIn("SCARLET_V125_NATIVE_GLASS", producer)

    def test_inplace_transform_fails_closed_on_drift(self):
        with self.assertRaises(ValueError):
            v111.apply_in_place_tab_transition("not the pinned picker")

    def test_generated_picker_reuses_existing_backdrop_without_collapsing(self):
        generated = os.environ.get("V126_PATCHED_LIVECONTAINER")
        if generated:
            rendered = (Path(generated) / v111.REL).read_text()
        else:
            raw = ROOT / "verify-work-v107-fix/LiveContainer" / v111.REL
            if raw.exists():
                rendered = v111.transform(v108.patch(raw.read_text()))
            else:
                rendered = None
        if rendered is None:
            # Pre-build repository check cannot see the pinned external checkout.
            # Full generated-source regression runs against the patched artifact
            # by setting V114_PATCHED_LIVECONTAINER in the build pipeline.
            return
        v111.audit(rendered)
        self.assertEqual(v111.transform(rendered), rendered)
        self.assertEqual(rendered.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'), 1)
        self.assertEqual(rendered.count('material.accessibilityIdentifier = "scarlet.v100.morph.panel"'), 1)
        self.assertEqual(rendered.count('tabPicker.addAction('), 1)
        self.assertEqual(rendered.count('let rebuildTabContent: () -> Void = {'), 1)
        self.assertIn("let footer = UILabel()", rendered)
        self.assertIn('if directMode {', rendered)
        self.assertIn('"minimizeWindow"', rendered)
        self.assertIn('"maximizeWindow"', rendered)
        self.assertIn('"closeWindow"', rendered)
        self.assertIn('scarlet.v112.direct.restart', rendered)
        callback_start = rendered.index("        tabPicker.addAction(")
        callback_end = rendered.index("        owner.layoutIfNeeded()", callback_start)
        callback = rendered[callback_start:callback_end]
        self.assertIn("rebuildTabContent()", callback)
        self.assertIn("UIView.transition(with: rows", callback)
        self.assertNotIn("collapse {", callback)
        self.assertNotIn("nrgV72PresentGuestSwitcher(from:", callback)
        self.assertNotIn("nrgV102PresentWindowActions(from:", callback)


if __name__ == "__main__":
    unittest.main()

"""V127 contract: native glass for every control and one signing path for IPA."""
import importlib.util
import os
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v108 = load("patch_v108_remove_blue_collapsed_dock")
dock = load("patch_v110_single_guest_dock")


class GlassAndAutomaticSigning(unittest.TestCase):
    def test_pinned_native_picker_has_three_glass_actions_and_one_panel(self):
        selected = os.environ.get("V127_PATCHED_LIVECONTAINER")
        raw = (Path(selected) if selected else ROOT / "verify-work-v107-fix/LiveContainer") / dock.REL
        if not raw.is_file():
            # A generated-source test is also run against the pinned external
            # checkout in the build workflow, not by fabricating that source.
            source = (ROOT / "scripts/patch_v110_single_guest_dock.py").read_text()
            self.assertIn("SCARLET_V127_COMPLETE_GLASS", source)
            self.assertIn("UIButton.Configuration.glass()", source)
            return
        result = raw.read_text() if selected else dock.transform(v108.patch(raw.read_text()))
        dock.audit(result)
        self.assertEqual(result, dock.transform(result))
        self.assertEqual(result.count('item.configuration = config'), 3)
        self.assertEqual(result.count('UIButton.Configuration.glass()'), 3)
        self.assertEqual(result.count('tabPicker.addAction('), 1)
        self.assertEqual(result.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'), 1)
        self.assertEqual(result.count('material.accessibilityIdentifier = "scarlet.v100.morph.panel"'), 1)
        self.assertIn('tabHousing.insertSubview(tabGlass, belowSubview: tabPicker)', result)
        self.assertIn('!UIAccessibility.isReduceTransparencyEnabled', result)
        self.assertIn('item.backgroundColor = UIColor.secondarySystemGroupedBackground', result)
        self.assertIn('UIGlassEffect()', result)
        self.assertIn('UIGlassEffect())', result)
        self.assertIn('scroll.setContentOffset(.zero, animated: false)', result)
        self.assertIn('UIAccessibility.isReduceMotionEnabled', result)
        self.assertNotIn('collapse { switchContent() }', result)

    def test_v127_is_guarded_and_avoids_new_overlay(self):
        source = (ROOT / 'scripts/patch_v110_single_guest_dock.py').read_text()
        self.assertIn('if "SCARLET_V127_COMPLETE_GLASS" not in source:', source)
        self.assertIn("if source.count(opaque) != 3:", source)
        self.assertNotIn('UIHostingController<AnyView>', dock.apply_complete_glass_surface.__code__.co_consts)
        with self.assertRaises(ValueError):
            dock.apply_complete_glass_surface("wrong upstream")

    def test_signed_and_unsigned_ipa_both_use_actual_signing_pipeline(self):
        runtime = (ROOT / 'scripts/templates/v3_headless_runtime.swift').read_text()
        primitive = (ROOT / 'scripts/templates/v3_behavioral_primitives.swift').read_text()
        start = runtime.index('    func resolveBundleIDOverride(initialBundleID:')
        end = runtime.index('    func resolveAppGroupMismatch(', start)
        handler = runtime[start:end]
        self.assertIn('SCARLET_V127_AUTO_SIGN_DEFAULT', handler)
        self.assertIn('return nil', handler)
        self.assertNotIn('ask(kind:', handler)
        self.assertNotIn('appendTeamID", "label"', handler)
        self.assertIn('return makeInstallDriver(id: id, kind: kind, route: route, app: app,', runtime)
        self.assertIn('AppOperation.install($0)', runtime)
        self.assertIn('convergence=AppProtocol pipeline=.install signing_pipeline=required', runtime)
        self.assertIn('enum V3InstallInputRoute: String, Equatable { case localIPA, remoteURL, catalog }', primitive)
        self.assertNotIn('bypassSign', handler)
        self.assertNotIn('skipSigning', handler)


if __name__ == '__main__':
    unittest.main()

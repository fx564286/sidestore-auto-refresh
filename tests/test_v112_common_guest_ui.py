"""V112: Direct and LiveProcess share the SAME native guest picker implementation."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v105=load("patch_v105_delete_legacy_return")
v108=load("patch_v108_remove_blue_collapsed_dock")
v111=load("patch_v110_single_guest_dock")
base=ROOT/"verify-work-v107-fix/LiveContainer"

class SharedGuestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        target=os.environ.get("V112_PATCHED_LIVECONTAINER")
        if target:
            root=Path(target)
            cls.shared=(root/"MultitaskSupport/MultitaskDockView.swift").read_text()
            cls.direct=(root/"LiveContainer/LCBootstrap.m").read_text()
        elif (base/"MultitaskSupport/MultitaskDockView.swift").is_file():
            raw=(base/"MultitaskSupport/MultitaskDockView.swift").read_text()
            cls.shared=v111.transform(v108.patch(raw))
            cls.direct=v105.DIRECT_CODE
        else:
            # Repository prepatch CI: the pinned guest sources have not
            # been materialized yet. Assert builder wiring here; execute
            # full real source assertions again after all source patches.
            cls.shared=None
            cls.direct=v105.DIRECT_CODE

    def require_generated(self):
        if self.shared is None:
            script=(ROOT/"scripts/patch_v110_single_guest_dock.py").read_text()
            self.assertIn("SCARLET_V112_SHARED_GUEST_UI",script)
            self.assertIn("SCUnifiedGuestUIBridge",script)
            self.skipTest("Final generated source is checked in the postpatch stage")

    def test_both_modes_use_one_picker_renderer(self):
        self.require_generated()
        swift=self.shared
        self.assertEqual(v111.transform(swift), swift)
        self.assertEqual(swift.count("public func nrgV72PresentGuestSwitcher("), 1)
        self.assertIn("@objc(SCUnifiedGuestUIBridge)",swift)
        self.assertIn("@objc(presentFrom:sourceView:)",swift)
        self.assertIn("nrgV112PresentDirectGuestUI(from: controller, sourceView: sourceView)",swift)
        self.assertIn("nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)",swift)
        self.assertIn("nrgV102PresentWindowActions(from: controller, sourceView: sourceView)",swift)
        self.assertEqual(swift.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'),1)
        self.assertEqual(swift.count('material.accessibilityIdentifier = "scarlet.v100.morph.panel"'),1)

    def test_direct_entry_delegates_to_shared_swift_instead_of_second_panel(self):
        direct=self.direct
        for required in ('SCARLET_V112_SHARED_GUEST_UI',
                         'NSClassFromString(@"SCUnifiedGuestUIBridge")',
                         'NSSelectorFromString(@"presentFrom:sourceView:")',
                         'NSSelectorFromString', '[UIImage systemImageNamed:@"ellipsis"]',
                         'UIBlurEffectStyleSystemThinMaterial',
                         'nrgV112RestartDirectGuest',
                         'confirmation=accepted'):
            self.assertIn(required,direct)
        for legacy in ('UIButton *scrim', 'UIView *card', 'UILabel *title',
                       'UILabel *note', 'portraitUI ? 44 : 28',
                       '[UIImage systemImageNamed:@"chevron.up"]',
                       '- (void)expand:', 'card.alpha ='):
            self.assertNotIn(legacy,direct)

    def test_direct_switch_action_requires_visible_explicit_restart(self):
        self.require_generated()
        source=self.shared
        self.assertIn('item.accessibilityIdentifier = "scarlet.v112.direct.restart"',source)
        self.assertIn('item.setTitle("재시작 후 Scarlet Crystal로 복귀"',source)
        self.assertIn('controller.responds(to: NSSelectorFromString("nrgV112RestartDirectGuest"))',source)
        self.assertIn('let models = directMode ? [] : DataManager.shared.model.apps',source)
        self.assertIn('if #available(iOS 16.1, *), !directMode',source)
        self.assertIn('else if !windowActions {',source)
        self.assertIn('SCARLET_V103_IMMEDIATE_GUEST_SWITCH',source)
        self.assertNotIn('@interface SCGuestMorphPresenter : NSObject',source)

    def test_v111_dock_removed_and_window_actions_kept(self):
        self.require_generated()
        source=self.shared
        for obsolete in ('struct AppIconView: View', 'struct MultitaskDockSwiftView: View',
                         'struct CollapsedDockView: View', 'hostingController.rootView'):
            self.assertNotIn(obsolete,source)
        self.assertIn('func bringMultitaskViewToFront(uuid:',source)
        self.assertIn('SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND',source)
        self.assertIn('("최소화", "minimizeWindow")',source)
        self.assertIn('("최대화 / 복원", "maximizeWindow")',source)
        self.assertIn('("창 닫기", "closeWindow")',source)

    def test_upstream_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"V111 missing"):
            v111.transform("unrelated source")
        with self.assertRaisesRegex(ValueError,"V108"):
            v108.patch("unrelated source")

if __name__=="__main__":
    unittest.main()

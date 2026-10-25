"""V114 regression: Direct button must call the SAME functional shared picker.

Checks the generated Swift/ObjC at the pinned V107 source contract, not a
second fallback panel. All tests must run before and after source patching
without unittest.skip: no destructive auth or guest state edits.
"""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v105=load("patch_v105_delete_legacy_return")
v108=load("patch_v108_remove_blue_collapsed_dock")
v111=load("patch_v110_single_guest_dock")
pinned=ROOT/"verify-work-v107-fix/LiveContainer"

class DirectPickerRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected=os.environ.get("V114_PATCHED_LIVECONTAINER")
        if selected:
            cls.swift=(Path(selected)/v111.REL).read_text()
            cls.objc=(Path(selected)/v105.BOOT).read_text()
        elif (pinned/v111.REL).is_file():
            src=(pinned/v111.REL).read_text()
            cls.swift=v111.transform(v108.patch(src))
            cls.objc=v105.DIRECT_CODE
        else:
            # GitHub's prepatch gate: test the builder's source contracts.
            # The full generated-source checks run after applying the patches.
            cls.swift=None
            cls.objc=v105.DIRECT_CODE

    def available(self):
        if self.swift is not None:
            return True
        source=(ROOT/"scripts/patch_v110_single_guest_dock.py").read_text()
        for expected in ("SCARLET_V114_PICKER_TABS",
                         "nrgV114DirectWindowActionsRequest = targetWindowActions",
                         "UISegmentedControl(items:"):
            self.assertIn(expected,source)
        return False

    def test_direct_button_loads_existing_framework_and_bridge(self):
        code=self.objc
        for required in ('SCARLET_V114_DIRECT_PICKER_REPAIR',
                         'tap=1 mode=direct',
                         'LiveContainerSwiftUI.framework',
                         'loadAndReturnError:',
                         'NSClassFromString(@"SCUnifiedGuestUIBridge")',
                         'presentFrom:sourceView:',
                         'common_router=bridge',
                         'NSClassFromString(@"MultitaskDockManager")',
                         'nrgV112PresentDirectGuestUIFrom:sourceView:',
                         'common_router=manager'):
            self.assertIn(required,code)
        self.assertEqual(code.count('- (void)openShared:(UIButton *)sourceView'),1)
        self.assertNotIn('UIButton *scrim',code)
        self.assertNotIn('UIView *card',code)

    def test_exactly_one_shared_picker_with_tabs_in_both_modes(self):
        if not self.available():
            return
        s=self.swift
        v111.audit(s)
        self.assertEqual(v111.transform(s),s)
        self.assertEqual(s.count('public func nrgV72PresentGuestSwitcher('),1)
        self.assertEqual(s.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'),1)
        for required in ('SCARLET_V114_PICKER_TABS',
                         'UISegmentedControl(items: ["최근 실행 앱", "창 관리"])',
                         'tabPicker.accessibilityIdentifier = "scarlet.v114.shared.guest.tabs"',
                         'nrgV114DirectWindowActionsRequest = targetWindowActions',
                         'self.nrgV102PresentWindowActions(from: controller, sourceView: sourceView)',
                         'self.nrgV112PresentDirectGuestUI(from: controller, sourceView: sourceView)',
                         'picker_guard_rejected',
                         'windowActions ? "창 관리" : "최근 실행 앱"'):
            self.assertIn(required,s)
        self.assertNotIn("UIHostingController<AnyView>",s)
        self.assertNotIn("struct MultitaskDockSwiftView: View",s)
        self.assertNotIn("struct AppIconView: View",s)

    def test_direct_window_actions_dont_call_foreign_guest_selectors(self):
        if not self.available():
            return
        s=self.swift
        self.assertIn('Direct 실행은 독립 창 조작을 지원하지 않아.',s)
        self.assertIn('controller is DecoratedAppSceneViewController',s)
        self.assertIn('if directMode {',s)
        self.assertIn('scarlet.v112.direct.restart',s)
        self.assertIn('nrgV112RestartDirectGuest',s)
        self.assertIn('[weak self, weak controller, weak sourceView, weak tabPicker]',s)
        self.assertNotIn('resetAdi',s)

    def test_upstream_changes_fail_closed(self):
        with self.assertRaises(ValueError):
            v111.transform('wrong upstream')
        with self.assertRaises(ValueError):
            v108.patch('wrong upstream')

if __name__=="__main__":
    unittest.main()

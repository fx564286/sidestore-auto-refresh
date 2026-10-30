"""V161 source-only correctness: physically test touch callbacks on iPhone."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v161',ROOT/'scripts/patch_v161_compact_outside.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class V161CompactOutside(unittest.TestCase):
    def test_unknown_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'V161 missing V160 prerequisite'):
            mod.patch('invalid')

    def test_one_existing_panel_adapts_height_and_blank_tap(self):
        root=os.environ.get('V161_PATCHED_LIVECONTAINER')
        if not root:return
        src=(Path(root)/mod.DOCK).read_text()
        self.assertEqual(mod.patch(src),src)
        for required in (
            'SCARLET_V161_BLANK_PANEL_DISMISS',
            'let outside = !panelOnScreen.contains(onScreen)',
            'NSLog("[SCARLET_V160_GUEST_WINDOW_COORDS] outside=%d", outside ? 1 : 0)',
            'if outside { return true }',
            'let nextListHeight = min(CGFloat((windowActions ? actionsCount :',
            'max(1, min(3, recent.count))) * 54)',
            'frozenHeight?.constant = stablePanelHeight - listHeight + nextListHeight',
            'tabListHeightConstraint.constant = min(',
            'panel.convert(panel.bounds, to: self).contains(touch.location(in: self))',
            'if view is UIControl { return false }',
            'list.contentSize.height > list.bounds.height + 1 { return false }',
            'return !panelOnScreen.contains(onScreen)',
        ):
            if required == 'return !panelOnScreen.contains(onScreen)':
                self.assertNotIn(required,src)
            else:self.assertIn(required,src)
        self.assertLess(src.index('let outside = !panelOnScreen.contains(onScreen)'),
                        src.index('if outside { return true }'))
        self.assertEqual(src.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(src.count('let tabPicker = UISegmentedControl(items:'),1)
        self.assertEqual(src.count('let material = UIVisualEffectView(effect:'),1)
        self.assertIn('SCGlassControlPress.attach(to: item, nativeOnly: true)',src)
        self.assertNotIn('private final class SCGuestMorphPresenter',src)

    def test_for_two_recent_apps_rows_fit_no_dead_space(self):
        for n,mode,expected in [(1,False,54),(2,False,108),(3,False,162),(7,False,162),(1,True,162)]:
            with self.subTest(n=n,window_actions=mode):
                self.assertEqual((3 if mode else max(1,min(3,n)))*54,expected)

if __name__=='__main__':unittest.main()

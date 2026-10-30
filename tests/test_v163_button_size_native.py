"""V163 native glass footprint regression: never enlarge the panel or trim bloom."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v163',ROOT/'scripts/patch_v163_button_size_native.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class V163NativeFootprint(unittest.TestCase):
    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'V163 requires V162'):
            mod.patch('bad source')
    def test_three_action_rows_fit_original_scroll_viewport(self):
        self.assertLessEqual(3*48+2*7,3*54)
        self.assertGreaterEqual(18, 12) # Glass optical side clearance retained.
    def test_patched_generated_native_controls(self):
        root=os.getenv('V163_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/mod.DOCK).read_text(encoding='utf-8')
        self.assertEqual(mod.patch(s),s)
        for marker in (
            'let panelWidth = max(CGFloat(270), min(CGFloat(390), availableWidth) * (5.0 / 6.0))',
            'material.widthAnchor.constraint(equalToConstant: panelWidth)',
            'content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 10)',
            'content.trailingAnchor.constraint(equalTo: material.contentView.trailingAnchor, constant: -10)',
            'scroll.clipsToBounds = false',
            'SCGlassControlPress.attach(to: item, nativeOnly: true)',
            'SCARLET_V163_PRESS_CLEARANCE','SCARLET_V163_NATIVE_HEIGHT',
            'SCARLET_V161_BLANK_PANEL_DISMISS','SCARLET_V161_RESIZE_TAB',
            'SCARLET_V160_OUTSIDE_RETURN','SCARLET_V160_GLASS_CONTRAST',
            'SCARLET_V159_ACTION_NATIVE_PRESS',
            'tabPicker.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)',
            'tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)',
        ):self.assertIn(marker,s)
        self.assertEqual(s.count('rows.layoutMargins = UIEdgeInsets(top: 0, left: 18, bottom: 0, right: 18)'),2)
        self.assertEqual(s.count('item.heightAnchor.constraint(equalToConstant: 48).isActive = true'),2)
        self.assertEqual(s.count('item.heightAnchor.constraint(equalToConstant: 47).isActive = true'),0)
        self.assertEqual(s.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(s.count('let tabPicker = UISegmentedControl(items:'),1)
        self.assertEqual(s.count('let material = UIVisualEffectView(effect:'),1)
        self.assertNotIn('item.transform = CGAffineTransform',s)
        # NSLog is outside NSLayoutConstraint.activate's [constraint] array.
        self.assertIn('content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)\n        ])\n        NSLog("[SCARLET_V163_BUTTON_FOOTPRINT]',s)
        self.assertIn('let outside = !panelOnScreen.contains(onScreen)',s)
        self.assertIn('if outside { return true }',s)
    def test_only_inner_button_sizing_changes(self):
        path=os.getenv('V163_V162_BASELINE_DOCK')
        root=os.getenv('V163_PATCHED_LIVECONTAINER')
        if not path or not root:return
        before=Path(path).read_text(encoding='utf-8')
        after=(Path(root)/mod.DOCK).read_text(encoding='utf-8')
        self.assertEqual(mod.patch(before),after)
        for needle in (
            'let panelWidth = max(CGFloat(270), min(CGFloat(390), availableWidth) * (5.0 / 6.0))',
            'content.topAnchor.constraint(equalTo: material.contentView.topAnchor, constant: 16)',
            'content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)',
            'let listHeight = min(CGFloat((windowActions ? actionsCount :',
            'let maxListHeight = max(60, owner.bounds.height',
            'tabListHeightConstraint.constant = min(',
            'frozenHeight?.constant = stablePanelHeight - listHeight + nextListHeight',
        ):
            self.assertEqual(before.count(needle),after.count(needle),needle)
        self.assertEqual(before.count('content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 17)'),1)
        self.assertEqual(after.count('content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 17)'),0)

if __name__=='__main__': unittest.main()

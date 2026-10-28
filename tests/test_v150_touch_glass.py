"""V150 real generated source and unchanged parent panel regressions."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v150',ROOT/'scripts'/'patch_v150_touch_glass.py')
p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)

def panel_layout(s):
    a=s.index('        let overlay = UIControl(frame: owner.bounds)')
    b=s.index('        let tabPicker = UISegmentedControl(items:',a)
    return s[a:b]

class V150GlassTouchTest(unittest.TestCase):
    def test_rejects_non_v149(self):
        with self.assertRaises(ValueError):p.patch('old source')

    def test_no_panel_overlay_replacement(self):
        code=(ROOT/'scripts'/'patch_v150_touch_glass.py').read_text()
        self.assertNotIn('let material = UIVisualEffectView',code)
        self.assertNotIn('let overlay = UIControl(',code)
        self.assertNotIn('UIWindow(frame:',code)
        self.assertNotIn('addSubview(material)',code)
        self.assertNotIn('let panelWidth =',code)

    def test_actual_generated_ui_if_available(self):
        root=os.environ.get('V150_PATCHED_LIVECONTAINER')
        if not root:
            self.assertEqual(p.PATH.name,'MultitaskDockView.swift')
            return
        dock=(Path(root)/p.PATH).read_text()
        self.assertEqual(p.patch(dock),dock)
        if os.environ.get('V150_BASELINE_DOCK'):
            old=Path(os.environ['V150_BASELINE_DOCK']).read_text()
            self.assertEqual(panel_layout(old),panel_layout(dock))
        self.assertEqual(dock.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',dock)
        self.assertEqual(dock.count('SCGlassControlPress.attach(to: item)'),3)
        self.assertEqual(dock.count('SCGlassControlPress.attach(to: tabPicker)'),1)
        self.assertEqual(dock.count('UIButton.Configuration.clearGlass()'),3)
        self.assertIn('hold.minimumPressDuration = 0.24',dock)
        self.assertIn('.scaledBy(x: 1.055, y: 1.105)',dock)
        self.assertIn('hold.cancelsTouchesInView = false',dock)
        self.assertIn('control.transform = .identity',dock)
        self.assertIn('tabPicker.selectedSegmentTintColor',dock)
        self.assertNotIn('item.layer.borderColor = UIColor.white.withAlphaComponent(0.25)',dock)
        self.assertIn('SCARLET_V149_TABS',dock)
        self.assertIn('SCARLET_V144_GLASS_INSTALLED',dock)

    def test_touchdown_across_foreground_guest_scenes(self):
        s=p.StringObserver
        self.assertIn('override func touchesBegan(',s)
        self.assertIn('state = .began',s)
        self.assertIn('gesture.cancelsTouchesInView = false',s)
        self.assertIn('shouldRecognizeSimultaneouslyWith',s)
        self.assertIn('connectedScenes.compactMap',s)
        self.assertIn('.foregroundActive',s)
        self.assertIn('.foregroundInactive',s)
        self.assertIn('window.screen === owner.screen',s)
        self.assertIn('owner.screen.coordinateSpace',s)
        self.assertIn('DispatchQueue.main.async',s)
        self.assertIn('dismissQueued = true',s)
        self.assertIn('windowTokens.removeAll()',s)
        self.assertIn('recent app selection outside gesture cleanup', (ROOT/'scripts'/'patch_v150_touch_glass.py').read_text())
        self.assertNotIn('window.windowScene === owner.windowScene',s)
        self.assertNotIn('recognizer.state == .ended,',s)

    def test_no_duplicate_control_or_event_stealing(self):
        s=p.PressClass
        self.assertIn('hold.cancelsTouchesInView = false',s)
        self.assertIn('gestureRecognizer(',s)
        self.assertIn('shouldRecognizeSimultaneouslyWith',s)
        self.assertNotIn('addSubview(',s)
        self.assertNotIn('UIWindow(',s)
        self.assertIn('minimumPressDuration = 0.24',s)

if __name__=="__main__":unittest.main()

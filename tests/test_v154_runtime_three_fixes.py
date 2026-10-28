"""V154 anchored source checks: old V153 must fail, patched V154 must pass."""
import importlib.util, os, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v154",ROOT/"scripts"/"patch_v154_three_runtime_fixes.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class V154SourceTests(unittest.TestCase):
    def test_invalid_sources_rejected(self):
        for fn in (m.dock,m.boot,m.shell):
            with self.subTest(fn=fn.__name__),self.assertRaises(ValueError):fn("V153 old")
    def test_v153_lacks_these_three_fixes(self):
        root=os.getenv("V154_BASELINE_LIVECONTAINER")
        if not root:return
        for f,fn in [(m.DOCK,m.dock),(m.BOOT,m.boot),(m.SHELL,m.shell)]:
            old=(Path(root)/f).read_text()
            self.assertNotEqual(fn(old),old)
    def test_patch_idempotence_and_single_control(self):
        root=os.getenv("V154_PATCHED_LIVECONTAINER")
        if not root:return
        for f,fn in [(m.DOCK,m.dock),(m.BOOT,m.boot),(m.SHELL,m.shell)]:
            current=(Path(root)/f).read_text()
            self.assertEqual(fn(current),current)
        dock=(Path(root)/m.DOCK).read_text()
        boot=(Path(root)/m.BOOT).read_text()
        shell=(Path(root)/m.SHELL).read_text()
        self.assertEqual(dock.count('let tabPicker = UISegmentedControl(items:'),1)
        self.assertEqual(dock.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(dock.count('let material = UIVisualEffectView(effect:'),1)
        self.assertEqual(dock.count('("앱 닫기", "closeWindow")'),1)
        self.assertEqual(boot.count('initWithTarget:self action:@selector(openSharedTap:)'),1)
        self.assertEqual(boot.count('forControlEvents:UIControlEventTouchUpInside'),1)
        self.assertEqual(shell.count('MultitaskDockManager.shared.nrgV112PresentDirectGuestUI('),1)
    def test_recent_only_breathing_room(self):
        root=os.getenv("V154_PATCHED_LIVECONTAINER")
        if not root:return
        dock=(Path(root)/m.DOCK).read_text()
        self.assertIn('rows.isLayoutMarginsRelativeArrangement = !windowActions && !directMode',dock)
        self.assertIn('UIEdgeInsets(top: 6, left: 12, bottom: 6, right: 12)',dock)
        self.assertIn('SCARLET_V153_RECENT_UNCLIPPED',dock)
        self.assertIn('SCARLET_V151_TAB_NATIVE_PRESS',dock)
        self.assertIn('SCGlassControlPress.attach(to: item)',dock)
    def test_outside_on_backdrop_first_touch(self):
        root=os.getenv("V154_PATCHED_LIVECONTAINER")
        if not root:return
        dock=(Path(root)/m.DOCK).read_text()
        self.assertIn('override func touchesBegan(',dock)
        self.assertIn('let outside = !panel.frame.contains(touch.location(in: self))',dock)
        self.assertIn('overlay.dismissOutside = { collapse({}) }',dock)
        self.assertIn('outsideObserver.install(with: outsideTap)',dock)
    def test_direct_success_only_if_visible(self):
        root=os.getenv("V154_PATCHED_LIVECONTAINER")
        if not root:return
        shell=(Path(root)/m.SHELL).read_text()
        a=shell.index('SCARLET_V154_DIRECT_VISIBLE_CHECK')
        b=shell.index('            return\n        }',a)
        block=shell[a:b]
        self.assertIn('let visible = hostWindow.subviews.contains',block)
        self.assertIn('if visible {\n                            delivered = true',block)
        self.assertIn('stage=panel_visible result=0 retry=1',block)
        self.assertNotIn('delivered = true\n                        //',block)
        # Regression for CI #40778017938: Xcode 27.2 type-checking
        # stalls on chained connectedScenes compactMap/filter/flatMap.
        self.assertIn('SCARLET_V154_DIRECT_XCODE_SIMPLE_LOOP',block)
        self.assertIn('for candidateScene in UIApplication.shared.connectedScenes',block)
        self.assertIn('for candidateWindow in activeScene.windows',block)
        self.assertNotIn('.flatMap { $0.windows }',block)
        self.assertNotIn('let windows = UIApplication.shared.connectedScenes',block)
if __name__=="__main__":unittest.main()

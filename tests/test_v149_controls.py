import importlib.util, os, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v149", ROOT/"scripts"/"patch_v149_controls.py")
v149=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v149)
class V149Test(unittest.TestCase):
    def test_no_parent_edits(self):
        src=(ROOT/"scripts"/"patch_v149_controls.py").read_text()
        self.assertNotIn("material.layer.cornerRadius =",src)
        self.assertNotIn("material.effect =",src)
        self.assertNotIn("UIWindow(frame:",src)
    def test_no_drift(self):
        with self.assertRaises(ValueError):v149.patch("not V148")
    def test_real_source(self):
        root=os.getenv("V149_PATCHED_LIVECONTAINER")
        if not root:
            self.assertEqual(v149.DOCK.name,"MultitaskDockView.swift")
            return
        dock=(Path(root)/v149.DOCK).read_text()
        self.assertEqual(v149.patch(dock),dock)
        self.assertIn("UIButton.Configuration.clearGlass()",dock)
        self.assertNotIn('("창 닫기", "closeWindow")',dock)
        self.assertIn('("앱 닫기", "closeWindow")',dock)
        self.assertIn("UIWindow.didBecomeVisibleNotification",dock)
        self.assertIn("windowTokens.removeAll()",dock)
        self.assertNotIn("tabsLens = UIVisualEffectView",dock)
        self.assertNotIn("tabPicker.setBackgroundImage(UIImage()",dock)
        old=os.getenv("V149_BASELINE_DOCK")
        if old:
            base=Path(old).read_text()
            a="        let material = UIVisualEffectView(effect:"
            b="        let tabPicker = UISegmentedControl(items:"
            self.assertEqual(base[base.index(a):base.index(b)],
                             dock[dock.index(a):dock.index(b)])
if __name__=="__main__":unittest.main()

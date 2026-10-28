"""V148 strict right-tab Liquid Glass and outside-dismiss source contracts."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]

spec=importlib.util.spec_from_file_location("v148",ROOT/"scripts"/"patch_v148_action_glass.py")
glass=importlib.util.module_from_spec(spec)
spec.loader.exec_module(glass)

class V148RightTabTests(unittest.TestCase):
    def test_no_overlays_or_extra_dismiss_button(self):
        code=(ROOT/"scripts"/"patch_v148_action_glass.py").read_text()
        self.assertNotIn("UIWindow(frame:",code)
        self.assertNotIn("rowLens = UIVisualEffectView",code)
        self.assertNotIn("removeProvisioningProfile(",code)
        self.assertIn("UIButton.Configuration.glass()",code)
        self.assertNotIn("('창 닫기', 'closeWindow')",code)

    def test_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            glass.patch("unrelated source")

    def test_right_tab_real_rendering(self):
        src=os.environ.get("V148_PATCHED_LIVECONTAINER")
        if not src:
            self.assertEqual(glass.FILE.as_posix(),
                             "MultitaskSupport/MultitaskDockView.swift")
            return
        dock=(Path(src)/glass.FILE).read_text()
        self.assertEqual(glass.patch(dock),dock)
        start=dock.index("// SCARLET_V147_WINDOW_ACTION_NATIVE_GLASS:")
        end=dock.index("rows.addArrangedSubview(item)",start)
        section=dock[start:end]
        self.assertEqual(section.count("var config = UIButton.Configuration.glass()"),1)
        self.assertEqual(section.count('item.configuration = config'),1)
        self.assertIn('config.title = title',section)
        self.assertIn('item.accessibilityIdentifier = "scarlet.v148.windowaction."',section)
        self.assertNotIn('UIColor.white.withAlphaComponent(0.25)',section)
        self.assertNotIn('let rowLens =',section)
        self.assertEqual(dock.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',dock)
        self.assertIn("let actionsCount = 3",dock)
        self.assertIn("바깥을 누르면 창 관리 닫기",dock)
        self.assertIn("outsideObserver.install(with: outsideTap)",dock)
        self.assertIn('overlay.addAction(UIAction',dock)
        self.assertIn('for: .touchDown',dock)
        self.assertIn('[SCARLET_V148_ACTION_GLASS] action=',dock)

if __name__=="__main__":
    unittest.main()

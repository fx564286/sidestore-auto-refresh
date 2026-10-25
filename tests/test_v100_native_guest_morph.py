"""V100: LiveProcess tap/hold parity with the host morph panel."""
import importlib.util
from pathlib import Path
import unittest
import os

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts/patch_v100_native_guest_morph.py"
spec = importlib.util.spec_from_file_location("v100_native", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SAMPLE = (
    "LC_GUEST_SWITCH_V76_PATCHED SCARLET_V87_HOST_GUEST_PICKER\n"
    "    __weak typeof(self) weakSelf = self;\n"
    + module.OLD_TAP + "\n"
    + "        self.lcReturnControl.switchAction = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };\n"
    + module.OLD_HOLD + "\n"
)

class NativeMorphParityTests(unittest.TestCase):
    def test_tap_opens_same_host_guest_picker(self):
        s = module.patch(SAMPLE)
        self.assertIn("self.lcReturnControl.action = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };", s)
        self.assertNotIn(module.OLD_TAP,s)
        self.assertEqual(module.patch(s),s)

    def test_hold_does_not_directly_return_or_restart_guest(self):
        s = module.patch(SAMPLE)
        self.assertIn("button.menu = [UIMenu menuWithChildren",s)
        self.assertIn("Return to Scarlet Crystal",s)
        self.assertIn("[weakSelf lcReturnToHost];",s)
        self.assertNotIn(module.OLD_HOLD,s)
        self.assertIn("v76Hold.enabled = NO",s)

    def test_refuses_missing_prerequisites(self):
        with self.assertRaises(ValueError):
            module.patch(SAMPLE.replace("SCARLET_V87_HOST_GUEST_PICKER",""))
        with self.assertRaises(ValueError):
            module.patch(SAMPLE+module.OLD_TAP)

    def test_generated_compiled_source_when_requested(self):
        root = os.getenv("V100_PATCHED_LIVECONTAINER")
        if not root: return
        s = (Path(root)/module.TARGET).read_text()
        self.assertEqual(module.patch(s),s)
        self.assertEqual(s.count(module.MARK),1)

if __name__=="__main__":
    unittest.main()

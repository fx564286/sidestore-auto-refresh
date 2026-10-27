"""V129 regression tests: JIT preflight, one-panel picker, per-app viewport."""
import importlib.util
import os
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def import_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v129=import_script("patch_v129_jit_viewport")
v127=import_script("patch_v110_single_guest_dock")

class V129JITAndViewport(unittest.TestCase):
    def test_jit_handoff_still_requires_real_helper(self):
        source=(ROOT/"scripts/patch_v129_jit_viewport.py").read_text()
        for s in ('SCARLET_V129_JIT_PREFLIGHT', 'legacy_provider=stosdebug fallback=stikdebug', 'SCARLET_V129_CLASSIC_JIT_ROUTE',
                  'result=missing_stikdebug', 'script=absent txm=unknown',
                  'runtime_jit_unverified=1', 'stikdebug://enable-jit',
                  'canOpenURL(helperURL)', 'StikDebug'):
            with self.subTest(s=s):
                self.assertIn(s,source)
        self.assertNotIn('jit_pool_verified=1',source)
        self.assertNotIn('enableJITSuccess=1',source)

    def test_geometry_toggle_and_one_authoritative_safe_area(self):
        source=(ROOT/"scripts/patch_v129_jit_viewport.py").read_text()
        for token in ('ScarletGuestTouchSafe.', 'nrgV129ToggleViewportMode',
                      'touchSafe ? portraitTop : 0',
                      'touchSafe ? 0 : portraitTop',
                      'SCARLET_V129_PICKER_RESILIENCE',
                      '("화면 표시 방식 전환", "nrgV129ToggleViewportMode")',
                      'actionsCount = 4'):
            self.assertIn(token,source)
        self.assertNotIn("SecItemDelete",source)
        self.assertNotIn("removeItemAtPath",source)

    def test_fixture_generation_is_idempotent_and_no_duplicate_picker(self):
        pinned = os.environ.get("V129_PATCHED_LIVECONTAINER")
        if pinned:
            root=Path(pinned)
            for file,func in ((v129.APP,v129.jit),(v129.UTIL,v129.jit_classic),(v129.DECO,v129.decorated),
                              (v129.DOCK,v129.dock),(v129.INFO,v129.info)):
                source=(root/file).read_text()
                self.assertEqual(func(source),source)
            dock=(root/v129.DOCK).read_text()
            self.assertEqual(dock.count('overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"'),1)
            self.assertEqual(dock.count('tabPicker.addAction('),1)
            self.assertEqual(dock.count('("화면 표시 방식 전환", "nrgV129ToggleViewportMode")'),1)
            self.assertIn('SCARLET_V127_COMPLETE_GLASS',dock)
        else:
            with self.assertRaises(ValueError):
                v129.jit("unrelated")
            with self.assertRaises(ValueError):
                v129.decorated("unrelated")
            with self.assertRaises(ValueError):
                v129.dock("unrelated")

if __name__=="__main__":
    unittest.main()

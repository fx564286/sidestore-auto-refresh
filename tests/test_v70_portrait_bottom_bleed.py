"""V70 regression: no underlying host panel below portrait guest tab bar."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v58", ROOT / "scripts/patch_v58_fullscreen.py")
v58 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v58)

class V70PortraitBottomBleed(unittest.TestCase):
    def test_physical_top_only_and_scene_bottom(self):
        patch = (ROOT / "scripts/patch_v58_fullscreen.py").read_text()
        self.assertEqual(patch.count('NRG_V70_PORTRAIT_BOTTOM_BLEED'), 1)
        self.assertIn('UIEdgeInsetsMake(portraitTop, 0, 0, 0)', patch)
        self.assertIn('UIEdgeInsetsMake(0, 0, portraitBottom, 0), orientation', patch)
        self.assertNotIn('UIEdgeInsetsMake(portraitTop, 0, portraitBottom, 0)', patch)
        self.assertIn('settings.peripheryInsets = UIEdgeInsetsZero;', patch)
    def test_landscape_and_windowed_guests_untouched(self):
        patch = (ROOT / "scripts/patch_v58_fullscreen.py").read_text()
        self.assertIn('if (portraitPhone) {',patch)
        self.assertIn('UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone',patch)
        self.assertIn('settings.frame = UIInterfaceOrientationIsLandscape(orientation)',patch)
        self.assertIn('if (CGRectIsEmpty(physicalRect)) return;',patch)
        self.assertIn('settings.frame = CGRectMake',patch)
    def test_ci_patched_source_is_idempotent(self):
        path=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if not path or os.environ.get('V70_PATCHED_LIVECONTAINER') != '1':
            return # before-patch suite sees pristine pinned upstream source
        candidate=Path(path)/v58.DECORATED
        source=candidate.read_text()
        self.assertIn('NRG_V70_PORTRAIT_BOTTOM_BLEED',source)
        self.assertEqual(v58.decorated(source), source)
        if 'SCARLET_V129_JIT_VIEWPORT' in source:
            # V129 preserves the V70 no-bottom-physical-inset contract while
            # allowing per-app top inset ownership to switch safely.
            self.assertIn('UIEdgeInsetsMake(touchSafe ? portraitTop : 0, 0, 0, 0)', source)
            self.assertIn('UIEdgeInsetsMake(touchSafe ? 0 : portraitTop, 0, portraitBottom, 0), orientation', source)
            self.assertIn('ScarletGuestTouchSafe.', source)
        else:
            self.assertIn('UIEdgeInsetsMake(portraitTop, 0, 0, 0)', source)
        self.assertNotIn('UIEdgeInsetsMake(portraitTop, 0, portraitBottom, 0)',source)

if __name__=='__main__': unittest.main()

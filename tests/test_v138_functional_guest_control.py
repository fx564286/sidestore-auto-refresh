"""V138: never sacrifice functional V73 to an inaccessible guest controller."""
import importlib.util
from pathlib import Path
import os
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v138', BASE / 'scripts/patch_v138_functional_guest_control.py')
v138 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v138)

class FunctionalGuestControlTests(unittest.TestCase):
    def test_liveprocess_does_not_initialize_the_direct_fallback(self):
        original = '''// SCARLET_V137_SCENE_OWNER
// SCARLET_V105_DIRECT_UNIFIED_MORPH
if (!isSideStore) {
            scGuestMorphPresenter = [SCGuestMorphPresenter new];
    NSLog(@"[SCARLET_V114_UI] common_router_unavailable=1 framework_loaded=0");'''
        rewritten = v138.boot(original)
        self.assertIn('if (!isLiveProcess && !isSideStore)', rewritten)
        self.assertIn('SCARLET_V138_FUNCTIONAL_OWNER', rewritten)
        self.assertIn('openURL:returnURL options:', rewritten)
        self.assertEqual(v138.boot(rewritten), rewritten)
        self.assertEqual(rewritten.count('scGuestMorphPresenter = [SCGuestMorphPresenter new];'), 1)

    def test_virtual_owner_is_real_native_path(self):
        native = '''// SCARLET_V103_VIRTUAL_ONLY_CONTROL
// NRG_V73_APPLE_FLOATING_CONTROL
// SCARLET_V136_ROTATION_ATOMIC
// nrgV100TapMorph:
// scarlet.v103.virtual.guest.control
'''
        self.assertEqual(v138.window(native), native)
        with self.assertRaises(ValueError):
            v138.window(native+'// SCARLET_V137_UNIFIED_GUEST_ENTRY')

    def test_disallow_other_generations_and_shadow_paths(self):
        with self.assertRaises(ValueError):
            v138.boot('SCARLET_V137_UNIFIED_GUEST_ENTRY')
        with self.assertRaises(ValueError):
            v138.window('not a V73 source')
        with self.assertRaises(ValueError):
            v138.dock('a replacement button with no functional router')

    def test_generated_sources_if_available(self):
        root = os.getenv('V138_PATCHED_LIVECONTAINER')
        if not root:
            return
        root = Path(root)
        for rel,fn in ((v138.BOOT,v138.boot),(v138.WINDOW,v138.window),(v138.DOCK,v138.dock)):
            source=(root/rel).read_text(encoding='utf-8')
            self.assertEqual(fn(source),source)
        bootstrap=(root/v138.BOOT).read_text()
        native=(root/v138.WINDOW).read_text()
        self.assertEqual(bootstrap.count('SCARLET_V138_FUNCTIONAL_OWNER'),1)
        self.assertEqual(native.count('scarlet.v103.virtual.guest.control'),1)
        self.assertNotIn('SCARLET_V137_UNIFIED_GUEST_ENTRY',bootstrap)

if __name__ == '__main__':unittest.main()

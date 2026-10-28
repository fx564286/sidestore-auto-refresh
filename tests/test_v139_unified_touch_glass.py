"""V139 canonical action + native glass regression against pinned source contracts."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

p=module('patch_v139_unified_touch_glass')

class UnifiedTouchGlass(unittest.TestCase):
    def test_live_direct_fallback_has_real_recognized_host_picker_route(self):
        v105=module('patch_v105_delete_legacy_return')
        v132=module('patch_v132_glass_drag_one_owner')
        v137=module('patch_v137_rotation_glass_owner')
        v138=module('patch_v138_functional_guest_control')
        initial=v105.DIRECT_CODE+'\nif (!isSideStore) {\nscGuestMorphPresenter = [SCGuestMorphPresenter new];\n}'
        final=p.boot(v138.boot(v137.boot(v132.boot_patch(initial))))
        self.assertIn('scarletcrystal251://nrg-guest-controls',final)
        self.assertNotIn('scarletcrystal251://"',final)
        self.assertEqual(final.count('scarlet.v139.direct.glass.touch'),2) # gradient identity and lookup
        self.assertIn('reactToGlassTouch:forEvent:',final)
        self.assertIn('locationInView:button',final)
        self.assertEqual(final.count('UIButton *handle = [UIButton buttonWithType:UIButtonTypeSystem]'),1)
        self.assertEqual(p.boot(final),final)

    def test_host_owns_one_working_button_with_same_touch_semantics(self):
        src='''// NRG_V73_APPLE_FLOATING_CONTROL
// SCARLET_V103_VIRTUAL_ONLY_CONTROL
// SCARLET_V136_ROTATION_ATOMIC
- (void)nrgV100TapMorph:(UIButton *)sender { }
    [overflow insertSubview:nrgV73Material atIndex:0];
- (void)nrgV73DragFloatingOverflow:(UIPanGestureRecognizer *)pan {
}
'''
        updated=p.decorated(src)
        self.assertIn('nrgV139HostedGlassTouch:forEvent:',updated)
        self.assertIn('nrgV100TapMorph:',updated)
        self.assertIn('scarlet.v139.hosted.glass.touch',updated)
        self.assertNotIn('UIButton *handle =',updated)
        self.assertEqual(p.decorated(updated),updated)

    def test_one_host_swift_picker_destination(self):
        source=module('patch_v60_island_guest_switch').patch_shell(
            (ROOT/'scripts/templates/v3_unified_shell.swift').read_text())
        final=p.shell(source)
        self.assertEqual(final.count('SCARLET_V139_UNIFIED_GUEST_ACTION'),1)
        self.assertIn('nrgV72PresentGuestSwitcher(',final)
        self.assertIn('nrg-guest-controls',final)
        # Xcode 27.2 reported this exact API is iOS-16+ only. A Swift parse
        # check alone does not enforce SDK availability annotations.
        self.assertIn('if #available(iOS 16.0, *) {',final)
        self.assertIn('route=host_picker result=unsupported_os',final)
        self.assertEqual(final.count('nrgV72PresentGuestSwitcher('),1)
        self.assertLess(final.index('if #available(iOS 16.0, *) {'),
                        final.index('MultitaskDockManager.shared.nrgV72PresentGuestSwitcher('))
        self.assertNotIn('UIWindow(frame:',final)
        self.assertEqual(p.shell(final),final)

    def test_no_delayed_native_glass_swap_in_generated_panel(self):
        source=(ROOT/'scripts/patch_v139_unified_touch_glass.py').read_text()
        self.assertIn('SCARLET_V139_PANEL_TOUCH',source)
        self.assertIn('fingerGesture.cancelsTouchesInView = false',source)
        self.assertIn('gestureRecognizer(_ gestureRecognizer:',source)
        self.assertIn('followPoint(x: x, y: y)',source)
        self.assertIn('contact.startPoint = CGPoint(x: x, y: y)',source)
        self.assertIn('material.effect = steadyGlass',source)
        self.assertIn('remove second native material mutation',source)

    def test_fail_closed_and_no_guest_mutation(self):
        for fn in (p.boot,p.decorated,p.dock,p.shell):
            with self.assertRaises(ValueError): fn('unsupported upstream')
        code=(ROOT/'scripts/patch_v139_unified_touch_glass.py').read_text()
        for unsafe in ('SecItemDelete(', 'deleteAppID(', 'setPairingFileContent('):
            self.assertNotIn(unsafe,code)

    def test_generated_source_if_available(self):
        path=os.environ.get('V139_PATCHED_LIVECONTAINER')
        if not path:return
        root=Path(path)
        for rel,fn in ((p.BOOT,p.boot),(p.DECORATED,p.decorated),(p.DOCK,p.dock),(p.SHELL,p.shell)):
            code=(root/rel).read_text()
            self.assertEqual(fn(code),code)
        code=(root/p.BOOT).read_text()
        shell=(root/p.SHELL).read_text()
        dock=(root/p.DOCK).read_text()
        self.assertEqual(code.count('SCARLET_V139_UNIFIED_GUEST_ACTION'),1)
        self.assertEqual(shell.count('SCARLET_V139_UNIFIED_GUEST_ACTION'),1)
        self.assertEqual(dock.count('SCARLET_V139_UNIFIED_GUEST_ACTION'),1)
        self.assertNotIn('material.effect = nil',dock)
        self.assertNotIn('status=materialized_after_visible',dock)

if __name__=='__main__':unittest.main()

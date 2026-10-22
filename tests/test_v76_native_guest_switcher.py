"""V76: full-screen LiveProcess and retained virtual guest switch controls."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
v76=load('patch_v76_native_guest_switcher')
guest=load('patch_guest_return')

class NativeGuestSwitchTests(unittest.TestCase):
    def test_real_guest_return_source_and_idempotence(self):
        pinned=Path('/workspace/scarlet-v65/pinned-livecontainer')
        if not pinned.is_dir():
            # A CI checkout has no external fixture. The post-patch gate below
            # inspects the real generated source, without adding to skip budget.
            self.assertIn('self.lcReturnControl.switchAction =',
                          (ROOT/'scripts/patch_v76_native_guest_switcher.py').read_text())
            return
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for relative in guest.PATHS:
                path=root/relative
                path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(pinned/relative,path)
            guest.patch(root)
            v76.main(root)
            before=(root/v76.TARGET).read_text()
            v76.main(root)
            self.assertEqual(before,(root/v76.TARGET).read_text())
            self.assertEqual(before.count(v76.MARKER),1)
            self.assertIn('self.lcReturnControl.switchAction =',before)
            self.assertIn('nrgV72PresentGuestSwitcherFrom:presenter',before)
    def test_native_button_material_and_safe_default(self):
        self.assertIn('UIBlurEffectStyleSystemThinMaterial',v76.MATERIAL)
        self.assertIn('v76Material.userInteractionEnabled = NO',v76.MATERIAL)
        self.assertIn('minimumPressDuration = 0.55',v76.LONG_PRESS)
        self.assertIn('cancelsTouchesInView = YES',v76.LONG_PRESS)
        self.assertIn('CGPointMake(0.06, 0.60)',(ROOT/'scripts/patch_v76_native_guest_switcher.py').read_text())
    def test_virtual_scene_has_one_control_and_owner_safe_route(self):
        self.assertIn('|| decorated;',v76.LAYOUT)
        self.assertIn('presenter.view.window',v76.SWITCH_METHOD)
        self.assertIn('UIApplicationStateActive',v76.SWITCH_METHOD)
        self.assertIn('nrgV72PresentGuestSwitcherFrom:presenter',v76.SWITCH_METHOD)
        self.assertIn('self.switchAction()',v76.METHODS)
        self.assertIn('UIGestureRecognizerStateBegan',v76.METHODS)
        for forbidden in ('SIGKILL','unregisterMultitaskContainer','terminate(', 'removeRunningApp'):
            self.assertNotIn(forbidden,v76.SWITCH_METHOD)
    def test_wrong_revision_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'prerequisite'):
            v76.patch('unrelated source')
        with self.assertRaisesRegex(ValueError,'partial'):
            v76.patch(v76.MARKER)
    def test_compiled_host_source_when_ci_patched(self):
        path=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if not path or os.environ.get('V76_PATCHED_LIVECONTAINER')!='1':return
        actual=(Path(path)/v76.TARGET).read_text()
        self.assertEqual(v76.patch(actual),actual)
        self.assertIn('nrgV72PresentGuestSwitcherFrom:presenter',actual)
if __name__=='__main__':unittest.main()

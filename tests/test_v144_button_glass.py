"""V144 native Liquid Glass button touch tracking is shared in both contexts."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v144button',ROOT/'scripts/patch_v144_button_glass.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class NativeButtonTests(unittest.TestCase):
    def test_direct_button(self):
        source='''// SCARLET_V139_GLASS
- (void)reactToGlassTouch:(UIButton *)button forEvent:(UIEvent *)event {
    UITouch *touch = [[event touchesForView:button] anyObject];
    if (!touch) return;
    [self updateDirectGlass:button atPoint:[touch locationInView:button]];
    NSLog(@"[SCARLET_V139_GLASS] surface=direct finger=tracked phase=%ld", (long)touch.phase);
}'''
        new=v.boot(source)
        self.assertEqual(v.boot(new),new)
        self.assertEqual(new.count(v.MARK),1)
        self.assertIn('glassSurface.transform = CGAffineTransformScale(',new)
        self.assertIn('touch.phase == UITouchPhaseEnded',new)
    def test_hosted_button(self):
        source='''// SCARLET_V139_GLASS
- (void)nrgV139HostedGlassTouch:(UIButton *)button forEvent:(UIEvent *)event {
    UITouch *touch = [[event touchesForView:button] anyObject];
    if (!touch) return;
    [self nrgV139UpdateHostedGlassAt:[touch locationInView:button] inButton:button];
    NSLog(@"[SCARLET_V139_GLASS] surface=hosted finger=tracked phase=%ld", (long)touch.phase);
}'''
        new=v.host(source)
        self.assertEqual(v.host(new),new)
        self.assertIn('CGAffineTransformMakeTranslation(fx * 5.0, fy * 5.0)',new)
        self.assertEqual(new.count(v.MARK),1)
    def test_fail_closed(self):
        for f in (v.boot,v.host):
            with self.assertRaises(ValueError):f('no actual button')
    def test_no_duplicate_buttons(self):
        s=(ROOT/'scripts/patch_v144_button_glass.py').read_text()
        for bad in ('UIButton *overflow =', 'UIWindow *newWindow', 'SecItemDelete(',
                    'addSubview:overlay', 'removeProvisioningProfile('):
            self.assertNotIn(bad,s)
    def test_real_compiled_sources(self):
        root=os.getenv('V144_PATCHED_LIVECONTAINER')
        if not root:return
        for path,fn in ((v.BOOT,v.boot),(v.HOST,v.host)):
            s=(Path(root)/path).read_text()
            self.assertEqual(fn(s),s)
            self.assertEqual(s.count(v.MARK),1)
if __name__=='__main__':unittest.main()

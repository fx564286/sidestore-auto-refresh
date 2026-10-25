"""V103: no duplicate controls on guest launch; native tap immediately opens picker."""
from pathlib import Path
import importlib.util
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    p=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,p)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
v102=load("patch_v102_guest_recent_coherence")
actions=load("patch_v102_unified_window_actions")
native102=load("patch_v102_retire_native_gestures")
v103=load("patch_v103_single_guest_control")
sys.path.insert(0,str(ROOT/"tests"))
from test_v102_guest_unification import fixture

def generated():
    d,w,n=fixture()
    d=actions.patch_dock(v102.patch(d))
    w=actions.patch_window(w)
    n=native102.patch(n)
    # The source from V41 suppresses ALL native buttons even though
    # V76/V102 still install actions; test real legacy structural segment.
    n += '''
    // NRG_V41_FLOATING_RETURN_REMOVED: do not create an overlapping guest-return overlay.
    [self.lcReturnControl removeFromSuperview];
    self.lcReturnControl = nil;
    return;
    if (!self.lcReturnControl) {
    }
    self.button.accessibilityLabel = @"Return to LiveContainer";
    self.button.accessibilityHint = @"Minimizes this guest without closing it";
    self.button.accessibilityLabel = self.collapsed ? @"Show Return to LiveContainer" : @"Return to LiveContainer";
    if (self.collapsed) {
        self.collapsed = NO;
        [self setNeedsLayout];
        NSLog(@"[LC_RETURN] CONTROL_RESTORED");
        return;
    }
        if ([NSUserDefaults.lcSharedDefaults boolForKey:@"LCGuestReturnStartsCollapsed"]) [self collapse];
        self.action();
'''
    w += '    overflow.accessibilityLabel = @"Guest window controls";'
    return d,n,w

class Tests(unittest.TestCase):
    def test_virtual_removes_blue_return_before_creating_button(self):
        _,n,_=generated()
        o=v103.patch_native(n)
        self.assertIn('if (virtualWindowGuest)',o)
        self.assertIn('[self.lcReturnControl removeFromSuperview];',o)
        self.assertIn('owner=virtual_v73 native=removed',o)
        self.assertNotIn('return;\n    if (!self.lcReturnControl)',o)
        self.assertEqual(v103.patch_native(o),o)

    def test_direct_owns_single_control_without_two_taps(self):
        _,n,_=generated()
        o=v103.patch_native(n)
        self.assertIn('if (!self.lcReturnControl)',o)
        self.assertIn('restored_and_dispatched=1',o)
        self.assertNotIn('CONTROL_RESTORED");\n        return;',o)
        self.assertNotIn('if ([NSUserDefaults.lcSharedDefaults boolForKey:@"LCGuestReturnStartsCollapsed"]) [self collapse];\n        self.action();',o)

    def test_virtual_button_has_unique_active_identifier(self):
        _,_,w=generated()
        o=v103.patch_virtual(w)
        self.assertEqual(o.count(v103.MARK_VIRTUAL),1)
        self.assertIn('scarlet.v103.virtual.guest.control',o)
        self.assertEqual(v103.patch_virtual(o),o)

    def test_switch_dispatch_occurs_before_dismiss_animation(self):
        d,_,_=generated()
        o=v103.patch_dock(d)
        self.assertEqual(o.count(v103.MARK_DOCK),1)
        self.assertIn('defer { dismissSelection() }',o)
        self.assertIn('overlay.removeFromSuperview()',o)
        self.assertNotIn('item.addAction(UIAction { [weak self] _ in\n                collapse {',o)
        self.assertIn('self.bringMultitaskViewToFront(uuid: guest.folder)',o)
        self.assertEqual(v103.patch_dock(o),o)

    def test_anchor_drift_fails(self):
        d,n,w=generated()
        with self.assertRaises(ValueError):
            v103.patch_native(n.replace('NRG_V41_FLOATING_RETURN_REMOVED',''))
        with self.assertRaises(ValueError):
            v103.patch_virtual(w.replace('SCARLET_V102_UNIFIED_ACTION_SURFACE',''))
        with self.assertRaises(ValueError):
            v103.patch_dock(d.replace('SCARLET_V102_RECENT_FOCUS_CLOCK',''))

    def test_generated_production_sources_on_ci(self):
        import os
        root=os.getenv('V103_PATCHED_LIVECONTAINER')
        if not root:return
        root=Path(root)
        for f,p in ((v103.patch_dock,root/v103.DOCK),
                    (v103.patch_native,root/v103.NATIVE),
                    (v103.patch_virtual,root/v103.VIRTUAL)):
            data=p.read_text()
            self.assertEqual(f(data),data)

if __name__=='__main__':unittest.main()

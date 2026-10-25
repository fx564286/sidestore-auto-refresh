"""V102: fail-closed source migration and no duplicate guest UI surfaces."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

v72=module('patch_v72_overflow_longpress')
v100=module('patch_v100_morph_guest_switcher')
n100=module('patch_v100_native_guest_morph')
focus=module('patch_v102_guest_recent_coherence')
action=module('patch_v102_unified_window_actions')
native=module('patch_v102_retire_native_gestures')

def fixture():
    old=v72.SWIFT_SWITCHER
    a=old.index(v100.START)
    b=old.index(v100.END,a)+len(v100.END)
    dock=('SCARLET_V97_RETAINED_GUEST_HOST_REBIND\n'
        '    @Published var apps: [DockAppModel] = []\n'
        '            self.apps.append(appModel)\n'
        '        animateViewAppearance(targetView, from: center, in: window)\n'
        + old[:a]+v100.RENDER.rstrip('\n')+old[b:])
    window=('NRG_V73_APPLE_FLOATING_CONTROL\nNRG_V72_OVERFLOW_LONGPRESS\n'
        +'    __weak typeof(self) weakOverflowSelf = self;\n'
        +v100.WINDOW_NEW+'\n'
        +'    overflow.menu = [UIMenu menuWithChildren:@[\n'
        +'        [UIAction actionWithTitle:@"Minimize" handler:^{ [weakOverflowSelf minimizeWindow]; }],\n'
        +'        [UIAction actionWithTitle:@"Maximize" handler:^{ [weakOverflowSelf maximizeWindow]; }],\n'
        +'        [UIAction actionWithTitle:@"Close" handler:^{ [weakOverflowSelf closeWindow]; }]\n'
        +'    ]];\n'
        +v100.WINDOW_METHOD
        +'- (void)nrgV72WindowOverflowLongPress:(UILongPressGestureRecognizer *)gesture {\n'
        +'    NSLog(@"[SCARLET_V100_MORPH] legacy_hold_not_installed=1");\n}\n')
    scene=('LC_GUEST_SWITCH_V76_PATCHED\nSCARLET_V87_HOST_GUEST_PICKER\n'
       +'@property(nonatomic, copy) void (^switchAction)(void);\n'
       +'        self.lcReturnControl.switchAction = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };\n'
       +n100.NEW_TAP+'\n'+v72.OBJC_HANDLER[:0]
       +'    UILongPressGestureRecognizer *v76Hold = [[UILongPressGestureRecognizer alloc]\n'
       +'        initWithTarget:self action:@selector(lcV76HoldToSwitch:)];\n'
       +'    v76Hold.minimumPressDuration = 0.55;\n'
       +'    v76Hold.cancelsTouchesInView = YES;\n'
       +n100.NEW_HOLD+'\n'
       +'''- (void)lcV76HoldToSwitch:(UILongPressGestureRecognizer *)recognizer {
    if (recognizer.state != UIGestureRecognizerStateBegan || self.collapsed) return;
    if (self.switchAction) { self.switchAction(); }
}
- (void)lcV76CollapseControl {
}
- (void)lcV76ShowInstalledGuestSwitcher {
}
''')
    return dock,window,scene

class V102MigrationTests(unittest.TestCase):
    def test_focus_uses_only_running_guest_views(self):
        d=focus.patch(fixture()[0])
        self.assertIn('guard isRunning else { return nil }',d)
        self.assertNotIn('48 * 60 * 60',d)
        self.assertIn('nrgV102NoteFocus(uuid)',d)
        self.assertIn('apps.remove(at: index)',d)
        self.assertIn('nrgV102FocusDates[folder]',d)
        self.assertEqual(focus.patch(d),d)

    def test_single_morph_surface_has_two_modes(self):
        d=action.patch_dock(focus.patch(fixture()[0]))
        for expected in ('nrgV102PresentWindowActionsFrom:sourceView:',
                         'windowActions ? "창 관리"', 'if !windowActions {',
                         'closeWindow', 'minimizeWindow', 'maximizeWindow',
                         'SCARLET_V107_LIVE_WINDOW_ACTIONS_ONLY',
                         'guard controller is DecoratedAppSceneViewController'):
            self.assertIn(expected,d)
        for retired in ('lcReturnToHost', 'lcV102CollapseFloatingButton', '홍수정',
                        'controller is DecoratedAppSceneViewController\n                    ?'):
            self.assertNotIn(retired,d)
        self.assertEqual(action.patch_dock(d),d)

    def test_prior_v102_dead_direct_selector_branch_fails_closed(self):
        d=action.patch_dock(focus.patch(fixture()[0]))
        with self.assertRaisesRegex(ValueError, "obsolete V102 window-action menu"):
            action.patch_dock(d.replace('"closeWindow"', '"lcReturnToHost"'))
        with self.assertRaisesRegex(ValueError, "obsolete V102 window-action menu"):
            action.patch_dock(d.replace('Scarlet Crystal 내부', '홍수정 내부'))

    def test_old_native_overflow_menu_is_deleted_not_hidden(self):
        w=action.patch_window(fixture()[1])
        self.assertNotIn('overflow.menu = [UIMenu menuWithChildren',w)
        self.assertNotIn('- (void)nrgV72WindowOverflowLongPress:',w)
        self.assertIn('nrgV102HoldWindowActions:',w)
        self.assertIn('nrgV102PresentWindowActionsFrom:self',w)
        self.assertEqual(action.patch_window(w),w)

    def test_native_legacy_hold_and_duplicate_callbacks_removed(self):
        s=native.patch(fixture()[2])
        for retired in ('lcV76HoldToSwitch:', 'v76Hold.enabled = NO',
                        'self.lcReturnControl.button.menu = [UIMenu',
                        '@property(nonatomic, copy) void (^switchAction)'):
            self.assertNotIn(retired,s)
        self.assertIn('lcV102NativeHoldActions:',s)
        self.assertIn('lcV102CollapseFloatingButton',s)
        self.assertEqual(native.patch(s),s)

    def test_refuses_drift_and_partial_patches(self):
        with self.assertRaises(ValueError):
            focus.patch(fixture()[0].replace('SCARLET_V97_RETAINED_GUEST_HOST_REBIND',''))
        with self.assertRaises(ValueError):
            action.patch_dock(fixture()[0])
        with self.assertRaises(ValueError):
            native.patch(fixture()[2].replace('v76Hold.enabled = NO',''))

    def test_production_generated_sources_if_available(self):
        import os
        root=os.getenv('V102_PATCHED_LIVECONTAINER')
        if not root:return
        root=Path(root)
        d=(root/action.DOCK).read_text()
        w=(root/action.WINDOW).read_text()
        s=(root/native.FILE).read_text()
        self.assertEqual(focus.patch(d),d)
        self.assertEqual(action.patch_dock(d),d)
        self.assertEqual(action.patch_window(w),w)
        self.assertEqual(native.patch(s),s)

if __name__=='__main__':
    unittest.main()

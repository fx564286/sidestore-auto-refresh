"""V72: preserve top-right menu tap, move guest picker to its hold, remove Island."""
from pathlib import Path
import importlib.util
import os
import plistlib
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v72',ROOT/'scripts/patch_v72_overflow_longpress.py')
v72=importlib.util.module_from_spec(spec);spec.loader.exec_module(v72)

class OverflowLongPressTests(unittest.TestCase):
    def test_exact_existing_overflow_anchor_and_independent_hold(self):
        script=(ROOT/'scripts/patch_v72_overflow_longpress.py').read_text()
        self.assertIn('overflow.showsMenuAsPrimaryAction = YES',script)
        self.assertIn('nrgV72Hold.minimumPressDuration = 0.55',script)
        self.assertIn('nrgV72Hold.cancelsTouchesInView = YES',script)
        self.assertIn('nrgV72PresentGuestSwitcherFrom:self sourceView:self.nrgWindowOverflow',script)
        self.assertIn('nrgV72WindowOverflowLongPress',script)
        self.assertIn('nrgWindowOverflow',script)
        self.assertIn('UIImpactFeedbackGenerator',script)

    def test_recent_mru_and_only_installed_lc_models(self):
        code=v72.SWIFT_SWITCHER
        for check in ('DataManager.shared.model.apps','model.appInfo.lastLaunched',
                      'activeFolders.contains(folder)','48 * 60 * 60',
                      'URLQueryItem(name: "bundle-name"',
                      'URLQueryItem(name: "container-folder-name"',
                      'URLQueryItem(name: "nrg-multitask"',
                      'components.scheme = "scarletcrystal251"',
                      'bringMultitaskViewToFront(uuid: guest.folder)',
                      'UIApplication.shared.open(guest.route',
                      'model.appInfo.relativeBundlePath == guest.bundle',
                      'controller.present(menu, animated: true)'):
            self.assertIn(check,code)
        self.assertNotIn('UIApplication.shared.open(URL(string: "instagram',code)

    def test_actual_pinned_dock_and_window_patches_idempotent(self):
        source=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if source:
            root=Path(source)
            dock=(root/v72.DOCK).read_text()
            window=(root/v72.WINDOW).read_text()
            if os.environ.get('V72_PATCHED_LIVECONTAINER') == '1':
                self.assertIn(v72.MARK,dock)
                self.assertIn('nrgV72WindowOverflowLongPress',window)
                self.assertEqual(dock,v72.patch_dock(dock))
                self.assertEqual(window,v72.patch_window(window))
            else:
                # The full CI pre-patch repository sweep intentionally sees
                # the pristine pinned upstream checkout.
                self.assertNotIn(v72.MARK,dock)
        else:
            # Regression against real pinned source with all V56/V58/V60
            # transforms, not a fake model or a string-only fixture.
            import sys
            sys.path.insert(0,str(ROOT/'scripts'))
            import patch_v47_resume as p47
            import patch_v55_rotation_geometry as p55
            import patch_v39_dock_app_switch_only as p39
            import patch_v56_notch_ui as p56
            import patch_v58_fullscreen as p58
            import patch_v58_native_activity as native
            import patch_v60_island_guest_switch as p60
            import patch_v192_startup as p192
            pinned=Path('/workspace/scarlet-v65/pinned-livecontainer/MultitaskSupport/MultitaskDockView.swift')
            if not pinned.exists(): self.skipTest('pinned LiveContainer fixture unavailable')
            s=pinned.read_text()
            s=s.replace(p47.DOCK_ANCHOR,p47.DOCK_ADDITION+p47.DOCK_ANCHOR,1)
            for patch in (p55.dock,p39.patch,p56.patch,p58.dock,native.patch_dock,p60.patch_dock,p192.patch_dock,v72.patch_dock):
                s=patch(s)
            self.assertEqual(v72.patch_dock(s),s)
            self.assertNotIn('ActivityKit',s)
            self.assertNotIn('nrgV56',s)
            self.assertNotIn('nrgV58',s)
            for declaration in ('enum LCMultitaskDockRenderedMode',
                                'struct LCMultitaskDockPresentationState',
                                'struct LCMultitaskDockSessionState'):
                self.assertEqual(s.count(declaration),1, declaration)

    def test_bundle_plan_widgetless_and_no_live_activity_entitlement(self):
        policy=__import__('json').loads((ROOT/'config/v68_required_features.json').read_text())
        self.assertFalse(policy['features']['native_dynamic_island'])
        self.assertTrue(policy['features']['native_share_sheet_receiver'])
        self.assertTrue(policy['features']['independent_guest_process'])
        from sys import path
        path.insert(0,str(ROOT/'scripts'))
        from v68_appid_minimizer import load_policy,shell_environment
        plan=load_policy(ROOT/'config/v68_required_features.json')
        self.assertEqual(3,plan['minimum_planned_app_ids'])
        self.assertEqual({'host','LiveProcess','ShareExtension'},set(plan['installable_roles']))
        self.assertIn('NRG_V58_NATIVE_ISLAND=0',shell_environment(plan))
        with tempfile.TemporaryDirectory() as temp:
            info=Path(temp)/'Info.plist'
            x={'NSSupportsLiveActivities':True,'CFBundleURLTypes':[{'CFBundleURLSchemes':['livecontainer','scarletcrystal251']}]}
            y=v72.patch_info(x)
            self.assertNotIn('NSSupportsLiveActivities',y)

    def test_ci_final_patched_source_no_island(self):
        source=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if not source or os.environ.get('V72_PATCHED_LIVECONTAINER') != '1':
            return # explicit generated-source test re-runs with V72_PATCHED=1
        root=Path(source)
        dock=(root/v72.DOCK).read_text()
        shell=(root/v72.SHELL).read_text()
        model=(root/v72.MODEL).read_text()
        plist=plistlib.loads((root/v72.INFO).read_bytes())
        for value in ('ActivityKit','NRGV56Island','nrgV58RefreshNativeIsland'):
            self.assertNotIn(value,dock)
        self.assertNotIn('nrgV192RefreshIslandIfReady',shell)
        self.assertNotIn('nrgV58RefreshNativeIsland',model)
        self.assertNotIn('NSSupportsLiveActivities',plist)

if __name__=='__main__':unittest.main()

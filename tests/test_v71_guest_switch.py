"""V71: restore in-guest picker while native Island stays system-owned."""
import importlib.util
import os
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def mod(name):
    p=ROOT/'scripts'/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

v71=mod('patch_v71_in_guest_switcher')

class V71Tests(unittest.TestCase):
    def test_tiny_guest_trigger_only_when_retained_guest_visible(self):
        script=(ROOT/'scripts/patch_v71_in_guest_switcher.py').read_text()
        self.assertIn('nrgV71HasVisibleGuestScene() && !nrgV71Guests.isEmpty',script)
        self.assertIn('nrgV56IslandExpanded ? 218.0 : 30.0',script)
        self.assertIn('nrgV56IslandExpanded',v71.UI)
        self.assertIn('nrgV71GuestSwitcherTrigger',v71.UI)
        self.assertIn('UIApplication.shared.applicationState == .active',v71.HELPER)
        self.assertIn('if candidate.isHidden || candidate.alpha < 0.05',v71.HELPER)
        self.assertIn('let portrait = window.bounds.height > window.bounds.width',script)
    def test_native_and_foreground_share_one_guest_catalog(self):
        src=(ROOT/'scripts/patch_v71_in_guest_switcher.py').read_text()
        self.assertIn('nrgV71Guests = guests',src)
        self.assertIn('ForEach(dockManager.nrgV71Guests, id: \\.launchURL)',v71.UI)
        self.assertIn('nrgV71Guests.contains(where: { $0.launchURL == route })',v71.HELPER)
        self.assertIn('components.host == "livecontainer-launch"',v71.HELPER)
        self.assertIn('bringMultitaskViewToFront(uuid: folder)',v71.HELPER)
        self.assertIn('UIApplication.shared.open(targetURL',v71.HELPER)
        self.assertNotIn('UIApplication.shared.canOpenURL(URL(string: "instagram',v71.HELPER)
    def test_real_pinned_manager_composition_repeatable(self):
        ci_source=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if ci_source:
            source=Path(ci_source)/v71.TARGET
            text=source.read_text()
            self.assertIn('NRG_V71_FOREGROUND_GUEST_SWITCHER',text)
            self.assertEqual(v71.patch(text),text)
            self.assertIn('nrgV71Guests = guests',text)
            self.assertIn('nrgV71SelectGuest',text)
            self.assertIn('Activity<NRGGuestActivityAttributes>.request(',text)
            return
        src=Path('/workspace/scarlet-v65/pinned-livecontainer/MultitaskSupport/MultitaskDockView.swift')
        if not src.exists():self.skipTest('pinned LiveContainer fixture unavailable')
        v47=mod('patch_v47_resume')
        v55=mod('patch_v55_rotation_geometry')
        v39=mod('patch_v39_dock_app_switch_only')
        v56=mod('patch_v56_notch_ui')
        v58=mod('patch_v58_fullscreen')
        native=mod('patch_v58_native_activity')
        v60=mod('patch_v60_island_guest_switch')
        s=src.read_text()
        s=s.replace(v47.DOCK_ANCHOR,v47.DOCK_ADDITION+v47.DOCK_ANCHOR,1)
        s=v55.dock(s)
        s=v39.patch(s)
        s=v56.patch(s)
        s=v58.dock(s)
        s=native.patch_dock(s)
        s=v60.patch_dock(s)
        out=v71.patch(s)
        self.assertEqual(out,v71.patch(out))
        self.assertIn('NRG_V71_FOREGROUND_GUEST_SWITCHER',out)
        self.assertIn('nrgV71Guests = guests',out)
        self.assertNotIn('nrgV56IslandHost?.view.removeFromSuperview()',out)
        self.assertIn('nrgV71SelectGuest',out)
        self.assertIn('Activity<NRGGuestActivityAttributes>.request(',out)
        self.assertIn("NRG_V58_NATIVE_ISLAND_ACTIVITY",out)

if __name__=='__main__': unittest.main()

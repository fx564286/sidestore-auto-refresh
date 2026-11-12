"""R6P40 native transparent title-bar *layout role* while preserving 1:1 guest scale."""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GEN=(R/'integration/apply_scarlet_host.py').read_text()
GUEST=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class TransparentChromeSlot(unittest.TestCase):
    def test_host_window_remains_full_and_guest_naturally_reflows(self):
        a=HOST.index('private func chromeTop(in scene:')
        b=HOST.index('func setResidentOutsideDismissEnabled(',a)
        f=HOST[a:b]
        for key in ('scene.interfaceOrientation.isPortrait',
                    'resolvedHostInsets(scene).top',
                    'top >= 20 && top <= 130',
                    'full.minY + top',
                    'height: full.height - top'):
            self.assertIn(key,f)
        layout=HOST.split('override func viewDidLayoutSubviews()',1)[1].split('func isAlive(folder:',1)[0]
        self.assertIn('scene.coordinateSpace.bounds.size',layout)
        self.assertIn('abs(expected.width - actual.width) < 2',layout)
        self.assertIn('vc.view.frame = slot',layout)
        self.assertIn('settings.setFrame(slot)',layout)
        self.assertIn('settings.setInterfaceOrientation(orientation)',layout)
        self.assertNotIn('CGAffineTransform',layout)
        self.assertNotIn('contentInset',layout)
        self.assertIn('scale_milli',f)
        self.assertIn('"1000"',f)
    def test_transparent_chrome_does_not_steal_touches_or_unhide_window_buttons(self):
        for key in ('transparentChrome.backgroundColor = .clear',
                    'transparentChrome.isUserInteractionEnabled = false',
                    'transparentChrome.isAccessibilityElement = false',
                    'view.insertSubview(transparentChrome, at: 0)',
                    'transparentChrome.frame = CGRect(x: 0, y: 0,',
                    'transparentChrome.isHidden = chromeTop < 1'):
            self.assertIn(key,HOST,key)
        self.assertIn('remove_upstream_legacy_window_ui',GEN)
        self.assertIn('chromeMinMaxCloseRemoved',GEN)
        self.assertNotIn('UIBarButtonItem *minimizeButton',HOST)
    def test_single_safe_top_owned_by_native_layout_not_both_root_and_scene(self):
        for key in ('scarletNativeTransparentChromeSlot',
                    'if(self.scarletNativeTransparentChromeSlot) safe.top = 0;',
                    'if(chrome && UIInterfaceOrientationIsPortrait(settings.interfaceOrientation))',
                    'safe.top = 0;'):
            self.assertIn(key,GEN,key)
        for key in ('Scarlet.Guest.TransparentChromeTop.V1',
                    'fabs(CGRectGetHeight(window.bounds) + chrome - screen) < 4',
                    'guest_transparent_chrome_slot_unpadded'):
            self.assertIn(key,GUEST,key)
        self.assertIn('Scarlet.Guest.TransparentChromeTop.V1',HOST)
        self.assertIn('vc.scarletNativeTransparentChromeSlot = chromeTop > 0',HOST)
        self.assertIn('guest_chrome_native_frame_readback',HOST)
        self.assertIn('remote_content_height_pt',HOST)
    def test_no_legacy_virtual_window_and_no_recycled_v37_v39_header_writes(self):
        layout=HOST.split('override func viewDidLayoutSubviews()',1)[1].split('func isAlive(folder:',1)[0]
        for forbidden in ('.transform =','window.frame =','window.bounds =',
                          'CGAffineTransform', 'slot.height /', 'scaleRatio =',
                          'UINavigationBar','UIControl('):
            self.assertNotIn(forbidden,layout)
        self.assertIn('vc.scaleRatio = 1',HOST)
        self.assertIn('if(actual',HOST.replace('if actual','if(actual'))
    def test_release_is_distinct_and_uses_p40_only(self):
        self.assertIn('fix/scarlet-v48-r6p40-transparent-chrome-slot-20261113',WF)
        self.assertIn('Scarlet-Crystal-V48-R6P40-TRANSPARENT-CHROME-UNSIGNED.ipa',WF)
        self.assertIn('scarlet-v48-r6p40-transparent-chrome-unsigned-20261113',WF)

if __name__=='__main__':unittest.main()

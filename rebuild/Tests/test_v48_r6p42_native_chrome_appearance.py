"""P42 user screenshot: clear chrome must not reveal fixed black host."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
REC=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
WORKFLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class MatchedStatusChrome(unittest.TestCase):
    def test_no_black_host_under_clear_native_chrome(self):
        start=HOST.index('override func viewDidLoad()')
        end=HOST.index('@objc private func onHostAppBecameActive()',start)
        body=HOST[start:end]
        self.assertIn('view.backgroundColor = .systemBackground',body)
        self.assertNotIn('view.backgroundColor = .black',body)
        self.assertIn('transparentChrome.backgroundColor = .clear',body)
        self.assertIn('transparentChrome.isUserInteractionEnabled = false',body)
        self.assertIn('transparentChrome.isAccessibilityElement = false',body)
    def test_guest_theme_controls_backdrop_and_status_bar_text(self):
        helper=HOST.split('private func applyNativeChromeAppearance(',1)[1].split('private func chromeTop(',1)[0]
        for expected in (
            'guest.contentView?.traitCollection.userInterfaceStyle',
            'guest.traitCollection.userInterfaceStyle',
            'style != .dark',
            'view.backgroundColor = isLight ? .white : .black',
            'chromeStatusBarPreference = isLight ? .darkContent : .lightContent',
            'setNeedsStatusBarAppearanceUpdate()',
            'view.window?.rootViewController?.setNeedsStatusBarAppearanceUpdate()',
            'guest_chrome_appearance_applied',
            'guest_chrome_status_style_readback',
            'scene?.statusBarManager?.statusBarStyle.rawValue'):
            self.assertIn(expected,helper,expected)
        self.assertIn('override var preferredStatusBarStyle: UIStatusBarStyle',HOST)
    def test_only_active_reserved_guest_sets_opaque_native_chrome_backdrop(self):
        helper=HOST.split('private func updateNativeChromeSlots(',1)[1].split('private func onUnsafeGuestControls(',1)[0]
        self.assertIn('let top = active ? chromeTop(in: scene) : 0',helper)
        self.assertIn('if top > 0, let id = stack?.activeID,',helper)
        self.assertIn('applyNativeChromeAppearance(for: guest, scene: scene)',helper)
        self.assertNotIn('view.frame =',HOST.split('private func applyNativeChromeAppearance(',1)[1].split('private func chromeTop(',1)[0])
        self.assertNotIn('setFrame(',HOST.split('private func applyNativeChromeAppearance(',1)[1].split('private func chromeTop(',1)[0])
    def test_private_data_not_logged_and_apparently_correct_controls_present(self):
        for field in ('"chrome_dark_status_text"','"status_style_raw"'):
            self.assertIn(field,REC)
        helper=HOST.split('private func applyNativeChromeAppearance(',1)[1].split('private func chromeTop(',1)[0]
        for forbidden in ('bundleIdentifier','bundleID','accessibilityLabel','screenSnapshot','UIImageJPEGRepresentation','guest.title'):
            self.assertNotIn(forbidden,helper)
        self.assertIn('scarlet-v48-r6p42-matched-chrome-unsigned-20261113',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P42-MATCHED-CHROME-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__': unittest.main()

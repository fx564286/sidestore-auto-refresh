"""Classic switcher must be owned by LC bootstrap, not optional TweakLoader."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'integration/apply_scarlet_host.py'
SPEC=importlib.util.spec_from_file_location("scarlet_classic_integration", SOURCE)
GLUE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GLUE)
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
TAB=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
LEDGER=(ROOT/'HostApp/ScarletGuestSessionLedger.swift').read_text()

class ClassicSwitcherBootstrap(unittest.TestCase):
    def test_bootstrap_arms_switcher_without_tweakloader(self):
        original='''bool sideStoreExist = false;
    // Go!
    NSLog(@"[LCBootstrap] jumping to main %p", appMain);
'''
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            (root/'LiveContainer').mkdir()
            target=root/'LiveContainer/LCBootstrap.m'
            target.write_text(original)
            GLUE.add_classic_guest_switcher(root)
            generated=target.read_text()
            self.assertIn('if(!isLiveProcess && !isSideStore && !is32bit)',generated)
            self.assertIn('ScarletArmClassicGuestSwitcher();',generated)
            self.assertLess(generated.index('ScarletArmClassicGuestSwitcher();'),generated.index('// Go!'))
            self.assertIn('UIWindowDidBecomeVisibleNotification',generated)
            self.assertIn('NSClassFromString(@"ScarletFullscreenGuestTabInstaller")',generated)
            self.assertIn('dlopen(frameworkPath.UTF8String, RTLD_LAZY | RTLD_GLOBAL)',generated)
            self.assertNotIn('dontLoadTweakLoader',generated)
            self.assertNotIn('dontInjectTweakLoader',generated)

    def test_classic_window_selection_checks_all_eligible_scenes(self):
        self.assertIn('let candidates = UIApplication.shared.connectedScenes',TAB)
        self.assertIn('window.windowLevel == .normal',TAB)
        self.assertIn('let original = candidates.first(where: { $0.isKeyWindow })',TAB)
        self.assertIn('let scene = original.windowScene',TAB)

    def test_classic_handoff_preserves_only_token_matched_previous_process(self):
        self.assertIn('ScarletGuestSessionLedger.beginClassicTraceHandoff()',HOST)
        self.assertIn('ScarletGuestSessionLedger.cancelClassicTraceHandoff()',HOST)
        self.assertIn('ScarletGuestSessionLedger.bindClassicTrace()',TAB)
        self.assertIn('entry.classicToken == ticket.token',LEDGER)
        self.assertIn('"source": "classic_guest_previous_process"',LEDGER)
        self.assertIn('entry.createdAt.map { $0 >= currentProcessStart } ?? false',LEDGER)
        self.assertIn('store.removeObject(forKey: classicTraceTicketKey)',LEDGER)

    def test_classic_geometry_is_read_only_and_captured_at_exit(self):
        self.assertIn('captureClassicGeometry(window: guestWindow, event: "classic_geometry_on_exit")',TAB)
        self.assertIn('classic_geometry_on_mount',TAB)
        self.assertIn('classicGeometry: metrics',TAB)
        self.assertIn('safe_top_pt',TAB)
        self.assertIn('near_controls',TAB)
        self.assertIn('severe_nodes',TAB)
        self.assertIn('scan_complete',TAB)

if __name__=="__main__": unittest.main()

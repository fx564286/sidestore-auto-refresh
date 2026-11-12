"""R6P17: the resident guard must read the ORIGINAL LC preferences domain.

A host-side safe-top receipt alone is NOT evidence the guest fix has run;
the guest-owned arming receipt is emitted before UIWindow event observers.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_GENERATOR = (ROOT/'integration/apply_scarlet_host.py').read_text()
GUARD = (ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
HOST = (ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
PINNED_LC = Path('/tmp/scarlet-upstream-lc-20261112')


class ResidentOptInDomainTests(unittest.TestCase):
    def test_guest_bit_is_read_from_original_lc_defaults_not_guest_defaults(self):
        init = GUARD.split('void initScarletGuestIslandContentGuard(void)', 1)[1]
        self.assertIn('[NSUserDefaults.lcUserDefaults\n           boolForKey:@"Scarlet.ResidentSDKContract.V1"]', init)
        self.assertNotIn('[NSUserDefaults.standardUserDefaults\n           boolForKey:@"Scarlet.ResidentSDKContract.V1"]', init)
        self.assertIn('NSUserDefaults.isLiveProcess', init)

    def test_initialized_and_injected_after_guests_are_selected(self):
        self.assertIn('forKey:@"Scarlet.ResidentSDKContract.V1"', BOOTSTRAP_GENERATOR)
        self.assertIn('initScarletGuestIslandContentGuard();', BOOTSTRAP_GENERATOR)
        self.assertIn('initScarletGuestAudioIsolation();', BOOTSTRAP_GENERATOR)

    def test_guest_emits_independent_proof_of_activation(self):
        init = GUARD.split('void initScarletGuestIslandContentGuard(void)', 1)[1]
        self.assertIn('ScarletIslandReceipt(@"guest_root_guard_armed", 0, 0, 0);', init)
        self.assertLess(init.index('guest_root_guard_armed'), init.index('UIWindowDidBecomeVisibleNotification'))
        self.assertIn('guest_root_safearea_receipt', HOST)
        self.assertIn('Scarlet.Guest.IslandRootReceipt.V1', HOST)

    def test_safearea_formula_and_guest_size_are_unchanged(self):
        self.assertIn('CGFloat deficit = MIN(130, MAX(0, target - before));', GUARD)
        self.assertIn('root.additionalSafeAreaInsets = extra;', GUARD)
        self.assertNotIn('window.frame =', GUARD)
        self.assertNotIn('method_exchangeImplementations(', GUARD)
        self.assertNotIn('UIApplication.sharedApplication', GUARD.split('#import <Foundation/Foundation.h>', 1)[1])

    def test_pinned_upstream_replaces_defaults_after_guest_flag_was_set(self):
        # This source contract is the reason the patch is not another blind
        # Safe Area retry; this is a distinct initialization-data-flow bug.
        if not (PINNED_LC/'LiveContainer/Tweaks/NSUserDefaults.m').exists():
            self.skipTest('Pinned upstream checkout unavailable in independent CI')
        defaults=(PINNED_LC/'LiveContainer/Tweaks/NSUserDefaults.m').read_text()
        bootstrap=(PINNED_LC/'LiveContainer/LCBootstrap.m').read_text()
        self.assertIn('NSUserDefaults.standardUserDefaults = newStandardUserDefaults;', defaults)
        self.assertLess(bootstrap.index('NUDGuestHooksInit();'), bootstrap.index('initDead10ccFix();'))


if __name__=='__main__':
    unittest.main()

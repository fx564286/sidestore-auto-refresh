"""R6P23: on-device R6P22 scroll correction had zero eligible targets.

SourceCommit 22355c4b112e on iOS 27.2:
  guest 6438 62pt safe root, no unsafe controls, 0 zero-inset scrollers;
  guest 6447 62pt root, 8 unsafe controls, 7 unsafe images and 3 zero-
  adjusted-top-inset scrollers, but guest_scroll_no_unique_unsafe_target.
  Native refresh code 1, pairing_state_read_timeout before late restore.
Correct the evidence gap before introducing another app-wide layout write.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
H=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
R=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
N=(ROOT/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
A=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()

class R6P23(unittest.TestCase):
    def test_safe_root_unchanged_and_guarded_scroll_fix_preserved(self):
        for text in ('guest_root_already_safe',
                     'ScarletIslandScheduleContentProbe(window, root, target);',
                     'if(candidates.count != 1)', 'scroll.contentInset = inset;'):
            self.assertIn(text,G)
        self.assertNotIn('ScarletIslandScheduleScrollContentRepair(window, root, target);',G)
        helper=G.split('// R6P23: inspect ancestry',1)[1].split('static void ScarletIslandInspect',1)[0]
        for forbidden in ('window.frame =', 'root.additionalSafeAreaInsets =',
                          'scroll.contentInset =', 'view.frame =',
                          'method_exchangeImplementations', 'accessibilityLabel',
                          'bundleIdentifier', 'NSStringFromClass', 'screenshot'):
            self.assertNotIn(forbidden,helper)
    def test_unsafe_ancestry_is_distinguishable_without_guest_names(self):
        self.assertIn('static void ScarletIslandMeasureUnsafeOwner(',G)
        for name in ('unsafe_controls_in_scroll','unsafe_controls_outside_scroll',
                     'unsafe_controls_under_zero_inset_child_owner',
                     'unsafe_image_nodes_in_scroll','unsafe_image_nodes_outside_scroll'):
            self.assertIn('@"'+name+'"',G)
            self.assertIn('"'+name+'"',H)
            self.assertIn('"'+name+'"',R)
        self.assertIn('ancestor.nextResponder',G)
        self.assertIn('isKindOfClass:UIScrollView.class',G)
    def test_exact_scroll_exclusion_reasons_not_another_inset_guess(self):
        self.assertIn('ScarletIslandScrollClass classification = {0};',G)
        for field in ('seen','nested','not_top_full_width','not_vertical',
                      'existing_inset','not_at_top','busy',
                      'missing_unsafe_descendant','eligible',
                      'scan_budget_exhausted'):
            self.assertIn('@"'+field+'"',G)
            self.assertIn('"'+field+'"',H)
            self.assertIn('"'+field+'"',R)
        self.assertIn('guest_scroll_target_classifier',G)
        self.assertIn('guest_scroll_target_classifier", fields: fields',H)
        self.assertIn('if result == "guest_scroll_target_classifier" {',H)
    def test_original_sidestore_unknown_failure_stage_only(self):
        self.assertIn('private static func stagedFailureReason(',N)
        self.assertIn('let reason = safeFailureReason(error)',N)
        self.assertIn('guard reason == "sidestore_native_operation_failed" else { return reason }',N)
        for s in ('database','team','transport','refresh'):
            self.assertIn('stage = "'+s+'"',N)
        self.assertIn('stagedFailureReason(error, stage: stage)',N)
        for reason in ('native_unknown_database_stage',
                       'native_unknown_team_stage',
                       'native_unknown_transport_stage',
                       'native_unknown_appmanager_stage'):
            self.assertIn('"'+reason+'"',N)
            self.assertIn('"'+reason+'"',A)
    def test_existing_pairing_data_signing_and_install_preflight_untouched(self):
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()',N)
        self.assertIn('AppManager.shared.backgroundRefresh(',N)
        self.assertIn('CertificateManager.shared.activeCertificate != nil',N)
        self.assertIn('ensureActiveTeamForRefresh()',N)
        self.assertNotIn('revokeCertificate(',N)
        self.assertNotIn('deletePairing',N)

if __name__ == '__main__': unittest.main()

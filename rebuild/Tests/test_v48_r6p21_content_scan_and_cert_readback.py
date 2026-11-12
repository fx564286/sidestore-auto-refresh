"""R6P21 tested against actual R6P20 iPhone geometry and certificate sequence.

R6P20: PIDs 5497/5506 returned scan_capped=true at only 46/15 nodes;
SideStore certificate was checked BEFORE original Apple certificate provider.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUARD=(ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
HOST=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
REC=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
PANEL=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()

class DepthTruncationAndNativeSigningReadback(unittest.TestCase):
    def test_bounded_scan_visits_beyond_old_nine_levels_without_ui_mutations(self):
        self.assertIn('metrics->visited >= 1200',GUARD)
        self.assertIn('depth > 24',GUARD)
        self.assertNotIn('depth > 9',GUARD)
        self.assertNotIn('metrics->visited >= 640',GUARD)
        helper=GUARD.split('// R6P18: root Safe Area was already 62pt',1)[1].split('static void ScarletIslandInspect',1)[0]
        for forbidden in ('root.additionalSafeAreaInsets =','window.frame =',
                          'setNeedsLayout','layoutIfNeeded','bundleIdentifier',
                          'NSStringFromClass','accessibilityLabel','screenshot'):
            self.assertNotIn(forbidden,helper)
    def test_depth_count_and_observed_depth_are_separate_not_optimistic(self):
        self.assertIn('metrics->depthCapped = YES',GUARD)
        self.assertIn('metrics->countCapped = YES',GUARD)
        self.assertIn('metrics->maxDepthSeen = MAX(metrics->maxDepthSeen, depth)',GUARD)
        for key in ('depth_capped','count_capped','max_depth_seen'):
            self.assertIn('"'+key+'"',HOST)
            self.assertIn('"'+key+'"',REC)
            self.assertIn('@"'+key+'"',GUARD)
    def test_anonymous_text_and_image_receipts_exist_at_window_coordinates(self):
        for key in ('top_text_nodes','unsafe_text_nodes','first_unsafe_text_y',
                    'top_image_nodes','unsafe_image_nodes','first_unsafe_image_y',
                    'scroll_first_y'):
            self.assertIn('@"'+key+'"',GUARD)
            self.assertIn('"'+key+'"',HOST)
            self.assertIn('"'+key+'"',REC)
        self.assertIn('convertRect:view.bounds toView:window',GUARD)
        self.assertIn('scroll.adjustedContentInset.top < 2',GUARD)
        self.assertIn('safeY - 2',GUARD)
    def test_legacy_receipts_and_root_correction_unchanged(self):
        for x in ('guest_root_already_safe','guest_root_guard_armed','guest_content_geometry_probe',
                  'ScarletIslandScheduleContentProbe(window, root, target);',
                  'root.additionalSafeAreaInsets = extra;',
                  'CGFloat deficit = MIN(130, MAX(0, target - before));'):
            self.assertIn(x,GUARD)
    def test_native_provider_always_rechecks_sidestore_after_response(self):
        func=PANEL.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        start=func.index('let (archive, password) =')
        first=func.index('importExportedP12()',start)
        second=func.index('let nativeState = await ScarletNativeRefreshInspector.inspect()',first)
        log=func.index('"sidestore_signing_rechecked"',second)
        self.assertLess(start,first)
        self.assertLess(first,second)
        self.assertLess(second,log)
        for term in ('refreshManagedAppCount = nativeState.count',
                     'refreshHostManaged = nativeState.hostManaged',
                     'nativeState.signingReady ? "true" : "false"',
                     '"host_managed"','"reason": nativeState.reason'):
            self.assertIn(term,func)
        for forbidden in ('setActiveCertificate(','clearActiveCertificate(',
                          'SecItemDelete(','revokeCertificate('):
            self.assertNotIn(forbidden,func)
    def test_reread_does_not_claim_app_installed_or_silently_replace_certificate(self):
        func=PANEL.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        self.assertIn('if !nativeState.signingReady {',func)
        self.assertNotIn('installation_verified": "true"',func)
        self.assertIn('team_validation_pending_or_passed',func)
        self.assertIn('native_provider_same_certificate',PANEL)

if __name__=='__main__':unittest.main()

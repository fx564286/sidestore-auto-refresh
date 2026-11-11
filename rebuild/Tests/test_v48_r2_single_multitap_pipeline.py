"""V48-R3 regression: original V48 Pan methods preserved, not rewritten."""
from pathlib import Path
import hashlib
import unittest
ROOT=Path(__file__).resolve().parents[1]
TAB=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
STACK=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
WORKFLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

def sha(src):return hashlib.sha256(src.encode()).hexdigest()

class OriginalV48Preserved(unittest.TestCase):
    def test_unmodified_original_v48_pan_class(self):
        a=TAB.index('// UIkit pan tracks finger')
        b=TAB.index('@objc(ScarletFullscreenGuestTabInstaller)',a)
        self.assertEqual(sha(TAB[a:b]),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
    def test_unmodified_original_v48_pan_state_machine(self):
        a=TAB.index('    private static func panChanged(')
        b=TAB.index('    private static func resizeOverlay(',a)
        self.assertEqual(sha(TAB[a:b]),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
    def test_original_pan_used_by_both_execution_modes(self):
        self.assertEqual(TAB.count('ScarletGuestScreenPan(onChange: traceOriginalPan)'),2)
        self.assertEqual(TAB.count('let pan = UIPanGestureRecognizer(target: panHandler,'),2)
        self.assertIn('ScarletFullscreenGuestTabInstaller.makeResidentSwitcherWindow(',STACK)
        self.assertIn('let panHandler = ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
        self.assertNotIn('ScarletGuestSwitcherWindowFactory',TAB)
        self.assertNotIn('UILongPressGestureRecognizer(',TAB)
        self.assertIn('floating_tab_position_saved',TAB)
        self.assertIn('v48_original_pan_observed',TAB)
    def test_unrequested_app_add_hidden_not_original_implementation_deleted(self):
        self.assertIn('if false && !installChoices.isEmpty {',TAB)
        self.assertIn('SCARLET_RESIDENT_GUEST_ADD_INLINE',TAB)
        self.assertNotIn('inplace_first_launch',STACK)
        self.assertIn('slots.map { slot in',STACK)
    def test_experimental_off_authoritative_and_switch_remains_enabled(self):
        self.assertIn('.onChange(of: experimentalFullscreenResident)',HOST)
        self.assertIn('if experimentalFullscreenResident,',HOST)
        self.assertNotIn('.disabled(fullscreenStack.hasResidentSession)',HOST)
        self.assertIn('pilot_mode_disabled_immediately',HOST)
        self.assertIn('fullscreenStack.goHome()',HOST)
        self.assertIn('try await app.runApp(multitask: false)',HOST)
    def test_instrumentation_privacy_and_version(self):
        diag=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
        self.assertIn('retainedFiles = 8',diag)
        self.assertIn('maxFileBytes = 4_000_000',diag)
        self.assertIn('v48_original_pan_reused_in_resident',TAB)
        self.assertIn('resident_viewport_safearea_changed',STACK)
        self.assertIn('island_overlap_suspected',STACK)
        self.assertIn('Scarlet-Crystal-V48-R3-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('scarlet-v48-r3-unsigned-20261111',WORKFLOW)
if __name__=='__main__':unittest.main()

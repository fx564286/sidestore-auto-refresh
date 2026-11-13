"""P48 current guest-root corroboration gate, not a visual device pass."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
WORKFLOW = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()

class P48FreshGuestCropGate(unittest.TestCase):
    def test_first_sample_is_provisional_and_second_is_current(self):
        s=SOURCE.split("private func onUnsafeGuestControls(",1)[1].split("private func onNativeHeaderTransform(",1)[0]
        self.assertIn("if sample == 650",s)
        self.assertIn("chromeFirstUnsafeSampleByPID[pid] = (first: first, top: top)",s)
        self.assertIn("guard let initial = chromeFirstUnsafeSampleByPID[pid]",s)
        self.assertIn("abs(initial.top - top) <= 3",s)
        self.assertIn("chromeFreshUnsafeProofPIDs.insert(pid)",s)
        self.assertIn("guest_chrome_fresh_risk_proof_confirmed",s)
        self.assertIn("guest_chrome_fresh_risk_proof_missing",s)

    def test_p44_failure_and_early_timeout_cannot_crop(self):
        native=SOURCE.split("private func onNativeHeaderTransform(",1)[1].split("private func applyP43FallbackChrome(",1)[0]
        self.assertIn("applyP43FallbackChrome(pid: pid,",native)
        crop=SOURCE.split("private func applyP43FallbackChrome(",1)[1].split("func setResidentOutsideDismissEnabled(",1)[0]
        self.assertLess(crop.index("guard chromeFreshUnsafeProofPIDs.contains(pid)"),crop.index("chromeEligiblePIDs.insert(pid)"))
        self.assertIn("guest_chrome_stale_crop_withheld",crop)
        self.assertIn("updateNativeChromeSlots(scene)",crop)

    def test_pid_provenance_cleared_on_guest_retirement(self):
        self.assertIn("chromeFirstUnsafeSampleByPID.removeValue(forKey: old.pid)",SOURCE)
        self.assertIn("chromeFreshUnsafeProofPIDs.remove(old.pid)",SOURCE)
        self.assertIn('"scale_milli": "1000"',SOURCE)

    def test_p47_fallback_and_release_are_kept_separate(self):
        self.assertIn('fix/scarlet-v48-r6p47-lifecycle-statusbar-20261113',WORKFLOW)
        self.assertIn('fix/scarlet-v48-r6p48-fresh-proof-crop-gate-20261113',WORKFLOW)
        self.assertIn('scarlet-v48-r6p48-fresh-proof-crop-unsigned-20261113',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P48-FRESH-PROOF-UNSIGNED.ipa',WORKFLOW)

if __name__ == '__main__': unittest.main()

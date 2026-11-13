"""P50 source contracts: scroll risk is not a license to crop the full FBScene."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
WF=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P50ScrollCropVeto(unittest.TestCase):
    def test_unaudited_scroll_metrics_reused_from_guest_not_invented(self):
        self.assertIn('var onTopRiskMeasured: ((Int32, Int, Int, Int, Int, Int, Int) -> Void)?',SRC)
        self.assertIn('let scrolling = (row["unsafe_controls_in_scroll"] as? NSNumber)?.intValue ?? -1',SRC)
        self.assertIn('let stationary = (row["unsafe_controls_outside_scroll"] as? NSNumber)?.intValue ?? -1',SRC)
        self.assertIn('onTopRiskMeasured?(pid, unsafe, first, target, sample,',SRC)
        self.assertIn('inScroll: inScroll, outsideScroll: outside',SRC)

    def test_two_independent_scroll_samples_veto_before_full_crop(self):
        sample=SRC.split('private func onUnsafeGuestControls(',1)[1].split('private func onNativeHeaderTransform(',1)[0]
        self.assertLess(sample.index('chromeFirstScrollRiskByPID[pid] ='),sample.index('if let scroll = chromeFirstScrollRiskByPID[pid]'))
        self.assertIn('scroll.inScroll > 0, inScroll > 0',sample)
        self.assertIn('chromeScrollCropVetoPIDs.insert(pid)',sample)
        self.assertIn('guest_chrome_scroll_crop_veto_armed',sample)
        self.assertIn('guard let initial = chromeFirstUnsafeSampleByPID[pid]',sample)
        self.assertLess(sample.index('guard let initial = chromeFirstUnsafeSampleByPID[pid]'),sample.index('chromeScrollCropVetoPIDs.insert(pid)'))
        crop=SRC.split('private func applyP43FallbackChrome(',1)[1].split('func setResidentOutsideDismissEnabled(',1)[0]
        self.assertLess(crop.index('guard !chromeScrollCropVetoPIDs.contains(pid)'),crop.index('chromeEligiblePIDs.insert(pid)'))
        self.assertIn('guest_chrome_scroll_surface_crop_withheld',crop)
        self.assertIn('full_fbscene_preserved_scroll_owner',crop)

    def test_retired_pid_does_not_leak_crop_veto_to_new_guest(self):
        self.assertIn('chromeFirstScrollRiskByPID.removeValue(forKey: old.pid)',SRC)
        self.assertIn('chromeScrollCropVetoPIDs.remove(old.pid)',SRC)
        self.assertIn('chromeFirstUnsafeSampleByPID.removeValue(forKey: old.pid)',SRC)
        self.assertIn('chromeFreshUnsafeProofPIDs.remove(old.pid)',SRC)

    def test_p49_status_and_p48_original_viewport_preserved(self):
        self.assertIn('hostStatusBarScheme = next',SRC)
        self.assertIn('let top = reserved ? chromeTop(in: scene) : 0',SRC)
        self.assertIn('let rect = contentSlot(in: scene, reserved: reserved)',SRC)
        self.assertIn('chromeFreshUnsafeProofPIDs.contains(pid)',SRC)
        self.assertIn('fix/scarlet-v48-r6p49-key-host-statusbar-20261113',WF)
        self.assertIn('fix/scarlet-v48-r6p50-scroll-crop-veto-20261113',WF)
        self.assertIn('scarlet-v48-r6p50-scroll-crop-veto-unsigned-20261113',WF)
        self.assertIn('Scarlet-Crystal-V48-R6P50-SCROLL-CROP-VETO-UNSIGNED.ipa',WF)

if __name__=='__main__': unittest.main()

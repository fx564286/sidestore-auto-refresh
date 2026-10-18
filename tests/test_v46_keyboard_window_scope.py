"""V46 regression: window ownership, guest-scoped focus and no global resign."""
import importlib.util
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v46",ROOT/"scripts/patch_v46_keyboard_window_scope.py")
v46=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v46)

class KeyboardWindowScope(unittest.TestCase):
 def test_window_ownership_and_no_global_resign(self):
  # Focus-source snippet from pinned LiveContainer after V27/V28 processing.
  source="""// NRG_V27_GUEST_SWITCH_LIFECYCLE
// NRG_V28_GUEST_LIFECYCLE
// NRG_V27_GEOMETRY_FADE_ONLY
        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene else {
            return false
        }

        for window in windowScene.windows {
    private func findMultitaskView(in view: UIView, withUUID uuid: String) -> UIView? {
        apps.first { $0.appUUID == uuid }?.view
    }
        var previousGuests = 0
        for app in apps {
            guard let old = app.view, old !== targetView, old.window === window else { continue }
            // NRG_V28_GUEST_LIFECYCLE: close remote responder and background old scene.
            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
                vc.appSceneVC.contentView?.endEditing(true)
                if PiPManager.shared?.isPiP(withDecoratedVC: vc) != true {
                    vc.appSceneVC.lcSetGuestSceneForeground(false)
                }
            }
            previousGuests += 1
        }
        window.endEditing(true)
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder),
                                       to: nil, from: nil, for: nil)
        NSLog("[NRG_V27_GUEST_FOCUS] previous_guests=%ld resign_requested=1", previousGuests)
"""
  result=v46.patch(source)
  self.assertIn("let owningWindow = guest.window",result)
  self.assertIn("guest.window === candidateWindow",result)
  self.assertIn("oldWindow.windowScene === targetScene",result)
  self.assertNotIn("connectedScenes.first",result)
  self.assertNotIn("window.endEditing(true)",result)
  self.assertNotIn("UIApplication.shared.sendAction",result)
  self.assertIn("PiPManager.shared?.isPiP(withDecoratedVC: vc)",result)
  self.assertEqual(v46.patch(result),result)

 def test_upstream_changes_fail_before_mutation(self):
  with self.assertRaisesRegex(RuntimeError,"requires existing V27/V28"):
   v46.patch("// unrelated upstream source")

 def test_real_generated_sources_if_available(self):
  root=os.environ.get("V46_PATCHED_LIVECONTAINER")
  if not root:self.skipTest("Set V46_PATCHED_LIVECONTAINER during post-patch CI")
  source=(Path(root)/v46.DOCK).read_text()
  self.assertEqual(v46.patch(source),source)
  self.assertIn("NRG_V28_GUEST_LIFECYCLE",source)

if __name__=="__main__":
 unittest.main()

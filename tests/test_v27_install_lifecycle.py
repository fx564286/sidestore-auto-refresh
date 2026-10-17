"""V27 regression checks: bounded, idempotent patches and preserved flows."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V27GuestSwitch(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("patch_v27_guest_switch.py")

    def fixture(self, root):
        target = root / self.mod.PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('''// MULTITASK_DOCK_START_COLLAPSED_V3
// GUEST_RESUMED_EXISTING
        passURLSchemeToView(targetView)
        animateViewAppearance(targetView, from: center, in: window)
    private func passURLSchemeToView(_ view: UIView) {
    }
    private func animateViewAppearance(_ view: UIView, from center: CGPoint?, in window: UIWindow) {
        let pipManager = PiPManager.shared!
        let scale = Constants.bringToFrontScale
    }
    private func bringViewToFront(_ view: UIView, in window: UIWindow) {
    }
''')
        return target

    def test_keyboard_focus_and_frame_are_preserved_on_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = self.fixture(root)
            self.mod.patch(root)
            result = target.read_text()
            self.assertIn('prepareKeyboardForGuestSwitch(targetView: targetView, in: window)', result)
            self.assertIn('old.endEditing(true)', result)
            self.assertIn('window.endEditing(true)', result)
            self.assertIn('resignFirstResponder', result)
            self.assertIn('view.transform = .identity', result)
            self.assertNotIn('view.transform = CGAffineTransform(scaleX:', result)
            self.assertNotIn('view.frame = origFrame', result)
            self.mod.patch(root)
            self.assertEqual(target.read_text(), result)

    def test_does_not_rewrite_unknown_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = self.fixture(root)
            source = target.read_text().replace('passURLSchemeToView(targetView)', 'unknownSwitch(targetView)')
            target.write_text(source)
            with self.assertRaises(SystemExit):
                self.mod.patch(root)
            self.assertEqual(target.read_text(), source)


class V27Provisioning(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("patch_v27_provisioning.py")

    def fixture(self, root):
        target = root / self.mod.PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('''// LC_PROVISIONING_PARENT_ID_UPSTREAM_V1
        self.setProgress(10)

        self.debugLog("[FetchProvisioningProfiles] Preparing main provisioning profile
        try await withThrowingTaskGroup(of: (String, ALTProvisioningProfile).self) { group in
        }
    private func getPreferredBundleID(for targetAppBundle: ALTApplication, team: ALTTeam) async -> String? {
    }
        let preferredBundleID = await self.getPreferredBundleID(for: targetAppBundle, team: team)
''')
        return target

    def test_preflight_unique_extension_ids_and_serial_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = self.fixture(root)
            self.mod.patch(root)
            result = target.read_text()
            self.assertIn('nrgV27PreflightFreeTeamCapacity', result)
            self.assertIn('missing <= available', result)
            self.assertIn('if team.type == .free', result)
            self.assertIn('let ordered = targetAppBundle.appExtensions.sorted', result)
            self.assertIn('for: parentAppBundle ?? targetAppBundle', result)
            self.assertIn('candidates.append(parentID + suffix)', result)
            self.assertIn('DeveloperPortalProxy.shared.fetchAppIDs(for: team)', result)
            self.assertNotIn('session: ALTAppleAPISession', result)
            self.assertNotIn('session: session', result)
            self.assertNotIn('removeItem(at:', result)
            self.mod.patch(root)
            self.assertEqual(target.read_text(), result)

    def test_missing_existing_parent_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = self.fixture(root)
            source = target.read_text().replace('let preferredBundleID = await self.getPreferredBundleID',
                                                'let preferredBundleID = await other')
            target.write_text(source)
            with self.assertRaises(SystemExit):
                self.mod.patch(root)
            self.assertEqual(target.read_text(), source)


if __name__ == "__main__":
    unittest.main()

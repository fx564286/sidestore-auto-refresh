"""Regression: the rebuilt Scarlet UI must never expose SideStore's guest screen.

These are executable packaging-level tests. They do not certify Apple login,
profile renewal, IPA signing or a physical-device install.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load_module("scarlet_pair_packager", "integration/package_paired.py")
verifier = load_module("scarlet_pair_verifier", "integration/verify_engines.py")

GUEST_UI_ITEM = {
    "Type": "PSToggleSwitchSpecifier",
    "Title": "Open SideStore",
    "Key": "LCOpenSideStore",
    "DefaultValue": False,
}
OTHER_ITEM = {
    "Type": "PSToggleSwitchSpecifier",
    "Title": "Keep existing container settings",
    "Key": "LCOriginalOption",
    "DefaultValue": True,
}


class SideStoreBackendOnlyCompatibility(unittest.TestCase):
    def test_package_removes_only_guest_ui_entry_without_losing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "Settings.bundle"
            settings.mkdir()
            original = {
                "StringsTable": "Root",
                "PreferenceSpecifiers": [OTHER_ITEM, GUEST_UI_ITEM, {"Type": "PSGroupSpecifier"}],
            }
            (settings / "Root.plist").write_bytes(plistlib.dumps(original))
            self.assertEqual(packager.remove_sidestore_ui_preference(settings), 1)
            updated = plistlib.loads((settings / "Root.plist").read_bytes())
            self.assertEqual(updated["PreferenceSpecifiers"],
                             [OTHER_ITEM, {"Type": "PSGroupSpecifier"}])
            self.assertEqual(updated["StringsTable"], "Root")
            self.assertEqual(packager.remove_sidestore_ui_preference(settings), 0)

    def test_missing_settings_bundle_is_safe_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "NoSettings.bundle"
            self.assertEqual(packager.remove_sidestore_ui_preference(settings), 0)
            self.assertFalse(settings.exists())

    def test_real_zip_verification_rejects_leaked_side_store_toggle(self):
        prefix = "Payload/LiveContainer.app/"
        path = prefix + "Settings.bundle/Root.plist"
        for entries, expected in (([OTHER_ITEM], True),
                                  ([OTHER_ITEM, GUEST_UI_ITEM], False)):
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as z:
                z.writestr(path, plistlib.dumps({"PreferenceSpecifiers": entries}))
            data.seek(0)
            with zipfile.ZipFile(data) as z:
                if expected:
                    self.assertTrue(verifier.verify_no_sidestore_screen_toggle(z, prefix))
                else:
                    with self.assertRaisesRegex(AssertionError,
                                                "legacy SideStore screen navigation"):
                        verifier.verify_no_sidestore_screen_toggle(z, prefix)

    def test_no_settings_bundle_in_zip_is_safe(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            z.writestr("Payload/LiveContainer.app/Info.plist", b"placeholder")
        data.seek(0)
        with zipfile.ZipFile(data) as z:
            self.assertTrue(verifier.verify_no_sidestore_screen_toggle(
                z, "Payload/LiveContainer.app/"))

    def test_unverified_auth_signing_release_status_not_promoted(self):
        source = (ROOT / "integration/package_paired.py").read_text()
        for marker in ('"sideStoreEngineTransportConnected":False',
                       '"loginDeviceVerified":False',
                       '"codesignedWithAppleProfile":False',
                       '"userDeviceInstallationVerified":False',
                       '"sideStoreSettingsScreenNavigationExposed":False'):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()

"""V88: dead-code deletion instead of layering the V87 post-patch."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import os

ROOT = Path(__file__).resolve().parents[1]


def imported(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT/"scripts"/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v72 = imported("patch_v72_overflow_longpress.py","v72_v88")
v76 = imported("patch_v76_native_guest_switcher.py","v76_v88")
audit = imported("verify_v88_canonical_guest_sources.py","audit_v88")


class CanonicalGuestTests(unittest.TestCase):
    def test_old_overlay_is_physically_removed(self):
        self.assertFalse((ROOT/"scripts/patch_v87_guest_button_switcher.py").exists())
        self.assertFalse((ROOT/"tests/test_v87_guest_button_switcher.py").exists())
        workflow = (ROOT/".github/workflows/livecontainer-build.yml").read_text()
        self.assertNotIn("python3 builder/scripts/patch_v87_guest_button_switcher.py", workflow)
        self.assertIn("verify_v88_canonical_guest_sources.py",workflow)

    def test_full_picker_exists_once_in_original_v72_source(self):
        source = v72.SWIFT_SWITCHER
        self.assertEqual(source.count("SCARLET_V87_NATIVE_RUNNING_GUESTS"),1)
        self.assertEqual(source.count("func nrgV72PresentGuestSwitcher"),1)
        self.assertIn("DataManager.shared.model.apps",source)
        self.assertIn("MultitaskWindowManager.appDict.values",source)
        self.assertIn("SCARLET_V89_IOS161_AVAILABILITY",source)
        self.assertIn("if #available(iOS 16.1, *)",source)
        self.assertLess(source.index("if #available(iOS 16.1, *)"),source.index("MultitaskWindowManager.appDict.values"))
        self.assertIn("var nativeFolders = Set<String>()",source)
        self.assertIn("controller.isAppRunning",source)
        self.assertIn("openExistingAppWindow(dataUUID: guest.folder)",source)
        self.assertIn("bringMultitaskViewToFront(uuid: guest.folder)",source)
        self.assertIn("48 * 60 * 60",source)
        self.assertIn("container-folder-name",source)
        self.assertIn("model.uiContainers.contains",source)
        self.assertNotIn("ActivityKit",source)

    def test_single_return_longpress_owner_presentation(self):
        method = v76.SWITCH_METHOD
        self.assertEqual(method.count("SCARLET_V87_HOST_GUEST_PICKER"),1)
        self.assertEqual(method.count("lcV76ShowInstalledGuestSwitcher"),2) # declaration + main-thread handoff
        self.assertIn("source.window",method)
        self.assertIn("owner.rootViewController",method)
        self.assertNotIn("UIApplicationStateActive",method)
        self.assertNotIn("ignored=presenter_has_no_window",method)
        self.assertIn("nrgV72PresentGuestSwitcherFrom:presenter",method)
        self.assertIn("sourceView:source",method)
        self.assertIn("minimumPressDuration = 0.55",v76.LONG_PRESS)

    def test_generated_source_audit_reports_retired_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for file in set(audit.REQUIRED) | set(audit.BANNED):
                tokens=audit.REQUIRED.get(file,{})
                p=root/file
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text("\n".join(token for token,count in tokens.items() for i in range(count)))
            # Include known model metadata and only genuine host-registered guest URLs
            p=root/audit.DOCK
            p.write_text(p.read_text()+"\nDataManager.shared.model.apps\nlastLaunched\n48 * 60 * 60")
            p=root/audit.PLIST
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(plistlib.dumps({"CFBundleURLTypes":[{"CFBundleURLSchemes":["scarletcrystal251"]}]}))
            result=audit.audit(root,ROOT)
            self.assertEqual(result["status"],"PASS",result["errors"])
            dock=root/audit.DOCK
            dock.write_text(dock.read_text()+"\nimport ActivityKit")
            bad=audit.audit(root,ROOT)
            self.assertEqual(bad["status"],"FAIL")
            self.assertTrue(any("import ActivityKit" in err for err in bad["errors"]))

    def test_compiled_final_source_when_available(self):
        source = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not source or os.environ.get("V88_CANONICAL_SOURCE") != "1":
            return
        result = audit.audit(Path(source),ROOT)
        self.assertEqual(result["status"],"PASS",result["errors"])

if __name__ == "__main__":
    unittest.main()

"""V147 focused regression from successful V144; no unexpected unittest skips."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]

def plugin(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ui=plugin("patch_v147_from_v144")
direct=plugin("patch_v147_direct")
audit=plugin("audit_v107_active_guest_ui")

class V147Regression(unittest.TestCase):
    def test_contracts_reject_unrelated_source(self):
        with self.assertRaises(ValueError):ui.patch("unrelated")
        with self.assertRaises(ValueError):direct.boot("unrelated")
        with self.assertRaises(ValueError):direct.shell("unrelated")

    def test_no_second_overlay_or_private_auth_mutation(self):
        src=(ROOT/"scripts"/"patch_v147_from_v144.py").read_text()
        self.assertNotIn("UIWindow(frame:",src)
        self.assertNotIn("SecItemDelete(",src)
        self.assertNotIn("removeProvisioningProfile(",src)
        self.assertNotIn("clearKeychain",src)
        self.assertIn("UIGlassEffect(style: .regular)",src)
        self.assertIn("SCARLET_V147_FROM_V144_GLASS_OWNER",src)

    def test_compiled_runtime_contracts_when_source_available(self):
        path=os.environ.get("V147_PATCHED_LIVECONTAINER")
        if not path:
            # Prepatch suite: test registration and the source contract
            # without skipping. Postpatch suite passes real generated root.
            self.assertEqual(ui.FILE.as_posix(),"MultitaskSupport/MultitaskDockView.swift")
            self.assertEqual(direct.BOOT.as_posix(),"LiveContainer/LCBootstrap.m")
            return
        root=Path(path)
        dock=(root/ui.FILE).read_text()
        boot=(root/direct.BOOT).read_text()
        shell=(root/direct.SHELL).read_text()
        self.assertEqual(ui.patch(dock),dock)
        self.assertEqual(direct.boot(boot),boot)
        self.assertEqual(direct.shell(shell),shell)
        self.assertEqual(dock.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',dock)
        self.assertEqual(dock.count('"scarlet.v147.row.glass"'),3)
        self.assertNotIn("secondarySystemBackground.withAlphaComponent(0.56)",dock)
        self.assertIn("바깥을 누르면 창 관리 닫기",dock)
        self.assertIn("outsideObserver.install(with: outsideTap)",dock)
        self.assertIn("observer.uninstall()",dock)
        self.assertIn("drag.cancelsTouchesInView = NO;",boot)
        self.assertIn("[SCARLET_V147_DIRECT] event=tap",boot)
        self.assertIn("route=host result=presented",shell)
        result=audit.inspect(root)
        self.assertEqual(result.get("status"),"PASS",result.get("problems"))

    def test_historical_audit_remains_version_aware(self):
        src=(ROOT/"scripts"/"audit_v107_active_guest_ui.py").read_text()
        self.assertIn('SCARLET_V147_FROM_V144_GLASS_OWNER',src)
        self.assertIn('("창 닫기", "closeWindow")',src)
        self.assertIn('("앱 닫기", "closeWindow")',src)

if __name__=="__main__":unittest.main()

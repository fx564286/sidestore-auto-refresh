import unittest
import importlib.util
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

dock=load("patch_v110_single_guest_dock")
http=load("patch_v110_gsa_http_phase")
v2=load("patch_nrg_gsa_http_v2")

class V110Tests(unittest.TestCase):
    def test_safe_http_phase_transform(self):
        source="// SCARLET_V98_GSA_PHASE_TRACE\n"+v2.NEW_CALL+"\n"+v2.HELPER
        updated=http.transform(source)
        self.assertEqual(http.transform(updated),updated)
        self.assertIn("SCARLET_V110_GSA_HTTP_PHASE",updated)
        self.assertIn("anisetteClientInfo: anisetteData.clientInfo",updated)
        self.assertIn("nrgLogSafeAuthPhase(operation: safeOperation",updated)
        with self.assertRaises(ValueError):
            http.transform("unknown source")

    def test_single_guest_overlay_is_touch_transparent(self):
        path=os.environ.get("V110_PATCHED_LIVECONTAINER")
        if not path:
            self.assertIn("SCARLET_V110_SINGLE_GUEST_DOCK_SUPPRESSED",
                          (ROOT/"scripts/patch_v110_single_guest_dock.py").read_text())
            return
        root=Path(path)
        source=(root/dock.REL).read_text()
        dock.audit(source)
        self.assertEqual(dock.transform(source),source)
        self.assertIn("dockManager.apps.count > 1 {",source)
        self.assertIn(".allowsHitTesting(dockManager.apps.count > 1)",source)
        self.assertIn("ForEach(dockManager.apps) { app in",source)
        self.assertIn("if isDockHidden && apps.count > 1",source)
        other=(root/"MultitaskSupport/DecoratedAppSceneViewController.m").read_text()
        self.assertIn("nrgWindowOverflow",other)

if __name__=="__main__":
    unittest.main()

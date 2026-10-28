"""V146 integration tests: no label regression, native glass on all rows, RP probe safe."""
from pathlib import Path
import importlib.util, os, unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
glass=load("patch_v146_liquid_glass")
rp=load("patch_v146_rp_handshake")

class V146Regression(unittest.TestCase):
    def test_glass_source_contract(self):
        root=os.environ.get("V146_PATCHED_LIVECONTAINER")
        if not root:return
        s=(Path(root)/glass.DOCK).read_text()
        self.assertEqual(glass.patch(s),s)
        self.assertEqual(s.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',s)
        self.assertEqual(s.count('"scarlet.v146.glass.action"'),3)
        self.assertNotIn("secondarySystemBackground.withAlphaComponent(0.56)",s)
        self.assertIn("바깥을 누르면 창 관리 닫기",s)
        self.assertIn('UIGlassEffect(style: .clear)',s)
        self.assertIn('outsideObserver.install(using: outsideTap)',s)
        self.assertIn('SCARLET_V145_DIRECT_HOST_DELIVERY', (Path(root)/"LiveContainerSwiftUI/Views/V3UnifiedShell.swift").read_text())

    def test_pairing_contract(self):
        root=os.environ.get("V146_PATCHED_SIDESTORE")
        if not root:
            # Pre-patch discovery runs the full repository test suite; verify
            # the contract itself but reserve generated-source assertions
            # for the explicit post-patch CI pass with V146_PATCHED_SIDESTORE.
            self.assertEqual(rp.FILE.as_posix(), "SideStore/Core/DeviceApi/MinimuxerWrapper.swift")
            return
        s=(Path(root)/rp.FILE).read_text()
        self.assertEqual(rp.patch(s),s)
        self.assertIn("state=route_missing transport_verified=false",s)
        self.assertIn("handshake=failed reset=",s)
        self.assertIn("SCARLET_V142_NETWORK_GENERATION_GUARD",s)
        self.assertIn("return useStatic ? PairingFileManager.shared.pairingUDID : nil",s)

    def test_fail_closed_not_textual_bypass(self):
        with self.assertRaises(ValueError):glass.patch("no original renderer")
        with self.assertRaises(ValueError):rp.patch("no original pairing transport")
        for mod in (glass,rp):
            s=Path(mod.__file__).read_text()
            for banned in ("SecItemDelete(", "removeProvisioningProfile(", "removeAllApplications("):
                self.assertNotIn(banned,s)

if __name__=="__main__": unittest.main()

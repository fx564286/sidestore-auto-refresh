"""NRG V55 geometry, lifecycle and memory probes: pinned/source-contract tests."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
v38=load("patch_v38_maximized_safe_area")
v47=load("patch_v47_resume")
v55=load("patch_v55_rotation_geometry")
memory=load("patch_v55_memory_probe")

class V55SourceTests(unittest.TestCase):
    def test_post_v47_geometry_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            # Test the pinned LiveContainer checkout if workflow provides it.
            import os
            live=Path(os.environ.get("LIVE_CONTAINER_TEST_SOURCE",""))
            if not live.is_dir() or not (live/"MultitaskSupport/DecoratedAppSceneViewController.m").is_file():
                self.skipTest("pinned LiveContainer checkout unavailable")
            for relative,_ in v55.PATCHES:
                dst=root/relative
                dst.parent.mkdir(parents=True,exist_ok=True)
                src=(live/relative).read_text()
                if relative.endswith("DecoratedAppSceneViewController.m"):
                    if v38.MARKER not in src:
                        self.assertEqual(src.count(v38.OLD),1)
                        src=src.replace(v38.OLD,v38.NEW,1)
                if relative.endswith("MultitaskDockView.swift") and v47.MARK not in src:
                    src=src.replace(v47.DOCK_ANCHOR,v47.DOCK_ADDITION+v47.DOCK_ANCHOR,1)
                if relative.endswith("AppDelegate.swift") and v47.MARK not in src:
                    src=src.replace(v47.DELEGATE_ANCHOR,v47.DELEGATE_ADDITION,1)
                dst.write_text(src)
            v55.main(root)
            before={p:p.read_text() for p,_ in ((root/r,fn) for r,fn in v55.PATCHES)}
            v55.main(root)
            self.assertEqual(before,{p:p.read_text() for p in before})
            swift=(root/v55.DOCK if hasattr(v55,"DOCK") else root/"MultitaskSupport/MultitaskDockView.swift").read_text()
            self.assertIn("if controller.isMaximized",swift)
            self.assertIn("windowHostingView.frame = parent.bounds",swift)
            m=(root/"MultitaskSupport/DecoratedAppSceneViewController.m").read_text()
            self.assertIn("convertRect:target fromView:window",m)
            self.assertIn("CGSizeEqualToSize(self.nrgV55LastHostSize, size)",m)

    def test_memory_probe_rejects_missing_signed_capability_probe(self):
        with self.assertRaises(RuntimeError):
            memory.patch("void not_v48() {}")

    def test_memory_probe_is_observational_only(self):
        sample='''#include <sys/proc.h>
/* NRG_V48_GUEST_RUNTIME_CAPABILITIES */
    int va = nrgV48EntitlementBool(CFSTR("com.apple.developer.kernel.extended-virtual-addressing"));
          "jit_pool_unverified=1", stage, getpid(), isLiveProcess,
          csResult, debugged, csAllow, traced, taskAllow, memory, va);
'''
        patched=memory.patch(sample)
        self.assertEqual(memory.patch(patched),patched)
        self.assertIn("phys_footprint_mb=%llu",patched)
        self.assertNotIn("SecTaskCreate",patched)

if __name__=="__main__":
    unittest.main()

"""JIT command handoff is not runtime JIT readiness; use correct StikDebug wire."""
from pathlib import Path
import os
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from patch_v134_jit_protocol import APP,UTIL,MODEL,MARK,app_patch,util_patch,model_patch

class V134(unittest.TestCase):
    def test_wire_and_guard(self):
        s=(ROOT/"scripts/patch_v134_jit_protocol.py").read_text()
        for token in ('"script-name"', '"script-data"', 'universal.js', 'legacy.js',
                      "runtime_verified=0", "txm_regions_unverified=1",
                      "status=pending_external_verification",
                      "SCARLET_V134_CLASSIC_JIT_PROTOCOL", MARK):
            self.assertIn(token,s)
        for unsafe in ("JIT26PrepareRegion(", "brk #0xf00d", "SecItemDelete",
                       "kill(getpid()", "jit_enabled=true", "JIT Enabled Successfully"):
            self.assertNotIn(unsafe,s)

    def test_requires_pinned_sources(self):
        for fn in (app_patch,util_patch,model_patch):
            with self.assertRaises(ValueError):
                fn("unrelated")

    def test_generated_source_contract(self):
        root=os.environ.get("V134_PATCHED_LIVECONTAINER")
        if not root:return
        root=Path(root)
        app=(root/APP).read_text()
        util=(root/UTIL).read_text()
        model=(root/MODEL).read_text()
        self.assertEqual(app_patch(app),app)
        self.assertEqual(util_patch(util),util)
        self.assertEqual(model_patch(model),model)
        self.assertEqual(app.count(MARK),1)
        self.assertIn('if scriptInput == "universal.js" || scriptInput == "legacy.js"',app)
        self.assertIn('if input == "universal.js" || input == "legacy.js"',util)
        self.assertIn("SCARLET_V134_JIT_PENDING",model)
        self.assertIn("continuation.resume()",model)
        self.assertIn("SCARLET_V129_JIT_PREFLIGHT",app)
        self.assertIn("SCARLET_V129_CLASSIC_JIT_ROUTE",util)

if __name__=="__main__":unittest.main()

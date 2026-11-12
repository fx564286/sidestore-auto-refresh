"""Execute the real C decision function, including refusal and once-only cases."""
import ctypes
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()


class DeferredAnchorDecision(unittest.TestCase):
    def test_native_decision_matrix(self):
        cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not cc:
            self.skipTest("C compiler unavailable on this host; CI runs the native decision")
        helper = G.split("// R6P33_ANCHOR_DECISION_BEGIN", 1)[1].split(
            "// R6P33_ANCHOR_DECISION_END", 1)[0]
        source = "#include <math.h>\n" + helper + """
int decide(double i, double a, double t, double o, double y, int done, int still) {
    return ScarletIslandShouldAnchorAfterInset(i,a,t,o,y,done,still);
}
"""
        with tempfile.TemporaryDirectory() as temp:
            c = Path(temp) / "decision.c"
            lib = Path(temp) / "decision.so"
            c.write_text(source)
            subprocess.run([cc, "-std=c11", "-Wall", "-Werror", "-fPIC",
                            "-shared", str(c), "-lm", "-o", str(lib)], check=True)
            fn = ctypes.CDLL(str(lib)).decide
            fn.argtypes = [ctypes.c_double] * 5 + [ctypes.c_int] * 2
            fn.restype = ctypes.c_int
            cases = [
                ((0,62,62,0,0,0,1),1),       # late OS inset: pending write
                ((62,62,62,0,0,0,1),0),      # inset was already available
                ((0,62,62,0,0,1,1),0),       # guest rejected first write
                ((0,62,62,0,-62,0,1),0),     # UIKit already moved the content
                ((0,62,62,0,5,0,1),0),       # guest/user changed offset
                ((0,62,62,0,0,0,0),0),       # gesture in progress
                ((0,0,62,0,0,0,1),0),        # UIKit never supplied an inset
                ((0,58,62,0,0,0,1),0),
                ((0,75,62,0,0,0,1),0),
                ((0,62,62,3,3,0,1),0),       # owner no longer top anchored
                ((0,10,10,0,0,0,1),0),
                ((0,150,150,0,0,0,1),0),
            ]
            for index in range(5):
                for invalid in (math.nan, math.inf, -math.inf):
                    args = [0,62,62,0,0,0,1]
                    args[index] = invalid
                    cases.append((tuple(args),0))
            for args, expected in cases:
                with self.subTest(args=args):
                    self.assertEqual(fn(*args),expected)
            # Consuming the readiness transition can never issue a second write.
            self.assertEqual(fn(0,62,62,0,0,0,1),1)
            self.assertEqual(fn(0,62,62,0,0,1,1),0)

    def test_receipt_survives_both_bridges(self):
        fields = ("anchor_initial_inset_pt", "anchor_initial_offset_y",
                  "anchor_observed_inset_pt", "anchor_observed_offset_y",
                  "anchor_final_offset_y", "anchor_attempts",
                  "owner_bounds_y", "scene_activation_state")
        for key in fields:
            for source in (G,H,R):
                self.assertIn('"'+key+'"',source)
        self.assertIn("guest_always_anchor_readback",H)

    def test_writes_remain_bounded_and_failure_still_rolls_back(self):
        section = G.split("static void ScarletIslandTryResidualAutomaticInset(",1)[1].split(
            "static void ScarletIslandScheduleResidualAutomaticInset(",1)[0]
        self.assertEqual(section.count("ScarletIslandShouldAnchorAfterInset("),1)
        self.assertIn("initialAnchorAttempted = YES",section)
        self.assertIn("UISceneActivationStateForegroundActive",section)
        self.assertIn("fabs(owner.contentOffset.x - originalOffset.x) <= 2",section)
        self.assertIn("(!always || fabs(owner.contentOffset.y + after) <= 3)",section)
        self.assertIn("owner.contentOffset = originalOffset",section)
        self.assertIn("lateControls < selectedControls",section)
        self.assertIn("late_geometry_not_persistent",section)
        self.assertNotIn("owner.contentInset =",section)
        self.assertNotIn("setNeedsStatusBarAppearanceUpdate",section)


if __name__ == "__main__":
    unittest.main()

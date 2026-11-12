"""P37 real-device override requires observing the parent's actual contract."""
from pathlib import Path
import re,unittest
ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
R=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
NEW=G.split("// R6P38_LAYOUT_OWNER_BEGIN",1)[1].split("// R6P38_LAYOUT_OWNER_END",1)[0]
class HeaderLayoutOwner(unittest.TestCase):
    def test_failed_trial_has_no_live_call_and_observer_has_no_geometry_writes(self):
        probe=G.split("static void ScarletIslandContentProbe(",1)[1].split(
            "// R6P37 distinct measured",1)[0]
        self.assertNotIn("ScarletIslandTryDeepHeaderSafeGuideAnchor(",probe)
        self.assertIn("ScarletIslandObserveDeepHeaderLayoutOwner(",probe)
        source="\n".join(l.split("//",1)[0] for l in NEW.splitlines())
        for key in ("frame", "bounds", "center", "transform", "autoresizingMask",
                    "translatesAutoresizingMaskIntoConstraints", "constant", "active"):
            self.assertIsNone(re.search(r"\."+key+r"\s*=(?!=)",source))
        for forbidden in ("method_setImplementation", "method_exchangeImplementations",
                          "class_replaceMethod", "object_setClass", "setNeedsLayout",
                          "layoutIfNeeded", "dispatch_after", "addConstraint:", "setFrame:("):
            self.assertNotIn(forbidden,source)
    def test_probe_is_bounded_and_requires_same_measured_header(self):
        for token in ("sample!=650 && sample!=2600", "seen&bit", "depth++<24",
                      "severe>=2", "conflicting", "safeTop-20",
                      "CGRectGetHeight(cursor.bounds)<34",
                      "CGRectGetHeight(cursor.bounds)>72",
                      "cursor.translatesAutoresizingMaskIntoConstraints",
                      "rows.count>=16", "inspected++>=96"):
            self.assertIn(token,NEW)
        self.assertIn("constraints.prefix(16)",H)
        self.assertIn('@"guest_short_header_quarantined"',NEW)
    def test_constraint_endpoints_and_implementation_origins_survive_relay(self):
        names=set(re.findall(r'@"(header_[a-z_]+)"',NEW))-{"header_constraints"}
        self.assertGreater(len(names),35)
        for name in names:
            self.assertIn('"'+name+'"',H,name)
            self.assertIn('"'+name+'"',R,name)
        self.assertIn('"guest_header_constraint_probe"',H)
        self.assertIn("NSAutoresizingMaskLayoutConstraint",NEW)
        self.assertIn("method_getImplementation",NEW)
        self.assertIn("NOT evidence that a method executed",NEW)
    def test_no_guest_identity_or_error_text_is_serialized(self):
        for bad in ('@"class_name"', '@"image_path"', '@"symbol"',
                    '@"caller_address"', "accessibilityLabel", "localizedDescription",
                    "bundleIdentifier", "NSStringFromClass"):
            self.assertNotIn(bad,NEW)
        for expression in ("info.dli_fname", "method_getImplementation(method)"):
            self.assertNotRegex(NEW,r'@"[^"]+"\s*:\s*@?\('+re.escape(expression))
if __name__=="__main__":unittest.main()

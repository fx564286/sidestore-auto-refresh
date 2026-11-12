from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
R=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
class ConstraintProof(unittest.TestCase):
    def test_failed_always_trial_is_not_scheduled(self):
        self.assertNotIn("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);",G)
        self.assertIn('ScarletIslandReceipt(@"guest_always_policy_quarantined"',G)
        self.assertIn('guest_always_policy_quarantined',H)
    def test_probe_has_bounds_and_no_layout_writes(self):
        section=G.split("// R6P34: the signed P33 owner",1)[1].split("static void ScarletIslandContentProbe",1)[0]
        for token in ("next >= 64","rows.count >= 12","levels++ < 8","inspected++ >= 96",
                      "constraintsAffectingLayoutForAxis:UILayoutConstraintAxisVertical",
                      ".frameLayoutGuide",".contentLayoutGuide",".safeAreaLayoutGuide"):
            self.assertIn(token,section)
        for forbidden in (".frame =",".bounds =",".contentOffset =",".contentInset =",
                          "constraint.constant =", "constraint.active =", "NSStringFromClass",
                          "accessibilityLabel","accessibilityIdentifier"):
            self.assertNotIn(forbidden,section)
    def test_all_numeric_fields_survive_relay_and_recorder(self):
        for key in ('node_slot', 'scroll_slot', 'node_window_x', 'node_window_width', 'node_window_height', 'node_window_y', 'node_window_bottom', 'node_owner_y', 'node_local_y', 'node_autoresizing', 'node_ambiguous', 'node_in_navbar', 'controller_safe_top', 'constraint_count', 'constraint_inspected', 'constraint_frame_refs', 'constraint_content_refs', 'constraint_safe_refs', 'constraint_external_refs', 'constraint_center_refs', 'constraint_other_refs', 'constraint_first_attribute', 'constraint_other_attribute', 'constraint_first_relation', 'constraint_first_constant', 'constraint_first_priority', 'constraint_scan_capped', 'probe_nodes_capped'):
            self.assertIn('@"'+key+'"',G)
            self.assertIn('"'+key+'"',H)
            self.assertIn('"'+key+'"',R)
        self.assertIn('nodes.prefix(12)',H)
        self.assertIn('@"nodes":rows',G)
if __name__=="__main__":unittest.main()

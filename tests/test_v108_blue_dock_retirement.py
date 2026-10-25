"""V108 regression: deleted blue Dock; preserved guest switching."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "retire_blue_dock", ROOT / "scripts/patch_v108_remove_blue_collapsed_dock.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def valid_minimal():
    return (
        module.MARK + " "
        "ForEach(dockManager.apps) { app in "
        "if dockManager.v3DockPresentationState.isReady && "
        "!dockManager.isDockHidden && !dockManager.apps.isEmpty "
        "nrgV108LeftEdgeGesture initialHidden || self.isCollapsed "
        "guard controller is DecoratedAppSceneViewController "
        "nrgV102PresentWindowActionsFrom"
    )

class V108BlueDockTests(unittest.TestCase):
    def test_audit_rejects_old_button_definitions_and_calls(self):
        clean = valid_minimal()
        module.audit(clean)
        for obsolete in ("struct CollapsedDockView: View",
                         "struct CollapseButtonView: View",
                         "CollapsedDockView(isHidden:",
                         "CollapseButtonView()", 'Image(systemName: "chevron.up")',
                         "hideCollapsedDock",
                         "keyWindow.gestureRecognizers?.removeAll"):
            with self.subTest(obsolete=obsolete), self.assertRaisesRegex(
                    ValueError, "obsolete rendered UI"):
                module.audit(clean + obsolete)

    def test_audit_requires_real_switcher_and_edge_state(self):
        for required in (module.MARK,
                         "ForEach(dockManager.apps) { app in",
                         "nrgV108LeftEdgeGesture",
                         "initialHidden || self.isCollapsed",
                         "nrgV102PresentWindowActionsFrom"):
            with self.subTest(required=required), self.assertRaisesRegex(
                    ValueError, "required surviving route"):
                module.audit(valid_minimal().replace(required, "NO_ROUTE", 1))

    def test_settings_retirement_preserves_edge_tuck(self):
        module.audit_settings('Toggle(isOn: $dockStartsTuckedToEdge) { Text("Start Dock Tucked To Edge") }')
        for legacy in ("Start Dock Collapsed", "hideCollapsedDock", "LCHideCollapsedDock"):
            with self.subTest(legacy=legacy), self.assertRaisesRegex(
                    ValueError, "obsolete Dock setting"):
                module.audit_settings("Start Dock Tucked To Edge " + legacy)

    def test_pin_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "old Dock definitions changed"):
            module.patch("unrelated SwiftUI")

    def test_generated_final_source_if_configured(self):
        root = os.environ.get("V108_PATCHED_LIVECONTAINER")
        if not root:
            # The prepatch suite still enforces all fail-closed source gates.
            self.assertEqual(module.FILE.name, "MultitaskDockView.swift")
            return
        root = Path(root)
        dock = (root / module.FILE).read_text(encoding="utf-8")
        module.audit(dock)
        self.assertEqual(module.patch(dock), dock)
        self.assertIn('[SCARLET_V108_DOCK] blue_collapsed_ui_deleted=1', dock)
        self.assertIn('prefs.removeObject(forKey: "LCMultitaskDockStartsCollapsed")', dock)
        settings = (root / module.SETTINGS).read_text()
        module.audit_settings(settings)
        self.assertEqual(module.patch_settings(settings), settings)
        self.assertIn("self.isDockHidden = initialHidden || self.isCollapsed", dock)
        self.assertIn("if inward { showDockFromHidden() }", dock)
        self.assertIn("nrgV108LeftEdgeGesture = leftEdgeGesture", dock)
        self.assertIn("nrgV108RightEdgeGesture = rightEdgeGesture", dock)
        window = (root / "MultitaskSupport/DecoratedAppSceneViewController.m").read_text()
        self.assertIn('self.nrgWindowOverflow = overflow;', window)
        self.assertIn('nrgV102HoldWindowActions:', window)
        self.assertIn('nrgV102PresentWindowActionsFrom:self', window)
        direct = (root / "LiveContainer/LCBootstrap.m").read_text()
        self.assertIn("SCGuestMorphPresenter", direct)
        self.assertIn("confirmation=accepted", direct)

if __name__ == "__main__":
    unittest.main()

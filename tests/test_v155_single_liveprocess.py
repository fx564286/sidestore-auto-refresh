"""V155: single LiveProcess launch and no Direct UI. Regression guard."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v155",ROOT/"scripts"/"patch_v155_single_liveprocess.py")
patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)

class SingleLiveProcess(unittest.TestCase):
    def test_fail_closed_on_unknown_upstream(self):
        for _,fn in patch.FILES:
            with self.subTest(fn=fn.__name__),self.assertRaises(ValueError):
                fn("unrelated source")

    def test_generated_sources_are_idempotent_and_single_mode(self):
        root=os.environ.get("V155_PATCHED_LIVECONTAINER")
        if not root:return
        tree=Path(root)
        for rel,fn in patch.FILES:
            with self.subTest(path=rel):
                s=(tree/rel).read_text()
                self.assertEqual(fn(s),s)
        model=(tree/"LiveContainerSwiftUI/Models/LCAppModel.swift").read_text()
        launch=model[model.index("    func runApp(multitask:"):model.index("    func forceResign()")]
        self.assertIn("let multitask = true",launch)
        self.assertIn('stage=guest_launch route=LiveProcess',launch)
        self.assertIn("try await LCUtils.launchMultitaskGuestApp",launch)
        self.assertNotIn("let multitask = classicMode ==",launch)
        self.assertNotIn("LCSharedUtils.launchToGuestApp(withClassicMode:",launch)
        self.assertIn("LiveProcess extension is unavailable",launch)
        boot=(tree/"LiveContainer/LCBootstrap.m").read_text()
        for forbidden in ("SCGuestMorphPresenter", "SCGuestMorphWindow",
                          "SCGuestMorphController", "scarlet.v105.direct.morph",
                          "openSharedTap:", "scarletcrystal251://nrg-guest-controls"):
            self.assertNotIn(forbidden,boot)
        self.assertIn("stage=bootstrap result=direct_rejected",boot)
        shell=(tree/"LiveContainerSwiftUI/Views/V3UnifiedShell.swift").read_text()
        self.assertNotIn("nrg-guest-controls",shell)
        self.assertNotIn("nrgV112PresentDirectGuestUI(",shell)
        dock=(tree/"MultitaskSupport/MultitaskDockView.swift").read_text()
        for forbidden in ("directMode", "nrgV112DirectGuestRequest",
                          "nrgV114DirectWindowActionsRequest",
                          "nrgV112PresentDirectGuestUI",
                          "SCUnifiedGuestUIBridge", "scarlet.v112.direct.restart"):
            self.assertNotIn(forbidden,dock)
        self.assertIn('("앱 닫기", "closeWindow")',dock)
        self.assertIn('SCARLET_V151_TAB_NATIVE_PRESS',dock)
        self.assertIn('SCARLET_V155_DOCK_SINGLE_MODE',dock)

    def test_no_second_launch_mode_menu(self):
        root=os.environ.get("V155_PATCHED_LIVECONTAINER")
        if not root:return
        banner=(Path(root)/"LiveContainerSwiftUI/Views/AppList/LCAppBanner/LCAppBannerViewController.swift").read_text()
        self.assertIn("SCARLET_V155_MENU_SINGLE_LIVEPROCESS",banner)
        self.assertNotIn('await self?.runApp(multitask: !shouldLaunchInMultitaskMode)',banner)

    def test_recent_glass_height_and_existing_outside_hit_target(self):
        root=os.environ.get("V155_PATCHED_LIVECONTAINER")
        if not root:return
        dock=(Path(root)/"MultitaskSupport/MultitaskDockView.swift").read_text()
        self.assertIn("SCARLET_V155_RECENT_OPTICAL_HEIGHT",dock)
        self.assertIn("(windowActions ? 0 : 12)",dock)
        self.assertIn("SCARLET_V155_OUTSIDE_HITTEST",dock)
        self.assertIn("if let panel = activePanel, !panel.frame.contains(point)",dock)
        self.assertIn("return self",dock)
        self.assertIn("return super.hitTest(point, with: event)",dock)
        self.assertIn("SCARLET_V154_OUTSIDE",dock)

    def test_panel_glass_style_and_ui_actions_unchanged(self):
        root=os.environ.get("V155_PATCHED_LIVECONTAINER")
        base=os.environ.get("V155_BASELINE_DOCK")
        if not root or not base:return
        now=(Path(root)/"MultitaskSupport/MultitaskDockView.swift").read_text()
        before=Path(base).read_text()
        a="            // SCARLET_V149_TABS:"
        b="        let scroll = UIScrollView()"
        self.assertEqual(before[before.index(a):before.index(b)],
                         now[now.index(a):now.index(b)],
                         "existing top tab style must be byte-identical")
        a='''            let actions: [(String, String)] = ['''
        b='''        }'''
        start_old=before.index(a); start_now=now.index(a)
        # Do not modify action list, native glass configuration or button press.
        self.assertEqual(before[start_old:before.index('''                item.addAction(UIAction''',start_old)],
                         now[start_now:now.index('''                item.addAction(UIAction''',start_now)])

    def test_final_source_audits_accept_only_single_mode(self):
        root=os.environ.get("V155_PATCHED_LIVECONTAINER")
        if not root:return
        import sys
        sys.path.insert(0,str(ROOT/"scripts"))
        import audit_v107_active_guest_ui as a107
        import audit_v102_final_source as a102
        source=Path(root)
        if not (source/"MultitaskSupport/AppSceneViewController.m").exists():
            return
        self.assertEqual(a107.inspect(source)["status"],"PASS")
        self.assertEqual(a102.audit(source)["status"],"PASS")

    def test_user_persisted_settings_not_deleted(self):
        code=(ROOT/"scripts/patch_v155_single_liveprocess.py").read_text()
        for bad in ("removePersistentDomain", "removeItem(", "deleteApp(",
                    "removeObject(forKey:", "removeObjectForKey:"):
            self.assertNotIn(bad,code)

if __name__=="__main__":unittest.main()

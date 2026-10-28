"""V145 source-contract tests. Real generated tree is checked when available."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj
native=module("patch_v145_native_glass")
direct=module("patch_v145_direct_action")
v144=module("patch_v144_glass_outside")

class NativeGlass(unittest.TestCase):
    @staticmethod
    def example():
        s="""// SCARLET_V129_PICKER_RESILIENCE
let steadyGlass = UIGlassEffect(style: .clear)
let actionsCount = 4 // V129: three window controls + per-app viewport switch.
("창 닫기", "closeWindow"),
                ("화면 표시 방식 전환", "nrgV129ToggleViewportMode")
"""
        import importlib.util
        t=ROOT/"tests"/"test_v144_glass_outside.py"
        spec=importlib.util.spec_from_file_location("v144fixture",t)
        obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
        return v144.patch(obj.GlassPickerTests.fixture())+s

    def test_native_multiwindow_glass(self):
        p=native.transform(self.example())
        self.assertEqual(native.transform(p),p)
        self.assertIn("UIGlassEffect(style: .regular)",p)
        self.assertIn("scene.windows.filter",p)
        self.assertIn("observer.uninstall()",p)
        self.assertIn("outsideObserver.install(using: outsideTap)",p)
        self.assertEqual(p.count("owner.addGestureRecognizer(outsideTap)"),0)
        self.assertNotIn('("화면 표시 방식 전환",',p)
        self.assertIn("let actionsCount = 3",p)

    def test_fail_closed_on_missing_source(self):
        with self.assertRaises(ValueError):native.transform("no presenter")

    def test_source_does_not_create_extra_ui(self):
        code=(ROOT/"scripts"/"patch_v145_native_glass.py").read_text()
        for bad in ("UIWindow(frame:", "UIButton(type:", "SecItemDelete(", "removeProvisioningProfile("):
            self.assertNotIn(bad,code)

    def test_direct_route_and_host_activation(self):
        boot='''// SCARLET_V139_UNIFIED_GUEST_ACTION
    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];
    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");
    NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://nrg-guest-controls"];'''
        s=direct.boot(boot)
        self.assertEqual(direct.boot(s),s)
        self.assertIn("drag.cancelsTouchesInView = NO;",s)
        self.assertIn("event=tap owner=existing_button",s)

        shell='''    private func dispatchURL(_ url: URL) {
        // SCARLET_V139_UNIFIED_GUEST_ACTION: Classic/Direct
        if url.scheme?.lowercased() == "scarletcrystal251",
           url.host?.lowercased() == "nrg-guest-controls" {
            sharedModel.selectedTab = .apps
            DispatchQueue.main.async {
                let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
                    .first { $0.activationState == .foregroundActive }
                guard let root = scene?.windows.first(where: {
                    !$0.isHidden && $0.windowLevel == .normal && $0.rootViewController != nil
                })?.rootViewController, root.view.window != nil else {
                    NSLog("[SCARLET_V139_ACTION] route=host_picker result=deferred_unavailable")
                    return
                }
                if #available(iOS 16.0, *) {
                    MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(
                        from: root, sourceView: root.view)
                }
            }
            return
        }
    }'''
        result=direct.shell(shell)
        self.assertEqual(direct.shell(result),result)
        self.assertIn("route=host_picker result=presented",result)
        self.assertIn("for delay in [0.0, 0.20, 0.55]",result)

    def test_real_generated(self):
        source=os.environ.get("V145_PATCHED_LIVECONTAINER")
        if not source:return
        root=Path(source)
        self.assertEqual(native.transform((root/native.DOCK).read_text()),(root/native.DOCK).read_text())
        self.assertEqual(direct.boot((root/direct.BOOT).read_text()),(root/direct.BOOT).read_text())
        self.assertEqual(direct.shell((root/direct.SHELL).read_text()),(root/direct.SHELL).read_text())

if __name__=="__main__": unittest.main()

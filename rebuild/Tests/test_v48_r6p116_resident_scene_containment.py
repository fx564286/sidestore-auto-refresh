"""Check both the pinned integration seam and the generated UIKit lifecycle."""
import importlib.util
import os
from pathlib import Path
import unittest


REBUILD = Path(__file__).resolve().parents[1]
INTEGRATOR = REBUILD / "integration" / "apply_scarlet_host.py"
SPEC = importlib.util.spec_from_file_location("scarlet_host", INTEGRATOR)
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)

# Pinned UIKit attachment and removal statements. CI also runs these checks
# against the complete Objective-C file immediately after host integration.
PINNED = """@property(nonatomic) UIWindowScene *hostScene;
- (void)setUpAppPresenter {
    if (@available(iOS 18.0, *)) {
        self.contentView = self.hostingController.sceneViewController.view;
        [self.delegate appSceneVCWillActivateScene:self];
        [self addChildViewController:self.hostingController.sceneViewController];
    } else {
        self.contentView = [[UIView alloc] init];
        [self.contentView addSubview:self.presenter.presentationView];
    }
    [self.view addSubview:_contentView];
    if(self.scarletNativeFullscreenSlot &&
       [self.delegate respondsToSelector:@selector(appSceneVCDidAttachRemoteContent:)]) {
        [weakSelf.delegate appSceneVCDidAttachRemoteContent:weakSelf];
    }
}
- (void)appTerminationCleanUp {
    _isAppTerminationCleanUpCalled = true;
    dispatch_async(dispatch_get_main_queue(), ^{
        if(self.sceneID) {
            [[PrivClass(FBSceneManager) sharedInstance] destroyScene:self.sceneID withTransitionContext:nil];
        }
        if(self.usesHostingControllerAPI) {
            if(@available(iOS 17.0, *)) {
                [self.hostingController invalidate];
                [self.hostingController.sceneViewController removeFromParentViewController];
                self.hostingController = nil;
            }
        }
    });
}
"""


class ResidentSceneContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generated = os.environ.get("SCARLET_TEST_GENERATED_ENGINE")
        if generated:
            scene = Path(generated) / "MultitaskSupport" / "AppSceneViewController.m"
            cls.source = scene.read_text()
        else:
            cls.source = HOST.repair_resident_scene_containment(PINNED)
        cls.setup = cls.source.split("- (void)setUpAppPresenter {", 1)[1].split("\n}", 1)[0]
        cls.cleanup = cls.source.split("- (void)appTerminationCleanUp {", 1)[1].split("\n}", 1)[0]

    def assert_in_order(self, source, *statements):
        indices = [source.index(statement) for statement in statements]
        self.assertEqual(indices, sorted(indices))

    def test_parents_exist_before_first_view_load_and_mount_completes_before_reveal(self):
        swift = (REBUILD / "HostApp" / "ScarletFullscreenSceneStack.swift").read_text()
        outer = swift.split("vc.scarletNativeFullscreenSlot = true", 1)[1]
        self.assert_in_order(outer, "addChild(vc)", "vc.view.", "view.addSubview(vc.view)",
                             "vc.didMove(toParent: self)")
        self.assert_in_order(self.setup, "if (self.scarletNativeFullscreenSlot)",
                             "if (!child) return;", "[self addChildViewController:child]",
                             "self.contentView = child.view;", "[self.view addSubview:_contentView]",
                             "[residentChild didMoveToParentViewController:self]",
                             "self.scarletAttachedSceneChild = residentChild;",
                             "[weakSelf.delegate appSceneVCDidAttachRemoteContent:weakSelf]")
        self.assertEqual(self.setup.count("didMoveToParentViewController:self"), 1)

    def test_native_and_legacy_branches_keep_their_child_ownership(self):
        self.assertIn("UIViewController *residentChild = nil;", self.setup)
        self.assertIn("if (!self.scarletNativeFullscreenSlot) {\n"
                      "            [self addChildViewController:self.hostingController.sceneViewController];",
                      self.setup)
        self.assertIn("if (residentChild) {\n"
                      "        [residentChild didMoveToParentViewController:self];", self.setup)
        self.assert_in_order(self.setup, "self.contentView = [[UIView alloc] init];",
                             "[self.contentView addSubview:self.presenter.presentationView]",
                             "[self.view addSubview:_contentView]")

    def test_teardown_clears_readiness_and_detaches_only_owned_child_before_invalidation(self):
        self.assert_in_order(self.cleanup, "dispatch_async(dispatch_get_main_queue()",
                             "UIViewController *child = self.scarletAttachedSceneChild;",
                             "self.scarletAttachedSceneChild = nil;", "child.parentViewController == self",
                             "[child willMoveToParentViewController:nil]",
                             "child.viewIfLoaded.superview == self.viewIfLoaded",
                             "[child.viewIfLoaded removeFromSuperview]",
                             "[child removeFromParentViewController]", "destroyScene:self.sceneID",
                             "[self.hostingController invalidate]", "if (!self.scarletNativeFullscreenSlot)",
                             "[self.hostingController.sceneViewController removeFromParentViewController]")

    def test_changed_or_ambiguous_upstream_anchor_blocks_integration(self):
        mount = "[self.view addSubview:_contentView];"
        for replacement in ("", mount + "\n    " + mount):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                HOST.repair_resident_scene_containment(PINNED.replace(mount, replacement))


if __name__ == "__main__":
    unittest.main()

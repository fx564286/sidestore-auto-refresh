"""V36 security-style regression: old LC UI components absent after integration."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
PANEL=(ROOT/'HostApp/ScarletGuestSwitcherOverlay.swift').read_text()
INTEGRATION=ROOT/'integration/apply_scarlet_host.py'
WORKFLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class RemoveLegacyVisualSource(unittest.TestCase):
    def test_source_renderer_and_three_button_controller_removed(self):
        spec=importlib.util.spec_from_file_location('integrator_v36',INTEGRATION)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            directory=pathlib.Path(temp)/'MultitaskSupport'
            directory.mkdir(parents=True)
            # Source-contract fixture owns only exact anchors verified from
            # the pinned upstream. The integration itself transforms the
            # actual pinned files in the Xcode build.
            (directory/'MultitaskDockView.swift').write_text(
                '// MARK: original\n'
                'public struct MultitaskDockSwiftView: View {}\n'
                'struct CollapsedDockView: View {}\n'
                'class MultitaskDockManager {}\n')
            (directory/'DecoratedAppSceneViewController.m').write_text(
                '- (instancetype)initWindowName: {\n'
                '    NSArray *menuItems = @[\n'
                '    ];\n'
                '    UIBarButtonItem *minimizeButton;\n'
                '    return self;\n}\n'
                '- (void)setupDecoratedView {\n'
                '    CGFloat navBarHeight = 44;\n'
                '    CGRect frame = CGRectMake(0, 0, isLandscape ? 480 : 320, 1);\n'
                '    UINavigationBar *navigationBar = nil;\n'
                '}\n// Stolen from UIKitester\n'
                '- (void)updateVerticalConstraints {\n'
                '    CGFloat navBarHeight = 44;\n'
                '}\n- (UIEdgeInsets)updateMaximizedSafeAreaWithSettings: {\n}\n')
            result=mod.remove_upstream_legacy_window_ui(pathlib.Path(temp))
            dock=(directory/'MultitaskDockView.swift').read_text()
            decorated=(directory/'DecoratedAppSceneViewController.m').read_text()
            self.assertTrue(result['chromeMinMaxCloseRemoved'])
            self.assertTrue(result['legacyScene320x480GeometryRemoved'])
            self.assertNotIn('MultitaskDockSwiftView',dock)
            self.assertNotIn('CollapsedDockView',dock)
            self.assertNotIn('setupDockView()',dock)
            self.assertNotIn('windowHostingView.superview',dock)
            self.assertNotIn('UIBarButtonItem *minimizeButton',decorated)
            self.assertNotIn('UINavigationBar *navigationBar =',decorated)
            self.assertNotIn('isLandscape ? 480 : 320',decorated)
            self.assertIn('class MultitaskDockManager',dock)
            self.assertIn('self.view.frame = self.view.superview.bounds;',decorated)

    def test_scarlet_own_single_round_switcher_and_original_fullscreen(self):
        self.assertIn('ScarletFullscreenGuestFloatingTab',GUEST)
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertIn('legacy_dock_source_removed',HOST)
        for text in ('MultitaskDockManager.shared', 'scarletEnsureWindowHost'):
            self.assertNotIn(text,HOST)
        for text in ('guestWindowCommand(', 'selectedSegment = 1',
                     'MultitaskDockManager.shared'):
            self.assertNotIn(text,PANEL)
        self.assertNotIn('MultitaskDockManager.shared',GUEST)

    def test_v36_release_is_separate_and_ipa_not_zip(self):
        self.assertIn('fix/scarlet-v36-remove-legacy-ui-20261110',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V36-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__':
    unittest.main()

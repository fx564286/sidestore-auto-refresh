"""V143 preserves guest lifecycle while eliminating legacy edge slivers."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v143',ROOT/'scripts/patch_v143_guest_window_peek.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class WindowPeekTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return '''// SCARLET_V141_INSET_AWARE_SETTLE
    CGFloat oobOffset = MAX(30, frame.size.width - 30);
    frame.origin.x = MAX(maxFrame.origin.x - oobOffset, MIN(CGRectGetMaxX(maxFrame) - frame.size.width + oobOffset, center.x - frame.size.width / 2));
    self.view.alpha = 0;
    } completion:^(BOOL finished) {
        if (!finished) return;
        self.view.hidden = YES;
        self.view.transform = CGAffineTransformIdentity;
        [self.view.superview sendSubviewToBack:self.view];
    }];
}

- (void)minimizeWindowPiP'''

    def test_edge_peek_removed(self):
        s=v.patch(self.fixture())
        self.assertEqual(v.patch(s),s)
        self.assertIn('SCARLET_V143_NO_EDGE_PEEK',s)
        self.assertIn('SCARLET_V143_INTERRUPTED_MINIMIZE',s)
        self.assertNotIn('CGFloat oobOffset',s)
        self.assertIn('MAX(minX, MIN(maxX,',s)
        self.assertIn('self.view.hidden = YES;',s)
        self.assertIn('self.view.alpha = 1.0;',s)

    def test_reject_unknown_or_partial_code(self):
        with self.assertRaises(ValueError):v.patch('unrelated original')
        with self.assertRaises(ValueError):
            v.patch(self.fixture().replace('self.view.hidden = YES;', ''))

    def test_preserves_existing_keyboard_rotation_and_completion_callbacks(self):
        source=self.fixture().replace(
            '        self.view.hidden = YES;',
            '        // Existing guest lifecycle instrumentation must survive.\\n'
            '        NSLog(@"[SCARLET_V133_KEYBOARD] minimize=done");\\n'
            '        self.view.hidden = YES;'
        ).replace(
            '    }];\\n}\\n\\n- (void)minimizeWindowPiP',
            '    }];\\n}\\n\\n// Existing V46/V133 lifecycle separation.\\n'
            '- (void)minimizeWindowPiP'
        )
        patched=v.patch(source)
        self.assertIn('SCARLET_V133_KEYBOARD',patched)
        self.assertIn('Existing V46/V133 lifecycle separation',patched)
        self.assertEqual(v.patch(patched),patched)
        self.assertEqual(patched.count('SCARLET_V143_INTERRUPTED_MINIMIZE'),1)
        self.assertNotIn('if (!finished) return;',patched)
        self.assertIn('if (!finished && self.view.alpha >= 0.95) return;',patched)

    def test_no_prior_completion_guard_still_patches_bounded_method(self):
        source=self.fixture().replace('        if (!finished) return;\\n','')
        patched=v.patch(source)
        self.assertIn('SCARLET_V143_INTERRUPTED_MINIMIZE',patched)
        self.assertEqual(v.patch(patched),patched)

    def test_no_guest_data_mutation(self):
        src=(ROOT/'scripts/patch_v143_guest_window_peek.py').read_text()
        for bad in ('removeApp(', 'deleteGuest(', 'SecItemDelete(', 'removeProvisioningProfile(', 'clearPairing('):
            self.assertNotIn(bad,src)

    def test_actual_generated_scene(self):
        root=os.getenv('V143_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/v.SOURCE).read_text()
        self.assertEqual(v.patch(s),s)
        self.assertEqual(s.count(v.MARK),1)
        self.assertEqual(s.count('SCARLET_V143_INTERRUPTED_MINIMIZE'),1)

if __name__=='__main__':unittest.main()

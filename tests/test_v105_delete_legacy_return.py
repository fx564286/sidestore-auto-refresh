"""V105 release blocker: old live/Direct guest controls deleted, not concealed."""
from pathlib import Path
import importlib.util
import os
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
S=importlib.util.spec_from_file_location('v105',HERE/'scripts'/'patch_v105_delete_legacy_return.py')
v=importlib.util.module_from_spec(S);S.loader.exec_module(v)

NATIVE='''#import "UIKitPrivate+MultitaskSupport.h"
static double LCReturnAxisCenter(double x, double y, double p) {return p;}
static int LCReturnShouldHide(int a,int b,int c) {return a;}
 // LC_GUEST_RETURN_V3: the control owns no guest process or scene.
@interface LCReturnControl : UIView
@end
@implementation LCReturnControl
@end
@interface AppSceneViewController()
@property(nonatomic, strong) LCReturnControl *lcReturnControl;
@property int resizeDebounceToken;
@end
@implementation AppSceneViewController
- (void)viewDidLayoutSubviews {
    // SCARLET_V103_SINGLE_CONTROL_OWNER
    // SCARLET_V102_NATIVE_GESTURE_CLEANUP
    [self.lcReturnControl removeFromSuperview];
}
- (void)lcReturnToHost { NSLog(@"OLD"); }
- (instancetype)initWithBundleId:(NSString*)b dataUUID:(NSString*)d delegate:(id)delegate {
    return self;
}
- (void)appTerminationCleanUp {
    self.lcReturnControl.hidden = YES;
    [self.lcReturnControl removeFromSuperview];
}
@end
'''
DIRECT='''#include <math.h>
static double LCReturnAxisCenter(double x, double y, double p) {return p;}
static int LCReturnShouldHide(int a,int b,int c) {return a;}
// LC_GUEST_RETURN_V3: old runtime
@interface LCDirectReturnControl : UIView
@end
@implementation LCDirectReturnControl
@end
@interface LCDirectReturnPresenter : NSObject
@end
@implementation LCDirectReturnPresenter
@end
static LCDirectReturnPresenter *lcDirectReturnPresenter;
extern char **environ;
void run(void) {
 if (!isLiveProcess && !isSideStore) {
    lcDirectReturnPresenter = [LCDirectReturnPresenter new];
 }
}
'''

class V105DeleteTests(unittest.TestCase):
    def test_really_remove_legacy_objc_class_and_methods(self):
        a=v.native(NATIVE)
        self.assertEqual(v.native(a),a)
        self.assertIn(v.SCENE_MARK,a)
        self.assertIn('- (instancetype)initWithBundleId:',a)
        self.assertIn('appTerminationCleanUp',a)
        self.assertIn('resizeDebounceToken',a)
        self.assertNotIn('removeFromSuperview',a)
        for forbidden in v.BANNED:self.assertNotIn(forbidden,a)

    def test_really_remove_direct_classes_keep_safe_confirmed_escape(self):
        a=v.direct(DIRECT)
        self.assertEqual(v.direct(a),a)
        self.assertIn('SCGuestMorphWindow',a)
        self.assertIn('SCGuestMorphPresenter',a)
        self.assertIn('scarlet.v105.direct.morph',a)
        self.assertIn('if (!isSideStore)',a)
        self.assertIn('SCARLET_V128_LIVEPROCESS_FALLBACK', Path(v.__file__).read_text())
        self.assertIn('SCARLET_V128_DIRECT_SCENE_RECOVERY',a)
        self.assertIn('SCARLET_V129_SINGLE_OWNER',a)
        self.assertIn('fallback_retired=1',a)
        self.assertIn('name:@"SCScarletVirtualHandleReady"',a)
        self.assertIn('SCARLET_V128_DIRECT_NATIVE_GLASS',a)
        self.assertIn('[[UIGlassEffect alloc] init]',a)
        self.assertIn('CGRectGetWidth(window.bounds)-52',a)
        self.assertIn('[LCSharedUtils launchToGuestAppWithClassicMode:0]',a)
        self.assertIn('confirmation=accepted',a)
        self.assertIn('SCARLET_V112_SHARED_GUEST_UI',a)
        self.assertIn('SCARLET_V105_DIRECT_UNIFIED_MORPH',a)
        self.assertIn('SCUnifiedGuestUIBridge',a)
        self.assertIn('presentFrom:sourceView:',a)
        self.assertIn('UIBlurEffectStyleSystemThinMaterial',a)
        self.assertIn('nrgV112RestartDirectGuest',a)
        self.assertNotIn('홍수정',a)
        for token in ('UIButton *scrim', 'UIView *card', '- (void)expand:',
                      'portraitUI ? 44 : 28', 'chevron.up'):
            self.assertNotIn(token,a)
        for forbidden in v.BANNED:self.assertNotIn(forbidden,a)

    def test_no_layout_time_remount_and_user_data_changes(self):
        a=v.native(NATIVE)
        b=v.direct(DIRECT)
        self.assertNotIn('viewDidLayoutSubviews',a)
        for key in ('SecItemDelete','removeItemAtPath','keychain','selectedContainer','dataUUID'):
            self.assertNotIn(key,b)
        self.assertNotIn('launchToGuestAppWithClassicMode:0];\n    };\n',b)

    def test_fail_closed_on_incomplete_source(self):
        with self.assertRaises(ValueError):v.native(NATIVE.replace('SCARLET_V103_SINGLE_CONTROL_OWNER',''))
        with self.assertRaises(ValueError):v.direct(DIRECT.replace('LCDirectReturnPresenter','NewUnknownPresenter'))
        with self.assertRaises(ValueError):v.direct(DIRECT.replace('extern char **environ;',''))

    def test_atomic_pinned_source_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for p,data in ((v.SCENE,NATIVE),(v.BOOT,DIRECT)):
                f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
            v.apply(root)
            v.apply(root)
            for p in (v.SCENE,v.BOOT):
                output=(root/p).read_text()
                self.assertTrue(all(x not in output for x in v.BANNED))

    def test_generated_final_app_source(self):
        path=os.environ.get('V105_PATCHED_LIVECONTAINER')
        if not path:return
        root=Path(path)
        scene=(root/v.SCENE).read_text()
        boot=(root/v.BOOT).read_text()
        self.assertEqual(v.native(scene),scene)
        self.assertEqual(v.direct(boot),boot)
        self.assertFalse(any(x in scene or x in boot for x in v.BANNED))

if __name__=='__main__':unittest.main()

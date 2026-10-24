"""V87 regression: long-hold opens chooser using visible host and native+virtual guests."""
from pathlib import Path
import importlib.util
import unittest
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
def module(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
v87=module('patch_v87_guest_button_switcher.py','v87')
v76=module('patch_v76_native_guest_switcher.py','v76')
v72=module('patch_v72_overflow_longpress.py','v72')

class V87Tests(unittest.TestCase):
    def test_host_source_uses_visible_return_button_window(self):
        src='LC_GUEST_SWITCH_V76_PATCHED\n' + v87.OLD_OBJC
        after=v87.objc(src)
        self.assertEqual(after,v87.objc(after))
        self.assertIn('source.window',after)
        self.assertIn('owner.rootViewController',after)
        self.assertIn('presenter=visible_host',after)
        self.assertNotIn('UIApplicationStateActive',after)
        self.assertNotIn('!self.isAppRunning',after)
        self.assertIn('sourceView:source',after)
        self.assertIn('!owner.windowScene',after)
        self.assertNotIn('SIGKILL',after)
        self.assertNotIn('terminate',after)

    def test_installed_guest_picker_tracks_native_liveprocess_as_well_as_virtual(self):
        src='NRG_V72_OVERFLOW_LONGPRESS\n' + v72.SWIFT_SWITCHER
        after=v87.swift(src)
        self.assertEqual(after,v87.swift(after))
        self.assertIn('MultitaskWindowManager.appDict.values',after)
        self.assertIn('controller.isAppRunning',after)
        self.assertIn('union(nativeFolders)',after)
        self.assertIn('MultitaskWindowManager.openExistingAppWindow(dataUUID: guest.folder)',after)
        self.assertLess(after.index('route=native_existing'),after.index('route=virtual_existing'))
        self.assertIn('DataManager.shared.model.apps',after)
        self.assertIn('model.uiContainers.contains',after)
        self.assertIn('lastLaunched',after)
        self.assertIn('홍수정 내부 앱 전환',after)
        self.assertNotIn('UIApplication.shared.open(URL(string: "settings:',after)
        self.assertNotIn('systemApplications',after)

    def test_bad_upstream_fails_closed(self):
        with self.assertRaises(ValueError):v87.objc('unused upstream')
        with self.assertRaises(ValueError):v87.swift('unused upstream')
        with self.assertRaises(ValueError):v87.objc(v87.MARK)
        with self.assertRaises(ValueError):v87.swift(v87.SWIFT_MARK)

    def test_atomic_install_and_two_pass(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            for p in (v87.OBJC,v87.DOCK):
                (root/p).parent.mkdir(parents=True,exist_ok=True)
            objcsrc='LC_GUEST_SWITCH_V76_PATCHED\n'+v87.OLD_OBJC
            (root/v87.OBJC).write_text(objcsrc)
            (root/v87.DOCK).write_text('BROKEN V72 SOURCE')
            with self.assertRaises(ValueError): v87.apply(root)
            self.assertEqual((root/v87.OBJC).read_text(),objcsrc)
            (root/v87.DOCK).write_text('NRG_V72_OVERFLOW_LONGPRESS\n'+v72.SWIFT_SWITCHER)
            v87.apply(root)
            first={p:(root/p).read_text() for p in (v87.OBJC,v87.DOCK)}
            v87.apply(root)
            self.assertEqual(first,{p:(root/p).read_text() for p in (v87.OBJC,v87.DOCK)})

    def test_gesture_unchanged_and_no_guest_process_kill(self):
        self.assertIn('minimumPressDuration = 0.55',v76.LONG_PRESS)
        self.assertIn('cancelsTouchesInView = YES',v76.LONG_PRESS)
        self.assertIn('self.switchAction()',v76.METHODS)
        self.assertNotIn('terminate(',v87.NEW_OBJC)
        self.assertNotIn('removeRunningApp',v87.NEW_OBJC)
        self.assertNotIn('unregisterMultitaskContainer',v87.NEW_OBJC)

if __name__=='__main__':unittest.main()

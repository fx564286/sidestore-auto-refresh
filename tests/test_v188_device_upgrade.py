"""Offline checks for in-place V188 upgrade; no real device or Apple access."""
from pathlib import Path
import importlib.util
import unittest
from unittest import mock

SRC=Path(__file__).resolve().parents[1]/"scripts/scarlet_v188_upgrade_existing_device.py"
spec=importlib.util.spec_from_file_location("v188_upgrade",SRC)
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class UpgradeTests(unittest.TestCase):
    def test_team_and_four_bundle_identifiers_preserved(self):
        self.assertEqual(s.TEAM,"P8EZT3U5N4")
        self.assertEqual(s.APP,"com.kdt.livecontainer.P8EZT3U5N4")
        self.assertEqual(s.GROUP,"group.com.SideStore.SideStore.P8EZT3U5N4")
        self.assertEqual(len(s.NAMES),4)
        self.assertEqual(set(s.NAMES.values()),{
            s.APP,s.APP+".LiveProcess",s.APP+".ShareExtension",s.APP+".LaunchAppExtension"})

    def test_missing_existing_app_blocks_upgrade(self):
        with mock.patch.object(s,"run",return_value="No matching apps"):
            with self.assertRaisesRegex(s.Stop,"ORIGINAL_APP_NOT_INSTALLED"):
                s.installed("fake",True,before=True)

    def test_wifi_device_preferred_over_usb(self):
        def run(args,timeout=120):
            return "paired_wifi_device\n" if args==["idevice_id","-n"] else ""
        with mock.patch.object(s.shutil,"which",return_value="/bin/stub"),mock.patch.object(s,"run",side_effect=run):
            udid,wifi=s.devices()
        self.assertEqual(udid,"paired_wifi_device")
        self.assertTrue(wifi)

    def test_multiple_devices_stop(self):
        with mock.patch.object(s.shutil,"which",return_value="/bin/stub"),mock.patch.object(s,"run",return_value="a\nb\n"):
            with self.assertRaisesRegex(s.Stop,"MULTIPLE_DEVICES"):
                s.devices()

    def test_no_pairing_stops(self):
        with mock.patch.object(s.shutil,"which",return_value="/bin/stub"),mock.patch.object(s,"run",return_value=""):
            with self.assertRaisesRegex(s.Stop,"NO_PAIRED_DEVICE"):
                s.devices()

    def test_upgrade_uses_upgrade_not_uninstall_or_install(self):
        calls=[]
        def fake_run(args,timeout=120):
            calls.append([str(x) for x in args])
            if args[0]=="idevice_id":return "paired_wifi_device\n"
            if "list" in args:return s.APP+" - 3.8.123\n"
            return "Install: Complete"
        with mock.patch.object(s,"verify_package",return_value="3.8.123"),mock.patch.object(s.shutil,"which",return_value="/bin/stub"),mock.patch.object(s,"run",side_effect=fake_run):
            with mock.patch.object(s.os,"geteuid",return_value=1000):
                s.main()
        verbs=[x for x in calls if x[0]=="ideviceinstaller"]
        self.assertEqual([x[x.index("upgrade")] for x in verbs if "upgrade" in x],["upgrade"])
        self.assertFalse(any("uninstall" in x or "install" in x for x in verbs))
        self.assertTrue(any("-n" in x and "upgrade" in x for x in verbs))

if __name__=="__main__":
    unittest.main()

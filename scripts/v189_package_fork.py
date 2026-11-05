#!/usr/bin/env python3
"""Package Scarlet Crystal V189 with verified installed bundle build 3.8.203."""
from pathlib import Path
import importlib.util
import plistlib

spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V189"
original_stamp = module.stamp

def stamp_with_installed_receipt(host):
    original_stamp(host)
    info_path = host / "Info.plist"
    data = plistlib.loads(info_path.read_bytes())
    # V188 signed IPA reported CFBundleVersion 3.8.202; advance the real
    # installed iOS build receipt, not only the public ScarletBuildLabel.
    if data.get("CFBundleVersion") != "3.8.202":
        raise RuntimeError("Unexpected original CFBundleVersion; refuse blind update")
    data["CFBundleVersion"] = "3.8.203"
    data["ScarletUpdateChannel"] = "scarlet-device-signed"
    info_path.write_bytes(plistlib.dumps(data, sort_keys=False))

module.stamp = stamp_with_installed_receipt
if __name__ == "__main__":
    module.main()

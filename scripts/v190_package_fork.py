#!/usr/bin/env python3
"""V190: package the reviewed V189 SideStore auth transport fixes with a new iOS build."""
from pathlib import Path
import importlib.util
import plistlib

spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V190"

_original_stamp = module.stamp

def _stamp_v190(host):
    _original_stamp(host)
    info_path = host / "Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    # The upstream fixture is still 3.8.202. V189 device-signed is 3.8.203.
    # Advance the REAL OS installation identity, not just a displayed label.
    if info.get("CFBundleVersion") != "3.8.202":
        raise RuntimeError("Unexpected upstream build; V190 packaging requires review")
    info["CFBundleVersion"] = "3.8.204"
    info["ScarletBuildLabel"] = "V190"
    info["ScarletUpdateChannel"] = "scarlet-device-signed"
    info_path.write_bytes(plistlib.dumps(info, sort_keys=False))

module.stamp = _stamp_v190

if __name__ == "__main__":
    module.main()

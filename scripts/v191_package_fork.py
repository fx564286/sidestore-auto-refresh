#!/usr/bin/env python3
"""V191: package the actual iOS build identity for bounded auth-lease admission.

Builds the pinned LiveContainer + embedded SideStore parents; preserves the
unchanged Scarlet Crystal host bundle ID and Liquid Glass. Not a signed IPA.
"""
from pathlib import Path
import importlib.util
import plistlib

spec=importlib.util.spec_from_file_location(
    "scarlet_v190_packager",Path(__file__).with_name("v190_package_fork.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.module.EXPECTED_VERSION="V191"

previous_stamp=module.module.stamp

def stamp_v191(host):
    previous_stamp(host)
    info_path=host/"Info.plist"
    info=plistlib.loads(info_path.read_bytes())
    if info.get("CFBundleVersion")!="3.8.204" or info.get("ScarletBuildLabel")!="V191":
        raise RuntimeError("Unexpected compiled parent or V190 packaging identity")
    info["CFBundleVersion"]="3.8.205"
    info["ScarletBuildLabel"]="V191"
    info["ScarletUpdateChannel"]="scarlet-device-signed"
    info_path.write_bytes(plistlib.dumps(info,sort_keys=False))

module.module.stamp=stamp_v191

if __name__=="__main__":
    module.module.main()

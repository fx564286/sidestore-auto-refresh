#!/usr/bin/env python3
"""V189 provenance-aware Scarlet IPA, monotonic actual CFBundleVersion."""
from pathlib import Path
import importlib.util
import plistlib

spec=importlib.util.spec_from_file_location(
    "scarlet_v181_packager",Path(__file__).with_name("v181_package_fork.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION="V189"

_original_stamp=module.stamp
def _stamp_with_receipt(host):
    _original_stamp(host)
    path=host/"Info.plist"
    info=plistlib.loads(path.read_bytes())
    # Latest verified V188 shipped CFBundleVersion 3.8.202. Advance the
    # actual iOS package build; only updating a UI label does not upgrade iOS.
    if info.get("CFBundleVersion")!="3.8.202":
        raise RuntimeError("Unexpected upstream build; V189 monotonic version requires review")
    info["CFBundleVersion"]="3.8.203"
    info["ScarletBuildLabel"]="V189"
    info["ScarletUpdateChannel"]="scarlet-device-signed"
    path.write_bytes(plistlib.dumps(info,sort_keys=False))
module.stamp=_stamp_with_receipt

if __name__=="__main__":
    module.main()

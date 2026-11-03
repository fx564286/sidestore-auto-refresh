#!/usr/bin/env python3
"""V183 versioned entrypoint for the original dual-parent Scarlet packager.

This imports the exact V181 source adapter but stamps the V183 build number.
No historical binary, bundled signing identity, pairing data or Liquid Glass
code is modified.
"""
from pathlib import Path
import importlib.util

SPEC=importlib.util.spec_from_file_location(
    "scarlet_v181_packager",
    Path(__file__).with_name("v181_package_fork.py"),
)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
module.EXPECTED_VERSION="V183"

if __name__=="__main__":
    module.main()

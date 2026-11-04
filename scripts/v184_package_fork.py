#!/usr/bin/env python3
"""V184 IPA packager: preserve the upstream + Scarlet design and bundle IDs.

V184 changes only the host-owned authentication cancellation diagnostic path.
It is not a signed build or evidence of an on-device Apple login fix.
"""
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V184"

if __name__ == "__main__":
    module.main()

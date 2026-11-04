#!/usr/bin/env python3
"""V186 Scarlet integration package, unsigned until Apple entitlement verification."""
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V186"
if __name__ == "__main__":
    module.main()

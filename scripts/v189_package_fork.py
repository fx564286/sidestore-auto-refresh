#!/usr/bin/env python3
"""Package Scarlet Crystal V189 with corrected signed-release identity and OTA display."""
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V189"
if __name__ == "__main__":
    module.main()

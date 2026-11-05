#!/usr/bin/env python3
"""Build Scarlet Crystal V188 from the V187 reviewed source and native profile guard."""
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scarlet_v181_packager", Path(__file__).with_name("v181_package_fork.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EXPECTED_VERSION = "V188"
if __name__ == "__main__":
    module.main()

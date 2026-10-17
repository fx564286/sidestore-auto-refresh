#!/usr/bin/env python3
"""V33: audited integration of Increased Memory Limit into pinned SideSign.

Never bundle iRAM+, ask for another Apple login, or print credentials. Reuse
SideStore's authenticated DeveloperPortal. Apply reviewed capability PATCH
from SideSign PR #4 to the exact pinned dependency, fail closed on drift.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import subprocess
import sys

PIN = "a731c0d5a9a6617c7b385ae493e07ffb7f81cd5d"
PATCH = Path(__file__).resolve().parent / "patches/v33_sidesign_memory.patch"
EXPECTED = {
    "Sources/Models/Feature.swift": (
        "4f358b740d08e3e1e1b617194cb7a5b1d63927831497d66bcbac37d7bb119c21",
        "01295b5d542a3b259ff13483e43593f8c76130ccb1a924f7f5075de5fcc4d8f9"),
    "Sources/DeveloperPortal/AppIDs.swift": (
        "4ce4431c4e90ddad1e9a5558d291c51ef5e1bac20ccd9e18cc0f9e9be3aae032",
        "8684ed43e2e99e662e6a083f1fea2c99f64921d90b808693146cea6a42ac8e1b"),
    "Sources/DeveloperPortal/DeveloperPortalAPI.swift": (
        "8bfb71fd38463210ab8140ea7a2a1ec60b4af324f8c9bacfb7762bce02cac43f",
        "27c83367f9019074b5ba7eab46aa9e4941a06e9102767275367e66944bd63641"),
}
REQUIRED = (
    "INCREASED_MEMORY_LIMIT",
    "bundleIdCapabilities",
    "sendServicesBodyRequest",
    "freeFeatures",
)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def patch(root: Path) -> None:
    actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        raise ValueError("V33 SideSign pinned source mismatch")
    if not PATCH.is_file():
        raise ValueError("V33 reviewed SideSign memory capability patch absent")
    current = {name: sha(root / name) for name in EXPECTED}
    if all(current[name] == vals[1] for name, vals in EXPECTED.items()):
        verify(root)
        return
    if any(current[name] != vals[0] for name, vals in EXPECTED.items()):
        raise ValueError("V33 SideSign memory capability patch would overwrite unexpected source")
    subprocess.run(["git", "-C", str(root), "apply", "--check", str(PATCH)], check=True)
    subprocess.run(["git", "-C", str(root), "apply", str(PATCH)], check=True)
    verify(root)
    print("[PATCH] Increased Memory Limit: free team + Apple v1 capability update installed")

def verify(root: Path) -> None:
    for name, (_, expected) in EXPECTED.items():
        if sha(root / name) != expected:
            raise ValueError(f"V33 pinned capability code diverged: {name}")
    texts = [(root / name).read_text() for name in EXPECTED]
    joined = "\n".join(texts)
    if any(token not in joined for token in REQUIRED):
        raise ValueError("V33 capability implementation incomplete")
    feature = (root / "Sources/Models/Feature.swift").read_text()
    if '.increasedMemoryLimit\n    ]' not in feature:
        raise ValueError("Increased Memory Limit not enabled for free teams")
    api = (root / "Sources/DeveloperPortal/AppIDs.swift").read_text()
    if 'request.httpMethod = "PATCH"' not in api or 'enableCapabilities(capabilityIDs.sorted()' not in api:
        raise ValueError("No Apple v1 capability request")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v33_sidesign_memory.py <pinned-SideSign-root>")
    patch(Path(sys.argv[1]))

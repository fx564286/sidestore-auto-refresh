#!/usr/bin/env python3
"""Forward-port Scarlet Crystal's *real* user-authored UI patches.

Each legacy transformer still validates its exact source anchors and is
applied on an isolated checkout. The old SHA-only guards are bypassed only
after verifying BOTH of the current coherent upstream git commits. Never
replace failing patches with stock UI or silent no-op markers.
"""
from pathlib import Path
import importlib
import json
import subprocess
import sys


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: port_v180_design.py <LiveContainer> <EmbeddedSideStore> <pins.json>")
    live, side, pin_path = map(lambda x: Path(x).resolve(), sys.argv[1:])
    pins = json.loads(pin_path.read_text())
    expected = {"LIVE_CONTAINER_REF", "EMBEDDED_SIDESTORE_REF",
                "MINIMUXER_REF", "SIDESIGN_REF"}
    if set(pins) != expected:
        raise ValueError("upstream source graph is not the reviewed four-key graph")
    for root, key in ((live, "LIVE_CONTAINER_REF"), (side, "EMBEDDED_SIDESTORE_REF")):
        sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                      text=True).strip()
        if sha != pins[key]:
            raise ValueError(f"upstream provenance mismatch: {key}")
    path = Path(__file__).resolve().parent
    sys.path.insert(0, str(path))
    def report(name, action):
        print(f"[SCARLET_V180] applying prior user UI overlay: {name}", flush=True)
        action()
        print(f"[SCARLET_V180] verified overlay: {name}", flush=True)

    # Historical dependency order; do not rebuild UI from stock.
    report("host guest return", lambda: importlib.import_module("patch_guest_return").patch(live))
    report("user dock geometry", lambda: importlib.import_module("patch_multitask_dock").patch(live))
    report("user app grid", lambda: importlib.import_module("patch_app_layout").patch_livecontainer(live, v3_grid=True))
    report("user unified shell", lambda: importlib.import_module("patch_v3_unified_shell").patch(live, side))
    print("[SCARLET_V180] initial source-preserving UI port anchor checks completed")


if __name__ == "__main__":
    main()

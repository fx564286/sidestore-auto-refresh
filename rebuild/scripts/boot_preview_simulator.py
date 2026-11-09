#!/usr/bin/env python3
"""Select a RESPONDING iPhone Simulator for Scarlet's UI-only preview.

GitHub's Xcode 27 runners can have a hung CoreSimulatorService even while
simctl lists a device as Booted. Try a proven-responsive existing template,
then isolated disposable devices. Never kill the host-wide simulator daemon.
Never report a preview as verified if simctl/launchd/screenshot fails.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid


def call(*argv: str, timeout: int = 30, checked: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout,
    )
    if checked and result.returncode:
        raise RuntimeError(f"{argv[:3]} exited {result.returncode}: {result.stderr[-300:]}")
    return result


def candidates(devices: dict) -> tuple[list[dict], list[dict]]:
    rows = []
    for runtime, items in devices.items():
        if "iOS" not in runtime:
            continue
        for device in items:
            if (device.get("isAvailable") and
                    device.get("name", "").startswith("iPhone") and
                    device.get("deviceTypeIdentifier") and device.get("udid")):
                rows.append({
                    "runtime": runtime,
                    "type": device["deviceTypeIdentifier"],
                    "name": device["name"],
                    "udid": device["udid"],
                    "state": device.get("state", ""),
                })
    # Prefer the selected Xcode's newest runtime; never mix a device type
    # from one runtime with a different runtime during creation.
    rows.sort(key=lambda d: (
        d["state"] != "Shutdown",
        "iOS-27-2" not in d["runtime"],
        not d["name"].startswith("iPhone 17"),
        d["name"],
    ))
    borrowed = [x for x in rows if x["state"] == "Booted"]
    return borrowed[:2], [x for x in rows if x["state"] == "Shutdown"][:3]


def responsive(udid: str, out: Path) -> None:
    # Booted != usable. Verify launchd AND an actual screenshot call.
    call("xcrun", "simctl", "spawn", udid, "launchctl", "list", timeout=18)
    with tempfile.TemporaryDirectory(prefix="scarlet-sim-probe-") as td:
        image = Path(td) / "probe.png"
        call("xcrun", "simctl", "io", udid, "screenshot", str(image), timeout=22)
        if not image.is_file() or image.stat().st_size < 1000:
            raise RuntimeError("simulator screenshot health probe missing/empty")


def try_dispose(udid: str) -> None:
    for verb in ("shutdown", "delete"):
        try:
            call("xcrun", "simctl", verb, udid, timeout=10, checked=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def select(out: Path, id_file: Path, owned_file: Path) -> bool:
    record: dict = {
        "kind": "isolated_swiftui_simulator_preview",
        "status": "infra_unavailable",
        "nativeGlassVerified": False,
        "iPhoneDeviceVerified": False,
        "attempts": [],
    }
    def save() -> None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "simulator-selection.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

    try:
        raw = call("xcrun", "simctl", "list", "devices", "available", "--json", timeout=40).stdout
        devices = json.loads(raw)["devices"]
        borrowed, disposable = candidates(devices)
        if not borrowed and not disposable:
            raise RuntimeError("No compatible available iPhone/runtime pairs")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as e:
        record["attempts"].append({"mode": "discovery", "error": str(e)[:300]})
        save()
        print("[SIM][INFRA] Discovery failed; screenshot NOT verified", file=sys.stderr)
        return False

    print(f"[SIM] Responsive-device search: {len(borrowed)} booted, {len(disposable)} shutdown", flush=True)

    # A prebooted simulator is used only when it has actually responded.
    for idx, device in enumerate(borrowed, start=1):
        try:
            responsive(device["udid"], out)
            id_file.write_text(device["udid"] + "\n")
            owned_file.write_text("0\n")
            record.update(status="ready", mode="borrowed_responsive",
                          runtime=device["runtime"], device=device["name"])
            save()
            print(f"[SIM][PASS] Responsive prebooted device {device['name']}", flush=True)
            return True
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
            record["attempts"].append({"mode": "prebooted_probe", "index": idx,
                                       "runtime": device["runtime"], "error": str(e)[:250]})
            print(f"[SIM][INFRA] Prebooted probe {idx} unresponsive: {type(e).__name__}", flush=True)

    # A preconfigured shutdown device already has a prepared runner disk.
    # Before creating another virtual device (which stalled on two runners),
    # boot the matching preconfigured device in place. Restore its Shutdown
    # state after capture; never delete or erase a runner-owned template.
    for idx, device in enumerate(disposable[:2], start=1):
        udid = device["udid"]
        try:
            print(f"[SIM] Preconfigured boot attempt {idx}: {device['name']} / {device['runtime']}", flush=True)
            call("xcrun", "simctl", "boot", udid, timeout=45)
            try:
                call("xcrun", "simctl", "bootstatus", udid, "-b", timeout=80)
            except (RuntimeError, subprocess.TimeoutExpired):
                print("[SIM][INFRA] Preconfigured bootstatus inconclusive; running active probe", flush=True)
            responsive(udid, out)
            id_file.write_text(udid + "\n")
            owned_file.write_text("2\n")
            record.update(status="ready", mode="preconfigured_booted_verified",
                          runtime=device["runtime"], device=device["name"])
            save()
            print(f"[SIM][PASS] Preconfigured simulator responsive attempt {idx}", flush=True)
            return True
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
            record["attempts"].append({"mode": "preconfigured_boot",
                                       "index": idx, "runtime": device["runtime"],
                                       "error": str(e)[:250]})
            print(f"[SIM][INFRA] Preconfigured attempt {idx} failed: {type(e).__name__}", flush=True)
            try:
                call("xcrun", "simctl", "shutdown", udid, timeout=10, checked=False)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass

    for idx, device in enumerate(disposable, start=1):
        udid = None
        try:
            print(f"[SIM] Disposable attempt {idx}: {device['name']} / {device['runtime']}", flush=True)
            created = call("xcrun", "simctl", "create",
                           "Scarlet-Preview-CI-" + uuid.uuid4().hex[:8],
                           device["type"], device["runtime"], timeout=50)
            udid = created.stdout.strip()
            if not udid:
                raise RuntimeError("simctl create returned no device ID")
            call("xcrun", "simctl", "boot", udid, timeout=45)
            try:
                call("xcrun", "simctl", "bootstatus", udid, "-b", timeout=85)
            except (RuntimeError, subprocess.TimeoutExpired):
                # bootstatus itself can hang even after launchd becomes ready.
                print("[SIM][INFRA] bootstatus inconclusive; running active probe", flush=True)
            responsive(udid, out)
            id_file.write_text(udid + "\n")
            owned_file.write_text("1\n")
            record.update(status="ready", mode="disposable_verified",
                          runtime=device["runtime"], device=device["name"])
            save()
            print(f"[SIM][PASS] Disposable simulator responsive attempt {idx}", flush=True)
            return True
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
            record["attempts"].append({"mode": "disposable", "index": idx,
                                       "runtime": device["runtime"], "error": str(e)[:250]})
            print(f"[SIM][INFRA] Disposable attempt {idx} failed: {type(e).__name__}", flush=True)
            if udid:
                try_dispose(udid)

    save()
    print("[SIM][INFRA] No responsive simulator; screenshot NOT verified", file=sys.stderr)
    return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: boot_preview_simulator.py UDID_FILE OWNED_FILE OUTPUT_DIR", file=sys.stderr)
        raise SystemExit(2)
    success = select(Path(sys.argv[3]), Path(sys.argv[1]), Path(sys.argv[2]))
    raise SystemExit(0 if success else 2)

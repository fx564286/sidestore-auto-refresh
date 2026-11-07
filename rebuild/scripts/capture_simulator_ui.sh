#!/usr/bin/env bash
# Deterministic SwiftUI screenshots ONLY (not the real Scarlet IPA).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/rebuild/reports/simulator-preview}"
mkdir -p "$OUT"
SDK="$(xcrun --sdk iphonesimulator --show-sdk-path)"
APP="$RUNNER_TEMP/ScarletUIOnlyPreview.app"
BIN="$APP/ScarletUIOnlyPreview"
mkdir -p "$APP"
python3 - "$APP/Info.plist" <<'PY'
import plistlib,sys
data={
  "CFBundleName":"Scarlet UI-only Preview",
  "CFBundleDisplayName":"Scarlet UI-only Preview",
  "CFBundleExecutable":"ScarletUIOnlyPreview",
  "CFBundleIdentifier":"dev.scarlet.design.ui-only-preview",
  "CFBundlePackageType":"APPL",
  "CFBundleShortVersionString":"0.0",
  "CFBundleVersion":"1",
  "LSRequiresIPhoneOS":True,
  "UIDeviceFamily":[1],
  "UILaunchScreen":{},
  "MinimumOSVersion":"17.0"
}
with open(sys.argv[1],"wb") as f:plistlib.dump(data,f)
PY
ARCH="$(uname -m)"
case "$ARCH" in arm64|x86_64) ;; *) echo "[STOP] Unsupported simulator host arch $ARCH";exit 1;;esac
xcrun --sdk iphonesimulator swiftc -swift-version 6 -parse-as-library \
    -target "$ARCH-apple-ios17.0-simulator" -sdk "$SDK" \
    "$ROOT/rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift" \
    "$ROOT/rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift" \
    "$ROOT/rebuild/Sources/ScarletCleanCore/ScarletUpdateCoordinator.swift" \
    "$ROOT/rebuild/Sources/ScarletCleanCore/ScarletRefreshPolicy.swift" \
    "$ROOT/rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift" \
    "$ROOT/rebuild/PreviewHost/ScarletScreenshotPreviewApp.swift" \
    -o "$BIN"
codesign --force --sign - --timestamp=none "$APP"
# Never reuse the macOS runner's prebooted simulator: it can report "Booted"
# while launchd and SpringBoard are unresponsive. Isolate a new disposable
# simulator from an available iOS runtime and device type.
SIM_UDID_FILE="$RUNNER_TEMP/scarlet-preview-udid.txt"
python3 - "$SIM_UDID_FILE" <<'PY'
import json,subprocess,sys,time,uuid
from pathlib import Path

def run(*args, seconds=30, checked=True):
    cp=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                      text=True,timeout=seconds)
    if checked and cp.returncode:
        raise RuntimeError(f"{args[:4]} failed rc={cp.returncode}: {cp.stderr[-600:]}")
    return cp

# Pair each simulated device type with the *same* runtime as an actual
# available runner image. Selecting newest runtime + newest phone separately
# yielded CoreSimulator.SimError 403 ("Incompatible device") on Xcode 27.2.
try:
    data=json.loads(run("xcrun","simctl","list","devices","available",
                        "--json",seconds=40).stdout)["devices"]
except Exception as e:
    print(f"[SIM][INFRA] Available simulator discovery failed: {e}",file=sys.stderr)
    sys.exit(2)
pairs=[]
for runtime_id,devices in data.items():
    if "iOS" not in runtime_id:
        continue
    for device in devices:
        name=device.get("name","")
        type_id=device.get("deviceTypeIdentifier")
        if device.get("isAvailable") and name.startswith("iPhone") and type_id:
            pairs.append((runtime_id,type_id,name,device.get("udid",""),device.get("state","")))
if not pairs:
    print("[SIM][INFRA] No preconfigured compatible iPhone/runtime pair",file=sys.stderr)
    sys.exit(2)
# Prefer a non-running template so the runner's stuck booted simulator remains
# undisturbed. Always use the complete device/runtime pair from the same row.
pairs.sort(key=lambda p:(p[4]!="Shutdown",not p[2].startswith("iPhone 17"),p[2]))
print(f"[SIM] Available compatible combinations: {len(pairs)}",file=sys.stderr)

for attempt in (1,2):
    udid=None
    try:
        runtime,device_type,device_name,template_udid,_ = pairs[min(attempt-1,len(pairs)-1)]
        print(f"[SIM] Attempt {attempt} using {device_name} / {runtime}",file=sys.stderr)
        if attempt==2:
            # The first try may leave a stuck simulator daemon on hosted macOS.
            # Restart only CoreSimulatorService, never user data / host keychains.
            run("killall","-9","com.apple.CoreSimulator.CoreSimulatorService",
                seconds=12,checked=False)
            time.sleep(4)
        name="Scarlet-Preview-CI-"+uuid.uuid4().hex[:8]
        udid=run("xcrun","simctl","create",name,device_type,runtime,
                 seconds=50).stdout.strip()
        if not udid:
            raise RuntimeError("Simulator create returned empty UDID")
        run("xcrun","simctl","boot",udid,seconds=45)
        try:
            run("xcrun","simctl","bootstatus",udid,"-b",seconds=115)
        except (subprocess.TimeoutExpired,RuntimeError):
            # bootstatus sometimes stalls even if launchd is responsive.
            # Positive launchd evidence is mandatory before proceeding.
            run("xcrun","simctl","spawn",udid,"launchctl","list",seconds=25)
        print(f"[SIM] Verified disposable runtime (attempt {attempt})",file=sys.stderr)
        Path(sys.argv[1]).write_text(udid + "\n")
        sys.exit(0)
    except Exception as e:
        print(f"[SIM][INFRA] Attempt {attempt} failed: {e}",file=sys.stderr)
        if udid:
            for command in ("shutdown","delete"):
                try:
                    run("xcrun","simctl",command,udid,seconds=12,checked=False)
                except Exception: pass
print("[SIM][INFRA] No responsive iPhone Simulator: capture not verified",file=sys.stderr)
sys.exit(2)
PY
UDID="$(cat "$SIM_UDID_FILE")"
echo "[SIM] Dedicated device $UDID"
cleanup() {
  python3 - "$UDID" <<'PY'
import subprocess,sys
for command in ("shutdown","delete"):
    try: subprocess.run(["xcrun","simctl",command,sys.argv[1]],
                        timeout=12,stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    except Exception: pass
PY
}
trap cleanup EXIT
python3 - "$UDID" "$APP" <<'PY'
import subprocess,sys,time
udid,app=sys.argv[1:]
# On cold GitHub macOS runners CoreSimulator can need more than 60s to
# initialize its package installation service after launchd becomes ready.
# Retry only the disposable simulator; never report a screenshot on failure.
for attempt in range(1,3):
    try:
        subprocess.run(["xcrun","simctl","install",udid,app],
                       check=True,timeout=180)
        print(f"[SIM] App installed successfully (attempt {attempt})",flush=True)
        break
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
        print(f"[SIM] Install attempt {attempt}/2 failed: {type(exc).__name__}",file=sys.stderr,flush=True)
        if attempt == 2:
            raise
        subprocess.run(["xcrun","simctl","bootstatus",udid,"-b"],
                       check=False,timeout=90)
        time.sleep(8)
PY
for screen in home apps sources settings connection; do
  python3 - "$UDID" "$screen" "$OUT/$screen.png" <<'PY'
import subprocess,sys,time
udid,screen,out=sys.argv[1:]
subprocess.run(["xcrun","simctl","launch","--terminate-running-process",
                udid,"dev.scarlet.design.ui-only-preview","--screen",screen],
               check=True,timeout=35)
time.sleep(3)
subprocess.run(["xcrun","simctl","io",udid,"screenshot",out],
               check=True,timeout=35,stdout=subprocess.DEVNULL)
PY
  [[ -s "$OUT/$screen.png" ]] || { echo "[FAIL] Missing screenshot $screen"; exit 1; }
  echo "[SCREENSHOT] $screen.png"
done
python3 - "$OUT" <<'PY'
from pathlib import Path
import json,sys
root=Path(sys.argv[1])
imgs=[{"screen":p.stem,"bytes":p.stat().st_size} for p in root.glob("*.png")]
assert len(imgs)==5,imgs
assert all(x["bytes"]>10000 for x in imgs),imgs
(root/"metadata.json").write_text(json.dumps({
    "renderKind":"isolated_swiftui_simulator_preview",
    "nativeGlassVerified":False,
    "originalHostIntegrated":False,
    "appleLoginVerified":False,
    "notes":"Matte mock controls, not original Liquid Glass. Compare only non-glass UI layout to Figma.",
    "images":imgs
},indent=2)+"\n")
print("[PASS] FIVE_REAL_SIMULATOR_SWIFTUI_SCREENSHOTS_NOT_DEVICE_OR_GLASS_PROOF")
PY

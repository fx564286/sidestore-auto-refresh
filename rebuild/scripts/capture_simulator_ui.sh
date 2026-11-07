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
UDID="$(python3 - <<'PY'
import json,subprocess,sys,time,uuid

def run(*args, seconds=30, checked=True):
    cp=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                      text=True,timeout=seconds)
    if checked and cp.returncode:
        raise RuntimeError(f"{args[:4]} failed rc={cp.returncode}: {cp.stderr[-600:]}")
    return cp

try:
    types=json.loads(run("xcrun","simctl","list","devicetypes","--json",seconds=40).stdout)["devicetypes"]
    runtimes=json.loads(run("xcrun","simctl","list","runtimes","--json",seconds=40).stdout)["runtimes"]
except Exception as e:
    print(f"[SIM][INFRA] CoreSimulator discovery failed: {e}",file=sys.stderr)
    sys.exit(2)
phones=[x for x in types if x.get("identifier") and x.get("name","").startswith("iPhone")]
ios=[x for x in runtimes if x.get("isAvailable") and "iOS" in x.get("name","")]
if not phones or not ios:
    print("[SIM][INFRA] No available iOS runtime or iPhone device type",file=sys.stderr)
    sys.exit(2)
phones.sort(key=lambda x:(not x["name"].startswith("iPhone 17"),x["name"]))
ios.sort(key=lambda x:x.get("version",""),reverse=True)
device_type,runtime=phones[0]["identifier"],ios[0]["identifier"]
print(f"[SIM] Disposable device: {phones[0]['name']} / {ios[0]['name']}",file=sys.stderr)

for attempt in (1,2):
    udid=None
    try:
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
        print(udid)
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
)"
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
import subprocess,sys
subprocess.run(["xcrun","simctl","install",sys.argv[1],sys.argv[2]],
               check=True,timeout=60)
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

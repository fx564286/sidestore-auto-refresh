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
SIM_OWNED_FILE="$RUNNER_TEMP/scarlet-preview-owned.txt"
# Positive readiness evidence is required. The selector first probes an
# already-booted device and then fresh isolated compatible runtime pairs.
# It never kills the machine-wide CoreSimulatorService.
python3 "$ROOT/rebuild/scripts/boot_preview_simulator.py" \
    "$SIM_UDID_FILE" "$SIM_OWNED_FILE" "$OUT"
UDID="$(cat "$SIM_UDID_FILE")"
echo "[SIM] Dedicated device $UDID"
cleanup() {
  # Mode 0: already booted runner template -- leave untouched.
  # Mode 2: we booted a runner template -- shut down only.
  # Mode 1: our disposable simulator -- shut down and delete.
  local mode
  mode="$(cat "$SIM_OWNED_FILE")"
  if [[ "$mode" == "0" ]]; then
    echo "[SIM] Existing runner simulator retained"
    return
  fi
  python3 - "$UDID" "$mode" <<'PY'
import subprocess,sys
actions=("shutdown", "delete") if sys.argv[2]=="1" else ("shutdown",)
for command in actions:
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

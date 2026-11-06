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
UDID="$(xcrun simctl list devices available --json | python3 -c '
import json,sys
data=json.load(sys.stdin)
devices=[d for bucket in data["devices"].values() for d in bucket
         if d.get("isAvailable") and d.get("name","").startswith("iPhone")]
if not devices:raise SystemExit("No available iPhone simulator")
devices.sort(key=lambda d:(not any(x in d["name"] for x in ("iPhone 16","iPhone 17")),d["name"]))
print(devices[0]["udid"])
')"
echo "[SIM] Selected device $UDID"
cleanup(){ xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true; }
trap cleanup EXIT
xcrun simctl boot "$UDID"
xcrun simctl bootstatus "$UDID" -b
xcrun simctl install "$UDID" "$APP"
for screen in home apps sources settings connection; do
  xcrun simctl launch --terminate-running-process "$UDID" \
    dev.scarlet.design.ui-only-preview --screen "$screen"
  sleep 3
  xcrun simctl io "$UDID" screenshot "$OUT/$screen.png" >/dev/null
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

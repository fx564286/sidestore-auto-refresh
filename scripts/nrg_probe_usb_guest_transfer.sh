#!/usr/bin/env bash
# Read-only account/certificate posture: stage only a test guest IPA into
# the existing NRG Documents directory using iPhone USB file sharing.
# Never install, resign, overwrite, revoke, or change app identifiers.
set -euo pipefail
umask 077

ROOT="$HOME/NRG-Tools"
SOURCE="$ROOT/NRGLinuxProbe/xtool/NRGLinuxProbe.ipa"
HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"
DEVICE_ID="00008160-000569490C600036"
DESTNAME="NRGLinuxProbe-USB-Guest-20261021.ipa"
MOUNT_DIR=""

say() { printf '%s\n' "$*"; }
fail() { say "[FAIL] $*" >&2; exit 1; }
cleanup() {
  status=$?
  trap - EXIT
  if [[ -n "$MOUNT_DIR" && -d "$MOUNT_DIR" ]]; then
    if mountpoint -q "$MOUNT_DIR" 2>/dev/null; then
      if command -v fusermount3 >/dev/null 2>&1; then
        fusermount3 -u "$MOUNT_DIR" || true
      elif command -v fusermount >/dev/null 2>&1; then
        fusermount -u "$MOUNT_DIR" || true
      else
        say "[WARN] FUSE mount still active at $MOUNT_DIR; unmount manually."
      fi
    fi
    if ! mountpoint -q "$MOUNT_DIR" 2>/dev/null; then
      rmdir "$MOUNT_DIR" 2>/dev/null || true
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

command -v ifuse >/dev/null 2>&1 || fail "ifuse missing. Install: sudo pacman -S --needed ifuse libimobiledevice usbmuxd fuse3"
command -v mountpoint >/dev/null 2>&1 || fail "mountpoint is missing"
command -v python3 >/dev/null 2>&1 || fail "python3 is missing"
[[ -s "$SOURCE" ]] || fail "Test IPA missing: $SOURCE"

python3 - "$SOURCE" <<'PY'
import sys,zipfile,plistlib
with zipfile.ZipFile(sys.argv[1]) as ipa:
    files=[n for n in ipa.namelist() if n.startswith("Payload/") and n.endswith(".app/Info.plist") and n.count("/")==2]
    if len(files)!=1: raise SystemExit("[FAIL] Not a single-app IPA")
    identity=plistlib.loads(ipa.read(files[0])).get("CFBundleIdentifier")
    if identity!="com.example.NRGLinuxProbe":
        raise SystemExit("[FAIL] Unexpected Bundle ID; refusing copy")
print("[PASS] Isolated test guest IPA verified")
PY

say "=== USB FILE SHARING ==="
APP_LIST="$(ifuse --list-apps --udid "$DEVICE_ID" 2>&1)" || fail "Unable to enumerate file-sharing apps. Unlock iPhone, tap Trust, check usbmuxd."
if ! printf '%s\n' "$APP_LIST" | grep -Fq "$HOST_ID"; then
  fail "Existing NRG file-sharing app not found; no files changed."
fi
say "[PASS] Existing NRG file sharing detected"

MOUNT_DIR="$(mktemp -d -t nrg-probe-usb.XXXXXXXX)"
if ! ifuse --documents "$HOST_ID" --udid "$DEVICE_ID" "$MOUNT_DIR"; then
  fail "Could not mount NRG Documents; no files changed."
fi
for n in 1 2 3 4 5 6 7 8 9 10; do
  mountpoint -q "$MOUNT_DIR" && break
  sleep 0.25
done
mountpoint -q "$MOUNT_DIR" || fail "FUSE mount inactive"
say "[PASS] NRG Documents mounted"

DEST="$MOUNT_DIR/$DESTNAME"
if [[ -e "$DEST" ]]; then
  if cmp -s -- "$SOURCE" "$DEST"; then
    say "[PASS] Identical guest IPA already staged"
    say "STAGED_FILENAME=$DESTNAME"
    exit 0
  fi
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  DESTNAME="NRGLinuxProbe-USB-Guest-$STAMP.ipa"
  DEST="$MOUNT_DIR/$DESTNAME"
  [[ ! -e "$DEST" ]] || fail "Destination collision; refusing overwrite."
fi

cp -- "$SOURCE" "$DEST" || fail "USB IPA copy failed"
cmp -s -- "$SOURCE" "$DEST" || fail "USB file verification failed"
say "[PASS] Guest IPA staged and byte-for-byte verified"
say "STAGED_FILENAME=$DESTNAME"
say "NEXT_ON_IPHONE=NRG > Apps > + > Install from IPA > select the staged file in On My iPhone."
say "NRG_HOST_AND_CERTIFICATE_UNCHANGED=YES"

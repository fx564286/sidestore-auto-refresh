#!/usr/bin/env bash
# Scarlet Crystal V190 paired-device upgrade. Does NOT delete apps or profiles.
# Requires an existing USB or Wi-Fi trusted pairing to this iPhone.
set -Eeuo pipefail
umask 077
REPO="fx564286/sidestore-auto-refresh"
TAG="scarlet-v190-device-signed-20261105"
FILE="Scarlet-Crystal-V190-SIGNED-DEVELOPMENT.ipa"
SHA="e774184a11e5be33a3ded1837d15c3651cdbce1904c73d91d4538f69907f309e"
BUNDLE="com.kdt.livecontainer.P8EZT3U5N4"
DEST="$HOME/.local/share/scarlet-crystal/v190-device-install"
FAIL(){ printf '[STOP] %s\n' "$*" >&2; exit 2; }
[[ "$(id -u)" != 0 ]] || FAIL "Do not run as root"
for exe in gh idevice_id ideviceinstaller ideviceinfo idevicepair sha256sum python3; do
  command -v "$exe" >/dev/null || FAIL "Missing command: $exe"
done
gh auth status >/dev/null 2>&1 || FAIL "GitHub CLI not authenticated on this CachyOS PC"
mkdir -p "$DEST"
chmod 700 "$DEST"
echo "[1/5] Download V190 exact published Apple Development IPA"
gh release download "$TAG" -R "$REPO" --dir "$DEST" --pattern "$FILE" --clobber >/dev/null
echo "$SHA  $DEST/$FILE" | sha256sum -c - || FAIL "Published IPA checksum mismatch"
python3 - "$DEST/$FILE" "$BUNDLE" <<'PY'
import plistlib,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    infos=[p for p in z.namelist() if p.startswith("Payload/")
           and p.endswith(".app/Info.plist") and p.count(".app/")==1]
    if len(infos)!=1: raise SystemExit("[STOP] Exactly one iOS app expected")
    info=plistlib.loads(z.read(infos[0]))
    assert info.get("CFBundleIdentifier")==sys.argv[2],info.get("CFBundleIdentifier")
    assert info.get("CFBundleVersion")=="3.8.204",info.get("CFBundleVersion")
    assert info.get("ScarletBuildLabel")=="V190"
    print("[PASS] V190 exact host identity verified")
PY

echo "[2/5] Detect an already paired iPhone (USB preferred)"
mapfile -t usb < <(idevice_id -l | sed '/^[[:space:]]*$/d' || true)
mapfile -t wifi < <(idevice_id -n | sed '/^[[:space:]]*$/d' || true)
FLAGS=()
if (("${#usb[@]}" == 1)); then
  ID="${usb[0]}"
elif (("${#usb[@]}" > 1)); then
  FAIL "Multiple USB devices; refuse automatic device selection"
elif (("${#wifi[@]}" == 1)); then
  ID="${wifi[0]}"
  FLAGS=(-n)
elif (("${#wifi[@]}" > 1)); then
  FAIL "Multiple Wi-Fi devices; refuse automatic device selection"
else
  FAIL "No already paired iPhone reachable over USB or LAN Wi-Fi. No installation attempted."
fi

echo "[3/5] Check trusted pairing and existing installed host (no uninstall)"
ideviceinfo "${FLAGS[@]}" -u "$ID" -k ProductVersion >/dev/null ||
  FAIL "Device unreachable or pairing not trusted; no installation attempted"
if (("${#FLAGS[@]}" == 0)); then
  idevicepair -u "$ID" validate >/dev/null || FAIL "Existing USB pairing invalid"
fi
if ! ideviceinstaller "${FLAGS[@]}" -u "$ID" list --user 2>/dev/null | grep -Fq "$BUNDLE"; then
  FAIL "Existing Scarlet Crystal host not found; refusing fresh/replace install"
fi

echo "[4/5] Upgrade in place: preserve app data and exact Bundle ID"
if ! ideviceinstaller --help 2>&1 | grep -Eq 'upgrade[[:space:]]+PATH'; then
  FAIL "Installed ideviceinstaller does not expose safe upgrade PATH command"
fi
ideviceinstaller "${FLAGS[@]}" -u "$ID" -w upgrade "$DEST/$FILE"

echo "[5/5] Confirm the installed bundle still exists"
ideviceinstaller "${FLAGS[@]}" -u "$ID" list --user | grep -F "$BUNDLE" >/dev/null ||
  FAIL "Upgrade command ended but installed app not visible"
echo "[PASS] V190 paired iPhone upgrade command returned success and app remains present"
echo "[IPA] $DEST/$FILE"
echo "[NOTE] Confirm ScarletBuildLabel=V190 and app build 3.8.204 inside iPhone."
echo "[NOTE] Actual Apple login/2FA and runtime UI must be re-validated after launch."

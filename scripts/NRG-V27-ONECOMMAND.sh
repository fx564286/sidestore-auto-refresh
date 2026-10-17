#!/usr/bin/env bash
# NRG V27: USB upgrade in place, preserving existing app container.
set -Eeuo pipefail
umask 077

ROOT="$HOME/다운로드/NRG-V27-DIRECT"
ART="$ROOT/artifact"
IPA="$ART/LiveContainer-SideStore-v3.0.3-rc.ipa"
REPO="fx564286/sidestore-auto-refresh"
RUN="39014208888"
EXPECTED_SHA="61e8a0f75a32cfb34ba5f082b8b7d2594e1df9a9"
ZSIGN="$HOME/.sideinstaller/bin/zsign"
mkdir -p "$ART"

LOG="$ROOT/NRG-V27-install.log"
exec > >(tee -a "$LOG") 2>&1
trap 'code=$?; echo "[FAIL] exit=$code line=$LINENO. Existing app was NOT uninstalled. Log: $LOG" >&2' ERR
echo "[START] NRG V27 in-place USB installer"

for tool in python3 openssl sha256sum idevice_id ideviceinstaller; do
  command -v "$tool" >/dev/null || { echo "[ERROR] Missing: $tool"; exit 2; }
done
[[ -x "$ZSIGN" ]] || { echo "[ERROR] Missing: $ZSIGN"; exit 3; }

SIGN=""
for candidate in "$HOME"/.sideinstaller/recovery-v13-*; do
  [[ -d "$candidate" && -s "$candidate/renewed-key.pem" &&
     -s "$candidate/renewed-cert.pem" ]] || continue
  complete=1
  for n in 0 1 2 3 4; do
    [[ -s "$candidate/profile-$n.mobileprovision" ]] || complete=0
  done
  if (( complete )); then SIGN="$candidate"; break; fi
done
[[ -n "$SIGN" ]] || { echo "[ERROR] Existing five-profile signing identity not found"; exit 4; }
SUFFIX="${SIGN##*recovery-v13-}"
BUNDLE="com.kdt.livecontainer.$SUFFIX"

openssl x509 -in "$SIGN/renewed-cert.pem" -checkend 0 -noout
key_hash=$(openssl pkey -in "$SIGN/renewed-key.pem" -pubout -outform DER | sha256sum | cut -d' ' -f1)
cert_hash=$(openssl x509 -in "$SIGN/renewed-cert.pem" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum | cut -d' ' -f1)
[[ "$key_hash" = "$cert_hash" ]] || { echo "[ERROR] Key and certificate do not match"; exit 5; }

mapfile -t devices < <(idevice_id -l)
if (( ${#devices[@]} != 1 )); then
  echo "[ERROR] Connect exactly one trusted iPhone by USB; detected ${#devices[@]}"
  exit 6
fi
UDID="${devices[0]}"
echo "[DEVICE] Paired iPhone detected; no removal will be performed"

if [[ ! -s "$IPA" ]]; then
  command -v gh >/dev/null || { echo "[ERROR] Missing gh for IPA download"; exit 7; }
  echo "[DOWNLOAD] https://github.com/$REPO/actions/runs/$RUN"
  gh run download "$RUN" -R "$REPO" \
    -n "LiveContainer-SideStore-v3.0.3-rc-IPA" -D "$ART"
fi
[[ -s "$IPA" ]] || { echo "[ERROR] V27 IPA missing"; exit 8; }
if [[ -s "$ART/builder-commit.txt" ]]; then
  grep -Fq "$EXPECTED_SHA" "$ART/builder-commit.txt" || {
    echo "[ERROR] Build provenance SHA mismatch"; exit 9;
  }
fi
python3 - "$IPA" <<'PY'
import sys, zipfile, plistlib, re
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.testzip() is None, "Damaged archive"
    info=plistlib.loads(z.read("Payload/LiveContainer.app/Info.plist"))
    assert info["CFBundleIdentifier"]=="com.kdt.livecontainer", info
    exts=[x for x in z.namelist() if re.fullmatch(
        r"Payload/LiveContainer.app/PlugIns/[^/]+\.appex/Info.plist",x)]
    assert len(exts)==4, f"Expected four extensions, found {len(exts)}"
print("[PASS] V27 source archive and extension count")
PY
OUT="$ART/NRG-V27-SIGNED-$(date +%Y%m%d-%H%M%S).ipa"
"$ZSIGN" -f -k "$SIGN/renewed-key.pem" -c "$SIGN/renewed-cert.pem" \
  -m "$SIGN/profile-0.mobileprovision" \
  -m "$SIGN/profile-1.mobileprovision" \
  -m "$SIGN/profile-2.mobileprovision" \
  -m "$SIGN/profile-3.mobileprovision" \
  -m "$SIGN/profile-4.mobileprovision" \
  -b "$BUNDLE" -r 3.8.22 -o "$OUT" "$IPA"
python3 - "$OUT" "$BUNDLE" <<'PY'
import sys, zipfile, plistlib
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.testzip() is None, "Damaged signed archive"
    base="Payload/LiveContainer.app/"
    info=plistlib.loads(z.read(base+"Info.plist"))
    assert info["CFBundleIdentifier"]==sys.argv[2], info
    assert info["CFBundleShortVersionString"]=="3.8.22", info
    assert base+"embedded.mobileprovision" in z.namelist()
print("[PASS] Signed archive, bundle ID and profile")
PY

echo "[INSTALL] USB in-place upgrade; existing app data should be preserved"
ideviceinstaller -u "$UDID" upgrade "$OUT"
echo "[VERIFY] Installed bundle"
installed=$(ideviceinstaller -u "$UDID" list --bundle-identifier "$BUNDLE")
printf '%s\n' "$installed"
grep -Fq "$BUNDLE" <<< "$installed" || {
  echo "[ERROR] Bundle not returned by installer query"; exit 10;
}
echo "[SUCCESS] USB upgrade returned success; launch the app to validate V27 runtime"
echo "[LOG] $LOG"

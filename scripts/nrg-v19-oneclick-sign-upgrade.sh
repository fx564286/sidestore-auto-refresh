#!/usr/bin/env bash
# NRG v19: download build, sign with existing v13 identity, upgrade paired iPhone.
set -Eeuo pipefail
umask 077
REPO=fx564286/sidestore-auto-refresh
RUN=38958855142
UDID=00008160-000569490C600036
BUNDLE=com.kdt.livecontainer.P8EZT3U5N4
ROOT="$HOME/다운로드/NRG-IPA"
SIGN="$HOME/.sideinstaller/recovery-v13-P8EZT3U5N4"
ZSIGN="$HOME/.sideinstaller/bin/zsign"
mkdir -p "$ROOT/v19-build"
cd "$ROOT"
for cmd in gh openssl python3 ideviceinstaller idevice_id sha256sum; do command -v "$cmd" >/dev/null || { echo "[ERROR] Missing $cmd"; exit 2; }; done
[[ -x "$ZSIGN" ]] || { echo "[ERROR] Missing zsign $ZSIGN"; exit 3; }
[[ -s "$SIGN/renewed-key.pem" && -s "$SIGN/renewed-cert.pem" ]] || { echo "[ERROR] Existing key/cert missing"; exit 4; }
for i in 0 1 2 3 4; do [[ -s "$SIGN/profile-$i.mobileprovision" ]] || { echo "[ERROR] profile-$i missing"; exit 5; }; done
openssl x509 -in "$SIGN/renewed-cert.pem" -checkend 0 -noout
a=$(openssl pkey -in "$SIGN/renewed-key.pem" -pubout -outform DER | sha256sum | cut -d' ' -f1)
b=$(openssl x509 -in "$SIGN/renewed-cert.pem" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum | cut -d' ' -f1)
[[ "$a" == "$b" ]] || { echo "[ERROR] Certificate/private key mismatch"; exit 6; }
IPA="$ROOT/v19-build/LiveContainer-SideStore-v3.0.3-rc.ipa"
if [[ ! -s "$IPA" ]]; then
  echo "[DOWNLOAD] https://github.com/$REPO/actions/runs/$RUN"
  gh run download "$RUN" --repo "$REPO" --name LiveContainer-SideStore-v3.0.3-rc-IPA --dir "$ROOT/v19-build"
fi
[[ -s "$IPA" ]] || { echo "[ERROR] IPA download failed"; exit 7; }
echo "[SOURCE SHA256] $(sha256sum "$IPA")"
OUT="$ROOT/NRG-JITLESS-USB-AUTO-v19-SIGNED.ipa"
if [[ -e "$OUT" ]]; then OUT="$ROOT/NRG-JITLESS-USB-AUTO-v19-SIGNED-$(date +%Y%m%d-%H%M%S).ipa"; fi
"$ZSIGN" -f -k "$SIGN/renewed-key.pem" -c "$SIGN/renewed-cert.pem" \
  -m "$SIGN/profile-0.mobileprovision" -m "$SIGN/profile-1.mobileprovision" \
  -m "$SIGN/profile-2.mobileprovision" -m "$SIGN/profile-3.mobileprovision" \
  -m "$SIGN/profile-4.mobileprovision" -b "$BUNDLE" -r 3.8.16 -o "$OUT" "$IPA"
python3 - "$OUT" "$BUNDLE" <<'PY'
import sys, zipfile, plistlib, re
path, bundle = sys.argv[1:]
with zipfile.ZipFile(path) as z:
    assert z.testzip() is None
    p='Payload/LiveContainer.app/'
    info=plistlib.loads(z.read(p+'Info.plist'))
    assert info['CFBundleIdentifier']==bundle
    assert info['CFBundleShortVersionString']=='3.8.16'
    exts=[n for n in z.namelist() if re.fullmatch(r'Payload/LiveContainer.app/PlugIns/[^/]+\.appex/Info.plist',n)]
    assert len(exts)==4, (len(exts),exts)
    assert p+'embedded.mobileprovision' in z.namelist()
    host=z.read(p+'Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI')
    assert b'certExportActive' in host
print('[PASS] Signed archive, identity, version, extensions, recovery-code markers')
PY
P12="$SIGN/NRG-existing-signing-identity-v16.p12"
PASS="$SIGN/NRG-existing-signing-identity-v16.password"
if [[ ! -e "$P12" && ! -e "$PASS" ]]; then
  openssl rand -hex 24 > "$PASS"
  openssl pkcs12 -export -inkey "$SIGN/renewed-key.pem" -in "$SIGN/renewed-cert.pem" -out "$P12" \
    -passout "file:$PASS" -keypbe PBE-SHA1-3DES -certpbe PBE-SHA1-3DES
fi
[[ -s "$P12" && -s "$PASS" ]] || { echo "[ERROR] P12/password missing or incomplete"; exit 8; }
openssl pkcs12 -in "$P12" -passin "file:$PASS" -clcerts -nokeys -out /dev/null
echo "[SIGNED] $OUT"
echo "[P12 LOCAL] $P12"
echo "[P12 PASSWORD LOCAL] $PASS"
echo "[DEVICE] $UDID"
idevice_id -l | grep -Fx "$UDID" || { echo "[WARN] iPhone not connected; signed IPA preserved"; exit 9; }
echo "[INSTALL] Upgrading existing NRG, not uninstalling..."
ideviceinstaller -u "$UDID" upgrade "$OUT"
echo "[VERIFY]"
ideviceinstaller -u "$UDID" list --bundle-identifier "$BUNDLE"
echo "[COMPLETE] NRG v19 upgraded. Pairing remains unchanged."
echo "[NEXT] Import the existing identity into embedded SideStore using the one-time USB inbox."
echo "[NEXT] Then select Embedded SideStore Certificate Import inside NRG."

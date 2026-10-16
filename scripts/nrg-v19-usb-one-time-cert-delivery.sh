#!/usr/bin/env bash
# Deliver the user's existing encrypted PKCS12 over trusted USB to the already installed NRG.
# This script never prints or uploads key material/password to GitHub.
set -Eeuo pipefail
umask 077
BUNDLE=com.kdt.livecontainer.P8EZT3U5N4
UDID=00008160-000569490C600036
ROOT="$HOME/.sideinstaller/recovery-v13-P8EZT3U5N4"
P12="$ROOT/NRG-existing-signing-identity-v16.p12"
PASS="$ROOT/NRG-existing-signing-identity-v16.password"
command -v python3 >/dev/null
command -v idevice_id >/dev/null
command -v ideviceinstaller >/dev/null
command -v openssl >/dev/null
[[ -s "$P12" && -s "$PASS" ]] || { echo '[ERROR] Original encrypted P12 or password missing'; exit 5; }
[[ "$(stat -c %s "$P12")" -le 4194304 ]] || exit 5
[[ "$(stat -c %s "$PASS")" -le 1024 ]] || exit 5
idevice_id -l | grep -Fx "$UDID" >/dev/null || { echo '[ERROR] Target iPhone is not connected'; exit 6; }
ideviceinstaller -u "$UDID" list --bundle-identifier "$BUNDLE" | grep -F '"3.8.16"' >/dev/null || { echo '[ERROR] NRG V19 must be installed'; exit 7; }
openssl pkcs12 -in "$P12" -passin "file:$PASS" -clcerts -nokeys -out /dev/null || { echo '[ERROR] P12/password validation failed'; exit 8; }
echo '[READY] Valid original encrypted P12; NRG V19 installed, USB target matches'
# AFC targets only the already installed app's own Documents container.
# Upload password first, then P12; side-loaded secret files are consumed and
# removed in-app on the next embedded SideStore certificate import operation.
export PYMOBILEDEVICE3_UDID="$UDID"
python3 -m pymobiledevice3 apps push "$BUNDLE" "$PASS" Documents/NRG-OneTimeCertificate.password
python3 -m pymobiledevice3 apps push "$BUNDLE" "$P12" Documents/NRG-OneTimeCertificate.p12
echo '[STAGED] Existing signing identity transferred via local USB to NRG Documents.'
echo '[NEXT] Invoke NRG > Settings > Import Certificate from embedded SideStore once.'
echo '[SECURITY] In-app V19 importer removes both staging files after consumption.'

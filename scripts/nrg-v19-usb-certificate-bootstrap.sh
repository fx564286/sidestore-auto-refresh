#!/usr/bin/env bash
# NRG v19 one-time USB certificate bootstrap.
# No Apple Developer portal calls, revocation, app uninstall, or cloud upload.
set -Eeuo pipefail
umask 077

BUNDLE='com.kdt.livecontainer.P8EZT3U5N4'
UDID='00008160-000569490C600036'
IDENTITY="$HOME/.sideinstaller/recovery-v13-P8EZT3U5N4"
P12="$IDENTITY/NRG-existing-signing-identity-v16.p12"
PASSWORD="$IDENTITY/NRG-existing-signing-identity-v16.password"
CERT="$IDENTITY/renewed-cert.pem"
PUSH='python3 -m pymobiledevice3 apps push'

for command_name in python3 idevice_id ideviceinstaller openssl sha256sum; do
    command -v "$command_name" >/dev/null || {
        printf '[ERROR] Required command missing: %s\n' "$command_name" >&2
        exit 2
    }
done
python3 -c 'import pymobiledevice3' || {
    echo '[ERROR] Install pymobiledevice3 in your active Python environment.' >&2
    exit 2
}
for filename in "$P12" "$PASSWORD" "$CERT"; do
    [[ -s "$filename" ]] || { echo '[ERROR] Existing certificate material not found.' >&2; exit 3; }
done
[[ "$(stat -c '%s' "$P12")" -le 4194304 ]] || { echo '[ERROR] P12 exceeds size limit.' >&2; exit 3; }
[[ "$(stat -c '%s' "$PASSWORD")" -le 1024 ]] || { echo '[ERROR] Password exceeds size limit.' >&2; exit 3; }

idevice_id -l | grep -Fxq "$UDID" || {
    echo '[ERROR] Paired iPhone is not connected by USB.' >&2
    exit 4
}
version_record="$(ideviceinstaller -u "$UDID" list --bundle-identifier "$BUNDLE")"
grep -Fq '"3.8.16"' <<< "$version_record" || {
    echo '[ERROR] NRG v19 (3.8.16) must already be installed. Existing apps were not touched.' >&2
    exit 5
}

# Validate that the password decrypts the P12 and its X.509 leaf is exactly
# the currently installed signing certificate. Do not print or log secrets.
p12_cert_digest="$(
    openssl pkcs12 -in "$P12" -passin "file:$PASSWORD" -clcerts -nokeys 2>/dev/null |
    openssl x509 -outform DER 2>/dev/null | sha256sum | awk '{print $1}'
)"
active_cert_digest="$(
    openssl x509 -in "$CERT" -outform DER 2>/dev/null | sha256sum | awk '{print $1}'
)"
[[ -n "$p12_cert_digest" && "$p12_cert_digest" == "$active_cert_digest" ]] || {
    echo '[ERROR] P12 does not match the existing signing certificate.' >&2
    exit 6
}
openssl x509 -in "$CERT" -checkend 0 -noout >/dev/null || {
    echo '[ERROR] Existing signing certificate has expired.' >&2
    exit 6
}

echo '[PASS] iPhone paired, NRG 3.8.16 installed, existing P12 verified.'
echo '[USB] Sending encrypted certificate into NRG Documents inbox ...'
$PUSH "$BUNDLE" "$P12" 'Documents/NRG-OneTimeCertificate.p12'
echo '[USB] Sending matching local password into NRG Documents inbox ...'
$PUSH "$BUNDLE" "$PASSWORD" 'Documents/NRG-OneTimeCertificate.password'

echo '[STAGED] Both existing signing-identity files are now in the one-time app inbox.'
echo '[NEXT] Open NRG > Settings > Import Certificate from embedded SideStore.'
echo '[NEXT] No file chooser: v19 should consume the inbox, activate the certificate,'
echo '       import to LiveContainer, and delete both temporary device files.'
echo '[VERIFY] Refresh JIT-Less Mode Diagnose; certificate data/password must both be Yes.'
echo '[SECURITY] Do this immediately. Do not back up or share the device inbox files.'

#!/usr/bin/env bash
# Local Apple CA trust for Scarlet V187 signing repair. No system CA changes.
set -Eeuo pipefail
umask 077

WORK="$HOME/.local/share/scarlet-crystal/v187"
TLS="$WORK/tls"
mkdir -p "$TLS"
chmod 700 "$WORK" "$TLS"

# Fingerprints published in Apple's official root certificate inventory:
# https://support.apple.com/ko-kr/126047
fetch_root() {
  local url="$1" expected="$2" name="$3"
  local tmp="$TLS/$name.tmp" der="$TLS/$name.cer" pem="$TLS/$name.pem"
  curl -fsSL --retry 3 --connect-timeout 15 --max-time 60 "$url" -o "$tmp"
  openssl x509 -inform DER -in "$tmp" -outform DER > "$TLS/$name.normalized.der"
  local actual
  actual="$(sha256sum "$TLS/$name.normalized.der" | cut -d' ' -f1)"
  if [[ "$actual" != "$expected" ]]; then
    echo "[STOP] CA_FINGERPRINT_MISMATCH $name actual=$actual" >&2
    rm -f "$tmp" "$TLS/$name.normalized.der"
    exit 3
  fi
  mv "$tmp" "$der"
  openssl x509 -inform DER -in "$der" -out "$pem"
  rm -f "$TLS/$name.normalized.der"
  echo "[PASS] APPLE_CA_PINNED $name"
}
fetch_root "https://www.apple.com/appleca/AppleIncRootCertificate.cer" \
  "b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024" \
  "AppleRootCA"
fetch_root "https://www.apple.com/certificateauthority/AppleRootCA-G3.cer" \
  "63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179" \
  "AppleRootCA-G3"

SYSTEM_CA="$(python3 -c 'import ssl; print(ssl.get_default_verify_paths().cafile or "")')"
if [[ ! -s "$SYSTEM_CA" ]]; then
  echo "[STOP] SYSTEM_CA_BUNDLE_MISSING: $SYSTEM_CA" >&2
  exit 4
fi

BUNDLE="$TLS/ca-bundle-with-apple.pem"
cat "$SYSTEM_CA" "$TLS/AppleRootCA.pem" "$TLS/AppleRootCA-G3.pem" > "$BUNDLE"
chmod 600 "$BUNDLE"
export SSL_CERT_FILE="$BUNDLE"

# Strict validation, including SNI and hostname, before credentials.
python3 - <<'PY'
import socket, ssl, sys
ctx = ssl.create_default_context()
targets = ("new.ani.sidestore.io", "gsa.apple.com",
           "developerservices2.apple.com", "api.github.com")
for host in targets:
    try:
        with socket.create_connection((host, 443), timeout=12) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                print("[PASS] TLS_TRUSTED", host, flush=True)
    except Exception as exc:
        print("[STOP] TLS_UNTRUSTED", host, str(exc), flush=True)
        sys.exit(5)
PY

SCRIPT="$WORK/scarlet_v187_repair_groups.py"
curl -fsSL --retry 3 --connect-timeout 15 \
  "https://raw.githubusercontent.com/fx564286/sidestore-auto-refresh/035fe5bcfc8286ef67c2211e7c9662fa34051eeb/scripts/scarlet_v187_repair_groups.py" \
  -o "$SCRIPT"
python3 -m py_compile "$SCRIPT"
echo "[PASS] V187_REPAIR_SCRIPT_READY"
echo "[NEXT] Apple account authentication and existing-group renewal"
exec python3 "$SCRIPT"

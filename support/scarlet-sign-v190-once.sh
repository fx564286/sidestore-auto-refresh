#!/usr/bin/env bash
# Run on the existing CachyOS signing PC. No SSH daemon, NAS port or new keys.
# The Apple private key/certificate, profile and Bundle IDs remain unchanged.
set -Eeuo pipefail
umask 077
REPO=fx564286/sidestore-auto-refresh
BASE="$HOME/.local/share/scarlet-crystal"
BIN="$BASE/latest-publisher"
STATE="$HOME/.local/state/scarlet-crystal-shortcut-sign"
PIN=66e33659c0af590be16089aa8889fb1541d840a6
RAW="https://raw.githubusercontent.com/$REPO/$PIN/tools/scarlet_latest_publish.py"
stop() { printf '[STOP] %s\n' "$*" >&2; exit 2; }
[[ "$(id -u)" != 0 ]] || stop "Run as ordinary user, not root"
for c in python3 gh openssl curl; do command -v "$c" >/dev/null || stop "Command not installed: $c"; done
[[ -f "$BASE/signing/identity-v188-enrolled/private-key.pem" ]] || stop "Existing Apple signing private key not found"
[[ -f "$BASE/signing/identity-v188-enrolled/certificate.pem" ]] || stop "Existing Apple signing certificate not found"
[[ -f "$BASE/v188-signed/sign-v188.py" ]] || stop "Existing verified signer not found"
gh auth status >/dev/null 2>&1 || stop "GitHub CLI authentication missing; use existing gh login"
mkdir -p "$BIN" "$STATE"
printf '[1/4] Verify V190 GitHub Actions IPA artifact\n'
artifact_status="$(gh api "repos/$REPO/actions/runs/42099644487/artifacts" --jq '.artifacts[] | select(.name=="Scarlet-Crystal-V190-AUTH-TRANSPORT-UNSIGNED") | if .expired then "expired" else "ready" end')"
[[ "$artifact_status" == "ready" ]] || stop "V190 unsigned IPA artifact is unavailable or expired"
printf '[PASS] V190 unsigned IPA artifact exists\n'
printf '[2/4] Download pinned universal publisher and check Python syntax\n'
staged="$(mktemp "$BIN/.latest-publisher.XXXXXX")"
trap 'rm -f "$staged"' EXIT
curl -fLSs --retry 3 --connect-timeout 12 --max-time 90 "$RAW" -o "$staged"
python3 -m py_compile "$staged" || stop "Pinned publisher syntax failed"
[[ "$(head -c 22 "$staged")" == '#!/usr/bin/env python3' ]] || stop "Unexpected publisher format"
if [[ -f "$BIN/latest.py" ]]; then cp -p "$BIN/latest.py" "$BIN/latest.py.backup.$(date -u +%Y%m%dT%H%M%SZ)"; fi
chmod 600 "$staged"
mv -f "$staged" "$BIN/latest.py"
printf '[3/4] Use existing local Apple identity to sign and publish newest verified build\n'
log="$STATE/sign-once-$(date -u +%Y%m%dT%H%M%SZ).log"
: > "$log"; chmod 600 "$log"
set +e
python3 "$BIN/latest.py" 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
set -e
[[ "$rc" == 0 ]] || stop "Signing/publishing failed (exit=$rc). Log: $log"
printf '[4/4] Verify that a signed V190 asset is listed in GitHub Releases\n'
asset_digest="$(gh api "repos/$REPO/releases?per_page=100" --jq '.[] | select(.tag_name | startswith("scarlet-v190-device-signed-")) | .assets[] | select(.name=="Scarlet-Crystal-V190-SIGNED-DEVELOPMENT.ipa") | .digest' | head -n 1)"
[[ "$asset_digest" =~ ^sha256:[[:xdigit:]]{64}$ ]] || stop "Publisher finished but V190 signed release cannot be verified. Log: $log"
echo "[PASS] V190 signed GitHub Release asset exists with SHA-256: $asset_digest"
echo "[STATUS] https://fx564286.github.io/sidestore-auto-refresh/scarlet-latest.html"
echo "[LOG] $log"
echo '[NOTICE] On-device install and Apple login/2FA remain unverified.'

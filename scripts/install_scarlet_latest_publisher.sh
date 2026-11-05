#!/usr/bin/env bash
# One-time CachyOS installation. Subsequent V{N} builds are discovered,
# signed with the owner's EXISTING Apple key and published automatically.
# No inbound NAS SSH ports, private keys in GitHub or phone-side SSH required.
set -Eeuo pipefail
umask 077

ROOT="$HOME/.local/share/scarlet-crystal"
BIN="$ROOT/latest-publisher"
UNIT="$HOME/.config/systemd/user"
STATE="$HOME/.local/state/scarlet-crystal-auto"
SOURCE="https://raw.githubusercontent.com/fx564286/sidestore-auto-refresh/66e33659c0af590be16089aa8889fb1541d840a6/tools/scarlet_latest_publish.py"
SHORTCUT_PAGE="https://fx564286.github.io/sidestore-auto-refresh/scarlet-latest.html"

die() { printf '[STOP] %s\n' "$*" >&2; exit 2; }
for x in curl python3 gh openssl rcodesign systemctl; do
    command -v "$x" >/dev/null || die "REQUIRED_PROGRAM_MISSING:$x"
done
[[ -f "$ROOT/signing/identity-v188-enrolled/private-key.pem" ]] ||
    die 'EXISTING_APPLE_PRIVATE_KEY_NOT_FOUND'
[[ -f "$ROOT/signing/identity-v188-enrolled/certificate.pem" ]] ||
    die 'EXISTING_APPLE_CERT_NOT_FOUND'
[[ -f "$ROOT/v188-signed/sign-v188.py" ]] ||
    die 'PREVIOUSLY_TESTED_PEM_SIGNER_NOT_FOUND'
gh auth status >/dev/null 2>&1 || die 'GITHUB_CLI_AUTH_REQUIRED'
systemctl --user status >/dev/null 2>&1 || die 'SYSTEMD_USER_MANAGER_UNAVAILABLE'

mkdir -p "$BIN" "$UNIT" "$STATE"
TEMP="$BIN/latest.py.tmp.$$"
trap 'rm -f "$TEMP"' EXIT
curl -fLsS --retry 3 --connect-timeout 12 --max-time 90 "$SOURCE" -o "$TEMP"
[[ -s "$TEMP" ]] || die 'PUBLISHER_DOWNLOAD_EMPTY'
python3 -m py_compile "$TEMP" || die 'PUBLISHER_PYTHON_SYNTAX'
chmod 600 "$TEMP"
mv -f "$TEMP" "$BIN/latest.py"

SERVICE="$UNIT/scarlet-latest-publisher.service"
TIMER="$UNIT/scarlet-latest-publisher.timer"
# Preserve any previous nonidentical service configuration.
for f in "$SERVICE" "$TIMER"; do
  if [[ -f "$f" ]]; then
    cp -p "$f" "$f.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  fi
done

cat > "$SERVICE" <<'SERVICE'
[Unit]
Description=Scarlet Crystal latest verified IPA sign and publish
Documentation=https://github.com/fx564286/sidestore-auto-refresh
After=default.target
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/env python3 %h/.local/share/scarlet-crystal/latest-publisher/latest.py
TimeoutStartSec=1200
WorkingDirectory=%h
StandardOutput=append:%h/.local/state/scarlet-crystal-auto/run.log
StandardError=append:%h/.local/state/scarlet-crystal-auto/run.log
NoNewPrivileges=true
PrivateTmp=true
SERVICE

cat > "$TIMER" <<'TIMER'
[Unit]
Description=Check for new Scarlet Crystal CI builds every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true
AccuracySec=5min
RandomizedDelaySec=60s
Unit=scarlet-latest-publisher.service

[Install]
WantedBy=timers.target
TIMER

chmod 600 "$SERVICE" "$TIMER"
systemctl --user daemon-reload
systemctl --user enable --now scarlet-latest-publisher.timer
echo "[PASS] AUTOMATION_TIMER_ENABLED"
systemctl --user is-enabled scarlet-latest-publisher.timer
systemctl --user list-timers --all scarlet-latest-publisher.timer --no-pager
echo "[LOG] $STATE/run.log"
echo "[INSTALL_PAGE] $SHORTCUT_PAGE"
echo "[NOTICE] This creates no signed IPA until the timer runs successfully."
echo "[NOTICE] No iPhone installation has been verified."
echo "[OPTIONAL] For operation while logged out, enable systemd linger with administrator approval."

#!/usr/bin/env bash
# ONE-TIME CachyOS setup: iPhone Shortcut dispatch -> local Apple signing.
# No timer-based signing. No public inbound NAS/PC SSH. Only GH API polling.
set -Eeuo pipefail
umask 077
BASE="$HOME/.local/share/scarlet-crystal"
BIN="$BASE/latest-publisher"
STATE="$HOME/.local/state/scarlet-crystal-shortcut-sign"
UNIT_DIR="$HOME/.config/systemd/user"
SERVICE="$UNIT_DIR/scarlet-shortcut-sign-agent.service"
AGENT_URL="https://raw.githubusercontent.com/fx564286/sidestore-auto-refresh/b0ab9f93bd4d00a2db9d9b29d826bb218c285c33/tools/scarlet_shortcut_sign_agent.py"

stop(){ echo "[STOP] $*" >&2; exit 2; }
[[ "$(id -u)" != 0 ]] || stop 'DO_NOT_RUN_AS_ROOT'
for tool in python3 gh curl systemctl openssl; do
  command -v "$tool" >/dev/null || stop "MISSING_COMMAND:$tool"
done
[[ -f "$BASE/signing/identity-v188-enrolled/private-key.pem" ]] || stop 'LOCAL_APPLE_PRIVATE_KEY_MISSING'
[[ -f "$BASE/signing/identity-v188-enrolled/certificate.pem" ]] || stop 'LOCAL_APPLE_CERT_MISSING'
[[ -f "$BASE/v188-signed/sign-v188.py" ]] || stop 'PREVIOUSLY_VERIFIED_APPLE_SIGNER_MISSING'
gh auth status >/dev/null 2>&1 || stop 'GITHUB_CLI_NOT_AUTHENTICATED'
mkdir -p "$BIN" "$STATE" "$UNIT_DIR"
temp="$BIN/shortcut-agent.py.tmp.$$"
trap 'rm -f "$temp"' EXIT
curl -fLSs --retry 3 --connect-timeout 12 --max-time 70 "$AGENT_URL" -o "$temp"
python3 -m py_compile "$temp" || stop 'AGENT_SYNTAX_FAILED'
chmod 600 "$temp"
mv -f "$temp" "$BIN/shortcut-agent.py"

if [[ -f "$SERVICE" ]]; then
  cp -p "$SERVICE" "$SERVICE.backup.$(date -u +%Y%m%dT%H%M%SZ)"
fi
cat > "$SERVICE" <<'UNIT'
[Unit]
Description=Scarlet Crystal iOS Shortcut signing requests
Documentation=https://github.com/fx564286/sidestore-auto-refresh
After=default.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=simple
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/env python3 %h/.local/share/scarlet-crystal/latest-publisher/shortcut-agent.py
WorkingDirectory=%h
Restart=on-failure
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true
StandardOutput=append:%h/.local/state/scarlet-crystal-shortcut-sign/agent.log
StandardError=append:%h/.local/state/scarlet-crystal-shortcut-sign/agent.log

[Install]
WantedBy=default.target
UNIT
chmod 600 "$SERVICE"
systemctl --user daemon-reload
systemctl --user enable scarlet-shortcut-sign-agent.service
systemctl --user restart scarlet-shortcut-sign-agent.service
sleep 2
systemctl --user is-active --quiet scarlet-shortcut-sign-agent.service || {
  systemctl --user status scarlet-shortcut-sign-agent.service --no-pager || true
  stop 'SIGN_AGENT_NOT_ACTIVE'
}
echo '[PASS] IPHONE_SHORTCUT_DISPATCH_LOCAL_APPLE_SIGN_AGENT_ACTIVE'
echo '[SERVICE] scarlet-shortcut-sign-agent.service'
echo "[LOG] $STATE/agent.log"
echo '[STATUS] https://fx564286.github.io/sidestore-auto-refresh/scarlet-sign.html'
echo '[NOTICE] PC must remain running; this service signs only on accepted owner dispatch requests.'
echo '[NOTICE] No on-device app install has been verified.'

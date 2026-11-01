#!/usr/bin/env bash
# One-time updater of the existing ScarletCrystal Arch Installer GUI.
# Only official project-owned files; download to ephemeral private directory.
set -Eeuo pipefail
umask 077
ROOT='https://raw.githubusercontent.com/fx564286/sidestore-auto-refresh/fix/scarlet-v166-integrated-setup-20261101/installer'
D="$(mktemp -d)"
trap 'rm -rf -- "$D"' EXIT
for x in scarlet_oneclick.py install_integration.py; do
  curl --fail --location --silent --show-error --retry 3 --proto '=https' --tlsv1.2 \
       -o "$D/$x" "$ROOT/$x"
done
printf '%s  %s\n' \
  2427de6584b02cd57524c63de474c6a231fb40cbd494e6cdbcf3ca1b4769a3e8 "$D/scarlet_oneclick.py" \
  44fbfc8b5f584a8becf1a22f7849906babe45e34469d19f9b346f58cb4d7d67c "$D/install_integration.py" | sha256sum -c -
python3 "$D/install_integration.py"
DIR=""
for dir in "$PWD" "$HOME/Downloads/ScarletCrystal-ArchInstaller-v1.1" "$HOME/다운로드/ScarletCrystal-ArchInstaller-v1.1"; do
  if [[ -f "$dir/scarlet_gui.py" && -f "$dir/launch.sh" ]]; then DIR="$dir"; break; fi
done
[[ -n "$DIR" ]] || { printf '기존 인스톨러가 확인되지 않았습니다.\n' >&2; exit 1; }
printf '기존 Scarlet Crystal Arch Installer GUI를 실행합니다.\n'
exec bash "$DIR/launch.sh"

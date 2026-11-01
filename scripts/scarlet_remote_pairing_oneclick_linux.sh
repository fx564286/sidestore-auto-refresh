#!/usr/bin/env bash
# Scarlet Crystal V165 — Linux USB RemotePairing bootstrap.
# Does not delete, overwrite or unpair any existing iOS app, profile or record.
# Prebuilt MIT-licensed idevice-tools v0.1.68, SHA-256 verified.
set -Eeuo pipefail
umask 077
WORK="${XDG_CACHE_HOME:-$HOME/.cache}/scarlet-remote-pairing"
PACKAGE='idevice-tools-linux-v0.1.68.zip'
URL='https://github.com/jkcoxson/idevice/releases/download/v0.1.68/idevice-tools-linux-v0.1.68.zip'
SHA256='87132c556db29b4fbaab8315f17fd0aa4eda0eee7c887ee80dad59ded68ce87f'
BUNDLE='com.kdt.livecontainer.P8EZT3U5N4'
log() { printf '[SCARLET-RP] %s\n' "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || fail 'Linux x86_64 환경에서만 실행할 수 있습니다.'
for cmd in curl sha256sum python3; do command -v "$cmd" >/dev/null || fail "필수 명령어 없음: $cmd"; done
mkdir -p "$WORK"; chmod 700 "$WORK"
ARCHIVE="$WORK/$PACKAGE"
if ! printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum -c - >/dev/null 2>&1; then
    tmp="$WORK/${PACKAGE}.partial.$$"
    trap 'rm -f -- "${tmp:-}"' EXIT
    log '공식 idevice-tools Linux 패키지 다운로드 및 무결성 검사'
    curl -fLsS --retry 3 --connect-timeout 15 --proto '=https' --tlsv1.2 -o "$tmp" "$URL" \
      || fail '공식 패키지 다운로드 실패'
    printf '%s  %s\n' "$SHA256" "$tmp" | sha256sum -c - >/dev/null || fail 'SHA-256 불일치: 실행 거부'
    mv -f -- "$tmp" "$ARCHIVE"
    trap - EXIT
fi
log '공식 배포 파일 SHA-256 PASS'
python3 - "$ARCHIVE" "$WORK" <<'PY'
import os,sys,zipfile,pathlib
archive=pathlib.Path(sys.argv[1]); root=pathlib.Path(sys.argv[2]); target=root/'idevice-tools'
with zipfile.ZipFile(archive) as z:
    member=z.getinfo('idevice-tools')
    if member.file_size<1000000 or member.file_size>30000000: raise SystemExit('바이너리 길이 검증 실패')
    temp=root/'idevice-tools.extracting'
    with z.open(member) as src, temp.open('wb') as dst:
        import shutil; shutil.copyfileobj(src,dst)
    temp.chmod(0o700); temp.replace(target)
PY
TOOL="$WORK/idevice-tools"
[[ -x "$TOOL" ]] || fail '실행 파일 없음'
# The existing USB trust established with JitterbugPair is reused; never unpair.
log '아이폰이 USB 연결되어 있고 잠금 해제되어 있어야 합니다.'
HOSTFILE="$WORK/host_name"
if [[ ! -s "$HOSTFILE" ]]; then
    python3 - "$HOSTFILE" <<'PY'
from pathlib import Path
import sys,uuid
p=Path(sys.argv[1]);p.write_text('ScarletCrystal-'+uuid.uuid4().hex[:12], encoding='ascii');p.chmod(0o600)
PY
fi
HOSTNAME="$(cat "$HOSTFILE")"
CURRENT="$WORK/Scarlet-RemotePairing.plist"
VERIFIED=0
if [[ -s "$CURRENT" ]]; then
    log '기존 RP 파일 확인 중 (파일은 삭제하지 않음)'
    previous="$WORK/previous-verify-$$.log"
    if "$TOOL" remotepairing_lockdown verify "$CURRENT" "$HOSTNAME" >"$previous" 2>&1 &&
       grep -Fq 'the device recognizes this pairing record' "$previous"; then
        VERIFIED=1
        log '기존 원격 페어링 신뢰 검증 PASS — 재생성하지 않음'
    fi
    rm -f -- "$previous"
fi
if [[ "$VERIFIED" -ne 1 ]]; then
    # Refuse overwrite, so a failed new attempt cannot destroy known history.
    if [[ -e "$CURRENT" ]]; then
        backup="$WORK/Scarlet-RemotePairing.previous.$(date +%Y%m%d%H%M%S).plist"
        cp -p -- "$CURRENT" "$backup"
        chmod 600 "$backup"
        log '이전 RP 기록을 로컬 백업함'
        rm -f -- "$CURRENT"
    fi
    log 'USB를 통해 새로운 Remote Pairing 생성 중 (추가 프로그램 GUI 불필요)'
    "$TOOL" remotepairing_lockdown pair "$HOSTNAME" "$CURRENT" || fail 'RP 생성 명령 실패'
    [[ -s "$CURRENT" ]] || fail 'RP 기록 생성 실패. USB 연결·개발자 모드·신뢰 승인 확인 필요'
    log '새 RP 파일 생성됨'
fi
# Check actual SideStore-compatible record without printing any key data.
python3 - "$CURRENT" <<'PY'
import plistlib,sys
from pathlib import Path
p=Path(sys.argv[1]); data=plistlib.loads(p.read_bytes())
if not isinstance(data,dict) or not isinstance(data.get('identifier'),str) or not data['identifier']:
    raise SystemExit('페어링 파일에 identifier 누락')
for k in ('public_key','private_key'):
    if not isinstance(data.get(k),bytes) or len(data[k])!=32:
        raise SystemExit(f'페어링 파일에 유효한 {k} 없음')
print('[SCARLET-RP] SideStore 호환 필드 검사 PASS (키 원문 비공개)')
PY
verify_log="$WORK/verify-$$.log"
if ! "$TOOL" remotepairing_lockdown verify "$CURRENT" "$HOSTNAME" >"$verify_log" 2>&1 ||
   ! grep -Fq 'the device recognizes this pairing record' "$verify_log"; then
    rm -f -- "$verify_log"
    fail 'iPhone RP pair-verify 실패: 기록을 앱에 적용하지 않음'
fi
rm -f -- "$verify_log"
log '실기기 Remote Pairing pair-verify PASS'
# V165 host-owned Pairing page looks inside the app Documents/Inbox.
# Never write the already-active pairing record directly; app service validates import.
STAGED=0
REMOTE="/Documents/Inbox/Scarlet-RemotePairing-$(date +%Y%m%d%H%M%S).plist"
if "$TOOL" afc --documents "$BUNDLE" list /Documents >/dev/null 2>&1; then
    if ! "$TOOL" afc --documents "$BUNDLE" list /Documents/Inbox >/dev/null 2>&1; then
        "$TOOL" afc --documents "$BUNDLE" mkdir /Documents/Inbox >/dev/null 2>&1 || true
    fi
    if "$TOOL" afc --documents "$BUNDLE" upload "$CURRENT" "$REMOTE" >/dev/null 2>&1; then
        STAGED=1
    fi
fi
if [[ "$STAGED" -eq 1 ]]; then
    log 'Scarlet Crystal 앱 Documents/Inbox로 안전하게 전달 완료'
    log '아이폰에서 Scarlet Crystal → Setup Assistant → Pairing File → Use Received Pairing File을 선택하세요.'
else
    log 'RP 기록은 검증했지만 앱 문서 접근은 거부됐습니다. 기존 앱은 건드리지 않았습니다.'
    log "PC에 생성된 파일: $CURRENT"
    log '아이폰으로 개인적으로 전송한 뒤 Scarlet Crystal의 Pairing File → Choose a Pairing File에서 선택하세요.'
fi
log '그 후 LocalDevVPN을 재연결하고 FETCH_UDID_PASS 여부를 확인하세요.'
log '개인키가 포함되므로 페어링 파일 전체를 채팅에 게시하지 마세요.'

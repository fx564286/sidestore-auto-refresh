#!/usr/bin/env python3
"""Scarlet Crystal V8 GUI-selected upstream force-upgrade: sign only with Apple-authorized entitlements.

Uses a previously issued set of 4 authentic Apple profiles and the existing
scy-auto signing function, but intentionally relaxes the *local* App Group and
installed-app entitlement-parity checks. iOS still enforces signing security.
No uninstall, provisioning deletion, certificate revocation or original IPA edit. Reuses Apple profiles when valid.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

TEAM = 'P8EZT3U5N4'
BASE = 'com.kdt.livecontainer.' + TEAM
EXTENSIONS = {'LaunchAppExtension', 'LiveProcess', 'ShareExtension'}
REQUIRED = {BASE, *(BASE + '.' + e for e in EXTENSIONS)}

class Halt(Exception):
    pass

def need(value, msg):
    if not value:
        raise Halt(msg)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def loads_scy_auto(path):
    loader = importlib.machinery.SourceFileLoader('scarlet_force_signer', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    need(spec is not None, '기존 scy-auto 모듈 로딩 불가')
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    for attr in ('inventory', 'verify_profile', 'cms_plist', 'sign_ipa', 'private_write'):
        need(callable(getattr(mod, attr, None)), 'scy-auto 필수 기능 없음: ' + attr)
    need(mod.BASE_ID == BASE and mod.TEAM == TEAM, '기존 서명기의 Bundle ID 또는 팀 불일치')
    return mod

def recent_session(root):
    valid = []
    for mf in root.glob('*/manifest.json'):
        try:
            obj = json.loads(mf.read_text(encoding='utf-8'))
            ids = obj['bundle_ids']
            if obj.get('team') != TEAM or len(ids) != 4 or set(ids) != REQUIRED:
                continue
            folder = mf.parent
            if all((folder / f'profile-{i:03d}.mobileprovision').is_file()
                   for i in range(4)):
                valid.append((mf.stat().st_mtime, folder, obj))
        except (KeyError, ValueError, OSError, TypeError):
            continue
    need(valid, '호스트 + 확장 3개에 대한 저장된 Apple 프로파일 발급 기록 없음')
    return max(valid, key=lambda a: a[0])

def staged_ipa(root, state_time, selected_source):
    valid = []
    for mf in root.glob('*/stage-manifest.json'):
        try:
            meta = json.loads(mf.read_text(encoding='utf-8'))
            if meta['target'] != BASE or set(meta['exts']) != EXTENSIONS:
                continue
            src = Path(meta['source']).resolve(strict=True)
            ipa = Path(meta['staged']).resolve(strict=True)
            if not ipa.is_relative_to(root.resolve()):
                continue
            if src == ipa or sha(src) != meta['original_sha256'] or sha(ipa) != meta['staged_sha256']:
                continue
            if src != selected_source.resolve(strict=True):
                continue
            valid.append((mf.stat().st_mtime, src, ipa))
        except (KeyError, ValueError, OSError, TypeError):
            continue
    need(valid, 'GUI 선택 IPA와 일치하는 안전한 변환본/무결성 기록을 찾지 못함')
    return max(valid, key=lambda a: a[0])

def authorized_grant(allowed_value, requested):
    return allowed_value == requested or (
        isinstance(allowed_value, str) and allowed_value.endswith('.*')
        and isinstance(requested, str) and requested.startswith(allowed_value[:-1])
    )

def make_supported_entitlements(mod, old, state, ids, profiles):
    """Deliberately prune unprovisioned groups/capabilities for force upgrade.

    The *same* entitlement plist is passed to the user's patched zsign, which
    adjusts the per-extension application-identifier. For all shared rights,
    therefore require authorization in every one of the four profiles.
    """
    old_data = plistlib.loads(old.read_bytes())
    need(isinstance(old_data, dict), '원본 entitlements 형식 오류')
    permitted_old = {None, '', BASE, BASE.removesuffix('.' + TEAM), TEAM + '.' + BASE,
                     TEAM + '.' + BASE.removesuffix('.' + TEAM)}
    need(old_data.get('application-identifier') in permitted_old,
         '과거 entitlements가 전혀 다른 앱의 것임')
    need(old_data.get('com.apple.developer.team-identifier') in (None, '', TEAM),
         '과거 entitlements의 Apple 팀이 다름')

    authorities = [profiles[i]['Entitlements'] for i in ids]
    need(all(isinstance(e, dict) for e in authorities), 'Apple 프로파일 권한 데이터가 불완전함')
    result = {'application-identifier': TEAM + '.' + BASE,
              'com.apple.developer.team-identifier': TEAM}
    removed = []
    for name, value in old_data.items():
        if name in result:
            continue
        if name in ('keychain-access-groups', 'com.apple.security.application-groups'):
            if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
                raise Halt('잘못된 entitlement 그룹 값: ' + name)
            keep = [group for group in value
                    if all(isinstance(profile.get(name), list) and any(
                        authorized_grant(x, group) for x in profile[name])
                        for profile in authorities)]
            if keep:
                result[name] = keep
            if len(keep) != len(value):
                removed.append(f'{name}: {len(value) - len(keep)}개 제외')
        elif all(profile.get(name) == value for profile in authorities):
            result[name] = value
        else:
            removed.append(name)
    out = state / 'force-v7-entitlements.xml'
    blob = plistlib.dumps(result, fmt=plistlib.FMT_XML, sort_keys=False)
    if out.exists():
        need(out.read_bytes() == blob, '같은 작업 폴더에 서로 다른 강제 서명 권한 파일이 있음')
    else:
        mod.private_write(out, blob)
    print('[FORCE] Apple 프로파일에서 승인되지 않은 권한 제외:',
          ', '.join(removed) if removed else '없음', flush=True)
    if 'com.apple.security.application-groups' not in result:
        print('[WARNING] App Group 접근 권한 없음. 공유 컨테이너 기능이 동작하지 않을 수 있음.', flush=True)
    return out

def select_and_verify(home, mod, selected_source):
    base = home / '.local/state/scarlet-crystal-installer'
    state_mtime, state, manifest = recent_session(base / 'auto-renew')
    _, source, ipa = staged_ipa(base / 'upstream-v5', state_mtime, selected_source)
    need(set(mod.inventory(ipa)) == REQUIRED, '서명용 IPA Bundle ID/확장 4개 불일치')
    need(manifest.get('udid'), '프로파일 대상 UDID 누락')
    cert = state / 'cert.pem'
    key = state / 'key.pem'
    need(cert.is_file() and key.is_file(), '프로파일과 연결된 인증서/개인키가 없음')
    cert_der = subprocess.run(['openssl', 'x509', '-in', str(cert), '-outform', 'DER'],
                              check=True, capture_output=True).stdout
    need(hashlib.sha256(cert_der).hexdigest() == manifest.get('certificate_sha256'),
         '인증서 지문이 갱신 매니페스트와 다름')
    pub1 = subprocess.run(['openssl','x509','-in',str(cert),'-pubkey','-noout'],
                          check=True,capture_output=True).stdout
    pub2 = subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],
                          check=True,capture_output=True).stdout
    need(pub1 == pub2, '인증서/개인키 불일치')
    udid = manifest['udid']
    proc = subprocess.run(['idevice_id','-l'],capture_output=True,text=True)
    need(proc.returncode == 0 and [s.strip() for s in proc.stdout.splitlines() if s.strip()] == [udid],
         'USB 연결 iPhone과 프로파일 대상 기기가 다름')
    profiles = {}
    for i, ident in enumerate(manifest['bundle_ids']):
        data = (state / f'profile-{i:03d}.mobileprovision').read_bytes()
        mod.verify_profile(data, TEAM, ident, udid, cert_der)
        profiles[ident] = mod.cms_plist(data)
    return state, source, ipa, udid, manifest['bundle_ids'], profiles

def load_source(name, file):
    loader = importlib.machinery.SourceFileLoader(name, str(file))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    need(spec is not None and spec.loader is not None, '원본 IPA 변환 모듈 로딩 실패')
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def ensure_renewed(home, mod, staged, signer):
    """Reuse valid Apple profiles; renew only when missing or near expiry."""
    base = home / '.local/state/scarlet-crystal-installer/auto-renew'
    valid = False
    try:
        _, folder, manifest = recent_session(base)
        ids = manifest['bundle_ids']
        der = subprocess.run(['openssl','x509','-in',str(folder/'cert.pem'),
                              '-outform','DER'], capture_output=True, check=True).stdout
        certpub = subprocess.run(['openssl','x509','-in',str(folder/'cert.pem'),
                                  '-pubkey','-noout'], capture_output=True, check=True).stdout
        keypub = subprocess.run(['openssl','pkey','-in',str(folder/'key.pem'),
                                 '-pubout'], capture_output=True, check=True).stdout
        need(certpub == keypub, '서명키와 인증서 불일치')
        need(hashlib.sha256(der).hexdigest() == manifest['certificate_sha256'],
             '기존 갱신 기록 인증서 지문 불일치')
        udid = manifest['udid']
        p = subprocess.run(['idevice_id','-l'],capture_output=True,text=True)
        need(p.returncode == 0 and
             [v.strip() for v in p.stdout.splitlines() if v.strip()] == [udid],
             'USB 연결된 iPhone이 프로파일 대상과 다름')
        expires = []
        for index, identifier in enumerate(ids):
            blob = (folder / f'profile-{index:03d}.mobileprovision').read_bytes()
            mod.verify_profile(blob, TEAM, identifier, udid, der)
            detail = mod.cms_plist(blob)
            expiry = detail['ExpirationDate']
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=dt.timezone.utc)
            expires.append(expiry)
        need(min(expires) > dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=12),
             '프로파일 유효기간 12시간 미만')
        valid = True
        print('[PASS] 기존 Apple 프로파일 4개 재사용 가능', flush=True)
    except (Halt, KeyError, OSError, ValueError, TypeError, subprocess.CalledProcessError,
            getattr(mod, 'Stop', Exception)) as e:
        print('[RENEW] 유효한 프로파일 재확인 필요:', type(e).__name__, flush=True)
    if not valid:
        cmd = [sys.executable, str(signer), '--ipa', str(staged), '--renew-only']
        print('[AUTH] Apple 프로파일 4개 자동 갱신', flush=True)
        p = subprocess.run(cmd)
        need(p.returncode == 0, 'Apple 프로파일 갱신 실패; iPhone 앱은 변경하지 않음')


def execute(install, selected_source):
    if os.geteuid() == 0:
        raise Halt('root가 아닌 hanabi 사용자로 실행')
    home = Path.home()
    signer = home / '.local/bin/scy-auto'
    need(signer.is_file(), '기존 scy-auto 서명기가 없음')
    need(selected_source is not None, 'GUI에서 선택한 IPA의 정확한 경로가 필요')
    selected_source = selected_source.expanduser().resolve(strict=True)
    need(selected_source.suffix.lower() == '.ipa', 'IPA 파일이 아님')
    # Reuse the verified V5 upstream transformer, never edit the source IPA.
    bridge = home / '.local/bin/scarlet-upstream-v5.py'
    need(bridge.is_file(), '원본 IPA 식별자 변환 도구 V5가 없음')
    stage_mod = load_source('scarlet_v8_stage', bridge)
    _, staged_file, changed = stage_mod.stage(selected_source)
    need(changed, '원본 unsigned IPA 대신 이미 변환된 IPA 선택; 기존 GUI 원본을 다시 선택해줘')
    mod = loads_scy_auto(signer)
    need(set(mod.inventory(staged_file)) == REQUIRED, '선택 IPA 변환본의 Bundle ID/확장 구성 오류')
    ensure_renewed(home, mod, staged_file, signer)
    state, original, staged, udid, ids, profiles = select_and_verify(home, mod, selected_source)
    old_root = [home / a / 'NRG-IPA/SCARLET-CRYSTAL-251-MEMORY-RESTORE-20261022/entitlements.xml'
                for a in ('다운로드', 'Downloads')]
    old = next((p for p in old_root if p.is_file()), None)
    need(old is not None, '기존 권한 파일을 찾지 못해 검증 가능한 강제 서명 불가')
    mod.scarlet_prepare_fresh_entitlements = lambda source, s, bundle_ids: make_supported_entitlements(
        mod, source, s, bundle_ids, profiles)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = staged.with_name(staged.stem + '-FORCE-SIGNED-' + stamp + '.ipa')
    print('[SOURCE]', original, flush=True)
    print('[SIGNED OUTPUT]', output, flush=True)
    print('[WARNING] 기존 App Groups/Keychain 접근이 바뀔 수 있음. 원본 IPA와 기존 앱은 삭제하지 않음.',flush=True)
    mod.sign_ipa(staged, state, output, ids, None)
    print('[PASS] 4개 프로파일 검증 및 서명 출력 완료',flush=True)
    if not install:
        print('[SAFE] USB 설치 미진행. --install 옵션으로 업데이트 가능.',flush=True)
        return 0
    print('[FORCE] 로컬 권한 동일성 검사 생략, iOS 시스템 검증이 최종 판단',flush=True)
    proc = subprocess.run(['ideviceinstaller','-u',udid,'upgrade',str(output)])
    need(proc.returncode == 0, f'iOS가 설치를 거부했음 (종료 코드 {proc.returncode}); 앱 삭제는 시도하지 않음')
    print('[PASS] iOS USB 업그레이드 명령 성공. 실제 앱 실행·데이터는 단말에서 확인 필요',flush=True)
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true', help='서명 후 데이터 권한 동일성 검사를 건너뛰고 기존 앱 업그레이드 시도')
    parser.add_argument('--ipa', type=Path, required=True,
                        help='GUI에서 사용자가 직접 선택한 V181 등 원본 unsigned IPA')
    args = parser.parse_args()
    try:
        return execute(args.install, args.ipa)
    except (Halt, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('[STOP]',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

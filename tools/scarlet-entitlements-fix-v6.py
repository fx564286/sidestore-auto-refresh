#!/usr/bin/env python3
"""Scarlet Crystal signing entitlements repair v6.

Patch the existing scy-auto in place. Use the freshly downloaded Apple
provisioning profile to validate original entitlements and create an auxiliary
entitlements file with the exact target application ID. Never overwrite the
original entitlements or remove Keychain/App Group access.
"""
from __future__ import annotations

import ast
import datetime as dt
import os
from pathlib import Path
import sys
import tempfile

MARK = 'SCARLET_FRESH_ENTITLEMENTS_V6'
TARGET = 'scy-auto'

HELPER = r'''
# SCARLET_FRESH_ENTITLEMENTS_V6

def scarlet_prepare_fresh_entitlements(source, state, ids):
    """Correct only missing/old app/team identifiers, retaining all other grants.

    All signable grants must be within newly issued, matching Apple provisioning
    profile. Unsupported or changed groups cause a hard stop.
    """
    require(state.is_dir(), '자동 갱신 작업 폴더가 없음')
    manifest_file = state / 'manifest.json'
    require(manifest_file.is_file(), '신규 Apple 프로파일 발급 매니페스트가 없음')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    require(manifest.get('team') == TEAM, 'Apple 팀 불일치')
    require(manifest.get('bundle_ids') == ids, '신규 프로파일과 IPA Bundle ID 순서 불일치')
    require(len(ids) == 4 and len(set(ids)) == 4, 'V181 서명 대상은 호스트와 확장 3개여야 함')
    require(BASE_ID in ids, '호스트 Bundle ID 누락')

    # Each newly issued Apple profile was already validated at issuance; check
    # again on the local machine immediately before signing, including the
    # actual certificate and registered device. No stale cache is trusted.
    cert_path = state / 'cert.pem'
    key_path = state / 'key.pem'
    require(cert_path.is_file() and key_path.is_file(), '갱신 인증서/개인키가 없음')
    cert_der = subprocess.run(
        ['openssl', 'x509', '-in', str(cert_path), '-outform', 'DER'],
        capture_output=True, check=True).stdout
    cert_pub = subprocess.run(
        ['openssl', 'x509', '-in', str(cert_path), '-pubkey', '-noout'],
        capture_output=True, check=True).stdout
    key_pub = subprocess.run(
        ['openssl', 'pkey', '-in', str(key_path), '-pubout'],
        capture_output=True, check=True).stdout
    require(cert_pub == key_pub, '서명 인증서/개인키 불일치')
    require(manifest.get('certificate_sha256') == hashlib.sha256(cert_der).hexdigest(),
            '프로파일 작업 매니페스트 인증서 지문 불일치')
    udid = manifest.get('udid', '')
    require(bool(udid), '검증할 기기 UDID 누락')
    host_profile = None
    for i, ident in enumerate(ids):
        profile_path = state / f'profile-{i:03d}.mobileprovision'
        require(profile_path.is_file(), f'{ident} 신규 프로파일 누락')
        blob = profile_path.read_bytes()
        verify_profile(blob, TEAM, ident, udid, cert_der)
        if ident == BASE_ID:
            host_profile = cms_plist(blob)
    require(host_profile is not None, '호스트 프로파일 누락')
    allowed = host_profile.get('Entitlements') or {}
    require(isinstance(allowed, dict), 'Apple 프로파일 Entitlements 형식 오류')
    expected_id = TEAM + '.' + BASE_ID
    permitted_id = allowed.get('application-identifier') or allowed.get('com.apple.application-identifier', '')
    require(permitted_id == expected_id or
            (isinstance(permitted_id, str) and permitted_id.endswith('.*') and
             expected_id.startswith(permitted_id[:-1])),
            f'새 Apple 프로파일이 설치 App ID를 허용하지 않음: {permitted_id}')

    ent = plistlib.loads(source.read_bytes())
    require(isinstance(ent, dict), '과거 entitlements.xml 형식 오류')
    old_id = ent.get('application-identifier')
    raw = BASE_ID.removesuffix('.' + TEAM)
    acceptable = {None, '', BASE_ID, raw, TEAM + '.' + BASE_ID, TEAM + '.' + raw}
    require(old_id in acceptable,
            '과거 entitlement가 전혀 다른 앱 식별자를 가리킴; 자동 변경 차단')
    old_team = ent.get('com.apple.developer.team-identifier')
    require(old_team in (None, '', TEAM), '과거 entitlement Apple 팀 불일치')

    def grants(group, permission):
        return group == permission or (
            isinstance(group, str) and group.endswith('.*') and
            isinstance(permission, str) and permission.startswith(group[:-1])
        )

    protected = ('keychain-access-groups', 'com.apple.security.application-groups')
    for field in protected:
        actual = ent.get(field)
        if actual is None:
            continue
        allowed_groups = allowed.get(field)
        require(isinstance(actual, list) and all(isinstance(x, str) and x for x in actual),
                f'기존 {field} 형식 오류')
        require(isinstance(allowed_groups, list) and allowed_groups,
                f'새 프로파일에 {field} 권한이 없음. 기존 그룹을 삭제하지 않고 중단')
        unknown = [v for v in actual if not any(grants(g, v) for g in allowed_groups)]
        require(not unknown,
                f'새 프로파일이 과거 {field}을(를) 허용하지 않음 (총 {len(unknown)}개). '
                'Keychain/App Group 보존 위해 서명 중단')

    # This file was historically created without these two identity fields.
    # Patch the *generated copy*, never the historical entitlement source.
    ent['application-identifier'] = expected_id
    ent['com.apple.developer.team-identifier'] = TEAM
    output = state / 'verified-scarlet-entitlements.xml'
    require(not output.exists(), '생성할 entitlements 파일이 이미 존재함')
    private_write(output, plistlib.dumps(ent, fmt=plistlib.FMT_XML, sort_keys=False))
    require(plistlib.loads(output.read_bytes()) == ent, '새 entitlement 파일 직렬화 확인 실패')
    note('[PASS] Apple 프로파일 기준 application-identifier 자동 보정')
    note('[PRESERVE] 기존 Keychain/App Group 권한 삭제·축소 없음')
    return output
'''

def patch(src: str) -> tuple[str, bool]:
    if MARK in src:
        ast.parse(src)
        return src, False
    tree = ast.parse(src)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'sign_ipa']
    if len(funcs) != 1:
        raise ValueError('sign_ipa 함수를 유일하게 특정할 수 없음')
    func = funcs[0]
    segment = ast.get_source_segment(src, func) or ''
    guards = ('old_ents', 'entitlement_file', 'application-identifier',
              'com.apple.developer.team-identifier', 'keychain-access-groups')
    if not all(g in segment for g in guards):
        raise ValueError('기존 sign_ipa 권한 보존 검사 구조가 변경됨')
    assignments = [n for n in ast.walk(func) if isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id == 'entitlement_file' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('entitlement_file 선택 구문이 한 개가 아님')
    node = assignments[0]
    lines = src.splitlines(keepends=True)
    indent = lines[node.lineno - 1][:len(lines[node.lineno - 1]) - len(lines[node.lineno - 1].lstrip())]
    if indent != '    ':
        raise ValueError('entitlement_file 대입문 위치가 예상과 다름')
    statement = (indent + 'if entitlement_file is not None:\n' +
                 indent + '    entitlement_file = scarlet_prepare_fresh_entitlements(\n' +
                 indent + '        entitlement_file, state, ids)\n')
    lines.insert(node.end_lineno, statement)
    updated = ''.join(lines)
    # Insert the helper immediately before the module-entry guard, at top level.
    anchor = 'if __name__ == "__main__":'
    if updated.count(anchor) != 1:
        raise ValueError('Python 진입점 확인 실패')
    updated = updated.replace(anchor, HELPER + '\n\n' + anchor, 1)
    ast.parse(updated)
    compile(updated, '<scy-auto-v6>', 'exec')
    return updated, True

def main():
    if os.geteuid() == 0:
        raise ValueError('root가 아니라 hanabi 계정으로 실행해야 함')
    target = Path.home() / '.local/bin' / TARGET
    if not target.is_file():
        raise ValueError('기존 scy-auto를 찾지 못함')
    source = target.read_text(encoding='utf-8')
    updated, changed = patch(source)
    if not changed:
        print('[PASS] entitlement v6 기존 적용 확인')
        return
    backup = target.with_name(TARGET + '.before-entitlements-v6-' +
                              dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    with backup.open('xb') as f:
        f.write(source.encode('utf-8'))
    backup.chmod(0o600)
    handle, staged = tempfile.mkstemp(prefix='.scarlet-entitlement-v6-', dir=target.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(staged, 0o700)
        os.replace(staged, target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    print('[PASS] scy-auto entitlements 검사 보완')
    print('[BACKUP]', backup)
    print('[PRESERVE] 과거 XML, P12, 새 Apple 프로파일, IPA, 기기 앱 데이터 변경 없음')
    print('[NEXT] 기존 scy GUI에서 자동 갱신 · 서명 · 설치 실행')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, SyntaxError) as exc:
        print('[STOP]', type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(2)

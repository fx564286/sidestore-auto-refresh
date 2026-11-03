#!/usr/bin/env python3
"""Scarlet Crystal: restore original GUI button binding without touching signing assets."""
import ast
import datetime as dt
import os
from pathlib import Path
import shutil
import sys
import tempfile

MARK = 'SCARLET_NATIVE_COMPAT_V4_20261103'
FOLD = 'ScarletCrystal-ArchInstaller-v1.1'

FIGMA_INSTALL = '''# SCARLET_NATIVE_COMPAT_V4_20261103
def install():
    global DONE
    if DONE: return
    app = QApplication.instance()
    if app is None: return
    for w in app.topLevelWidgets():
        b = getattr(w, "both_btn", None)
        if b is None: continue
        # The GUI's original clicked.connect() stays authoritative.
        b.setText("서명 · 설치")
        b.setToolTip("기존 인스톨러: 원본 ID → 설치 ID 변환 → 서명 → 검증")
        w._scarlet_figma_controller = Responsive(w)
        DONE = True
        log("NATIVE V4: original sign/install callback retained")
        return
    QTimer.singleShot(300, install)
'''

OLD_INSTALL = '''# SCARLET_NATIVE_COMPAT_V4_20261103
def install():
    # Disable stale bridge that replaced the GUI's original signal.
    return None
'''


def repair(source, figma):
    if MARK in source:
        return source, False
    tree = ast.parse(source)
    candidates = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'install' and
                  'clicked.disconnect' in (ast.get_source_segment(source, n) or '') and
                  'clicked.connect' in (ast.get_source_segment(source, n) or '')]
    if len(candidates) != 1:
        raise ValueError('버튼 가로채기 코드를 유일하게 확인하지 못함')
    if figma and not all(x in source for x in ('class Responsive(', 'both_btn', 'QApplication')):
        raise ValueError('Figma 브리지 구조 불일치')
    original_node = candidates[0]
    index = tree.body.index(original_node)
    lines = source.splitlines(keepends=True)
    lines[original_node.lineno-1:original_node.end_lineno] = [
        (FIGMA_INSTALL if figma else OLD_INSTALL) + '\n']
    modified = ''.join(lines)
    parsed = ast.parse(modified)
    if len(tree.body) != len(parsed.body) or any(
        ast.dump(x, include_attributes=False) != ast.dump(y, include_attributes=False)
        for k, (x, y) in enumerate(zip(tree.body, parsed.body)) if k != index
    ):
        raise ValueError('서명 외 기타 코드 변경 감지')
    compile(modified, '<scarlet-native-v4>', 'exec')
    return modified, True


def native_connections(gui):
    source = gui.read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    count = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'connect':
            s = ast.get_source_segment(source, n.func) or ''
            if 'both_btn' in s and 'clicked' in s:
                count += 1
    return count


def write_atomic(p, source):
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.scarlet-v4-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(source)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def main():
    if os.geteuid() == 0:
        raise ValueError('root가 아닌 hanabi 계정으로 실행해야 함')
    dry = '--check' in sys.argv
    rollback = '--rollback' in sys.argv
    home = Path.home()
    roots = [p for p in [home/'Downloads'/FOLD, home/'다운로드'/FOLD]
             if (p/'scarlet_gui.py').is_file()]
    if not roots: raise ValueError('ScarletCrystal Arch Installer 소스를 찾지 못함')
    for root in roots:
        count = native_connections(root/'scarlet_gui.py')
        print('[GUI]', root, '[native both_btn handlers]', count, flush=True)
        if count > 1:
            raise ValueError('원래 버튼 연결이 여러 개여서 중복 설치 위험; 변경하지 않음')
        if count == 0:
            print('[INFO] 버튼 연결이 make_button 팩토리에서 이루어질 수 있음;'
                  ' 기존 연결을 절대 해제하지 않음')
        backups = root/'.scarlet-native-v4-backups'
        if rollback:
            folders = sorted((x for x in backups.iterdir() if x.is_dir()), reverse=True) if backups.exists() else []
            if not folders: raise ValueError('복구 백업 없음')
            if not dry:
                for f in folders[0].iterdir():
                    shutil.copy2(f,root/f.name)
            print('[RESTORED]',folders[0]);continue
        pending = []
        for name, figma in [('scarlet_figma_bridge.py',True), ('scarlet_auto_gui_bridge.py',False)]:
            p=root/name
            if not p.is_file(): continue
            content = p.read_text(encoding='utf-8-sig')
            updated, changed = repair(content, figma)
            if changed: pending.append((p,updated))
        if not pending:
            print('[PASS] 복구 패치 이미 적용됨 또는 추가 브리지 없음');continue
        print('[CHECK]',', '.join(str(p) for p,_ in pending))
        if dry: continue
        backup = backups/dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True,mode=0o700)
        try:
            for p,_ in pending: shutil.copy2(p,backup/p.name)
            for p,updated in pending: write_atomic(p,updated)
        except BaseException:
            for f in backup.iterdir(): shutil.copy2(f,root/f.name)
            raise
        print('[PASS] 기존 GUI 서명·설치 버튼 경로 복구')
        print('[BACKUP]', backup)
    if not dry and not rollback:
        print('[SAFE] 원본 IPA/Apple 인증서/프로파일/기기 앱 데이터 미변경')
        print('[NEXT] GUI 종료 후 일반 사용자 데스크톱에서 scy 실행')
        print('[NOTE] 자동 프로파일 재발급 기능과 native pipeline 연결은 별도 검증 필요')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, SyntaxError) as e:
        print('[STOP]',type(e).__name__,str(e),file=sys.stderr)
        raise SystemExit(2)

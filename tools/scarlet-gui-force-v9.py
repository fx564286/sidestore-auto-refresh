#!/usr/bin/env python3
"""Scarlet Crystal Arch Installer: stable v9 GUI handoff to verified force v8.

Patches only GUI helper modules. Disables legacy signal-rebinding helpers,
then installs one authoritative callback. Never reads credentials or installs.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import os
from pathlib import Path
import shutil
import sys
import tempfile

MARK = 'SCARLET_FORCE_GUI_V9_SINGLE_ROUTE'
LEGACY_MARK = 'SCARLET_FORCE_GUI_V9_LEGACY_DISABLED'
NAME = 'ScarletCrystal-ArchInstaller-v1.1'
RUNTIME = r'''
# SCARLET_FORCE_GUI_V9_SINGLE_ROUTE
_SCARLET_V9_ATTEMPTS = 0


def _scarlet_v9_report(message):
    try:
        log('V9 ' + message)
    except Exception:
        pass
    from pathlib import Path as _P
    import datetime as _D
    p = _P.home() / '.local/state/scarlet-crystal-installer/gui-force-v9.log'
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as stream:
            stream.write(_D.datetime.now().astimezone().isoformat() + ' ' + message + '\n')
    except OSError:
        pass


def _scarlet_v9_run(window):
    import os as _os
    import sys as _sys
    import shutil as _shutil
    import subprocess as _sp
    from pathlib import Path as _Path
    from PySide6.QtWidgets import QMessageBox as _MessageBox
    from PySide6.QtWidgets import QFileDialog as _FileDialog
    if _os.geteuid() == 0:
        _MessageBox.critical(window, '실행 계정 오류', 'GUI는 hanabi 사용자로 실행해야 해.')
        return
    helper = _Path.home() / '.local/bin/scarlet-force-install-v8.py'
    if not helper.is_file():
        _MessageBox.critical(window, '강제 설치 도구 없음', str(helper))
        return

    # Resolve only the IPA selected inside the current GUI. Never use newest mtime.
    finder = globals().get('_scarlet_v5_chosen_ipa')
    chosen = finder(window) if callable(finder) else None
    if chosen is None:
        file, _ = _FileDialog.getOpenFileName(
            window, 'Scarlet Crystal 원본 IPA 선택',
            str(_Path.home() / '바탕화면'), 'iOS IPA (*.ipa)')
        if not file:
            return
        chosen = _Path(file)
    chosen = _Path(chosen).expanduser()
    if not chosen.is_file() or chosen.suffix.lower() != '.ipa':
        _MessageBox.critical(window, '선택 IPA 오류', '원본 IPA가 존재하지 않거나 IPA 파일이 아니야.')
        return
    chosen = chosen.resolve(strict=True)

    answer = _MessageBox.warning(
        window, 'Scarlet Crystal 강제 업그레이드',
        'Apple 프로파일에서 허용하지 않는 App Group 등의 권한은 서명 시 제외돼.\n'
        '기존 앱을 삭제하지 않고 업데이트하지만 공유 데이터 접근이 달라질 수 있어.\n'
        '선택한 IPA로 진행할까?',
        _MessageBox.StandardButton.Yes | _MessageBox.StandardButton.No,
        _MessageBox.StandardButton.No)
    if answer != _MessageBox.StandardButton.Yes:
        _scarlet_v9_report('USER_CANCEL')
        return

    cmd = [_sys.executable, str(helper), '--ipa', str(chosen), '--install']
    available = (
        ('konsole', ['konsole', '--noclose', '-e', *cmd]),
        ('kitty', ['kitty', '--hold', *cmd]),
        ('xterm', ['xterm', '-hold', '-e', *cmd]),
    )
    terminal = next((argv for name, argv in available if _shutil.which(name)), None)
    if terminal is None:
        _MessageBox.critical(window, '로컬 터미널 없음',
            'Apple 로그인·2FA 입력을 위해 konsole/kitty/xterm 중 하나가 필요해.')
        return
    _scarlet_v9_report('LAUNCH force-v8 --ipa=' + str(chosen) + ' --install')
    try:
        _sp.Popen(terminal, cwd=str(_Path.home()), close_fds=True,
                  start_new_session=True)
    except OSError as exc:
        _MessageBox.critical(window, '강제 설치 실행 실패', str(exc))
        _scarlet_v9_report('LAUNCH_ERROR ' + str(exc))
        return
    _MessageBox.information(window, '서명·설치 시작',
        'Scarlet Crystal 강제 설치 v8이 실행됐어.\n'
        '새 터미널에서 [SOURCE], [SIGNED OUTPUT], [FORCE]와 최종 결과를 확인해.\n'
        '터미널 시작은 설치 성공을 의미하지 않아.')


def install():
    """Do not call previous install() implementations: they rebind the same signal."""
    global _SCARLET_V9_ATTEMPTS
    app = QApplication.instance()
    if app is None:
        return
    try:
        filt = globals().get('scarlet_register_dialog_filter')
        if callable(filt):
            filt()
    except (AttributeError, RuntimeError) as exc:
        _scarlet_v9_report('DIALOG_FILTER ' + str(exc))
    windows = [w for w in app.topLevelWidgets()
               if getattr(w, 'both_btn', None) is not None]
    if not windows:
        _SCARLET_V9_ATTEMPTS += 1
        if _SCARLET_V9_ATTEMPTS < 120:
            QTimer.singleShot(250, install)
        else:
            _scarlet_v9_report('ERROR: no both_btn after 30s')
        return
    for win in windows:
        if getattr(win, '_scarlet_force_v9_ready', False):
            continue
        button = win.both_btn
        try:
            # Preserve the original Figma controller but prevent V2/V5/V8
            # rebinders from running after us.
            if not getattr(win, '_scarlet_figma_controller', None):
                try:
                    win._scarlet_figma_controller = Responsive(win)
                except Exception as exc:
                    _scarlet_v9_report('RESPONSIVE_INIT_ERROR ' + str(exc))
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass  # An unconnected button has nothing to remove.
            button.clicked.connect(lambda checked=False, w=win: _scarlet_v9_run(w))
            button.setText('자동 갱신 · 강제 서명 · 설치')
            button.setToolTip('V9 단일 실행 경로: GUI 선택 IPA → force-v8 → Apple 프로파일 갱신/재사용 → 서명 → 기존 앱 업그레이드')
            win._scarlet_force_v9_ready = True
            _scarlet_v9_report('READY: force-v8 ONLY; window=' + type(win).__name__)
        except (AttributeError, RuntimeError, TypeError) as exc:
            _scarlet_v9_report('BIND_ERROR ' + type(exc).__name__ + ': ' + str(exc))
'''

LEGACY_OVERRIDE = r'''
# SCARLET_FORCE_GUI_V9_LEGACY_DISABLED
# Older timer callbacks must not overwrite the authoritative V9 GUI binding.
def install():
    return None
'''


def syntax_ok(text: str, path: Path) -> None:
    ast.parse(text)
    compile(text, str(path), 'exec')


def atomic(path: Path, text: str) -> None:
    fd, temp = tempfile.mkstemp(prefix='.scarlet-v9-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply_to(root: Path, check: bool, rollback: bool) -> None:
    gui = root / 'scarlet_gui.py'
    figma = root / 'scarlet_figma_bridge.py'
    legacy = root / 'scarlet_auto_gui_bridge.py'
    if not gui.is_file() or not figma.is_file():
        raise RuntimeError(f'기존 GUI 또는 Figma 브리지가 없음: {root}')
    gui_src = gui.read_text(encoding='utf-8-sig')
    if 'import scarlet_figma_bridge' not in gui_src:
        raise RuntimeError('scarlet_gui.py에서 Figma 브리지를 사용하지 않음')

    backup_root = root / '.scarlet-force-v9-backups'
    if rollback:
        prior = sorted(backup_root.glob('*/scarlet_figma_bridge.py'), reverse=True)
        if not prior:
            raise RuntimeError('v9 백업을 찾지 못함')
        source = prior[0].parent
        if not check:
            shutil.copy2(source / 'scarlet_figma_bridge.py', figma)
            if (source / 'scarlet_auto_gui_bridge.py').is_file():
                shutil.copy2(source / 'scarlet_auto_gui_bridge.py', legacy)
        print('[ROLLBACK]', root)
        return

    figma_src = figma.read_text(encoding='utf-8-sig')
    syntax_ok(figma_src, figma)
    needed = ('def install():', 'class Responsive(', '_scarlet_v5_chosen_ipa')
    if not all(tok in figma_src for tok in needed):
        raise RuntimeError('Figma 브리지 구조가 예상과 달라 안전하게 중단')
    if MARK in figma_src:
        print('[PASS] v9 Figma 설치 이미 적용:', figma)
        return

    legacy_src = legacy.read_text(encoding='utf-8-sig') if legacy.is_file() else None
    if legacy_src is not None:
        syntax_ok(legacy_src, legacy)
    updated_figma = figma_src.rstrip() + '\n\n' + RUNTIME + '\n'
    syntax_ok(updated_figma, figma)
    updated_legacy = None
    if legacy_src is not None and LEGACY_MARK not in legacy_src:
        updated_legacy = legacy_src.rstrip() + '\n\n' + LEGACY_OVERRIDE + '\n'
        syntax_ok(updated_legacy, legacy)
    print('[CHECK] Figma single route + legacy disable:', root)
    if check:
        return

    backup = backup_root / dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    try:
        shutil.copy2(figma, backup / figma.name)
        if legacy_src is not None:
            shutil.copy2(legacy, backup / legacy.name)
        if updated_legacy is not None:
            atomic(legacy, updated_legacy)
        atomic(figma, updated_figma)
    except BaseException:
        for old in backup.iterdir():
            shutil.copy2(old, root / old.name)
        raise
    print('[PASS] force v8 단일 버튼 연결 + 구형 신호 연결 비활성화:', root)
    print('[BACKUP]', backup)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError('root가 아닌 hanabi 계정으로 실행해야 함')
    h = Path.home()
    for fname in ('scy-auto', 'scarlet-force-install-v8.py', 'scarlet-upstream-v5.py'):
        if not (h / '.local/bin' / fname).is_file():
            raise RuntimeError('기존 실행 도구가 없음: ' + fname)
    roots = [p.resolve() for p in (h / '다운로드' / NAME, h / 'Downloads' / NAME)
             if (p / 'scarlet_gui.py').is_file() and (p / 'scarlet_figma_bridge.py').is_file()]
    roots = list(dict.fromkeys(roots))
    if not roots:
        raise RuntimeError('설치된 기존 Scarlet GUI 파일을 찾지 못함')
    for root in roots:
        apply_to(root, args.check, args.rollback)
    if not args.check and not args.rollback:
        print('[NEXT] scy를 완전히 종료한 뒤 일반 사용자로 다시 실행해')
        print('[VERIFY] 로그에 V9 READY와 V9 LAUNCH가 보여야 해')
        print('[SAFE] IPA, P12, Apple 프로파일, iPhone 앱 데이터는 이 패치에서 변경하지 않음')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, SyntaxError) as exc:
        print('[STOP]', type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(2)

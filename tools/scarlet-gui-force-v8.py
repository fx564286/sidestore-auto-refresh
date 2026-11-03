#!/usr/bin/env python3
"""Connect existing Scarlet Crystal Arch Installer Figma GUI button to force v8.

The selected IPA is forwarded unchanged, and local policy excludes App Groups
only if Apple has not authorized them. The GUI visual/layout source is otherwise
preserved; only the existing bridge module receives a final override of the
button callback. Does not sign or install at patch time.
"""
from __future__ import annotations
import ast
import datetime as dt
import os
from pathlib import Path
import shutil
import sys
import tempfile

MARK = 'SCARLET_GUI_FORCE_INSTALL_V8'
ROOT = 'ScarletCrystal-ArchInstaller-v1.1'

RUNTIME = r'''
# SCARLET_GUI_FORCE_INSTALL_V8
_ScarletV8PreviousInstall = install

def _scarlet_v8_oneclick(window):
    import os, sys, shutil, subprocess
    from pathlib import Path
    from PySide6.QtWidgets import QMessageBox, QFileDialog
    if os.geteuid() == 0:
        QMessageBox.critical(window, "권한 오류", "hanabi 일반 사용자로 실행해야 해.")
        return
    helper=Path.home()/".local/bin/scarlet-force-install-v8.py"
    if not helper.is_file():
        QMessageBox.critical(window, "서명기 없음", str(helper))
        return
    ipa=_scarlet_v5_chosen_ipa(window)
    if ipa is None:
        chosen,_=QFileDialog.getOpenFileName(
            window, "원본 Scarlet Crystal IPA 선택",
            str(Path.home()/"바탕화면"), "iOS IPA (*.ipa)")
        if not chosen:return
        ipa=Path(chosen)
    else:
        ipa=Path(ipa)
    if not ipa.is_file() or ipa.suffix.lower()!='.ipa':
        QMessageBox.critical(window, "IPA 선택 오류", "선택한 원본 IPA가 존재하지 않아.")
        return
    if not getattr(window, "_scarlet_v8_warned", False):
        # User previously requested and completed force install. Retain explicit
        # non-destructive behavior and disclose missing App Groups on each session.
        decision=QMessageBox.warning(
            window, "강제 서명 · USB 업데이트",
            "Apple 프로파일이 허용하지 않는 App Group/추가 권한을 서명에서 제외해.\\n"
            "기존 앱은 삭제하지 않지만 일부 공유 데이터에 접근하지 못할 수 있어.\\n"
            "선택한 원본 IPA로 업그레이드를 계속할까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if decision != QMessageBox.StandardButton.Yes:return
        window._scarlet_v8_warned=True
    job=[sys.executable,str(helper),"--ipa",str(ipa.resolve()),"--install"]
    exe=next((args for binary,args in (
        ("konsole",["konsole","--noclose","-e",*job]),
        ("kitty",["kitty","--hold",*job]),
        ("xterm",["xterm","-hold","-e",*job])
    ) if shutil.which(binary)),None)
    if not exe:
        QMessageBox.critical(window,"인증 터미널 없음",
            "Apple 로그인 및 2FA 입력을 위해 konsole/kitty/xterm이 필요해.")
        return
    try:
        subprocess.Popen(exe,cwd=str(Path.home()),close_fds=True,start_new_session=True)
    except OSError as exc:
        QMessageBox.critical(window,"설치 실행 오류",str(exc));return
    log("V8 GUI INSTALL / IPA="+str(ipa)+" / force")
    QMessageBox.information(window,"설치 실행",
        "선택한 원본 IPA로 자동 갱신·강제 서명·기존 앱 업데이트를 시작했어.\\n"
        "로컬 터미널에서 진행 결과를 확인해.")

def install():
    _ScarletV8PreviousInstall()
    app=QApplication.instance()
    if app is None:return
    found=False
    for win in app.topLevelWidgets():
        button=getattr(win,"both_btn",None)
        if button is None:continue
        found=True
        if getattr(win,"_scarlet_v8_ready",False):continue
        try:
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False,w=win:_scarlet_v8_oneclick(w))
            button.setText("자동 갱신 · 강제 서명 · 설치")
            button.setToolTip("GUI에서 선택한 원본 IPA → 인증서/프로파일 재사용 또는 갱신 → 허용 권한으로 서명 → 기존 앱 USB 업그레이드")
            win._scarlet_v8_ready=True
            log("V8 GUI READY: original selected IPA only")
        except (TypeError,RuntimeError,AttributeError) as exc:
            log("V8 CONNECT ERROR "+str(exc))
    if not found:
        QTimer.singleShot(250, install)
'''

def patch(path, check=False, rollback=False):
    original=path.read_text(encoding='utf-8-sig')
    backup_dir=path.parent/'.scarlet-v8-gui-backups'
    if rollback:
        items=sorted(backup_dir.glob('*/scarlet_figma_bridge.py'),reverse=True)
        if not items:raise RuntimeError('복구 가능한 V8 GUI 백업이 없음: '+str(path))
        if not check:
            shutil.copy2(items[0],path)
        print('[RESTORED]', path)
        return
    if MARK in original:
        print('[PASS] V8 GUI 연결 이미 적용:', path)
        return
    tree=ast.parse(original)
    if not all(s in original for s in ('SCARLET_UPSTREAM_AUTORENEW_V5',
                                       '_scarlet_v5_chosen_ipa',
                                       'def install():',
                                       'class Responsive(')):
        raise RuntimeError('기존 v5/Figma 브리지 구조 불일치; 원본을 수정하지 않음: '+str(path))
    new=original.rstrip()+"\n\n"+RUNTIME+"\n"
    ast.parse(new)
    compile(new,str(path),'exec')
    if check:
        print('[PASS] V8 GUI 패치 가능:', path)
        return
    backup=backup_dir/dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True,mode=0o700)
    shutil.copy2(path,backup/'scarlet_figma_bridge.py')
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.scarlet-v8-gui-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(new);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print('[PASS] GUI 자동갱신/강제서명/업그레이드 통합:',path)
    print('[BACKUP]',backup)

def main():
    if os.geteuid()==0:
        raise RuntimeError('root 대신 hanabi 계정으로 실행해야 해')
    base=Path.home()
    signer=base/'.local/bin/scarlet-force-install-v8.py'
    if not signer.is_file():
        raise RuntimeError('scarlet-force-install-v8.py가 없음')
    paths=[]
    for root in (base/'Downloads'/ROOT, base/'다운로드'/ROOT):
        gui=root/'scarlet_gui.py'
        bridge=root/'scarlet_figma_bridge.py'
        if gui.is_file() and bridge.is_file():
            src=gui.read_text(encoding='utf-8-sig')
            if 'import scarlet_figma_bridge' in src:
                paths.append(bridge)
    if not paths:
        raise RuntimeError('Figma 적용된 기존 Scarlet Arch Installer GUI를 찾지 못함')
    check='--check' in sys.argv
    rollback='--rollback' in sys.argv
    for path in paths:
        patch(path,check,rollback)
    if not check and not rollback:
        print('[NEXT] 기존 scy GUI 완전히 종료 후 일반 사용자로 scy 실행')
        print('[SAFE] 기존 IPA/P12/프로파일/서명 소스/UI 레이아웃 변경 없음')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,SyntaxError) as e:
        print('[STOP]',e,file=sys.stderr)
        raise SystemExit(2)

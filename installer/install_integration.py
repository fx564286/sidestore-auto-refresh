#!/usr/bin/env python3
"""Safely integrate one-click pairing into the EXISTING Arch Installer GUI.

Only injects a hook after the Window class. Operational signing/install code
and entire class body remain byte-identical; backups are retained.
"""
from __future__ import annotations
import ast
from pathlib import Path
import os
import shutil
import sys
import datetime

MARK="# SCARLET_V166_INTEGRATED_SETUP_HOOK"
INJECT=f'''\n{MARK}
from scarlet_oneclick import enable as _scarlet_enable_integrated_setup
_scarlet_enable_integrated_setup(Window)
'''


def locate(roots=None):
    base=Path.home()
    roots=roots or [Path.cwd(),base/"Downloads"/"ScarletCrystal-ArchInstaller-v1.1",
                    base/"다운로드"/"ScarletCrystal-ArchInstaller-v1.1"]
    for root in roots:
        root=Path(root)
        if (root/"scarlet_gui.py").is_file() and (root/"launch.sh").is_file():
            return root
    raise RuntimeError("기존 ScarletCrystal-ArchInstaller-v1.1 폴더를 찾지 못함")


def patch(source):
    if MARK in source:
        if source.count(MARK)!=1:
            raise RuntimeError("중복 V166 삽입 감지")
        return source
    t=ast.parse(source)
    classes=[c for c in t.body if isinstance(c,ast.ClassDef) and c.name=="Window"]
    if len(classes)!=1:
        raise RuntimeError("기존 Window 클래스를 정확히 하나 찾지 못함")
    c=classes[0]
    methods={m.name:m for m in c.body if isinstance(m,ast.FunctionDef)}
    if "make_ui" not in methods:
        raise RuntimeError("기존 make_ui가 없어 서명/설치 기능을 보존할 수 없음")
    ui=ast.get_source_segment(source,methods["make_ui"]) or ""
    for n in ("self.actions_row","self.both_btn"):
        if n not in ui:
            raise RuntimeError("설치 GUI 계약 불일치: "+n)
    if c.end_lineno is None:raise RuntimeError("Window 클래스 줄 범위가 없음")
    lines=source.splitlines(keepends=True)
    # AST lineno is 1-based; insert after class, before entrypoint.
    lines.insert(c.end_lineno,INJECT)
    out="".join(lines)
    compile(out,"scarlet_gui_integrated.py","exec")
    new=ast.parse(out)
    after=next(x for x in new.body if isinstance(x,ast.ClassDef) and x.name=="Window")
    if ast.dump(c,include_attributes=False)!=ast.dump(after,include_attributes=False):
        raise RuntimeError("기존 Window 서명·설치 코드 변경 감지")
    return out


def install(root=None):
    root=Path(root) if root else locate()
    gui=root/"scarlet_gui.py"
    module_src=Path(__file__).with_name("scarlet_oneclick.py")
    if not gui.is_file() or not (root/"launch.sh").is_file() or not module_src.is_file():
        raise RuntimeError("기존 설치 프로그램 파일이 없거나 배포 모듈 누락")
    source=gui.read_text(encoding="utf-8-sig")
    updated=patch(source)
    backup=root/".scarlet-v166-snapshots"/datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(gui,backup/"scarlet_gui.py")
    if (root/"scarlet_oneclick.py").is_file():
        shutil.copy2(root/"scarlet_oneclick.py",backup/"scarlet_oneclick.py")
    staged=root/"scarlet_gui.py.v166-staged"
    staged_module=root/"scarlet_oneclick.py.v166-staged"
    try:
        shutil.copy2(module_src,staged_module)
        compile(staged_module.read_text(encoding="utf-8"),str(staged_module),"exec")
        staged.write_text(updated,encoding="utf-8")
        compile(staged.read_text(),str(staged),"exec")
        # Only replace after every validation; launch.sh untouched.
        os.replace(staged_module,root/"scarlet_oneclick.py")
        os.replace(staged,gui)
    finally:
        staged.unlink(missing_ok=True)
        staged_module.unlink(missing_ok=True)
    return str(root),str(backup)


if __name__=="__main__":
    try:
        folder,snapshot=install(Path(sys.argv[1]) if len(sys.argv)>1 else None)
        print("[PASS] Scarlet Crystal 기존 GUI 내 통합 설치 버튼 추가:",folder)
        print("[KEEP] 원본 서명·프로비저닝·설치 기능 및 백업:",snapshot)
        print("[RUN] bash",str(Path(folder)/"launch.sh"))
    except Exception as e:
        print("[STOP] 통합 적용 실패 — 기존 설치 프로그램 변경하지 않음:",e,file=sys.stderr)
        sys.exit(1)

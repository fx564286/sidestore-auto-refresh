#!/usr/bin/env python3
"""Scarlet Crystal V5: use proven SideInstaller renewal for upstream unsigned IPA.

No certificate issuance/revocation or app removal. Original IPA is never edited.
The existing scy-auto tool owns Apple login, profile verification, zsign and
the fail-closed installed-app entitlement audit. GUI patch only rebinds the
combined-action button, retaining the existing layout and diagnostic logs.
"""
from __future__ import annotations
import argparse
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

BASE = "com.kdt.livecontainer"
TARGET = BASE + ".P8EZT3U5N4"
EXT = {"LaunchAppExtension", "LiveProcess", "ShareExtension"}
MARK = "SCARLET_UPSTREAM_AUTORENEW_V5"
GUI_ROOT = "ScarletCrystal-ArchInstaller-v1.1"

RUNTIME = r'''
# SCARLET_UPSTREAM_AUTORENEW_V5
from pathlib import Path as _ScarletPath
from PySide6.QtWidgets import QFileDialog as _ScarletFileDialog
from PySide6.QtWidgets import QMessageBox as _ScarletMessageBox
import os as _scarlet_os
import shutil as _scarlet_shutil
import subprocess as _scarlet_subprocess
import sys as _scarlet_sys

_ScarletV5OriginalInstall = install

def _scarlet_v5_chosen_ipa(window):
    from pathlib import Path
    found = {}
    for owner in (window, getattr(window, "drop", None),
                  getattr(window, "ipa_drop", None)):
        if owner is None: continue
        for name, value in vars(owner).items():
            if isinstance(value, (str, Path)):
                candidate = str(value).strip()
            elif hasattr(value, "text") and callable(value.text):
                try: candidate = str(value.text()).strip()
                except (RuntimeError, TypeError): continue
            else: continue
            if not candidate.lower().endswith(".ipa"): continue
            p=Path(candidate).expanduser()
            if p.is_file():
                found[str(p.resolve())]=p.resolve()
    if len(found)==1: return next(iter(found.values()))
    return None

def _scarlet_v5_oneclick(window):
    if _scarlet_os.geteuid() == 0:
        _ScarletMessageBox.critical(window, "권한 오류", "hanabi 계정으로 실행해야 해.")
        return
    path = _scarlet_v5_chosen_ipa(window)
    if path is None:
        p, _ = _ScarletFileDialog.getOpenFileName(
            window, "Scarlet Crystal 원본 IPA 선택",
            str(_ScarletPath.home() / "바탕화면"), "iOS 앱 (*.ipa)")
        if not p: return
        path = _ScarletPath(p)
    helper=_ScarletPath.home()/".local/bin/scarlet-upstream-v5.py"
    if not helper.is_file():
        _ScarletMessageBox.critical(window,"통합 도구 없음",str(helper));return
    # Directly pass the user-selected IPA, never search or silently replace it.
    job=[_scarlet_sys.executable,str(helper),"--ipa",str(path.resolve())]
    for executable,args in (
        ("konsole",["konsole","--noclose","-e",*job]),
        ("kitty",["kitty","--hold",*job]),
        ("xterm",["xterm","-hold","-e",*job])):
        if _scarlet_shutil.which(executable):
            try:
                _scarlet_subprocess.Popen(args,close_fds=True,
                                         start_new_session=True,cwd=str(_ScarletPath.home()))
            except OSError as exc:
                _ScarletMessageBox.critical(window,"터미널 실행 실패",str(exc));return
            _ScarletMessageBox.information(
                window,"자동 갱신 · 서명 · 설치",
                "선택한 IPA를 별도 작업 파일로 안전하게 변환한 뒤 "
                "SideInstaller로 프로파일 4개를 갱신해.\n"
                "서명·데이터 보존 검증을 통과할 때만 기존 앱 업데이트를 실행해.\n"
                "Apple 인증은 열린 로컬 터미널에서 진행돼.")
            return
    _ScarletMessageBox.critical(window,"터미널 없음",
         "konsole, kitty 또는 xterm이 필요해. 암호 입력을 위해 로컬 터미널을 사용해야 해.")

def install():
    _ScarletV5OriginalInstall()
    app=QApplication.instance()
    if app is None:return
    for win in app.topLevelWidgets():
        b=getattr(win,"both_btn",None)
        if b is None or getattr(win,"_scarlet_v5_ready",False):continue
        try:
            b.clicked.disconnect()
            b.clicked.connect(lambda checked=False,w=win:_scarlet_v5_oneclick(w))
        except (RuntimeError,TypeError) as exc:
            log("V5_GUI_CONNECT_ERROR "+str(exc))
            continue
        b.setText("자동 갱신 · 서명 · 설치")
        b.setToolTip("선택한 V181 원본 IPA → App ID 변환 사본 → Apple 4개 프로파일 → 검증 후 업데이트")
        win._scarlet_v5_ready=True
        log("V5_GUI_READY: oneclick via safe upstream staging")
    if not any(getattr(win,"_scarlet_v5_ready",False) for win in app.topLevelWidgets()):
        QTimer.singleShot(300,install)
'''

def stop(reason: str):
    raise SystemExit("[STOP] " + reason)

def describe(path: Path):
    with zipfile.ZipFile(path) as z:
        entries=z.namelist()
        if len(entries)!=len(set(entries)) or len(entries)>25000:
            stop("IPA 내 중복 항목 또는 너무 많은 항목")
        if z.testzip() is not None:
            stop("IPA 압축 데이터 손상")
        if any(name.startswith("/") or ".." in Path(name).parts for name in entries):
            stop("IPA 내 비정상 경로")
        total=sum(x.file_size for x in z.infolist())
        if total > 4*1024**3:stop("IPA 무압축 데이터가 4 GiB 초과")
        mains=[n for n in entries if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist",n)]
        if len(mains)!=1:stop("메인 앱 Info.plist가 하나가 아님")
        prefix=mains[0].removesuffix("Info.plist")
        records={}
        for name in entries:
            if name==mains[0] or re.fullmatch(re.escape(prefix)+
                    r"(?:PlugIns|Extensions)/[^/]+\.appex/Info\.plist",name):
                info=plistlib.loads(z.read(name))
                bundle=info.get("CFBundleIdentifier")
                if not isinstance(bundle,str):stop("Bundle ID 누락: "+name)
                records[name]=(bundle,info)
        if len(records)!=4:stop(f"V181 호스트+확장 3개 필요 (발견 {len(records)})")
        host=records[mains[0]][0]
        if host not in (BASE,TARGET):stop("기존 원본/설치 Bundle ID와 불일치: "+host)
        names=set()
        for path,(bundle,info) in records.items():
            if path==mains[0]:continue
            allowed={host+"."+suffix:suffix for suffix in EXT}
            if bundle not in allowed:
                stop("인식할 수 없는 확장 Bundle ID: "+bundle)
            names.add(allowed[bundle])
        if names!=EXT:stop("필수 확장 세 개가 없음: "+str(names))
        return mains[0],records

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def stage(source: Path):
    source=source.expanduser().resolve(strict=True)
    if source.suffix.lower()!=".ipa":stop("IPA 파일만 허용")
    main,records=describe(source)
    if records[main][0]==TARGET:
        return source,source,False
    state=Path.home()/".local/state/scarlet-crystal-installer/upstream-v5"
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    folder=state/dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    folder.mkdir(mode=0o700)
    output=folder/"Scarlet-Crystal-V181-STAGED-UNSIGNED.ipa"
    digest=sha256(source)
    replacements={}
    for name,(bundle,info) in records.items():
        expected=TARGET if bundle==BASE else TARGET+"."+bundle.removeprefix(BASE+".")
        if expected!=bundle:
            info["CFBundleIdentifier"]=expected
            replacements[name]=plistlib.dumps(info,fmt=plistlib.FMT_BINARY,
                                               sort_keys=False)
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(output,"w",
                                            allowZip64=True) as zout:
        for entry in zin.infolist():
            data=replacements.get(entry.filename)
            if data is None:data=zin.read(entry.filename)
            zout.writestr(entry,data)
    os.chmod(output,0o600)
    outmain,outrecords=describe(output)
    if outrecords[outmain][0]!=TARGET or \
       {b for b,_ in outrecords.values()} != {TARGET}|{TARGET+"."+x for x in EXT}:
        output.unlink(missing_ok=True)
        stop("변환 IPA의 Bundle ID 검증 실패")
    # Verify every untouched IPA member has identical uncompressed bytes.
    with zipfile.ZipFile(source) as a,zipfile.ZipFile(output) as b:
        for name in a.namelist():
            if name not in replacements and a.read(name)!=b.read(name):
                output.unlink(missing_ok=True)
                stop("원본 콘텐츠 보존 검사 실패")
    report={"source":str(source),"original_sha256":digest,
            "staged":str(output),"staged_sha256":sha256(output),
            "target":TARGET,"exts":sorted(EXT),
            "modified_infos":sorted(replacements)}
    (folder/"stage-manifest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    os.chmod(folder/"stage-manifest.json",0o600)
    return source,output,True

def atomic(path:Path, data:str):
    fd,temp=tempfile.mkstemp(prefix=".scarlet-upstream-v5-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def patch_gui(dry=False,undo=False):
    home=Path.home()
    folders=[x for x in (home/"다운로드"/GUI_ROOT,home/"Downloads"/GUI_ROOT)
             if (x/"scarlet_gui.py").is_file()
             and (x/"scarlet_figma_bridge.py").is_file()]
    if not folders:stop("통합 Figma GUI가 설치된 Scarlet Arch Installer 경로 없음")
    ast.parse(RUNTIME)
    for folder in folders:
        p=folder/"scarlet_figma_bridge.py"
        gui=(folder/"scarlet_gui.py").read_text(encoding="utf-8-sig")
        if "import scarlet_figma_bridge" not in gui:
            stop("기존 GUI에서 Figma 브리지를 import하지 않음: "+str(folder))
        bridge=p.read_text(encoding="utf-8-sig")
        backups=folder/".scarlet-upstream-v5-backups"
        if undo:
            hist=sorted(backups.glob("*/scarlet_figma_bridge.py"),reverse=True)
            if not hist:stop("V5 복구 백업 없음")
            if not dry:shutil.copy2(hist[0],p)
            print("[RESTORED]",p)
            continue
        if MARK in bridge:
            print("[PASS] V5 already installed:",p);continue
        if not all(k in bridge for k in ("def install():","def oneclick(", "class Responsive(")):
            stop("예상한 Figma 브리지 구조가 아님: "+str(p))
        auto=folder/"scarlet_auto_gui_bridge.py"
        if auto.is_file():
            s=auto.read_text(encoding="utf-8-sig")
            if "clicked.disconnect" in s and "SCARLET_NATIVE_COMPAT_V4" not in s:
                stop("기존 v2 자동 클릭 브리지가 충돌함; 먼저 native-v4 패치 적용 필요")
        result=bridge.rstrip()+"\n\n"+RUNTIME+"\n"
        ast.parse(result)
        compile(result,str(p),"exec")
        if dry:
            print("[CHECK] V5 GUI bridge can patch",p)
            continue
        saved=backups/dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        saved.mkdir(parents=True,mode=0o700)
        shutil.copy2(p,saved/p.name)
        atomic(p,result)
        print("[PASS] V5 integrated button",p)
        print("[BACKUP]",saved)

def run_sign(path:Path,renew_only=False,check=False):
    if os.geteuid()==0:stop("hanabi 일반 사용자로 실행")
    if not path.is_file():stop("선택한 IPA 파일 없음: "+str(path))
    original,staged,changed=stage(path)
    print("[IPA]",original)
    print("[STAGED]",staged if changed else "already target ID")
    print("[SAFE] original intact, target="+TARGET+", extensions=3")
    signer=Path.home()/".local/bin/scy-auto"
    if not signer.is_file():stop("기존 SideInstaller 자동 서명기 scy-auto 없음")
    if check:
        print("[PASS] Bundle ID staging verified. No Apple request/install")
        return 0
    cmd=[sys.executable,str(signer),"--ipa",str(staged),
         "--renew-only" if renew_only else "--install"]
    print("[RUN] SideInstaller Apple renewal → 4 profiles → signing",
          "→ device audit → upgrade" if not renew_only else "(renew only)",flush=True)
    return subprocess.call(cmd)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--ipa",type=Path)
    a.add_argument("--check",action="store_true")
    a.add_argument("--renew-only",action="store_true")
    a.add_argument("--rollback",action="store_true")
    args=a.parse_args()
    if os.geteuid()==0:stop("hanabi 일반 사용자로 실행")
    if args.ipa:
        return run_sign(args.ipa,args.renew_only,args.check)
    patch_gui(dry=args.check,undo=args.rollback)
    print("[NEXT] close GUI and launch scy")
    return 0
if __name__=="__main__":
    raise SystemExit(main())

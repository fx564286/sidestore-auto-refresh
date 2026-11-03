#!/usr/bin/env python3
"""Scarlet Crystal Arch Installer: one-click Apple profile renewal + Figma adaptive layout.
Only patches the user's existing PySide6 GUI, leaving signing internals untouched.
Run as hanabi; original GUI and new helper are backed up.
"""
import ast
import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile

MARK = "SCARLET_FIGMA_ONECLICK_20261103"
ROOT = "ScarletCrystal-ArchInstaller-v1.1"

RUNTIME = r'''
from pathlib import Path
import os
import plistlib
import shutil
import subprocess
import sys
import zipfile
from PySide6.QtCore import QTimer, QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QBoxLayout, QTabWidget, QSizePolicy, QLabel

BUNDLE = "com.kdt.livecontainer.P8EZT3U5N4"
ROOT_LOG = Path.home()/".local/state/scarlet-crystal-installer"
DONE = False

def log(msg):
    try:
        from scarlet_realtime_log import record
        record("FIGMA-ONECLICK",msg)
    except Exception:
        ROOT_LOG.mkdir(parents=True,exist_ok=True)
        with (ROOT_LOG/"figma-oneclick.log").open("a") as f:f.write(msg+"\n")

def selected_ipa(window):
    values=[]
    for w in (window,getattr(window,"drop",None),getattr(window,"ipa_drop",None)):
        if w is None:continue
        for name in ("selected_ipa","ipa_path","current_ipa","source_ipa","selected_path","selected_file","file_path","ipa_file","ipa"):
            v=getattr(w,name,None)
            if hasattr(v,"text") and callable(v.text):
                try:v=v.text()
                except RuntimeError:continue
            if isinstance(v,(str,Path)):
                p=Path(v).expanduser()
                if p.suffix.lower()==".ipa" and p.is_file() and p not in values:values.append(p)
    return values[0] if len(values)==1 else None

def preflight(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError("IPA ZIP이 손상됨")
        ns=z.namelist()
        mains=[n for n in ns if n.startswith("Payload/") and n.count("/")==2 and n.endswith(".app/Info.plist")]
        if len(mains)!=1:raise ValueError("메인 앱이 정확히 하나가 아님")
        main=plistlib.loads(z.read(mains[0]))
        if main.get("CFBundleIdentifier")!=BUNDLE:raise ValueError("기존 Bundle ID 불일치")
        prefix=mains[0][:-10]
        extensions=set()
        for n in ns:
            if not n.startswith(prefix) or not n.endswith(".appex/Info.plist"):continue
            part=n[len(prefix):].split("/")
            if len(part)!=3 or part[0] not in ("PlugIns","Extensions"):continue
            ident=plistlib.loads(z.read(n)).get("CFBundleIdentifier")
            if not isinstance(ident,str) or not ident.startswith(BUNDLE+"."):raise ValueError("확장 Bundle ID 불일치")
            if ident in extensions:raise ValueError("확장 중복")
            extensions.add(ident)
        if BUNDLE+".LiveProcess" not in extensions:raise ValueError("필수 LiveProcess 없음")
        if BUNDLE+".LiveWidget" in extensions:raise ValueError("제거했던 LiveWidget이 포함됨. 회귀 빌드 차단")
        return main,extensions

def oneclick(window):
    if os.geteuid()==0:
        QMessageBox.critical(window,"권한 오류","root가 아닌 hanabi 계정으로 실행해줘.")
        return
    signer=Path.home()/".local/bin/scy-auto"
    if not signer.is_file():
        QMessageBox.critical(window,"자동 갱신기 없음",str(signer));return
    ipa=selected_ipa(window)
    if ipa is None:
        chosen,_=QFileDialog.getOpenFileName(window,"원본 Scarlet Crystal IPA 선택",str(Path.home()/"다운로드"),"IPA (*.ipa)")
        if not chosen:return
        ipa=Path(chosen)
    try:info,ext=preflight(ipa)
    except (OSError,ValueError,zipfile.BadZipFile,plistlib.InvalidFileException) as e:
        QMessageBox.critical(window,"IPA 검증 중단",str(e));log("IPA REJECT "+str(e));return
    if BUNDLE+".LaunchAppExtension" not in ext:
        ans=QMessageBox.warning(window,"확장 구성 변경 가능성",
            "선택한 IPA에는 LaunchAppExtension이 없어. 기존 기능에 영향을 줄 수 있어.\n"
            "기존 IPA 구조를 수정하지 않고 그대로 업데이트할까?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if ans!=QMessageBox.StandardButton.Yes:return
    program=[sys.executable,str(signer),"--ipa",str(ipa.resolve()),"--install"]
    choices=[("konsole",["konsole","--noclose","-e",*program]),
             ("kitty",["kitty","--hold",*program]),
             ("xterm",["xterm","-hold","-e",*program])]
    cmd=next((x for exe,x in choices if shutil.which(exe)),None)
    if cmd is None:
        QMessageBox.critical(window,"로컬 인증 터미널 필요",
            "Konsole, kitty 또는 xterm이 필요해. Apple 암호/2FA는 터미널에서만 입력돼.")
        return
    try:subprocess.Popen(cmd,cwd=str(Path.home()),close_fds=True,start_new_session=True)
    except OSError as e:
        QMessageBox.critical(window,"실행 오류",str(e));return
    log("START ipa="+str(ipa)+" extensions="+str(len(ext)))
    QMessageBox.information(window,"통합 서명 시작",
        "원본 IPA의 자동 프로파일 갱신 → 재서명 → 안전 검사 → 제자리 업데이트를 시작했어.\n"
        "열린 로컬 터미널에서 Apple 암호/2FA를 입력해줘.\n"
        "실제 설치 성공 여부는 터미널 최종 로그에서 확인해야 해.")

class Responsive(QObject):
    def __init__(self,w):
        super().__init__(w);self.w=w;self.tabs=None;self.last=None;self.busy=False
        w.installEventFilter(self)
        for key in ("kicker","subheading","sectionKicker"):
            item=w.findChild(QLabel,key)
            if item is not None:item.hide()
        QTimer.singleShot(0,self.reflow)
    def eventFilter(self,obj,event):
        if obj is self.w and event.type() in (QEvent.Type.Resize,QEvent.Type.Show):
            QTimer.singleShot(0,self.reflow)
        return False
    def reflow(self):
        if self.busy:return
        self.busy=True
        try:
            w=self.w;small=w.width()<1000;tight=small or w.height()<780
            spacing=8 if small else 14
            layout=getattr(w,"content_layout",None)
            if layout:
                pad=16 if small else 24
                layout.setContentsMargins(pad,9 if tight else 16,pad,9 if tight else 16)
                layout.setSpacing(spacing)
            row=getattr(w,"info_row",None)
            cards=[getattr(w,n,None) for n in ("metadata_card","signing_card")]
            if isinstance(row,QBoxLayout) and all(c is not None for c in cards):
                if self.tabs is None:
                    self.tabs=getattr(w,"_sc_tabs_widget_v4",None)
                if small:
                    if not isinstance(self.tabs,QTabWidget):
                        self.tabs=QTabWidget(w);self.tabs.setObjectName("scarletResponsiveTabs")
                        row.addWidget(self.tabs)
                    for i,c in enumerate(cards):
                        if self.tabs.indexOf(c)<0:self.tabs.addTab(c,("IPA 분석","Apple 서명")[i])
                    self.tabs.show()
                else:
                    if isinstance(self.tabs,QTabWidget):
                        for c in cards:
                            idx=self.tabs.indexOf(c)
                            if idx>=0:self.tabs.removeTab(idx)
                        self.tabs.hide()
                    row.setDirection(QBoxLayout.Direction.LeftToRight)
                    for i,c in enumerate(cards):
                        if row.indexOf(c)<0:row.insertWidget(i,c,1)
                        c.setMinimumWidth(0);c.setMaximumWidth(16777215)
                        c.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
                        row.setStretch(row.indexOf(c),1)
            buttons=getattr(w,"actions_row",None)
            if isinstance(buttons,QBoxLayout):
                buttons.setDirection(QBoxLayout.Direction.LeftToRight)
                buttons.setSpacing(spacing)
                for name in ("sign_btn","upgrade_btn","both_btn"):
                    widget=getattr(w,name,None)
                    if widget is not None:
                        widget.setMinimumWidth(0);widget.setMaximumWidth(16777215)
                        widget.setFixedHeight(37 if tight else 46)
                        widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
                        idx=buttons.indexOf(widget)
                        if idx>=0:buttons.setStretch(idx,1)
            drop=getattr(w,"drop",None)
            if drop is not None and hasattr(drop,"setFixedHeight"):drop.setFixedHeight(58 if tight else 96)
            scroll=getattr(w,"workspace_scroll",None)
            if scroll is not None:
                scroll.setWidgetResizable(True)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                overflow=scroll.verticalScrollBar().maximum()
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if overflow==0 else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                key=(w.width(),w.height(),overflow)
                if overflow and key!=self.last:
                    self.last=key;log("OVERFLOW "+str(key)+"; control accessibility retained")
        except (TypeError,RuntimeError,AttributeError) as e:log("LAYOUT ERROR "+str(e))
        finally:self.busy=False

def install():
    global DONE
    if DONE:return
    app=QApplication.instance()
    if app is None:return
    for w in app.topLevelWidgets():
        button=getattr(w,"both_btn",None)
        if button is None:continue
        try:
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False,window=w:oneclick(window))
            button.setText("자동 갱신 · 서명 · 설치")
            button.setToolTip("선택한 원본 IPA를 기존 인증서로 갱신·재서명·업데이트")
            w._scarlet_figma_controller=Responsive(w)
            DONE=True;log("READY: one-click and responsive UI attached")
            return
        except (TypeError,RuntimeError) as e:log("BIND ERROR "+str(e))
    QTimer.singleShot(300,install)
'''

def patch(source):
    if MARK in source:return source
    t=ast.parse(source)
    win=[n for n in t.body if isinstance(n,ast.ClassDef) and n.name=="Window"]
    if len(win)!=1 or "both_btn" not in (ast.get_source_segment(source,win[0]) or ""):
        raise RuntimeError("Window/both_btn 구조 불일치 — 원본 유지")
    app=[n for n in ast.walk(t) if isinstance(n,(ast.Assign,ast.AnnAssign)) and isinstance(n.value,ast.Call) and
         ((isinstance(n.value.func,ast.Name) and n.value.func.id=="QApplication") or
          (isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="QApplication"))]
    if len(app)!=1:raise RuntimeError("QApplication 생성 지점 불명확")
    lines=source.splitlines(keepends=True)
    n=app[0];ind=lines[n.lineno-1][:len(lines[n.lineno-1])-len(lines[n.lineno-1].lstrip())]
    lines.insert(n.end_lineno,ind+"scarlet_figma_bridge.QTimer.singleShot(0, scarlet_figma_bridge.install)\n")
    result="".join(lines);t=ast.parse(result);pos=0
    for n in t.body:
        if isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):pos=n.end_lineno
        elif isinstance(n,ast.ImportFrom) and n.module=="__future__":pos=n.end_lineno
        else:break
    lines=result.splitlines(keepends=True)
    lines.insert(pos,"\n# "+MARK+"\nimport scarlet_figma_bridge\n")
    result="".join(lines);ast.parse(result)
    return result

def main():
    if os.geteuid()==0:raise RuntimeError("hanabi 사용자로 실행해야 해 (root 금지)")
    home=Path.home();name=ROOT
    options=[home/"Downloads"/name,home/"다운로드"/name]
    folders=[x for x in options if (x/"scarlet_gui.py").is_file() and (x/"launch.sh").is_file()]
    if not folders:raise RuntimeError("기존 ScarletCrystal Arch Installer 소스가 없음")
    launcher=home/".local/bin/scy"
    if len(folders)>1 and launcher.is_file():
        src=launcher.read_text(errors="replace")
        folders.sort(key=lambda p:0 if str(p) in src else 1)
    app=folders[0]
    gui=app/"scarlet_gui.py";helper=app/"scarlet_figma_bridge.py"
    data=gui.read_text(encoding="utf-8-sig");updated=patch(data)
    if updated==data:print("[PASS] 이미 통합됨");return
    compile(updated,str(gui),"exec");compile(RUNTIME,str(helper),"exec")
    if not (home/".local/bin/scy-auto").is_file():raise RuntimeError("검증된 scy-auto 갱신기가 없음")
    backup=app/".scarlet-oneclick-backups"/datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True,mode=0o700)
    shutil.copy2(gui,backup/"scarlet_gui.py")
    if helper.exists():shutil.copy2(helper,backup/"scarlet_figma_bridge.py")
    def atomic(path,value):
        fd,tmp=tempfile.mkstemp(prefix=".scarlet-stage-",dir=path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                f.write(value);f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o600);os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    try:atomic(helper,RUNTIME);atomic(gui,updated)
    except BaseException:
        shutil.copy2(backup/"scarlet_gui.py",gui);raise
    print("[PASS] 기존 GUI에 Figma 적응형 배치 + 서명·설치 원클릭 연결")
    print("[BACKUP]",backup)
    print("[NEXT] GUI를 완전히 종료하고 기존 scy 명령으로 실행")
    print("[SAFE] Apple 인증서·IPA·iPhone 데이터는 변경하지 않음")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[STOP]",str(e),file=sys.stderr);sys.exit(1)

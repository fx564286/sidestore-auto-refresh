#!/usr/bin/env python3
"""Scarlet Crystal Arch Installer UI hotfix v3.
Targets the existing Figma bridge, without touching signing, bundles or data.
"""
import argparse
import ast
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile

MARK = "SCARLET_UI_V3_MODAL_AND_REFLOW"
APP = "ScarletCrystal-ArchInstaller-v1.1"

RUNTIME = r'''
# SCARLET_UI_V3_MODAL_AND_REFLOW
from PySide6.QtGui import QPalette, QColor

SCARLET_ERROR_QSS = """
QMessageBox {
    background: #151F30; color: #F4F7FD;
    border: 1px solid #34445A; border-radius: 12px;
}
QMessageBox QLabel {
    color: #F4F7FD; background: transparent;
    font-size: 13px; padding: 3px;
}
QMessageBox QPushButton {
    background: #284E85; color: #FFFFFF;
    border: 1px solid #577CA9; border-radius: 9px;
    min-height: 32px; min-width: 92px;
    padding: 5px 14px; font-size: 13px;
}
QMessageBox QPushButton:hover { background: #3567AE; }
QMessageBox QPushButton:focus { border: 2px solid #F17994; }
"""

def scarlet_theme_messagebox(dialog):
    try:
        if dialog.property("scarlet_v3_themed"):
            return
        dialog.setProperty("scarlet_v3_themed", True)
        dialog.setStyleSheet(SCARLET_ERROR_QSS)
        palette = dialog.palette()
        for role, code in (
            (QPalette.ColorRole.Window, "#151F30"),
            (QPalette.ColorRole.WindowText, "#F4F7FD"),
            (QPalette.ColorRole.Text, "#F4F7FD"),
            (QPalette.ColorRole.ButtonText, "#FFFFFF"),
        ):
            palette.setColor(role, QColor(code))
        dialog.setPalette(palette)
        for label in dialog.findChildren(QLabel):
            if label.text():
                label.setWordWrap(True)
                label.setStyleSheet("color: #F4F7FD; background: transparent; font-size: 13px;")
        available = dialog.screen().availableGeometry() if dialog.screen() else None
        maximum = available.width() - 28 if available else 470
        dialog.setMinimumWidth(min(460, max(270, maximum)))
        dialog.setMinimumHeight(156)
        QTimer.singleShot(0, lambda box=dialog: scarlet_fit_dialog(box))
    except (RuntimeError, AttributeError, TypeError) as exc:
        log("MESSAGEBOX_STYLE_ERROR " + str(exc))

def scarlet_fit_dialog(dialog):
    try:
        dialog.adjustSize()
        area = dialog.screen().availableGeometry() if dialog.screen() else None
        if area:
            dialog.resize(min(dialog.width(), max(270, area.width()-20)),
                          min(dialog.height(), max(156, area.height()-20)))
            x = max(area.left(), min(dialog.x(), area.right()-dialog.width()+1))
            y = max(area.top(), min(dialog.y(), area.bottom()-dialog.height()+1))
            if (x,y)!=(dialog.x(),dialog.y()): dialog.move(x,y)
    except (RuntimeError, AttributeError):
        pass

class ScarletDialogFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QMessageBox):
            scarlet_theme_messagebox(obj)
        return False

def scarlet_register_dialog_filter():
    app = QApplication.instance()
    if app and not getattr(app, "_scarlet_dialog_filter_v3", None):
        filt = ScarletDialogFilter(app)
        app.installEventFilter(filt)
        app._scarlet_dialog_filter_v3 = filt
        log("DIALOG_V3_READY")

_ScarletPreviousResponsive = Responsive

class Responsive(_ScarletPreviousResponsive):
    def reflow(self):
        if getattr(self, "_v3_reflow_busy", False):
            return
        self._v3_reflow_busy = True
        try:
            super().reflow()
            self._balance()
        except (RuntimeError, AttributeError, TypeError) as exc:
            log("V3_LAYOUT_ERROR " + str(exc))
        finally:
            self._v3_reflow_busy = False

    def _balance(self):
        w = self.w
        width, height = w.width(), w.height()
        compact = height < 790 or width < 990
        pad = 7 if compact else 12
        gap = 5 if compact else 11
        content = getattr(w, "content_layout", None)
        if content:
            content.setContentsMargins(pad, pad, pad, pad)
            content.setSpacing(gap)

        hero = getattr(w, "_sc7_hero", None)
        if isinstance(hero, QBoxLayout):
            horizontal = width >= 790
            hero.setDirection(QBoxLayout.Direction.LeftToRight if horizontal
                              else QBoxLayout.Direction.TopToBottom)
            hero.setSpacing(6 if compact else 11)
            for idx, weight in enumerate((2,5,2)):
                if idx < hero.count():
                    hero.setStretch(idx, weight if horizontal else 0)
            h = 58 if compact else 76
            for field, target_height in (
                ("drop", h if horizontal else 52),
                ("choose_btn", h if horizontal else 42),
            ):
                widget = getattr(w, field, None)
                if widget:
                    widget.setMinimumHeight(0)
                    widget.setMaximumHeight(16777215)
                    widget.setFixedHeight(target_height)
            for label in w.findChildren(QLabel):
                if label.text().strip().upper() == "READY":
                    label.setMinimumHeight(0)
                    label.setMaximumHeight(16777215)
                    label.setFixedHeight(h if horizontal else 38)

        columns = getattr(w, "info_row", None)
        panels = [getattr(w, name, None) for name in ("metadata_card","signing_card")]
        if isinstance(columns, QBoxLayout) and all(panel is not None for panel in panels):
            if width >= 990:
                columns.setDirection(QBoxLayout.Direction.LeftToRight)
                columns.setSpacing(gap)
                for panel in panels:
                    panel.setMinimumWidth(0)
                    panel.setMaximumWidth(16777215)
                    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    i = columns.indexOf(panel)
                    if i >= 0:
                        columns.setStretch(i, 1)
            for panel in panels:
                layout = panel.layout()
                if layout:
                    layout.setContentsMargins(pad,pad,pad,pad)
                    if hasattr(layout, "setVerticalSpacing"):
                        layout.setVerticalSpacing(3 if compact else 6)
                        layout.setHorizontalSpacing(6 if compact else 10)

        for name in ("key_field","cert_field","p12_field","profile_field","zsign_field"):
            edit = getattr(w,name,None)
            if edit:
                edit.setMinimumHeight(0)
                edit.setMaximumHeight(27 if compact else 33)

        actions = getattr(w,"actions_row",None)
        if isinstance(actions,QBoxLayout):
            actions.setDirection(QBoxLayout.Direction.LeftToRight if width>=740
                                 else QBoxLayout.Direction.TopToBottom)
            actions.setSpacing(6)
            for name in ("sign_btn","upgrade_btn","both_btn"):
                btn=getattr(w,name,None)
                if btn:
                    btn.setMinimumWidth(0)
                    btn.setMaximumWidth(16777215)
                    btn.setFixedHeight(34 if compact else 43)
                    i=actions.indexOf(btn)
                    if i>=0:actions.setStretch(i,1)

        splitter = getattr(w, "splitter", None)
        if splitter and splitter.orientation() == Qt.Orientation.Vertical:
            total=max(200,splitter.height())
            log_height=max(132,min(194,round(total*.23)))
            splitter.setChildrenCollapsible(False)
            splitter.setStretchFactor(0,4)
            splitter.setStretchFactor(1,1)
            splitter.setSizes([max(1,total-log_height),log_height])

        sc=getattr(w,"workspace_scroll",None)
        if sc:
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            def check():
                try:
                    overflow=sc.verticalScrollBar().maximum()
                    sc.setVerticalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAlwaysOff if overflow==0
                        else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                    if overflow:
                        log("V3_OVERFLOW "+str((w.width(),w.height(),overflow)))
                except RuntimeError: pass
            QTimer.singleShot(0,check)

_ScarletPreviousInstall = install

def install():
    scarlet_register_dialog_filter()
    return _ScarletPreviousInstall()
'''

def replace_atomically(path, data):
    handle, temp = tempfile.mkstemp(prefix=".scarlet-ui-v3-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--rollback",action="store_true")
    args=parser.parse_args()
    if os.geteuid()==0:
        sys.exit("[STOP] hanabi 일반 사용자 권한으로 실행해야 함")
    home=Path.home()
    paths=[]
    for root in (home/"Downloads"/APP,home/"다운로드"/APP):
        helper=root/"scarlet_figma_bridge.py"
        gui=root/"scarlet_gui.py"
        if helper.is_file() and gui.is_file() and helper.resolve() not in paths:
            paths.append(helper.resolve())
    if not paths:
        sys.exit("[STOP] 이전 Figma 통합 패치가 설치된 GUI를 찾지 못함")
    ast.parse(RUNTIME)
    for helper in paths:
        backup_root=helper.parent/".scarlet-ui-v3-backups"
        if args.rollback:
            old=sorted(backup_root.glob("*/scarlet_figma_bridge.py"),reverse=True)
            if not old: print("[SKIP] 백업 없음",helper);continue
            if not args.dry_run:shutil.copy2(old[0],helper)
            print("[RESTORE]",helper)
            continue
        original=helper.read_text(encoding="utf-8-sig")
        if MARK in original:
            print("[PASS] v3 이미 적용됨",helper);continue
        ast.parse(original)
        if not all(s in original for s in ("class Responsive(", "def oneclick(", "def install(")):
            sys.exit("[STOP] 예상한 Figma 브리지 구조가 아님. 원본 유지: "+str(helper))
        result=original.rstrip()+"\n\n"+RUNTIME+"\n"
        ast.parse(result)
        compile(result,str(helper),"exec")
        if args.dry_run:
            print("[PASS] 패치 가능",helper);continue
        backup=backup_root/datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup.mkdir(parents=True,mode=0o700)
        (backup/"scarlet_figma_bridge.py").write_text(original,encoding="utf-8")
        (backup/"scarlet_figma_bridge.py").chmod(0o600)
        replace_atomically(helper,result)
        print("[PASS] 오류 팝업 테마/대비 및 적응형 레이아웃 적용:",helper)
        print("[BACKUP]",backup)
    print("[NEXT] 기존 scy 창을 닫고 일반 사용자로 scy 실행")
    print("[SAFE] Bundle ID 검증/Apple 인증서/IPA/설치 코드 변경 없음")

if __name__=="__main__":
    main()

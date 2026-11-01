"""Scarlet Crystal integrated first install (Arch/CachyOS + existing PySide6 GUI).

One button in the *existing* Scarlet Crystal Arch Installer. Preserves signing,
profiles, AppIDs, and app layout logic. No extra GUI or terminal steps.
Apple trust/2FA/VPN consent remains user-controlled; nothing bypasses it.
MIT-licensed idevice-tools prebuilt executable, download verified before run.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import time
import uuid
from urllib.request import urlopen
import zipfile

TOOL_URL = "https://github.com/jkcoxson/idevice/releases/download/v0.1.68/idevice-tools-linux-v0.1.68.zip"
TOOL_SHA256 = "87132c556db29b4fbaab8315f17fd0aa4eda0eee7c887ee80dad59ded68ce87f"
BUNDLE_ID = "com.kdt.livecontainer.P8EZT3U5N4"


def _home_root():
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home()/".cache"))) / "scarlet-crystal" / "integrated-installer"


class SetupError(RuntimeError):
    pass


def fetch_tool(cache=None, *, opener=None):
    """Use an atomic, SHA-verified extract; never run failed or partial data."""
    cache = Path(cache or _home_root())
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)
    binary = cache / "idevice-tools"
    archive = cache / "idevice-tools-v0.1.68.zip"
    def valid_archive(p):
        if not p.is_file():
            return False
        h = hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                h.update(block)
        return h.hexdigest() == TOOL_SHA256
    if not valid_archive(archive):
        fd, temp_name = tempfile.mkstemp(prefix="idevice-partial-", suffix=".zip", dir=cache)
        os.close(fd)
        temp = Path(temp_name)
        try:
            source = (opener or urlopen)(TOOL_URL, timeout=35)
            with source as response, temp.open("wb") as out:
                shutil.copyfileobj(response, out)
            if not valid_archive(temp):
                raise SetupError("공식 idevice-tools 무결성(SHA-256) 검증 실패")
            os.replace(temp, archive)
        finally:
            temp.unlink(missing_ok=True)
    # Always verify the extracted binary against the signed-off ZIP; never
    # execute an unvalidated cache file after a partial or external overwrite.
    with zipfile.ZipFile(archive) as z:
        entry = z.getinfo("idevice-tools")
        expected_binary_hash = hashlib.sha256(z.read(entry)).hexdigest()
    actual_binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.is_file() else None
    if actual_binary_hash != expected_binary_hash:
        with zipfile.ZipFile(archive) as z:
            member = z.getinfo("idevice-tools")
            if not (1_000_000 < member.file_size < 30_000_000):
                raise SetupError("idevice-tools 실행 파일 크기 검증 실패")
            fd, tmp = tempfile.mkstemp(prefix="bin-", dir=cache)
            os.close(fd)
            try:
                with z.open(member) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.chmod(tmp, 0o700)
                os.replace(tmp, binary)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
    binary.chmod(0o700)
    return binary


def run_cmd(args, *, timeout=30):
    """No shell, no personal pairing payloads or credentials in logs."""
    return subprocess.run([str(x) for x in args],capture_output=True,text=True,
                          timeout=timeout,check=False)


def recognized(result):
    # The upstream CLI returns exit 0 even when pair-verify is rejected.
    return result.returncode == 0 and "the device recognizes this pairing record" in result.stdout


def parse_rp(path):
    try:
        d=plistlib.loads(Path(path).read_bytes())
    except (ValueError, OSError, plistlib.InvalidFileException) as e:
        raise SetupError("RP 기록의 plist 형식 오류") from e
    if not isinstance(d,dict) or not isinstance(d.get("identifier"),str) or not d["identifier"]:
        raise SetupError("RP 기록의 identifier 누락")
    for key in ("public_key","private_key"):
        if not isinstance(d.get(key),bytes) or len(d[key]) != 32:
            raise SetupError("RP 기록의 키 길이 오류")
    return True


class SetupBackend:
    def __init__(self,cache=None,runner=run_cmd,fetcher=fetch_tool):
        self.cache=Path(cache or _home_root())
        self.runner=runner
        self.fetcher=fetcher
        self.binary=None
        self.pair_file=self.cache/"Scarlet-RemotePairing.plist"
        self._hostname_file=self.cache/"pair-host-name"

    def _call(self,*args,timeout=30):
        return self.runner([self.binary,*args],timeout=timeout)

    def prepare(self,progress):
        progress("USB 기기 연결 확인")
        self.binary=self.fetcher(self.cache)
        # If multiple devices are connected do not guess which one to pair.
        # The installed tools can report devices with idevice_id, but do not
        # mistake a disconnected usbmuxd host or stale Wi-Fi peer for success.
        usb=shutil.which("idevice_id")
        if usb:
            listing=self.runner([usb,"-l"],timeout=10)
            if listing.returncode == 0:
                devices=[x.strip() for x in listing.stdout.splitlines() if x.strip()]
                if len(devices)>1:
                    raise SetupError("USB 기기 여러 대 감지: 단일 아이폰만 연결해야 함")
                if not devices:
                    raise SetupError("USB 아이폰 미발견: 케이블과 신뢰 승인을 확인해야 함")
        self.cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.cache.chmod(0o700)
        if not self._hostname_file.is_file():
            self._hostname_file.write_text("ScarletCrystal-"+uuid.uuid4().hex[:12],encoding="ascii")
            self._hostname_file.chmod(0o600)
        host=self._hostname_file.read_text(encoding="ascii").strip()
        if self.pair_file.is_file():
            try:
                parse_rp(self.pair_file)
                test=self._call("remotepairing_lockdown","verify",self.pair_file,host,timeout=45)
                if recognized(test):
                    progress("기존 Remote Pairing 검증 통과 — 재사용")
                    return self.pair_file
            except SetupError:
                pass
        progress("Remote Pairing 생성 중 (기기 신뢰·개발자 모드 확인 필요)")
        new=self.cache/(".Scarlet-RemotePairing-"+uuid.uuid4().hex+".plist")
        try:
            result=self._call("remotepairing_lockdown","pair",host,new,timeout=75)
            if not new.is_file() or new.stat().st_size==0:
                raise SetupError("아이폰 RP 생성 실패 — USB 신뢰 승인·개발자 모드 확인 필요")
            parse_rp(new)
            result=self._call("remotepairing_lockdown","verify",new,host,timeout=50)
            if not recognized(result):
                raise SetupError("아이폰 RP 인증 거절 — 설치를 진행하지 않음")
            # Never delete old pairing; backup atomically after new record VERIFIED.
            if self.pair_file.exists():
                backup=self.cache/("Scarlet-RemotePairing.backup."+str(int(time.time()))+".plist")
                shutil.copy2(self.pair_file,backup)
                backup.chmod(0o600)
            os.replace(new,self.pair_file)
            self.pair_file.chmod(0o600)
            progress("새 Remote Pairing 실기기 검증 통과")
            return self.pair_file
        finally:
            new.unlink(missing_ok=True)

    def stage_pairing(self,progress):
        if not self.binary or not self.pair_file.is_file():
            raise SetupError("검증된 RP 페어링 파일 없음")
        # App Documents/Inbox only; do not overwrite SideStore's *active* pairing.
        listing=self._call("afc","--documents",BUNDLE_ID,"list","/Documents",timeout=15)
        if listing.returncode != 0:
            return False
        self._call("afc","--documents",BUNDLE_ID,"mkdir","/Documents/Inbox",timeout=12)
        dest="/Documents/Inbox/Scarlet-RemotePairing.plist"
        result=self._call("afc","--documents",BUNDLE_ID,"upload",self.pair_file,dest,timeout=30)
        if result.returncode != 0:
            return False
        progress("RP 파일을 Scarlet Crystal에 안전하게 전달함")
        return True


def enable(Window):
    """Attach to original GUI, preserving all its existing methods/callbacks."""
    from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
    from PySide6.QtWidgets import QPushButton, QLabel, QLayout

    class Worker(QThread):
        info=Signal(str)
        done=Signal(bool,str)
        def __init__(self,parent):
            super().__init__(parent)
            self.backend=SetupBackend()
        def run(self):
            try:
                file=self.backend.prepare(self.info.emit)
                self.info.emit("RP 검증 완료 · 기존 서명·설치 과정 연결")
                self.done.emit(True,str(file))
            except (SetupError, OSError, subprocess.TimeoutExpired) as exc:
                self.done.emit(False,str(exc))

    class StageWorker(QThread):
        done=Signal(bool)
        def __init__(self,parent,backend):
            super().__init__(parent)
            self.backend=backend
        def run(self):
            try:
                self.done.emit(self.backend.stage_pairing(lambda _: None))
            except (SetupError, OSError, subprocess.TimeoutExpired):
                self.done.emit(False)

    class Controller(QObject):
        def __init__(self,win):
            super().__init__(win)
            self.win=win
            self.worker=None
            self.backend=None
            self.checks=0
            self.stage_worker=None
            self.button=QPushButton("자동 최초 설정 + 서명·설치",win)
            self.button.setObjectName("scarletIntegratedFirstInstall")
            self.button.setMinimumHeight(34)
            self.state=QLabel("",win)
            self.state.setObjectName("scarletIntegratedSetupState")
            self.state.setWordWrap(True)
            self.state.setVisible(False)
            lay=getattr(win,"actions_row",None)
            if hasattr(lay,"layout") and callable(lay.layout):
                lay=lay.layout()
            if not isinstance(lay,QLayout):
                lay=getattr(win,"content_layout",None)
            if not isinstance(lay,QLayout):
                raise RuntimeError("Scarlet Installer 통합 위치를 찾지 못함")
            lay.addWidget(self.button)
            # Preserve the existing row's height and symmetry: update the
            # existing status text, not a newly inserted log/scroll row.
            self.button.clicked.connect(self.begin)
            self.timer=QTimer(win)
            self.timer.setInterval(1700)
            self.timer.timeout.connect(self.post_install)
        def status(self,value):
            self.state.setText(value)
            existing=getattr(self.win,"state",None)
            if hasattr(existing,"setText"):
                existing.setText(value)
            self.button.setToolTip(value)
            # Avoid secret material in the application's debug log.
            print("[SCARLET_INTEGRATED]",value)
        @Slot()
        def begin(self):
            if self.worker and self.worker.isRunning():return
            if not hasattr(self.win,"both_btn") or not self.win.both_btn.isEnabled():
                self.status("먼저 기존 IPA·인증서 입력을 완료해야 함")
                return
            self.button.setEnabled(False)
            self.worker=Worker(self.win)
            self.worker.info.connect(self.status)
            self.worker.done.connect(self.prepared)
            self.worker.start()
        @Slot(bool,str)
        def prepared(self,success,detail):
            self.button.setEnabled(True)
            if not success:
                self.status("설정 중단: "+detail)
                return
            self.backend=self.worker.backend
            self.status("RP 인증 성공 · 기존 서명/설치 프로세스 시작")
            # Existing GUI's combined signing/provisioning/install pipeline;
            # clicking it preserves the original auth prompt, 2FA and logs.
            self.win.both_btn.click()
            self.checks=0
            self.timer.start()
        @Slot()
        def post_install(self):
            self.checks+=1
            if self.stage_worker is None or not self.stage_worker.isRunning():
                self.stage_worker=StageWorker(self.win,self.backend)
                self.stage_worker.done.connect(self.staged)
                self.stage_worker.start()
            if self.checks>=150:
                self.timer.stop()
                self.status("설치·파일 전달 결과 미확인. 기존 앱·인증서·기록 보존됨")
        @Slot(bool)
        def staged(self,success):
            if success:
                self.timer.stop()
                self.status("RP 전달 완료. Scarlet Crystal 실행 후 FETCH_UDID_PASS 검증 필요")

    old=Window.make_ui
    def patched_make_ui(self,*args,**kwargs):
        result=old(self,*args,**kwargs)
        if not hasattr(self,"_scarlet_integrated_setup"):
            self._scarlet_integrated_setup=Controller(self)
        return result
    Window.make_ui=patched_make_ui
    return Window

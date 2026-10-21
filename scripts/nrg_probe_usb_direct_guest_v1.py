#!/usr/bin/env python3
"""NRG direct USB guest injection (NO native iOS installation or Apple signing).

Safely extracts one known standalone LinuxProbe IPA into the existing NRG
Documents/Applications directory over ifuse USB file sharing. Uses a hidden
staging folder, validates transferred file hashes, and commits by rename.
Never touches an existing .app, LCAppInfo.plist, Madeira, NRG app binaries,
provisioning profiles, certificates, or Apple developer account.
After copying, force-quit and restart NRG to refresh its guest list.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

HOST_ID = "com.kdt.livecontainer.P8EZT3U5N4"
PROBE_ID = "com.example.NRGLinuxProbe"
DEVICE_UDID = "00008160-000569490C600036"
APP_DEST_NAME = PROBE_ID + ".app"
DEFAULT_IPA = Path.home() / "NRG-Tools/NRGLinuxProbe/xtool/NRGLinuxProbe.ipa"
MAX_FILES = 10000
MAX_UNPACKED = 1_000_000_000


def log(message: str) -> None:
    print(message, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_extract(ipa: Path, destination: Path) -> Path:
    """Validate every ZIP member before writing to an isolated temp directory."""
    if not ipa.is_file() or ipa.stat().st_size == 0:
        raise RuntimeError(f"IPA missing or empty: {ipa}")
    with zipfile.ZipFile(ipa) as z:
        entries = z.infolist()
        if len(entries) > MAX_FILES:
            raise RuntimeError("Too many IPA ZIP entries")
        if sum(item.file_size for item in entries) > MAX_UNPACKED:
            raise RuntimeError("Unexpectedly large IPA")
        apps = {
            parts[1] for item in entries
            if len(parts := PurePosixPath(item.filename).parts) >= 3
            and parts[0] == "Payload"
            and parts[1].endswith(".app")
            and parts[2] == "Info.plist"
            and len(parts) == 3
        }
        if len(apps) != 1:
            raise RuntimeError("Expected exactly one Payload/*.app/Info.plist")
        appname = next(iter(apps))
        prefix = f"Payload/{appname}/"
        content_entries = []
        for item in entries:
            raw = item.filename
            p = PurePosixPath(raw)
            if p.is_absolute() or ".." in p.parts or "\\" in raw:
                raise RuntimeError("Unsafe ZIP path")
            # The probe must not include an unrelated second application.
            if raw.startswith("Payload/") and not raw.startswith(prefix):
                raise RuntimeError("Additional app or Payload content found")
            if not raw.startswith(prefix):
                continue
            filemode = item.external_attr >> 16
            if stat.S_IFMT(filemode) == stat.S_IFLNK:
                raise RuntimeError("Symlinks are not supported by this safe installer")
            if item.is_dir():
                content_entries.append((item, True))
            else:
                if stat.S_IFMT(filemode) not in (0, stat.S_IFREG):
                    raise RuntimeError("Unexpected IPA file type")
                content_entries.append((item, False))
        target = destination / "app"
        target.mkdir()
        for item, is_dir in content_entries:
            rel = PurePosixPath(item.filename).relative_to(prefix.rstrip("/"))
            path = target.joinpath(*rel.parts)
            if is_dir:
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also rejects duplicate ZIP member paths.
            with path.open("xb") as output, z.open(item, "r") as source:
                shutil.copyfileobj(source, output, 1024 * 1024)
            mode = item.external_attr >> 16
            if mode & 0o111:
                path.chmod(0o755)

        info_file = target / "Info.plist"
        info = plistlib.loads(info_file.read_bytes())
        if info.get("CFBundleIdentifier") != PROBE_ID:
            raise RuntimeError("IPA Bundle ID is not the isolated Probe")
        exe = info.get("CFBundleExecutable")
        if not isinstance(exe, str) or "/" in exe or exe in ("", ".", ".."):
            raise RuntimeError("Invalid executable name in IPA")
        if not (target / exe).is_file():
            raise RuntimeError("IPA executable absent")
        log("[PASS] IPA validated; expected independent guest Bundle ID")
        return target


@contextmanager
def nrg_documents(udid: str, host_id: str, offline_docs: Path | None):
    if offline_docs is not None:
        if not offline_docs.is_dir():
            raise RuntimeError("Offline test documents directory missing")
        yield offline_docs
        return
    if not shutil.which("ifuse"):
        raise RuntimeError("ifuse missing; install with pacman")
    if not shutil.which("mountpoint"):
        raise RuntimeError("mountpoint missing")
    apps = subprocess.run(
        ["ifuse", "--list-apps", "--udid", udid],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True, timeout=20, check=False
    )
    if apps.returncode != 0:
        raise RuntimeError("Could not list iPhone file-sharing apps; check USB trust")
    if host_id not in apps.stdout:
        raise RuntimeError("Original NRG file-sharing container not found")
    log("[PASS] Original NRG confirmed on USB")

    with tempfile.TemporaryDirectory(prefix="nrg-ifuse-") as mount:
        mount_dir = Path(mount)
        operation = subprocess.run(
            ["ifuse", "--documents", host_id, "--udid", udid, str(mount_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, timeout=22, check=False,
        )
        if operation.returncode != 0:
            raise RuntimeError("ifuse could not mount NRG Documents")
        try:
            for _ in range(30):
                if subprocess.run(["mountpoint", "-q", str(mount_dir)], check=False).returncode == 0:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("ifuse mount did not become active")
            log("[PASS] USB mount of NRG Documents ready")
            yield mount_dir
        finally:
            if subprocess.run(["mountpoint", "-q", str(mount_dir)], check=False).returncode == 0:
                unmount = shutil.which("fusermount3") or shutil.which("fusermount")
                if unmount:
                    subprocess.run([unmount, "-u", str(mount_dir)], check=False, timeout=20)
                else:
                    log("[WARN] FUSE unmount utility missing; manually unmount NRG mount")


def preexisting_guest_conflicts(apps_path: Path) -> list[str]:
    conflicts: list[str] = []
    for app in apps_path.iterdir():
        if not app.is_dir() or not app.name.endswith(".app"):
            continue
        # Fail closed if a guest is present with a duplicate Bundle ID under
        # a different directory (including a custom folder name).
        info_path = app / "Info.plist"
        try:
            info = plistlib.loads(info_path.read_bytes())
            if info.get("CFBundleIdentifier") == PROBE_ID:
                conflicts.append(app.name)
        except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
            # No interference with other existing guest app; never modify it.
            continue
    return conflicts


def check_copy(source: Path, target: Path) -> int:
    files = 0
    for root, _dirs, names in os.walk(source):
        folder = Path(root)
        for filename in names:
            rel = (folder / filename).relative_to(source)
            original = folder / filename
            device_file = target / rel
            if not device_file.is_file():
                raise RuntimeError(f"USB transfer missing expected file: {rel}")
            if original.stat().st_size != device_file.stat().st_size:
                raise RuntimeError(f"USB transfer size mismatch: {rel}")
            if sha256(original) != sha256(device_file):
                raise RuntimeError(f"USB transfer checksum mismatch: {rel}")
            files += 1
    return files


def copy_to_device(local_app: Path, documents: Path) -> None:
    apps = documents / "Applications"
    apps.mkdir(parents=True, exist_ok=True)
    final = apps / APP_DEST_NAME
    if final.exists() or final.is_symlink():
        raise RuntimeError(f"Existing guest present: {APP_DEST_NAME}; refusing overwrite")
    duplicates = preexisting_guest_conflicts(apps)
    if duplicates:
        raise RuntimeError("Probe Bundle ID already registered under another name; refusing duplicate")
    stage = apps / (".nrg-probe-staging-" + uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    committed = False
    try:
        for root, dirs, filenames in os.walk(local_app):
            here = Path(root)
            rel = here.relative_to(local_app)
            device_folder = stage / rel
            device_folder.mkdir(parents=True, exist_ok=True)
            for dirname in dirs:
                (device_folder / dirname).mkdir(exist_ok=True)
            for name in filenames:
                source = here / name
                destination = device_folder / name
                # Use no metadata copying; AFC cannot guarantee POSIX xattrs
                # or chmod. LiveContainer patches/signs guest on first launch.
                with source.open("rb") as read, destination.open("xb") as write:
                    shutil.copyfileobj(read, write, 1024 * 1024)
                if os.access(source, os.X_OK):
                    try:
                        destination.chmod(0o755)
                    except OSError:
                        log("[WARN] AFC did not support chmod; guest launch may require iOS-side patch")
        files = check_copy(local_app, stage)
        log(f"[PASS] Guest files copied and SHA-256 verified: {files}")
        if final.exists() or preexisting_guest_conflicts(apps):
            raise RuntimeError("Existing guest appeared during upload; refusing commit")
        # Atomic commit: staging directory is not .app, so no partial app
        # can be indexed by LiveContainer even if NRG starts mid-transfer.
        stage.rename(final)
        committed = True
        log(f"[PASS] GUEST_REGISTERED_AS=Documents/Applications/{APP_DEST_NAME}")
        log("HOST_APP_UNCHANGED=YES")
        log("NRG_CERTIFICATE_UNCHANGED=YES")
        log("NEXT=Force close NRG from app switcher, reopen, and select NRGLinuxProbe")
    finally:
        if not committed and stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, default=DEFAULT_IPA)
    parser.add_argument("--udid", default=DEVICE_UDID)
    parser.add_argument("--host", default=HOST_ID)
    parser.add_argument(
        "--offline-documents", type=Path, default=None,
        help="For local automated tests only: skip USB and use a disposable Documents directory"
    )
    opts = parser.parse_args()
    if opts.udid != DEVICE_UDID or opts.host != HOST_ID:
        parser.error("Unexpected iPhone or host ID; refusing unverified target")
    with tempfile.TemporaryDirectory(prefix="nrg-probe-validate-") as temporary:
        prepared = safe_extract(opts.ipa, Path(temporary))
        with nrg_documents(opts.udid, opts.host, opts.offline_documents) as docs:
            copy_to_device(prepared, docs)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        raise SystemExit(1)

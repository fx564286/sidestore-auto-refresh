#!/usr/bin/env python3
"""Read-only NRG signing preflight: local P12, mobileprovision and Apple portal cert.

It never exports private keys, prints passwords, signs apps, installs IPAs,
creates app IDs, or revokes certificates. Optional --remote uses xtool
'ds certificates list', which only queries existing certificates.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import zipfile

TEAM = "P8EZT3U5N4"
BUNDLE = "com.example.NRGLinuxProbe"
BASE = Path.home()
DEFAULT_P12 = BASE / ".sideinstaller" / f"recovery-v13-{TEAM}" / "NRG-existing-signing-identity-v16.p12"
EXCLUDE = {".git", ".build", "node_modules", "DerivedData", ".cache", "venv", ".venv", "Pods"}
SEARCH_DIRS = (
    BASE / ".sideinstaller",
    BASE / "NRG-Tools",
    BASE / "다운로드" / "NRG-IPA",
    BASE / "Downloads" / "NRG-IPA",
)


def proc(command: list[str], input_data: bytes | None = None, timeout: int = 20) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, input=input_data, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(command, 127, b"", b"")


def get_certificate(p12: Path, password: Path) -> tuple[bytes | None, str | None, bool | None]:
    if not (p12.is_file() and password.is_file()):
        return None, None, None
    pem = b""
    # OpenSSL 3 may need legacy algorithms; retry without -legacy if not needed.
    for legacy in ((), ("-legacy",)):
        args = ["openssl", "pkcs12", "-in", str(p12), "-clcerts",
                "-nokeys", "-passin", "file:" + str(password), *legacy]
        result = proc(args)
        if result.returncode == 0 and b"BEGIN CERTIFICATE" in result.stdout:
            pem = result.stdout
            break
    if not pem:
        return None, None, None
    der = proc(["openssl", "x509", "-inform", "PEM", "-outform", "DER"], pem)
    serial = proc(["openssl", "x509", "-inform", "PEM", "-serial", "-noout"], pem)
    valid = proc(["openssl", "x509", "-inform", "PEM", "-checkend", "0", "-noout"], pem)
    found = re.search(rb"serial=([0-9A-Fa-f]+)", serial.stdout, re.IGNORECASE)
    serial_number = found.group(1).decode("ascii").upper().lstrip("0") if found else None
    return (der.stdout if der.returncode == 0 else None,
            serial_number, valid.returncode == 0)


def read_profile(raw: bytes) -> dict | None:
    if len(raw) > 8_000_000 or len(raw) < 20:
        return None
    try:
        val = plistlib.loads(raw)
        if isinstance(val, dict):
            return val
    except (ValueError, TypeError, OverflowError, plistlib.InvalidFileException):
        pass
    for option in ("cms", "smime"):
        decoded = proc(["openssl", option, "-verify", "-inform", "DER", "-noverify"], raw)
        if decoded.returncode != 0:
            continue
        try:
            val = plistlib.loads(decoded.stdout)
            if isinstance(val, dict):
                return val
        except (ValueError, TypeError, OverflowError, plistlib.InvalidFileException):
            pass
    return None


def candidate_profiles():
    scanned = 0
    seen: set[str] = set()
    for root in SEARCH_DIRS:
        if not root.is_dir():
            continue
        for current, folders, files in os.walk(root):
            rel_depth = len(Path(current).relative_to(root).parts)
            folders[:] = [x for x in folders if x not in EXCLUDE] if rel_depth < 6 else []
            for name in files:
                scanned += 1
                if scanned > 15000:
                    return
                lower = name.lower()
                if not (lower.endswith(".mobileprovision")
                        or lower.endswith(".provisionprofile")
                        or lower == "embedded.mobileprovision"):
                    continue
                path = Path(current) / name
                try:
                    key = str(path.resolve())
                    if key not in seen and path.stat().st_size < 8_000_000:
                        seen.add(key)
                        yield str(path), path.read_bytes()
                except (OSError, PermissionError):
                    continue
    # Inspect profiles packaged inside recent IPA archives, never unpack apps.
    ipa_paths = []
    for root in SEARCH_DIRS:
        if not root.is_dir():
            continue
        for name in ("*.ipa", "NRG-*.ipa", "NRGLinuxProbe.ipa"):
            ipa_paths += list(root.glob(name))
    probe = BASE / "NRG-Tools" / "NRGLinuxProbe" / "xtool" / "NRGLinuxProbe.ipa"
    ipa_paths.append(probe)
    existing = [p for p in set(ipa_paths) if p.is_file()]
    existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in existing[:35]:
        try:
            with zipfile.ZipFile(path) as z:
                for item in z.infolist():
                    if item.filename.endswith("/embedded.mobileprovision") and item.file_size <= 8_000_000:
                        yield path.name + "::profile", z.read(item)
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
            continue


def profile_matches(info: dict, certificate: bytes | None, team: str, bundle: str, udid: str):
    entitlements = info.get("Entitlements", {})
    if not isinstance(entitlements, dict):
        return False, "INVALID_ENTITLEMENTS"
    teams = info.get("TeamIdentifier", [])
    app_id = str(entitlements.get("application-identifier",
                entitlements.get("com.apple.application-identifier", "")))
    team_match = team in teams or app_id.startswith(team + ".")
    app_match = fnmatch.fnmatchcase(f"{team}.{bundle}", app_id)
    date = info.get("ExpirationDate")
    if isinstance(date, datetime):
        expiry_utc = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
        expiry_ok = expiry_utc > datetime.now(timezone.utc)
    else:
        expiry_ok = False
    devices = info.get("ProvisionedDevices", [])
    device_ok = udid in devices if udid else False
    certs = info.get("DeveloperCertificates", [])
    cert_ok = bool(certificate) and isinstance(certs, list) and any(
        isinstance(c, bytes) and hashlib.sha256(c).digest() == hashlib.sha256(certificate).digest()
        for c in certs
    )
    if team_match and app_match and expiry_ok and device_ok and cert_ok:
        return True, "PASS"
    return False, f"team={int(team_match)} app={int(app_match)} expiry={int(expiry_ok)} device={int(device_ok)} cert={int(cert_ok)}"


def get_remote_cert_state(xtool: Path, serial: str | None) -> str:
    if not serial:
        return "UNKNOWN_NO_LOCAL_SERIAL"
    if not xtool.is_file():
        return "UNKNOWN_NO_XTOOL"
    if os.environ.get("NRG_XTOOL_SIDESTORE_AUTH") != "1" or not os.environ.get("NRG_XTOOL_COMPAT_STATE", "").startswith("/"):
        return "SKIPPED_NEED_ISOLATED_AUTH"
    result = proc([str(xtool), "ds", "certificates", "list"], timeout=45)
    if result.returncode != 0:
        return "UNKNOWN_REMOTE_QUERY_FAILED"
    server_serials = re.findall(rb"^\s*serial number:\s*([0-9a-fA-F]+)", result.stdout, re.MULTILINE)
    normalized = {s.decode("ascii").upper().lstrip("0") for s in server_serials}
    return "YES" if serial in normalized else "NO"


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--p12", type=Path, default=DEFAULT_P12)
    a.add_argument("--password-file", type=Path)
    a.add_argument("--team", default=TEAM)
    a.add_argument("--bundle", default=BUNDLE)
    a.add_argument("--udid", default="")
    a.add_argument("--remote", action="store_true", help="read-only Apple certificate list")
    a.add_argument("--xtool", type=Path, default=BASE / "NRG-Tools/xtool-nrg-auth-v1/.build/release/xtool")
    args = a.parse_args()
    p12 = args.p12.expanduser()
    password = (args.password_file.expanduser() if args.password_file else p12.with_suffix(".password"))
    print("=== EXISTING SIGNING IDENTITY ===")
    print("P12_EXISTS=" + ("YES" if p12.is_file() else "NO"))
    print("P12_PASSWORD_FILE_EXISTS=" + ("YES" if password.is_file() else "NO"))
    cert, serial, valid = get_certificate(p12, password)
    print("P12_CERT_PARSE=" + ("OK" if cert else "NOT_VERIFIED"))
    print("P12_CERT_NOT_EXPIRED=" + ("YES" if valid is True else "NO" if valid is False else "UNKNOWN"))
    print("=== PROFILE COMPATIBILITY (LOCAL, READ ONLY) ===")
    count = matched = team_profiles = 0
    for source, data in candidate_profiles():
        info = read_profile(data)
        if not info:
            continue
        count += 1
        if args.team in info.get("TeamIdentifier", []):
            team_profiles += 1
        ok, _details = profile_matches(info, cert, args.team, args.bundle, args.udid)
        if ok:
            matched += 1
            print("MATCHING_PROFILE=FOUND")  # never expose profile contents or path
    print("PROFILES_PARSED=" + str(count))
    print("TEAM_PROFILES=" + str(team_profiles))
    print("PROFILES_MATCHING_CERT_BUNDLE_DEVICE=" + str(matched))
    if args.remote:
        print("=== APPLE CERTIFICATE REGISTRY (READ ONLY) ===")
        print("P12_CERT_REGISTERED=" + get_remote_cert_state(args.xtool.expanduser(), serial))
    if matched:
        print("SIGNING_PREFLIGHT=PROFILE_AVAILABLE")
    else:
        print("SIGNING_PREFLIGHT=NOT_READY_DO_NOT_INSTALL")
    print("NO_SIGNING_OR_CERTIFICATE_CHANGES_PERFORMED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

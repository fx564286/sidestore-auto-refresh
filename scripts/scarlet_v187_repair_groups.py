#!/usr/bin/env python3
"""Repair existing Scarlet V187 App Group associations and issue candidate profiles.

Only acts on the exact existing Apple Team, App Group, and four App IDs.
Does NOT revoke certificates, create/delete App IDs, install apps, or touch the IPA.
Local Apple ID prompts use a pinned, public SideInstaller SRP login backend.
"""
import datetime as dt
import getpass
import hashlib
import importlib.util
import os
from pathlib import Path
import plistlib
import re
import subprocess
import ssl
import socket
import sys
import urllib.request

TEAM = "P8EZT3U5N4"
GROUP = "group.com.SideStore.SideStore.P8EZT3U5N4"
BUNDLES = ["com.kdt.livecontainer.P8EZT3U5N4" + suffix for suffix in
           ("", ".LiveProcess", ".ShareExtension", ".LaunchAppExtension")]
UPSTREAM_COMMIT = "9ac886af5277dfc6bdecc6f9b21e53f8a45ad746"
UPSTREAM_URL = ("https://raw.githubusercontent.com/FrizzleM/SideInstaller/"
                + UPSTREAM_COMMIT + "/ish/sideinstaller.py")
HOME = Path.home()
BASE = HOME / ".local/share/scarlet-crystal"
BACKUP = BASE / "recovery-backup"
SIGNING = BASE / "signing"
WORK = BASE / "v187"
BACKEND_FILE = WORK / "vendor" / ("sideinstaller-" + UPSTREAM_COMMIT + ".py")

def stop(message):
    raise RuntimeError("[STOP] " + message)

def decode_profile(data):
    p = subprocess.run(["openssl", "cms", "-verify", "-inform", "DER", "-noverify"],
                       input=data, capture_output=True)
    if p.returncode:
        stop("PROFILE_CMS_INVALID")
    return plistlib.loads(p.stdout)

def saved_certificate():
    p12 = SIGNING / "existing-identity.p12"
    password_file = SIGNING / "existing-identity.password"
    if not p12.is_file() or not password_file.is_file():
        stop("P12_OR_PASSWORD_FILE_MISSING")
    p = subprocess.run(
        ["openssl", "pkcs12", "-in", str(p12), "-clcerts", "-nokeys",
         "-passin", "file:" + str(password_file)], capture_output=True)
    if p.returncode:
        stop("P12_INVALID")
    cert = subprocess.run(["openssl", "x509", "-outform", "DER"],
                          input=p.stdout, capture_output=True)
    if cert.returncode:
        stop("P12_CERT_EXTRACT_FAILED")
    return hashlib.sha256(cert.stdout).digest()

def load_backend():
    BACKEND_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BACKEND_FILE.parent, 0o700)
    if not BACKEND_FILE.is_file():
        with urllib.request.urlopen(UPSTREAM_URL, timeout=40) as r:
            source = r.read()
        if len(source) < 50000 or b"class DeveloperSession" not in source:
            stop("UPSTREAM_SOURCE_INVALID")
        BACKEND_FILE.write_bytes(source)
        os.chmod(BACKEND_FILE, 0o600)
    spec = importlib.util.spec_from_file_location("scarlet_apple_backend", BACKEND_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def tls_preflight():
    """Check certificate validation before prompting for any Apple credentials."""
    hosts = (
        "new.ani.sidestore.io", "mac-ani.jkcoxson.com",
        "ani.iloader.app", "ani3.stikstore.app",
        "ani.jkcoxson.com", "ani2.stikstore.app",
    )
    paths = ssl.get_default_verify_paths()
    print("[TLS_CA] file=", paths.cafile, "dir=", paths.capath, flush=True)
    ctx = ssl.create_default_context()
    verified = []
    for host in hosts:
        try:
            with socket.create_connection((host, 443), timeout=8) as sock:
                with ctx.wrap_socket(sock, server_hostname=host):
                    print("[TLS_PASS]", host, flush=True)
                    verified.append(host)
        except (OSError, ssl.SSLError) as exc:
            print("[TLS_FAIL]", host, str(exc)[:220], flush=True)
    if not verified:
        stop("ALL_ANISETTE_TLS_UNTRUSTED; CHECK_CA_STORE_OR_HTTPS_INTERCEPTION")
    return verified

def main():
    os.umask(0o077)
    print("[V187] Renew existing App Group profiles; do not delete old app or cert")
    old = BACKUP / "profile-0.mobileprovision"
    if not old.is_file():
        stop("OLD_PROFILE_MISSING")
    old_devices = set(decode_profile(old.read_bytes()).get("ProvisionedDevices", []))
    if not old_devices:
        stop("OLD_PROFILE_DEVICE_IDS_MISSING")
    cert_hash = saved_certificate()
    print("[PASS] OLD_CERT_AND_DEVICE_REFERENCE")
    api = load_backend()

    email = input("Apple ID email (local): ").strip()
    if "@" not in email:
        stop("APPLE_ID_REQUIRED")
    password = getpass.getpass("Apple ID password (hidden, local): ")
    if not password:
        stop("APPLE_PASSWORD_REQUIRED")
    state = HOME / ".local/state/scarlet-v187-apple"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    anisette, gs = api.connect_anisette(api.FALLBACK_ANISETTE, str(state / "anisette.json"))
    account = api.AppleAccount(email, gs, anisette)
    def ask_code(prompt):
        return re.sub(r"\D", "", getpass.getpass(prompt + " (hidden): "))
    try:
        account.login(password, ask_code)
    finally:
        password = None
    token, adsid = account.app_token("xcode.auth")
    session = api.DeveloperSession(account, token, adsid)
    team = next((t for t in session.call("listTeams", key="teams", device_type="")
                 if t.get("teamId") == TEAM), None)
    if not team:
        stop("EXISTING_TEAM_INACCESSIBLE")
    print("[PASS] TEAM", TEAM, "TYPE", team.get("type", "unknown"))

    listed = session.call("listAppIds", {"teamId": TEAM})
    apps = {a.get("identifier"): a for a in listed.get("appIds", [])}
    if any(bundle not in apps for bundle in BUNDLES):
        for bundle in BUNDLES:
            if bundle not in apps:
                print("[MISSING_APP_ID]", bundle)
        stop("APP_IDS_MISSING; NO_MUTATIONS")
    print("[PASS] FOUR_EXISTING_APP_IDS")

    groups = session.call("listApplicationGroups", {"teamId": TEAM},
                          key="applicationGroupList")
    group = next((g for g in groups if g.get("identifier") == GROUP), None)
    if not group or not group.get("applicationGroup"):
        stop("EXISTING_APP_GROUP_INACCESSIBLE; NO_NEW_GROUP_CREATED")
    print("[PASS] EXISTING_GROUP", GROUP)

    for bundle in BUNDLES:
        app = apps[bundle]
        if not app.get("features", {}).get("APG3427HIY"):
            app = session.call("updateAppId",
                               {"teamId": TEAM, "appIdId": app["appIdId"],
                                "APG3427HIY": True}, key="appId")
            apps[bundle] = app
            print("[PASS] GROUP_CAPABILITY_ENABLED", bundle)
        session.call("assignApplicationGroupToAppId",
                     {"teamId": TEAM, "appIdId": app["appIdId"],
                      "applicationGroups": group["applicationGroup"]})
        print("[PASS] GROUP_ASSIGNED", bundle)

    out = WORK / ("candidate-profiles-" +
                  dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for bundle in BUNDLES:
        result = session.call("downloadTeamProvisioningProfile",
                              {"teamId": TEAM, "appIdId": apps[bundle]["appIdId"]},
                              key="provisioningProfile")
        raw = bytes(result["encodedProfile"])
        plist = decode_profile(raw)
        ent = plist.get("Entitlements", {})
        if ent.get("application-identifier") != TEAM + "." + bundle:
            stop("APP_ID_MISMATCH " + bundle)
        if GROUP not in ent.get("com.apple.security.application-groups", []):
            stop("GROUP_NOT_GRANTED_BY_APPLE " + bundle)
        if not ent.get("get-task-allow", False):
            stop("PROFILE_IS_NOT_DEVELOPMENT " + bundle)
        expiry = plist.get("ExpirationDate")
        if expiry is None or expiry.replace(tzinfo=dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc):
            stop("PROFILE_EXPIRED " + bundle)
        if not old_devices.issubset(set(plist.get("ProvisionedDevices", []))):
            stop("ORIGINAL_DEVICE_NOT_AUTHORIZED " + bundle)
        digests = {hashlib.sha256(bytes(cert)).digest()
                   for cert in plist.get("DeveloperCertificates", [])}
        if cert_hash not in digests:
            stop("ORIGINAL_P12_CERT_NOT_AUTHORIZED " + bundle)
        name = "Main" if bundle == BUNDLES[0] else bundle.rsplit(".", 1)[-1]
        dest = out / (name + ".mobileprovision")
        dest.write_bytes(raw)
        os.chmod(dest, 0o600)
        print("[PASS] PROFILE_VALID", name, "expires", expiry)
    print("[PASS] FOUR_VALID_PROFILES", out)
    print("[NEXT] Existing-ID bundle rewrite and rcodesign; no IPA installed")

if __name__ == "__main__":
    try:
        tls_preflight()
        if "--tls-check" not in sys.argv:
            main()
    except KeyboardInterrupt:
        print("\n[STOP] CANCELLED")
        sys.exit(130)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

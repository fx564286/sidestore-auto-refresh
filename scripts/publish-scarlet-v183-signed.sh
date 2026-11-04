#!/usr/bin/env bash
# Scarlet Crystal V183 signed IPA → GitHub Release (existing local signed output).
# Never imports P12/private keys, alters profiles, signs, reinstalls or deletes user data.
set -Eeuo pipefail
umask 077

repo="fx564286/sidestore-auto-refresh"
release="scarlet-v183-usb-signed-20261104"
expected="dc9fbd0b0d20d7d469040bca573949a68be9162354d92e1f2de62c75a8b1afef"
source_path="$HOME/.local/state/scarlet-crystal-installer/upstream-v5/20261104-212534-581395/Scarlet-Crystal-V181-STAGED-UNSIGNED-FORCE-SIGNED-20261104-212538-454196.ipa"

for tool in python3 openssl sha256sum gh; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "[STOP] Missing command: $tool"
    if [[ "$tool" == gh ]]; then
      echo "[INFO] CachyOS/Arch: sudo pacman -S --needed github-cli"
      echo "[INFO] Then: gh auth login"
    fi
    exit 2
  fi
done

[[ -s "$source_path" && ! -L "$source_path" ]] || {
  echo "[STOP] Local signed output is absent: $source_path"
  exit 2
}
actual="$(sha256sum "$source_path" | awk '{print $1}')"
[[ "$actual" == "$expected" ]] || {
  echo "[STOP] The local signed IPA SHA256 differs from the successful USB install log."
  echo "[EXPECTED] $expected"
  echo "[ACTUAL]   $actual"
  exit 2
}

python3 - "$source_path" <<'PY'
import datetime,plistlib,subprocess,sys,zipfile
p=sys.argv[1]
base="com.kdt.livecontainer.P8EZT3U5N4"
want={base} | {base+"."+v for v in ("LiveProcess","ShareExtension","LaunchAppExtension")}
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None, "corrupted ZIP"
    files=set(z.namelist())
    plist_names=sorted(f for f in files if f=="Payload/LiveContainer.app/Info.plist" or
        (f.startswith("Payload/LiveContainer.app/PlugIns/") and f.endswith(".appex/Info.plist")))
    assert len(plist_names)==4, "expected host and 3 extensions"
    found=set()
    now=datetime.datetime.now(datetime.timezone.utc)
    for infop in plist_names:
        info=plistlib.loads(z.read(infop))
        bundle=info["CFBundleIdentifier"]
        assert bundle in want and bundle not in found, "wrong or duplicate bundle"
        found.add(bundle)
        profile=infop.removesuffix("Info.plist")+"embedded.mobileprovision"
        assert profile in files, "missing embedded provisioning profile"
        result=subprocess.run(["openssl","cms","-verify","-inform","DER","-noverify"],
             input=z.read(profile),capture_output=True)
        assert result.returncode==0, "bad embedded provisioning CMS"
        prof=plistlib.loads(result.stdout)
        ent=prof.get("Entitlements",{})
        appid=ent.get("application-identifier") or ent.get("com.apple.application-identifier")
        assert appid=="P8EZT3U5N4."+bundle, "provisioning Bundle ID mismatch"
        assert "P8EZT3U5N4" in prof.get("TeamIdentifier",[]), "Apple Team mismatch"
        expiry=prof["ExpirationDate"].replace(tzinfo=datetime.timezone.utc)
        assert expiry>now, "embedded provisioning profile expired"
    assert found==want
print("[PASS] V183 local IPA: ZIP, 4 bundle IDs, Apple profile signatures, Team and expiry")
print("[WARNING] Previous force-sign removed App Group and memory grants.")
print("[WARNING] GitHub public release embeds Apple's device provisioning profiles.")
PY

gh auth status >/dev/null || {
  echo "[STOP] Sign in once with 'gh auth login' on this PC."
  exit 2
}
gh release view "$release" --repo "$repo" >/dev/null || {
  echo "[STOP] Expected V183 signed release is unavailable."
  exit 2
}

temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
asset="$temp/Scarlet-Crystal-V183-SIGNED.ipa"
cp -- "$source_path" "$asset"
echo "[UPLOAD] Existing locally signed V183 → GitHub"
gh release upload "$release" "$asset" --repo "$repo"
echo "[PASS] SHA256: $expected"
echo "[PASS] Public GitHub IPA:"
echo "https://github.com/$repo/releases/download/$release/Scarlet-Crystal-V183-SIGNED.ipa"
echo "[NOTE] Verify Apple App Group functionality on-device before replacing a healthy app."

#!/usr/bin/env bash
# V48 widgetless: only upgrade the existing app; never create new App IDs.
set -Eeuo pipefail
REPO=fx564286/sidestore-auto-refresh
BRANCH=fix/nrg-v48-madeira-runtime-20261018
R=${1:?usage: bash nrg_v48_widgetless_install_oneclick.sh <successful-V48-run-id>}
B=com.kdt.livecontainer.P8EZT3U5N4
TEAM=P8EZT3U5N4
U=00008160-000569490C600036
C="$HOME/.sideinstaller/recovery-v13-P8EZT3U5N4"
Z="$HOME/.sideinstaller/bin/zsign"
for x in gh openssl python3 ideviceinstaller idevice_id; do
  command -v "$x" >/dev/null || { echo "[ERROR] missing $x" >&2; exit 1; }
done
[[ -x "$Z" ]] || { echo "[ERROR] missing signer: $Z" >&2; exit 1; }
[[ -s "$C/renewed-key.pem" && -s "$C/renewed-cert.pem" ]] || { echo '[ERROR] signing key/certificate missing' >&2; exit 1; }
[[ "$R" =~ ^[0-9]+$ ]] || { echo '[ERROR] invalid run ID' >&2; exit 1; }
[[ $(gh run view "$R" -R "$REPO" --json conclusion,headBranch -q '[.conclusion,.headBranch] | join("|")') == "success|$BRANCH" ]] || {
  echo '[ERROR] run is not a successful V48 branch build' >&2; exit 1;
}
idevice_id -l | grep -Fxq "$U" || { echo '[ERROR] iPhone is not connected' >&2; exit 1; }
# Do not switch the Bundle ID or uninstall the current installation.
ideviceinstaller -u "$U" list | grep -F "$B" >/dev/null || {
  echo '[ERROR] existing NRG app ID not found: refusing fresh install' >&2; exit 1;
}
mkdir -p "$HOME/다운로드"
D=$(mktemp -d "$HOME/다운로드/NRG-V48-4ID.XXXXXXXX")
I="$D/widgetless.ipa"
S="$D/NRG-V48-WIDGETLESS-SIGNED.ipa"
P="$D/profiles.txt"
gh run download "$R" -R "$REPO" -n LiveContainer-SideStore-v3.0.3-rc-IPA -D "$D"
I=$(find "$D" -type f -name '*.ipa' ! -name '*SIGNED*' -print -quit)
[[ -n "$I" ]] || { echo '[ERROR] IPA not downloaded' >&2; exit 1; }
export I C B U TEAM P
python3 - <<'PY'
import datetime,glob,os,plistlib,subprocess,sys,zipfile
ipa, directory, bundle, team = [os.environ[k] for k in ('I','C','B','TEAM')]
ids = [bundle] + [bundle + '.' + suffix for suffix in ('LiveProcess','ShareExtension','LaunchAppExtension')]
with zipfile.ZipFile(ipa) as z:
    names=z.namelist()
    info=[n for n in names if n.startswith('Payload/') and n.count('/')==2 and n.endswith('.app/Info.plist')]
    if len(info)!=1: sys.exit('[ERROR] invalid host app layout')
    original=plistlib.loads(z.read(info[0]))['CFBundleIdentifier']
    if original not in ('com.kdt.livecontainer',bundle): sys.exit('[ERROR] unexpected candidate bundle ID '+original)
    exts={n:plistlib.loads(z.read(n))['CFBundleIdentifier'] for n in names if n.startswith(info[0].removesuffix('Info.plist')+'PlugIns/') and n.endswith('.appex/Info.plist')}
    expect={'com.kdt.livecontainer.'+suffix for suffix in ('LiveProcess','ShareExtension','LaunchAppExtension')}
    if len(exts)!=3 or set(exts.values())!=expect: sys.exit('[ERROR] IPA does not contain exactly 3 expected extensions: '+repr(exts))
    if any('/LiveWidgetExtension.appex/' in n or '/AltWidgetExtension.appex/' in n for n in names):
        sys.exit('[ERROR] widget is still packaged; refusing to install')
    print('[PASS] unsigned IPA: host + 3 required extensions; no widget')
now=datetime.datetime.now(datetime.timezone.utc)
profiles={}
for file in glob.glob(os.path.join(directory,'*.mobileprovision')):
    p=subprocess.run(['openssl','cms','-verify','-inform','DER','-noverify','-in',file],capture_output=True)
    if p.returncode: continue
    try: d=plistlib.loads(p.stdout)
    except Exception: continue
    ent=d.get('Entitlements',{})
    aid=ent.get('application-identifier',ent.get('com.apple.application-identifier',''))
    ident=aid.removeprefix(team+'.')
    expiry=d.get('ExpirationDate')
    if ident not in ids or aid!=team+'.'+ident: continue
    if team not in d.get('TeamIdentifier',[]) or os.environ['U'] not in d.get('ProvisionedDevices',[]):continue
    if expiry is not None and expiry.replace(tzinfo=datetime.timezone.utc)<=now: continue
    if ent.get('get-task-allow') is not True:
        print('[WARN] profile lacks get-task-allow:',ident,file=sys.stderr)
        continue
    profiles.setdefault(ident,file)
missing=set(ids)-set(profiles)
if missing: sys.exit('[ERROR] missing/expired development profiles (will not modify app): '+repr(sorted(missing)))
with open(os.environ['P'],'w') as f:
    for ident in ids:
        f.write(profiles[ident]+'\n')
# NRG_V47_MEMORY_PROFILE_AUDIT: only an Apple-signed entitlement grant
# can raise an iOS guest's memory allowance. Never claim unlimited memory.
memory_key='com.apple.developer.kernel.increased-memory-limit'
granted=0
for ident in ids:
    proc=subprocess.run(['openssl','cms','-verify','-inform','DER','-noverify','-in',profiles[ident]],capture_output=True)
    if proc.returncode: sys.exit('[ERROR] previously selected profile is unreadable')
    data=plistlib.loads(proc.stdout)
    active=data.get('Entitlements',{}).get(memory_key) is True
    granted+=int(active)
    print('[NRG_V47_MEMORY_PROFILE] bundle='+ident+' increased_memory_granted='+str(active).lower())
if granted==0:
    print('[WARN] No profile grants Increased Memory Limit; do not claim iOS memory cap was raised')
else:
    print('[INFO] Increased Memory Limit granted in '+str(granted)+'/4 profiles; device jetsam limits remain')
print('[PASS] found 4 compatible development profiles; no LiveWidget profile required')
PY
mapfile -t PROFILES < "$P"
[[ ${#PROFILES[@]} -eq 4 ]] || { echo '[ERROR] profile count not 4' >&2; exit 1; }
ARGS=()
for F in "${PROFILES[@]}"; do ARGS+=(-m "$F"); done
"$Z" -f -k "$C/renewed-key.pem" -c "$C/renewed-cert.pem" "${ARGS[@]}" -b "$B" -o "$S" "$I"
export S
python3 - <<'PY'
import os,plistlib,sys,zipfile
with zipfile.ZipFile(os.environ['S']) as z:
    names=z.namelist()
    hosts=[n for n in names if n.startswith('Payload/') and n.count('/')==2 and n.endswith('.app/Info.plist')]
    if len(hosts)!=1 or plistlib.loads(z.read(hosts[0]))['CFBundleIdentifier']!=os.environ['B']:
        sys.exit('[ERROR] signed host bundle changed unexpectedly')
    exts=[plistlib.loads(z.read(n))['CFBundleIdentifier'] for n in names if n.startswith(hosts[0].removesuffix('Info.plist')+'PlugIns/') and n.endswith('.appex/Info.plist')]
    expected={os.environ['B']+'.'+x for x in ('LiveProcess','ShareExtension','LaunchAppExtension')}
    if len(exts)!=3 or set(exts)!=expected:
        sys.exit('[ERROR] signed extension bundle IDs mismatch: '+repr(exts))
    if any('/LiveWidgetExtension.appex/' in n or '/AltWidgetExtension.appex/' in n for n in names):
        sys.exit('[ERROR] widget still present after signing')
    print('[PASS] signed host and 3 extensions have expected bundle IDs')
PY
ideviceinstaller -u "$U" upgrade "$S"
ideviceinstaller -u "$U" list | grep -F "$B"
echo '[PASS] upgraded without uninstalling; previous data preserved by same app ID'

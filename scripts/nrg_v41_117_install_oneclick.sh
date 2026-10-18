#!/usr/bin/env bash
set -Eeuo pipefail
R=39083771063
B=com.kdt.livecontainer
U=00008160-000569490C600036
C="$HOME/.sideinstaller/recovery-v13-P8EZT3U5N4"
Z="$HOME/.sideinstaller/bin/zsign"
D=$(mktemp -d "$HOME/다운로드/NRG-V41-117.XXXXXXXX")
for x in gh openssl python3 ideviceinstaller idevice_id; do command -v "$x" >/dev/null || { echo "[ERROR] missing $x"; exit 1; }; done
test -x "$Z"
idevice_id -l | grep -Fxq "$U" || { echo "[ERROR] iPhone not connected"; exit 1; }
gh run download "$R" -R fx564286/sidestore-auto-refresh -n LiveContainer-SideStore-v3.0.3-rc-IPA -D "$D"
I=$(find "$D" -type f -name '*.ipa' -print -quit)
test -n "$I"
export I B C U
P=$(python3 - <<'PY'
import os,glob,zipfile,plistlib,subprocess,datetime,sys
with zipfile.ZipFile(os.environ['I']) as z:
 a=[n for n in z.namelist() if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/')==2]
 if len(a)!=1: sys.exit('[ERROR] IPA app structure')
 bundle=plistlib.loads(z.read(a[0]))['CFBundleIdentifier']
 print('[INFO] unsigned IPA bundle: '+bundle,file=sys.stderr)
 if bundle not in (os.environ['B'],'com.kdt.livecontainer.P8EZT3U5N4'): sys.exit('[ERROR] unexpected bundle ID')
valid=[]
for f in glob.glob(os.environ['C']+'/profile-*.mobileprovision'):
 p=subprocess.run(['openssl','cms','-verify','-inform','DER','-noverify','-in',f],capture_output=True)
 if p.returncode:continue
 try:d=plistlib.loads(p.stdout)
 except Exception:continue
 ent=d.get('Entitlements',{})
 aid=ent.get('application-identifier',ent.get('com.apple.application-identifier',''))
 if aid!='P8EZT3U5N4.'+os.environ['B']:continue
 if os.environ['U'] not in d.get('ProvisionedDevices',[]):continue
 if 'P8EZT3U5N4' not in d.get('TeamIdentifier',[]):continue
 expiry=d.get('ExpirationDate')
 if expiry and expiry.replace(tzinfo=datetime.timezone.utc)<=datetime.datetime.now(datetime.timezone.utc):continue
 valid.append(f)
if len(valid)!=1:
 print('[DIAGNOSTIC] No compatible signing profile. Existing app will NOT be modified.',file=sys.stderr)
 for f in sorted(glob.glob(os.environ['C']+'/*.mobileprovision')):
  p=subprocess.run(['openssl','cms','-verify','-inform','DER','-noverify','-in',f],capture_output=True)
  try:
   d=plistlib.loads(p.stdout) if p.returncode==0 else {}
   e=d.get('Entitlements',{})
   print('[PROFILE]',os.path.basename(f),'app_id=',e.get('application-identifier',e.get('com.apple.application-identifier','?')),'team=',d.get('TeamIdentifier'),'device_match=',os.environ['U'] in d.get('ProvisionedDevices',[]),'expires=',d.get('ExpirationDate'),file=sys.stderr)
  except Exception as ex: print('[PROFILE]',os.path.basename(f),'decode_failed=',str(ex),file=sys.stderr)
 sys.exit('[ERROR] No valid profile for '+os.environ['B']+'; signing blocked')
print(valid[0])
PY
)
echo "[INFO] matched profile: $P"
S="$D/NRG-V41-117-SIGNED.ipa"
"$Z" -f -k "$C/renewed-key.pem" -c "$C/renewed-cert.pem" -m "$P" -b "$B" -o "$S" "$I"
export S
python3 - <<'PY'
import zipfile,plistlib,os,sys
with zipfile.ZipFile(os.environ['S']) as z:
 a=[n for n in z.namelist() if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/')==2]
 if len(a)!=1 or plistlib.loads(z.read(a[0]))['CFBundleIdentifier']!=os.environ['B']:sys.exit('[ERROR] signed bundle mismatch')
 print('[PASS] signed bundle verified')
PY
ideviceinstaller -u "$U" upgrade "$S"
ideviceinstaller -u "$U" list | grep -F "$B"
echo "[PASS] upgrade complete"

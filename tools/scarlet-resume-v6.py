#!/usr/bin/env python3
"""Resume Scarlet V181 signing with 4 already-renewed Apple profiles.

Checks the original IPA and staged IPA against their SHA256 manifest, checks
Apple profile auth and cert/key, signs using patched scy-auto and refuses
in-place installation unless its existing entitlements-parity audit passes.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, importlib.machinery, importlib.util
import json, os, pathlib, plistlib, subprocess, sys

TEAM = 'P8EZT3U5N4'
BASE = 'com.kdt.livecontainer.'+TEAM
EXPECTED = {BASE, BASE+'.LaunchAppExtension', BASE+'.LiveProcess', BASE+'.ShareExtension'}

class Stop(Exception): pass

def need(ok, msg):
    if not ok: raise Stop(msg)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for blob in iter(lambda:f.read(1024*1024),b''):
            h.update(blob)
    return h.hexdigest()

def _load(signer):
    loader=importlib.machinery.SourceFileLoader('scarlet_autorenew_v6',str(signer))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    need(spec is not None and spec.loader is not None,'자동 갱신기 Python 로더 실패')
    module=importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    need('SCARLET_FRESH_ENTITLEMENTS_V6' in signer.read_text(encoding='utf-8'),
         'entitlements v6 패치가 설치되지 않음')
    return module

def _latest_state(root, mod):
    choices=[]
    expected_ids=EXPECTED
    for file in root.glob('*/manifest.json'):
        try:
            data=json.loads(file.read_text())
            state=file.parent
            if data.get('team')!=TEAM or set(data.get('bundle_ids',[]))!=expected_ids:
                continue
            if len(data['bundle_ids'])!=4 or len(set(data['bundle_ids']))!=4: continue
            if not all((state/f'profile-{i:03d}.mobileprovision').is_file() for i in range(4)):continue
            age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromtimestamp(file.stat().st_mtime,dt.timezone.utc)).total_seconds()
            if 0 <= age <= 7200: choices.append((file.stat().st_mtime,state,data))
        except (OSError,ValueError,TypeError,KeyError): continue
    need(bool(choices),'2시간 이내에 발급된 4개 Apple 프로파일 작업 폴더를 찾지 못함')
    return max(choices)

def _matching_stage(root, state_time, mod):
    eligible=[]
    for file in root.glob('*/stage-manifest.json'):
        try:
            data=json.loads(file.read_text())
            output=pathlib.Path(data['staged']).expanduser().resolve(strict=True)
            source=pathlib.Path(data['source']).expanduser().resolve(strict=True)
            need(output.is_relative_to(root.resolve()),'작업 IPA가 지정 경로 외부에 있음')
            if (data.get('target')!=BASE or set(data.get('exts',[]))!=
                {'LaunchAppExtension','LiveProcess','ShareExtension'}):continue
            if digest(output)!=data['staged_sha256'] or digest(source)!=data['original_sha256']:continue
            t=file.stat().st_mtime
            if -60 <= state_time-t <= 2700:eligible.append((t,source,output,data))
        except (OSError,ValueError,TypeError,KeyError,Stop):continue
    need(bool(eligible),'발급 시각과 연결되는 V181 원본/변환 IPA 무결성 기록이 없음')
    return max(eligible)

def resume(install=False):
    if os.geteuid()==0: raise Stop('root 실행 금지. hanabi로 실행')
    home=pathlib.Path.home()
    signer=home/'.local/bin/scy-auto'
    need(signer.is_file(),'scy-auto 자동 갱신기를 찾지 못함')
    mod=_load(signer)
    base=home/'.local/state/scarlet-crystal-installer'
    state_ts,state,manifest=_latest_state(base/'auto-renew',mod)
    stage_ts,source,staged,stage_manifest=_matching_stage(base/'upstream-v5',state_ts,mod)
    ids=manifest['bundle_ids']
    need(set(mod.inventory(staged))==EXPECTED,'서명용 IPA의 Bundle ID/확장 구성 불일치')
    key=state/'key.pem'
    cert=state/'cert.pem'
    need(key.is_file() and cert.is_file(),'기존 인증서/개인키 누락')
    cert_der=subprocess.run(['openssl','x509','-in',str(cert),'-outform','DER'],
        check=True,capture_output=True).stdout
    need(hashlib.sha256(cert_der).hexdigest()==manifest['certificate_sha256'],
         '인증서 지문이 갱신된 Apple 프로파일 매니페스트와 다름')
    xcert=subprocess.run(['openssl','x509','-in',str(cert),'-pubkey','-noout'],check=True,capture_output=True).stdout
    xkey=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],check=True,capture_output=True).stdout
    need(xcert==xkey,'개인키/인증서 불일치')
    udid=manifest.get('udid')
    need(isinstance(udid,str) and bool(udid),'Apple 기기 UDID 누락')
    proc=subprocess.run(['idevice_id','-l'],capture_output=True,text=True)
    listed=proc.stdout.splitlines()
    need(proc.returncode==0 and listed==[udid],
         '현재 USB 기기와 프로파일 발급 대상이 다름. 자동 설치 차단')
    for i, identifier in enumerate(ids):
        mod.verify_profile((state/f'profile-{i:03d}.mobileprovision').read_bytes(),
                           TEAM,identifier,udid,cert_der)
    print('[PASS] Apple 서명 프로파일 4개·인증서·USB 기기 일치',flush=True)
    print('[SOURCE]',source,flush=True)
    print('[STATE]',state,flush=True)
    stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out=staged.with_name(staged.stem+'-SIGNED-'+stamp+'.ipa')
    mod.sign_ipa(staged,state,out,ids,None)
    print('[PASS] 서명 IPA 결과물',out,flush=True)
    if install:
        mod.audit_before_install(out,state,udid,ids)
        print('[INSTALL] 무결성·기존 데이터 보존 검증 통과; USB 업그레이드',flush=True)
        p=subprocess.run(['ideviceinstaller','-u',udid,'upgrade',str(out)])
        need(p.returncode==0,'USB 업그레이드 명령 실패. 기존 앱 제거하지 않음')
        print('[PASS] USB 업데이트 명령 완료. 실제 앱 실행은 기기에서 확인 필요',flush=True)
    else:
        print('[SAFE] --install 미지정: 앱 설치를 수행하지 않음',flush=True)
    return 0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--install',action='store_true',help='서명 후 기존 앱 보존 감사 통과 시에만 업데이트')
    args=ap.parse_args()
    try:return resume(args.install)
    except (Stop, OSError, ValueError, subprocess.CalledProcessError) as e:
        print('[STOP]',e,file=sys.stderr,flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())

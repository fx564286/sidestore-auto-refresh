#!/usr/bin/env python3
"""Build an unsigned two-action iOS Shortcut; macOS shortcuts sign is required.

Import prompts collect SSH host, user and SSH password on the iPhone. No Apple ID,
GitHub PAT, P12 password, signing key or SSH credential is embedded in this file.
"""
from pathlib import Path
import hashlib
import plistlib
import uuid
import sys

REPO="fx564286/sidestore-auto-refresh"
BRANCH="feat/scarlet-universal-shortcut-publisher-20261105"
def build(output):
    ssh=str(uuid.uuid4()).upper()
    action=str(uuid.uuid4()).upper()
    shell="""set -eu
D="$HOME/.local/share/scarlet-crystal/latest-publisher"
mkdir -p "$D"
URL='https://raw.githubusercontent.com/""" + REPO + "/" + BRANCH + """/tools/scarlet_latest_publish.py'
curl -fLSs --retry 3 --connect-timeout 15 --max-time 60 "$URL" -o "$D/latest.py.tmp"
python3 -m py_compile "$D/latest.py.tmp"
mv -f "$D/latest.py.tmp" "$D/latest.py"
python3 "$D/latest.py" 2>> "$D/last-run.log"
"""
    root={
        "WFWorkflowName":"Scarlet Crystal 최신 버전 서명 배포",
        "WFWorkflowClientVersion":"2700.0.4",
        "WFWorkflowMinimumClientVersion":900,
        "WFWorkflowIcon":{
            "WFWorkflowIconStartColor":0x715ADDFF,
            "WFWorkflowIconGlyphNumber":61440,
        },
        "WFWorkflowTypes":[],
        "WFWorkflowHasOutputFallback":False,
        "WFWorkflowHasShortcutInputVariables":False,
        "WFWorkflowImportQuestions":[
            {"ActionIndex":0,"Category":"Parameter","ParameterKey":"WFSSHHost",
             "Text":"CachyOS PC SSH 주소 또는 VPN 호스트",
             "DefaultValue":"cachyos-x8664.local"},
            {"ActionIndex":0,"Category":"Parameter","ParameterKey":"WFSSHUser",
             "Text":"CachyOS PC SSH 사용자","DefaultValue":"hanabi"},
            {"ActionIndex":0,"Category":"Parameter","ParameterKey":"WFSSHPassword",
             "Text":"PC SSH 로그인 비밀번호. Apple ID/P12 암호가 아님."},
        ],
        "WFWorkflowActions":[
            {"WFWorkflowActionIdentifier":"is.workflow.actions.runsshscript",
             "WFWorkflowActionParameters":{
                 "UUID":ssh,
                 "WFSSHHost":"cachyos-x8664.local",
                 "WFSSHUser":"hanabi",
                 "WFSSHPort":"22",
                 "WFSSHAuthenticationType":"Password",
                 "WFSSHPassword":"",
                 "WFSSHScript":shell,
             }},
            {"WFWorkflowActionIdentifier":"is.workflow.actions.openurl",
             "WFWorkflowActionParameters":{
                 "UUID":action,
                 "WFInput":{
                     "Value":{"OutputUUID":ssh,"Type":"ActionOutput",
                              "OutputName":"Shell Script Result"},
                     "WFSerializationType":"WFTextTokenAttachment",
                 },
             }},
        ],
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(plistlib.dumps(root,fmt=plistlib.FMT_BINARY))
    parsed=plistlib.loads(output.read_bytes())
    assert len(parsed["WFWorkflowActions"])==2
    assert len(parsed["WFWorkflowImportQuestions"])==3
    assert not parsed["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["WFSSHPassword"]
    assert "scarlet_latest_publish.py" in shell
    assert "V188" not in shell and "V189" not in shell
    print("[PASS] UNSIGNED_SHORTCUT_CREATED path=",output)
    print("[SHA256]",hashlib.sha256(output.read_bytes()).hexdigest())
    print("[SIGNING_REQUIRED] macOS shortcuts sign --mode anyone --input <unsigned> --output <signed>")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: build_scarlet_latest_shortcut.py <output.shortcut>")
    build(Path(sys.argv[1]))

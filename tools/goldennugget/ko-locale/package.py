#!/usr/bin/env python3
"""Package verified Korean localizations into GitHub-built GoldenNugget unsigned IPA."""
import base64
import copy
import hashlib
import lzma
import plistlib
import re
import sys
import zipfile
from pathlib import Path

def decode(directory, name):
    raw=(directory / name).read_text(encoding="ascii").strip()
    return lzma.decompress(base64.b85decode(raw.encode("ascii")))

def main():
    source=Path(sys.argv[1])
    target=Path(sys.argv[2])
    locale=Path(__file__).parent
    ko_local=decode(locale, "Localizable.strings.xz.b85")
    ko_info=decode(locale, "InfoPlist.strings.xz.b85")
    assert len(re.findall(rb'(?m)^"(?:[^"\\]|\\.)*"\\s*=\\s*"',ko_local)) >= 1000, "incomplete Korean catalog"
    prefix="Payload/GoldenNuggetMobile.app/"
    with zipfile.ZipFile(source) as prior:
        assert prior.testzip() is None
        info=plistlib.loads(prior.read(prefix+"Info.plist"))
        assert info.get("CFBundleIdentifier") == "com.awesomenull.goldennugget"
        assert info.get("CFBundleShortVersionString") == "9.7.5"
        binary=prior.read(prefix+"GoldenNuggetMobile")
        assert b"Dev.SkipProtectiveBackup" in binary
        info["CFBundleLocalizations"]=sorted(set(info.get("CFBundleLocalizations",[]))|{"en","ko"})
        replacements={
            prefix+"ko.lproj/Localizable.strings":ko_local,
            prefix+"ko.lproj/InfoPlist.strings":ko_info,
            prefix+"Info.plist":plistlib.dumps(info,fmt=plistlib.FMT_BINARY,sort_keys=False),
        }
        with zipfile.ZipFile(target,"w") as out:
            for entry in prior.infolist():
                out.writestr(copy.copy(entry),replacements.pop(entry.filename,prior.read(entry.filename)))
            for name,data in replacements.items():
                out.writestr(name,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(target) as check:
        assert check.testzip() is None
        assert check.read(prefix+"GoldenNuggetMobile")==binary
        assert check.read(prefix+"ko.lproj/Localizable.strings")==ko_local
        assert "ko" in plistlib.loads(check.read(prefix+"Info.plist"))["CFBundleLocalizations"]
    print("IPA_OK",target.stat().st_size,hashlib.sha256(target.read_bytes()).hexdigest())

if __name__=="__main__": main()

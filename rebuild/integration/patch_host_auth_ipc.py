#!/usr/bin/env python3
"""Research-only extension of the PINNED LiveContainer SideStoreSupport XPC path.

Adds a separate runtime authentication command. Original refresh and other
protocol operations are preserved, never reimplemented. Refuses upstream drift.
Does not sign, install or access credentials during CI.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

def replace_once(data, before, after, label):
    if data.count(before)!=1:
        raise RuntimeError(f"{label}: unexpected pinned source anchor ({data.count(before)})")
    return data.replace(before, after)

def hash_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def apply(engine:Path, root:Path):
    h=engine/"SideStoreSupport/XPCServer.h"
    m=engine/"SideStoreSupport/XPCClient.m"
    proj=engine/"LiveContainer.xcodeproj/project.pbxproj"
    swift=engine/"SideStoreSupport/ScarletAuthTransport.swift"
    required=[h,m,proj]
    if not all(p.is_file() for p in required) or swift.exists():
        raise RuntimeError("Pinned LiveContainer auth transport files missing/duplicated")
    hs=h.read_text()
    hs=replace_once(hs,"- (void)finishedLaunching;\n",
        "- (void)finishedLaunching;\n"
        "- (void)scarletRequest2FACodeForPrompt:(NSString*)prompt reply:(void (^)(NSString* _Nullable code))reply;\n",
        "XPC RefreshServer")
    hs=replace_once(hs,
        '- (void)refreshAllAppsWithIdentifier:(NSString*)identifier mangledTypeName:(NSString *)mangledTypeName;\n',
        '- (void)refreshAllAppsWithIdentifier:(NSString*)identifier mangledTypeName:(NSString *)mangledTypeName;\n'
        '- (void)scarletAuthenticateWithAppleID:(NSString*)appleID password:(NSString*)password reply:(void (^)(NSString* _Nullable error))reply;\n',
        "XPC RefreshClient")

    ms=m.read_text()
    injected='''// Auth commands remain in the original SideStore runtime, not a guest UI.
- (void)scarletAuthenticateWithAppleID:(NSString*)appleID
                               password:(NSString*)password
                                  reply:(void (^)(NSString* _Nullable error))reply {
    if(!handler || !handler.server) {
        reply(@"Private SideStore authentication channel is unavailable");
        return;
    }
    Class cls = NSClassFromString(@"ScarletSideStoreAuthEngine");
    SEL sel = NSSelectorFromString(@"beginAuthenticationWithAppleID:password:challenge:reply:");
    if(!cls || ![cls respondsToSelector:sel]) {
        reply(@"Original SideStore authentication engine was not loaded");
        return;
    }
    NSMethodSignature *signature = [cls methodSignatureForSelector:sel];
    if(!signature || signature.numberOfArguments != 6) {
        reply(@"Original SideStore authentication engine ABI mismatch");
        return;
    }
    id<RefreshServer> server = handler.server;
    id challenge = [^(NSString *prompt, void (^codeReply)(NSString*)) {
        [server scarletRequest2FACodeForPrompt:prompt reply:codeReply];
    } copy];
    id completion = [reply copy];
    id a = appleID, p = password;
    NSInvocation *inv = [NSInvocation invocationWithMethodSignature:signature];
    inv.target = cls;
    inv.selector = sel;
    [inv setArgument:&a atIndex:2];
    [inv setArgument:&p atIndex:3];
    [inv setArgument:&challenge atIndex:4];
    [inv setArgument:&completion atIndex:5];
    [inv retainArguments];
    [inv invoke];
}

'''
    ms=replace_once(ms,"- (void) relaunchLC {\n",injected+"- (void) relaunchLC {\n","XPCClient")

    ps=proj.read_text()
    newBuild="AC9EBA012026110600000001"
    if newBuild in ps:raise RuntimeError("Auth framework link already configured")
    ps=replace_once(ps,
        "/* Begin PBXBuildFile section */\n",
        "/* Begin PBXBuildFile section */\n"
        f"\t\t{newBuild} /* SideStoreSupport.framework in Frameworks */ = "
        "{isa = PBXBuildFile; fileRef = 173545A82E2C7913001B3B4C /* SideStoreSupport.framework */; };\n",
        "Xcode BuildFile")
    ps=replace_once(ps,
        "\t\t17413FB22D9C0BAE00F3F928 /* Frameworks */ = {\n"
        "\t\t\tisa = PBXFrameworksBuildPhase;\n"
        "\t\t\tbuildActionMask = 2147483647;\n"
        "\t\t\tfiles = (\n",
        "\t\t17413FB22D9C0BAE00F3F928 /* Frameworks */ = {\n"
        "\t\t\tisa = PBXFrameworksBuildPhase;\n"
        "\t\t\tbuildActionMask = 2147483647;\n"
        "\t\t\tfiles = (\n"
        f"\t\t\t\t{newBuild} /* SideStoreSupport.framework in Frameworks */,\n",
        "LC SwiftUI Frameworks")
    old=('17413FB42D9C0BAE00F3F928 /* LiveContainerSwiftUI */ = {\n'
        '\t\t\tisa = PBXNativeTarget;\n')
    if ps.count(old)!=1:raise RuntimeError("LC NativeTarget anchor missing")
    start=ps.index(old)
    # Modify ONLY the LiveContainerSwiftUI target. The original project
    # legitimately contains multiple independent empty dependency blocks.
    target_end=ps.index("\n\t\t};",start)+len("\n\t\t};")
    target=ps[start:target_end]
    target=replace_once(target,
        "\t\t\tdependencies = (\n\t\t\t);\n",
        "\t\t\tdependencies = (\n"
        "\t\t\t\t173545AD2E2C7913001B3B4C /* PBXTargetDependency */,\n"
        "\t\t\t);\n",
        "LC SwiftUI dependency")
    ps=ps[:start]+target+ps[target_end:]

    src=root/"rebuild/EngineBridge/ScarletSideStoreSupportAuth.swift"
    assert src.is_file(),"Auth transport source missing"
    # Preflight all anchors before mutating the checkout.
    h.write_text(hs);m.write_text(ms);proj.write_text(ps)
    shutil.copy2(src,swift)
    return dict(modified=[str(x.relative_to(engine)) for x in [h,m,proj,swift]],
                hashes={str(x.relative_to(engine)):hash_file(x) for x in [h,m,proj,swift]})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--engine",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    root=Path(__file__).resolve().parents[2]
    result=apply(args.engine,root)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(dict(schema=1,hostAuthTransportInjected=True,
                                           originalRefreshContractRetained=True,
                                           deviceVerified=False,**result),indent=2)+"\n")
    print("[PASS] Research auth-only XPC interface injected without touching Apple assets")
    print("[BLOCK] Device authentication, guest runtime XPC and profile checks unverified")

if __name__=="__main__":main()

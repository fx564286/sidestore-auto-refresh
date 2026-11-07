#!/usr/bin/env python3
"""Apply reviewed, fail-closed auth XPC shims to exact pinned sources.

The independent Scarlet UI never displays the standalone SideStore guest.
The unchanged SideSign authentication implementation runs in the embedded
SideStore LiveProcess, and only the anonymous host/guest XPC interface is
extended. Do not change upstream pins, App IDs, profiles or existing keychain.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def replace_one(source: str, old: str, new: str, label: str) -> str:
    assert source.count(old) == 1, (label, source.count(old))
    return source.replace(old, new)


def patch_livecontainer(engine: Path) -> None:
    header = engine / "SideStoreSupport/XPCServer.h"
    h = header.read_text()
    h = replace_one(h,
        "- (void)removePendingNotificationRequestsWithIdentifiers:(NSArray<NSString*>*)identifiers;\n@end",
        """- (void)removePendingNotificationRequestsWithIdentifiers:(NSArray<NSString*>*)identifiers;
- (void)scarletAuthNeedsCode:(NSString*)requestID;
- (void)scarletAuthCompleted:(NSString*)requestID code:(NSInteger)code domain:(NSString*)domain;
@end""", "RefreshServer proto")
    h = replace_one(h,
        '- (void)refreshAllAppsWithIdentifier:(NSString*)identifier mangledTypeName:(NSString *)mangledTypeName;\n@end',
        """- (void)refreshAllAppsWithIdentifier:(NSString*)identifier mangledTypeName:(NSString *)mangledTypeName;
- (void)scarletAuthReady:(void (^)(BOOL isReady))reply;
- (void)scarletBeginAuth:(NSString*)requestID email:(NSString*)email password:(NSString*)password profile:(NSString*)profile;
- (void)scarletProvideCode:(NSString*)requestID code:(NSString*)code;
- (void)scarletCancelAuth:(NSString*)requestID;
@end""", "RefreshClient proto")
    header.write_text(h)

    client = engine / "SideStoreSupport/XPCClient.m"
    s = client.read_text()
    s = replace_one(s, '#include "../LiveContainer/LCSharedUtils.h"\n',
        '#include "../LiveContainer/LCSharedUtils.h"\n#import <objc/message.h>\n',
        "objc runtime")
    s = replace_one(s,
        '    handler.connection.exportedObject = SideStoreClient.shared;\n',
        """    handler.connection.exportedObject = SideStoreClient.shared;
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(scarletNeedsCode:)
                                                 name:@"ScarletGuestAuthNeedsCode" object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(scarletCompleted:)
                                                 name:@"ScarletGuestAuthCompleted" object:nil];
""", "auth notifications")
    extra = """
+ (void)scarletNeedsCode:(NSNotification*)notification {
    NSString* requestID = notification.userInfo[@"requestID"];
    if (requestID.length && handler.server) {
        [handler.server scarletAuthNeedsCode:requestID];
    }
}

+ (void)scarletCompleted:(NSNotification*)notification {
    NSString* requestID = notification.userInfo[@"requestID"];
    NSNumber* code = notification.userInfo[@"code"];
    NSString* domain = notification.userInfo[@"domain"];
    if (requestID.length && handler.server) {
        [handler.server scarletAuthCompleted:requestID code:code.integerValue domain:domain ?: @"scarlet.auth.unknown"];
    }
}

- (void)scarletAuthReady:(void (^)(BOOL))reply {
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    reply(worker && [worker respondsToSelector:@selector(begin:)]);
}

- (void)scarletBeginAuth:(NSString*)requestID email:(NSString*)email password:(NSString*)password profile:(NSString*)profile {
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    if (![worker respondsToSelector:@selector(begin:)]) {
        [handler.server scarletAuthCompleted:requestID code:-2 domain:@"scarlet.auth.worker_missing"];
        return;
    }
    NSDictionary* args = @{@"requestID": requestID, @"email": email, @"password": password, @"profile": profile ?: @"default"};
    ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(begin:), args);
}

- (void)scarletProvideCode:(NSString*)requestID code:(NSString*)code {
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    if (![worker respondsToSelector:@selector(receiveCode:)]) return;
    NSDictionary* args = @{@"requestID": requestID, @"code": code};
    ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(receiveCode:), args);
}

- (void)scarletCancelAuth:(NSString*)requestID {
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    if (![worker respondsToSelector:@selector(cancel:)]) return;
    ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(cancel:),
                                          @{@"requestID": requestID});
}

"""
    # XPCClient.m has a Swift category declaration and the implementation;
    # append the worker methods only to the final implementation @end.
    assert s.count("@end") == 2, "Pinned XPCClient ObjC structure changed"
    head, last = s.rsplit("@end", 1)
    s = head + extra + "@end" + last
    client.write_text(s)

    support = engine / "SideStoreSupport/ScarletAuthXPCSupport.swift"
    assert not support.exists(), "Auth support already staged"
    shutil.copyfile(ROOT / "rebuild/HostApp/ScarletAuthXPCSupport.swift", support)

    project = engine / "LiveContainer.xcodeproj/project.pbxproj"
    p = project.read_text()
    p = replace_one(p,
        '/* Begin PBXBuildFile section */\n',
        """/* Begin PBXBuildFile section */
        A21C52E711220CFA00000001 /* SideStoreSupport.framework in Frameworks */ = {isa = PBXBuildFile; fileRef = 173545A82E2C7913001B3B4C /* SideStoreSupport.framework */; };
""", "PBXBuildFile")
    p = replace_one(p,
        """17413FB22D9C0BAE00F3F928 /* Frameworks */ = {
            isa = PBXFrameworksBuildPhase;""".replace("            ", "\t\t\t"),
        """17413FB22D9C0BAE00F3F928 /* Frameworks */ = {
            isa = PBXFrameworksBuildPhase;""".replace("            ", "\t\t\t"),
        "SwiftUI framework stage") if False else p
    old = '\t\t17413FB22D9C0BAE00F3F928 /* Frameworks */ = {\n\t\t\tisa = PBXFrameworksBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n'
    p = replace_one(p, old,
        old + '\t\t\t\tA21C52E711220CFA00000001 /* SideStoreSupport.framework in Frameworks */,\n',
        "framework linker")
    p = replace_one(p,
        '\t\t17413FB42D9C0BAE00F3F928 /* LiveContainerSwiftUI */ = {',
        '\t\t17413FB42D9C0BAE00F3F928 /* LiveContainerSwiftUI */ = {',
        "check target") if False else p
    start = p.index('\t\t17413FB42D9C0BAE00F3F928 /* LiveContainerSwiftUI */ = {')
    end = p.index('\t\t\tname = LiveContainerSwiftUI;', start)
    sub = p[start:end]
    assert sub.count('\t\t\tdependencies = (\n\t\t\t);\n') == 1
    sub = sub.replace('\t\t\tdependencies = (\n\t\t\t);\n',
                      '\t\t\tdependencies = (\n\t\t\t\t173545AD2E2C7913001B3B4C /* PBXTargetDependency */,\n\t\t\t);\n')
    p = p[:start] + sub + p[end:]
    project.write_text(p)
    print("[PASS] SideStoreSupport XPC auth protocol and SwiftUI module linking staged")


def patch_sidestore(engine: Path) -> None:
    target = engine / "SideStore/Core/Auth/AuthManager.swift"
    assert target.is_file(), target
    source = target.read_text()
    assert source.count("public final class AuthManager") == 1
    assert source.count("func signIn(appleID: String,") == 1
    assert "ScarletGuestSignInAgent" not in source
    extra = (ROOT / "rebuild/integration/ScarletGuestSignInAgent.swift.txt").read_text()
    target.write_text(source.rstrip() + "\n\n" + extra)
    print("[PASS] SideStore SideSign-backed guest authentication worker staged")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("livecontainer", "sidestore"))
    args = parser.parse_args()
    (patch_livecontainer if args.mode == "livecontainer" else patch_sidestore)(args.engine)


if __name__ == "__main__":
    main()

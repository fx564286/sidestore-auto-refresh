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
- (void)scarletAuthStored:(void (^)(BOOL hasStoredSession))reply;
- (void)scarletRefreshReadiness:(void (^)(NSInteger managedCount, BOOL hostManaged, BOOL signingReady, NSString *status))reply;
- (void)scarletPerformNativeRefresh:(void (^)(BOOL operationReturned, NSString *status))reply;
- (void)scarletInstallPairingRecord:(NSData*)record reply:(void (^)(BOOL verified, NSString *status))reply;
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
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(scarletInstallCompleted:)
                                                 name:@"ScarletDeviceInstallCompleted" object:nil];
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

+ (void)scarletInstallCompleted:(NSNotification*)notification {
    NSString* result = notification.userInfo[@"result"];
    if (handler.server) {
        if ([result isEqualToString:@"installed"]) {
            [handler.server finish:nil];
        } else {
            [handler.server finish:[@"scarlet.install." stringByAppendingString:
                result ?: @"unknown"]];
        }
    }
}

- (void)scarletAuthReady:(void (^)(BOOL))reply {
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    reply(worker && [worker respondsToSelector:@selector(begin:)]);
}

- (void)scarletRefreshReadiness:(void (^)(NSInteger, BOOL, BOOL, NSString *))reply {
    // The real SideStore worker owns its install DB and signing Keychain.
    // Missing worker must never look like a successful refresh.
    Class worker = NSClassFromString(@"ScarletGuestRefreshAgent");
    if (!worker || ![worker respondsToSelector:@selector(inspect:)]) {
        reply(0, NO, NO, @"refresh_worker_missing");
        return;
    }
    ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(inspect:), reply);
}

- (void)scarletPerformNativeRefresh:(void (^)(BOOL, NSString *))reply {
    // This executes original SideStore AppManager directly in its guest
    // worker (where the registered apps + signing Keychain actually live).
    // RefreshAllAppsIntent in the LC host was proxying through an iOS
    // PrivateIntentRunner and reducing failures to SideStore(1).
    Class worker = NSClassFromString(@"ScarletGuestRefreshAgent");
    if (!worker || ![worker respondsToSelector:@selector(perform:)]) {
        reply(NO, @"refresh_worker_missing");
        return;
    }
    ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(perform:), reply);
}

- (void)scarletInstallPairingRecord:(NSData*)record
                              reply:(void (^)(BOOL, NSString *))reply {
    // All bytes remain within the on-device LC -> embedded SideStore XPC.
    // The Swift worker parses and tests the pairing BEFORE disk commit;
    // neither this Objective-C bridge nor the diagnostic journal logs it.
    if (!record || record.length > 1048576) {
        reply(NO, @"pairing_file_invalid");
        return;
    }
    Class worker = NSClassFromString(@"ScarletGuestRefreshAgent");
    SEL selector = NSSelectorFromString(@"importDevicePairing:reply:");
    if (!worker || ![worker respondsToSelector:selector]) {
        reply(NO, @"refresh_worker_missing");
        return;
    }
    ((void (*)(id, SEL, id, id))objc_msgSend)(worker, selector, record, reply);
}

- (void)scarletAuthStored:(void (^)(BOOL))reply {
    // Read saved status in the *SideStore* process from its original Keychain.
    // Returning cached host UI state here would falsely survive broken sign-in.
    Class worker = NSClassFromString(@"ScarletGuestSignInAgent");
    if (!worker || ![worker respondsToSelector:@selector(persistedState)]) {
        reply(NO);
        return;
    }
    BOOL authenticated = ((BOOL (*)(id, SEL))objc_msgSend)(worker,
                                                         @selector(persistedState));
    reply(authenticated);
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
    s = replace_one(s,
        '    [self performRefreshForRealWithIdentifier:identifier mangledTypeName:mangledTypeName server:handler.server];',
        '''    if ([identifier isEqualToString:@"scarlet.install.ipa"]) {
        Class worker = NSClassFromString(@"ScarletDeviceInstallAgent");
        if (!worker || ![worker respondsToSelector:@selector(install:)]) {
            [handler.server finish:@"scarlet.install.worker_missing"];
            return;
        }
        NSString* requestID = [[NSUUID UUID] UUIDString];
        NSDictionary* payload = @{@"requestID": requestID,
                                  @"filename": mangledTypeName ?: @""};
        ((void (*)(id, SEL, id))objc_msgSend)(worker, @selector(install:), payload);
        return;
    }
    [self performRefreshForRealWithIdentifier:identifier mangledTypeName:mangledTypeName server:handler.server];''',
        "headless device install dispatcher")
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
    # Reuse the SAME signed SideStore LiveProcess/XPC channel as refresh.
    # Do not copy SideInstaller's engine or open its standalone screen.
    bridge = engine / "SideStoreSupport/SideStore.swift"
    support_source = bridge.read_text()
    assert "scarlet.install.ipa" not in support_source, "Device installer already staged"
    support_source += """
@available(iOS 17.0, *)
public enum ScarletDeviceInstaller {
    public static func install(stagedIPA: URL) async throws {
        let groupID = "group.com.SideStore.SideStore.P8EZT3U5N4"
        guard let root = FileManager.default.containerURL(
                  forSecurityApplicationGroupIdentifier: groupID) else {
            throw NSError(domain: "scarlet.install.app_group_unavailable", code: 1)
        }
        let allowed = root.appendingPathComponent("ScarletDeviceInstall",
                           isDirectory: true).standardizedFileURL
        let resolved = stagedIPA.standardizedFileURL.resolvingSymlinksInPath()
        guard resolved.deletingLastPathComponent() == allowed,
              resolved.pathExtension.lowercased() == "ipa",
              FileManager.default.isReadableFile(atPath: resolved.path) else {
            throw NSError(domain: "scarlet.install.staged_ipa_invalid", code: 2)
        }
        try await RefreshHandler.shared.startRefresh(
            identifier: "scarlet.install.ipa",
            mangledName: resolved.lastPathComponent)
    }
}
"""
    bridge.write_text(support_source)

    # In-app Apple certificate issuance runs in the same SideStore worker and
    # is opt-in, preserving the authenticated XPC transport and Apple identity.
    cert_server = engine / "SideStoreSupport/XPCServer.h"
    h = cert_server.read_text()
    h = replace_one(h,
        '- (void)scarletAuthCompleted:(NSString*)requestID code:(NSInteger)code domain:(NSString*)domain;',
        '- (void)scarletAuthCompleted:(NSString*)requestID code:(NSInteger)code domain:(NSString*)domain;\n'
        '- (void)scarletCertificateCompleted:(NSString*)requestID code:(NSInteger)code domain:(NSString*)domain certificateData:(NSData*)certificateData password:(NSString*)password;',
        "certificate result XPC")
    h = replace_one(h,
        '- (void)scarletCancelAuth:(NSString*)requestID;',
        '- (void)scarletCancelAuth:(NSString*)requestID;\n'
        '- (void)scarletIssueCertificate:(NSString*)requestID;\n'
        '- (void)scarletRetrieveCertificate:(NSString*)requestID;',
        "certificate request XPC")
    cert_server.write_text(h)
    cert_client = engine / "SideStoreSupport/XPCClient.m"
    s = cert_client.read_text()
    s = replace_one(s,
        '                                                 name:@"ScarletGuestAuthCompleted" object:nil];',
        '                                                 name:@"ScarletGuestAuthCompleted" object:nil];\n'
        '    [[NSNotificationCenter defaultCenter] addObserver:self\n'
        '                                             selector:@selector(scarletCertificateReady:)\n'
        '                                                 name:@"ScarletGuestCertificateCompleted" object:nil];',
        "certificate notifications")
    assert s.count("@end") == 2
    head, tail = s.rsplit("@end", 1)
    head += """
+ (void)scarletCertificateReady:(NSNotification*)note {
    NSString* requestID = note.userInfo[@"requestID"];
    NSNumber* code = note.userInfo[@"code"];
    NSString* domain = note.userInfo[@"domain"];
    NSData* archive = note.userInfo[@"archive"];
    NSString* password = note.userInfo[@"password"];
    if (requestID.length && handler.server) {
        [handler.server scarletCertificateCompleted:requestID
            code:code.integerValue domain:domain ?: @"scarlet.cert.unknown"
            certificateData:archive ?: [NSData data] password:password ?: @""];
    }
}

- (void)scarletRetrieveCertificate:(NSString*)requestID {
    Class worker = NSClassFromString(@"ScarletGuestCertificateAgent");
    if (!worker || ![worker respondsToSelector:@selector(retrieve:)]) {
        [handler.server scarletCertificateCompleted:requestID
            code:-5300 domain:@"scarlet.cert.retrieve_worker_missing"
            certificateData:[NSData data] password:@""];
        return;
    }
    ((void (*)(id, SEL, id))objc_msgSend)(
        worker, @selector(retrieve:), @{@"requestID": requestID});
}

- (void)scarletIssueCertificate:(NSString*)requestID {
    Class worker = NSClassFromString(@"ScarletGuestCertificateAgent");
    if (!worker || ![worker respondsToSelector:@selector(issue:)]) {
        [handler.server scarletCertificateCompleted:requestID
            code:-5200 domain:@"scarlet.cert.worker_missing"
            certificateData:[NSData data] password:@""];
        return;
    }
    ((void (*)(id, SEL, id))objc_msgSend)(
        worker, @selector(issue:), @{@"requestID": requestID});
}
"""
    cert_client.write_text(head + "@end" + tail)
    support = engine / "SideStoreSupport/ScarletCertificateXPCSupport.swift"
    assert not support.exists(), "cert transport is already staged"
    shutil.copyfile(ROOT / "rebuild/HostApp/ScarletCertificateXPCSupport.swift", support)
    print("[PASS] SideStoreSupport authenticated certificate XPC staged")



def patch_sidestore(engine: Path) -> None:
    # SideStore's original self-registration returns immediately inside ALL
    # .appex processes. Scarlet intentionally runs SideStore headlessly in
    # LiveProcess.appex, unlike the upstream UI setup that first opens the
    # embedded SideStore as an app. Allow only this signed LC host + exact
    # LiveProcess extension to run the ORIGINAL prepareDatabase() pipeline.
    # The original pipeline verifies embedded.mobileprovision, creates the
    # correct InstalledApp + StoreApp records, and caches its signed IPA.
    # No synthetic database rows or certificate replacement.
    database = engine / "AltStore/Core/Model/DatabaseManager/DatabaseManager.swift"
    db = database.read_text()
    db = replace_one(db,
        "        guard !Bundle.isAppExtension() else { return }",
        """        let isEmbeddedLCRefreshWorker =
            (Bundle.main.executablePath?.contains("LiveProcess.appex/") == true) &&
            getenv("LC_HOME_PATH") != nil &&
            Bundle.Info.activeBundleURL.pathExtension.lowercased() == "app"
        guard !Bundle.isAppExtension() || isEmbeddedLCRefreshWorker else { return }""",
        "SideStore headless LiveProcess self registration")
    db = replace_one(db,
        "                    guard let pluginURL = Bundle.main.builtInPlugInsURL else {",
        "                    guard let pluginURL = Bundle.Info.activeBundle.builtInPlugInsURL else {",
        "signed LC host extension receipt for self registration")
    database.write_text(db)
    print("[PASS] Embedded SideStore LiveProcess may run original signed-host DB self registration")
    target = engine / "SideStore/Core/Auth/AuthManager.swift"
    assert target.is_file(), target
    source = target.read_text()
    assert source.count("public final class AuthManager") == 1
    assert source.count("func signIn(appleID: String,") == 1
    assert "ScarletGuestSignInAgent" not in source
    # The original SideStore token-restoration path always requests the
    # DEFAULT Anisette, even after successful Mac-server auth. That can
    # recreate Apple -80045 on the next launch or signing operation. Keep
    # the original token/team database and change only this Anisette source.
    original = "            let anisetteData = try await AnisetteProvider.fetch()"
    assert source.count(original) == 1, "Pinned SideStore token restoration changed"
    source = source.replace(original,
        "            let anisetteData = try await ScarletGuestSignInAgent.restoreAnisetteForSavedSession()")
    extra = (ROOT / "rebuild/integration/ScarletGuestSignInAgent.swift.txt").read_text()
    installer = (ROOT / "rebuild/integration/ScarletDeviceInstallAgent.swift.txt").read_text()
    target.write_text(source.rstrip() + "\n\n" + extra + "\n\n" + installer)
    cert_agent = (ROOT / "rebuild/integration/ScarletGuestCertificateAgent.swift.txt").read_text()
    assert "ScarletGuestCertificateAgent" not in source
    refresh_agent = (ROOT / "rebuild/integration/ScarletGuestRefreshAgent.swift.txt").read_text()
    team_repair = (ROOT / "rebuild/integration/ScarletGuestAuthTeamRepair.swift.txt").read_text()
    target.write_text(source.rstrip() + "\n\n" + extra + "\n\n" +
                      installer + "\n\n" + cert_agent + "\n\n" +
                      team_repair + "\n\n" + refresh_agent)
    print("[PASS] SideStore original active Team CoreData repair included in guest AuthManager")
    print("[PASS] Native SideStore managed-app/host-identity refresh inspector staged")
    print("[PASS] SideStore authenticated certificate worker staged")
    print("[PASS] SideStore SideSign auth + headless installer workers staged")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("livecontainer", "sidestore"))
    args = parser.parse_args()
    (patch_livecontainer if args.mode == "livecontainer" else patch_sidestore)(args.engine)


if __name__ == "__main__":
    main()

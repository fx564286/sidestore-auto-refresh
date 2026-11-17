"""P94: make public DER of original ZSigner signing cert accessible to Swift.

All changes apply only to pinned upstream LC workspace at build time, not
Apple signing credentials or private key material. Fail closed on source drift.
"""
from pathlib import Path
import hashlib

Z_IMPL = r'''// P94: return only the public X509 DER from the same OpenSSL parser that
// the original LiveContainer guest signer uses. No private key output.
+ (NSData *)scarletCertificateDERWithCert:(NSData *)p12 pass:(NSString *)password {
    if (!p12 || p12.length == 0 || p12.length > (10 * 1024 * 1024) ||
        !password || password.length > 1024) return nil;
    const char *raw = (const char *)p12.bytes;
    const char *pass = password.UTF8String;
    if (!raw || !pass) return nil;
    ZSignAsset signer;
    if (!signer.InitSimple(raw, (int)p12.length, nil, 0, string(pass))) return nil;
    X509 *certificate = (X509 *)signer.m_x509Cert;
    if (!certificate) return nil;
    unsigned char *derBytes = nullptr;
    int derLength = i2d_X509(certificate, &derBytes);
    if (derLength <= 0 || !derBytes) {
        if (derBytes) OPENSSL_free(derBytes);
        return nil;
    }
    NSData *der = [NSData dataWithBytes:derBytes length:(NSUInteger)derLength];
    OPENSSL_free(derBytes);
    return der;
}
'''

UTILS_IMPL = r'''// P94: use the loaded original ZSign signer, not SecPKCS12Import.
+ (NSData *)scarletCertificateDERWithKeyData:(NSData *)keyData
                                  password:(NSString *)password {
    NSError *error = nil;
    [self loadStoreFrameworksWithError2:&error];
    if (error || !NSClassFromString(@"ZSigner")) return nil;
    return [NSClassFromString(@"ZSigner")
        scarletCertificateDERWithCert:keyData pass:password];
}
'''


def replace_once(path: Path, needle: str, addition: str, *, after=False):
    text=path.read_text()
    assert text.count(needle)==1, f"Pinned LC changed: {path}:{needle[:65]}"
    path.write_text(text.replace(needle,needle+addition if after else addition+needle,1))


def attach_p94_zsign_public_der(engine: Path) -> dict:
    zsign=engine/'ZSign/zsign.mm'
    zheader=engine/'ZSign/zsigner.h'
    lcutils=engine/'LiveContainerSwiftUI/Utilities/LCUtils.m'
    lcheader=engine/'LiveContainerSwiftUI/Utilities/LCUtils.h'
    assert all(p.is_file() for p in (zsign,zheader,lcutils,lcheader))
    replace_once(zsign,'+ (NSString*)getTeamIdWithCert:(NSData *)cert pass:(NSString *)pass {',Z_IMPL+'\n')
    replace_once(zheader,'+ (NSString*)getTeamIdWithCert:(NSData *)cert pass:(NSString *)pass;',
      '\n+ (NSData *)scarletCertificateDERWithCert:(NSData *)p12 pass:(NSString *)password;',after=True)
    replace_once(lcutils,'+ (NSString*)getCertTeamIdWithKeyData:(NSData*)keyData password:(NSString*)password {',UTILS_IMPL+'\n')
    replace_once(lcheader,'+ (NSString*)getCertTeamIdWithKeyData:(NSData*)keyData password:(NSString*)password;',
      '\n+ (NSData *)scarletCertificateDERWithKeyData:(NSData *)keyData password:(NSString *)password;',after=True)
    return {'certificate_der_only':True,'original_zsign_parser':True,
            'private_key_exported':False,
            'zsign_sha256':hashlib.sha256(zsign.read_bytes()).hexdigest()}

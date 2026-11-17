"""P101 Python port of the Swift TBSCertificate DER time parser; OpenSSL crosscheck."""
import datetime as dt
import pathlib
import ssl
import subprocess
import tempfile
import unittest


def tlv(b, pos, limit):
    if pos < 0 or limit > len(b) or limit-pos < 2:
        raise ValueError('short TLV header')
    tag = b[pos]
    i = pos + 1
    first = b[i]
    i += 1
    length = first
    if first >= 0x80:
        n = first & 0x7f
        if n == 0 or n > 4 or n > limit-i or b[i] == 0:
            raise ValueError('noncanonical TLV length')
        length = 0
        for _ in range(n):
            length = (length << 8) | b[i]
            i += 1
        if length < 128:
            raise ValueError('noncanonical long length')
    if length > limit-i:
        raise ValueError('truncated TLV')
    return tag, i, i+length


def parse_time(tag, field):
    if tag not in (0x17, 0x18):
        raise ValueError('invalid X509 time tag')
    field = field.decode('ascii')
    year_len = 2 if tag == 0x17 else 4
    if len(field) != (13 if year_len == 2 else 15) or field[-1] != 'Z' or not field[:-1].isascii() or not field[:-1].isdigit():
        raise ValueError('invalid X509 time')
    year = int(field[:year_len])
    if year_len == 2:
        year += 1900 if year >= 50 else 2000
    n = [int(field[i:i+2]) for i in range(year_len, year_len+10, 2)]
    return dt.datetime(year, *n, tzinfo=dt.timezone.utc)


def validity_window(der):
    tag, start, end = tlv(der, 0, len(der))
    if tag != 0x30 or end != len(der):
        raise ValueError('invalid certificate')
    tag, tbsstart, tbsend = tlv(der, start, end)
    if tag != 0x30:
        raise ValueError('invalid TBS')
    cursor = tbsstart
    tag, valstart, valend = tlv(der, cursor, tbsend)
    if tag == 0xa0:
        cursor = valend
        tag, valstart, valend = tlv(der, cursor, tbsend)
    if tag != 0x02:
        raise ValueError('missing serial')
    tag, _, cursor = tlv(der, valend, tbsend)
    if tag != 0x30:
        raise ValueError('missing signature algorithm')
    tag, _, cursor = tlv(der, cursor, tbsend)
    if tag != 0x30:
        raise ValueError('missing issuer')
    tag, valstart, valend = tlv(der, cursor, tbsend)
    if tag != 0x30:
        raise ValueError('missing validity')
    btag, bs, be = tlv(der, valstart, valend)
    atag, ans, ane = tlv(der, be, valend)
    if ane != valend:
        raise ValueError('extra validity fields')
    before, after = parse_time(btag, der[bs:be]), parse_time(atag, der[ans:ane])
    if before >= after:
        raise ValueError('reversed validity')
    return before, after


class X509ValidityAlgorithm(unittest.TestCase):
    @staticmethod
    def certificate(days):
        with tempfile.TemporaryDirectory() as d:
            pem = pathlib.Path(d) / 'cert.pem'
            key = pathlib.Path(d) / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048',
                '-nodes', '-keyout', str(key), '-out', str(pem), '-sha256',
                '-subj', '/CN=Scarlet P101 X509 parser', '-days', str(days)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            der = ssl.PEM_cert_to_DER_cert(pem.read_text())
            result = subprocess.run(['openssl', 'x509', '-in', str(pem),
                '-noout', '-enddate'], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, check=True)
            openssl_end = dt.datetime.strptime(result.stdout.strip().split('=', 1)[1],
                '%b %d %H:%M:%S %Y GMT').replace(tzinfo=dt.timezone.utc)
        return der, openssl_end

    def test_utctime_certificate_90_days(self):
        der, openssl_end = self.certificate(90)
        before, after = validity_window(der)
        self.assertLess(before, after)
        self.assertEqual(after, openssl_end)
        self.assertLess(after.year, 2050)

    def test_generalizedtime_certificate_after_2050(self):
        der, openssl_end = self.certificate(14600)
        before, after = validity_window(der)
        self.assertLess(before, after)
        self.assertEqual(after, openssl_end)
        self.assertGreater(after.year, 2049)

    def test_truncated_and_garbage_input_is_rejected(self):
        der, _ = self.certificate(90)
        for damaged in (b'', b'123', b'\x30\x80', der[:20], der[:-1],
                        b'\x30\x81\x01\x00', b'\x30\x82\x00\x05\x30\x00',
                        der + b'\x00'):
            with self.subTest(damaged=damaged[:8]), self.assertRaises(ValueError):
                validity_window(damaged)


if __name__ == '__main__':
    unittest.main()

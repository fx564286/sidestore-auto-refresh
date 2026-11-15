"""P79: distinct tested runtime change for P78 device archive + statusbar failures."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/'integration/apply_scarlet_host.py').read_text()
H=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P=G.split('def add_r6p79_mapped_archive_fallback(',1)[1].split('def hide_embedded_sidestore_guest_navigation(',1)[0]
class P79SignedDeviceFourImports(unittest.TestCase):
 def test_real_p78_error_is_before_sign_or_overwrite(self):
  # Device log 3.8.78: 4 file_staged followed by 4 failures Swift.String code1;
  # 2..3ms after file_import_requested, never reached original signing.
  self.assertIn('let result = extract(path, destination, progress)',P)
  self.assertIn('guard result != 0 else { return result }',P)
  self.assertIn('let fallback = scarletExtractGuestIPAFromMappedData(path, destination, progress)',P)
  self.assertIn('return fallback == 0 ? 0 : result',P)
  self.assertIn('hasPrefix("scarlet-guest-")',P)
 def test_zip_fallback_reuses_existing_native_archive_unit_and_preserves_paths(self):
  for x in ('LiveContainerSwiftUI/Utilities/unarchive.m',
             'LiveContainerSwiftUI/Utilities/unarchive.h',
             'archive_read_open_memory(reader,mapped.bytes,mapped.length)',
             'NSDataReadingMappedIfSafe',
             'archive_read_support_format_zip(reader)',
             'archive_write_disk_new()',
             'archive_entry_filetype(entry)==AE_IFLNK',
             '[relative hasPrefix:@"/"]',
             '[parts containsObject:@".."]',
             'hasAppPlist && entries<=80000',
             'return (ok && wrote) ? 0 : 1;',
             'target.write_text(source+',
):
   self.assertIn(x,P,x)
  self.assertIn('guest_archive_recovery=add_r6p79_mapped_archive_fallback(engine)',G)
  self.assertNotIn('relative.hasPrefix(@"/")', P)
  for forbidden in ('removeItem(at: outputFolder)', 'SecItemDelete',
                    'deleteCertificate', 'removeItem(at: fileUrl)'):
   self.assertNotIn(forbidden,P)
 def test_statusbar_release_is_after_two_verified_native_samples(self):
  start=H.index('func acceptVerifiedPostHeaderStatusband(')
  stop=H.index('// R6P56:',start)
  section=H[start:stop]
  first=section.index('guard nativeStatusBandFirstPassPIDs.remove(pid) != nil else { return }')
  release=section.index('nativeStatusBarCollisionShield = false')
  invalidate=section.index('host.setNeedsStatusBarAppearanceUpdate()')
  self.assertLess(first,release)
  self.assertLess(release,invalidate)
  for x in ('headerVerified && complete && severe == 0',
            '$0.isKeyWindow && $0.windowLevel == .normal',
            'self.activeID == activeID',
            '!self.nativeStatusBarCollisionShield',
            'resident_native_status_band_readback'):
   self.assertIn(x,section,x)
 def test_p79_workflow_artifact(self):
  for x in ('fix/scarlet-v48-r6p79-import-archive-status-20261116',
            '--host-build-version 3.8.79', '"r6p79"',
            'Scarlet-Crystal-V48-R6P79-IMPORT-STATUS-UNSIGNED.ipa',
            'scarlet-v48-r6p79-import-status-unsigned-20261116'):
   self.assertIn(x,W,x)
if __name__=='__main__': unittest.main()

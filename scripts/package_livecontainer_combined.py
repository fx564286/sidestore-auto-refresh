"""Run pinned upstream combined packaging using the locally patched SideStore."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import zipfile

from audit_ipa_signing import inventory

REQUIRED_SIDESTORE_INTENT_SYMBOLS = (
    b"9SideStore20RefreshAllAppsIntentV",
    b"9SideStore26RefreshAllAppsWidgetIntentV",
)
REQUIRED_HOST_INTENT_SYMBOLS = (
    b"16SideStoreSupport20RefreshAllAppsIntentV",
    b"16SideStoreSupport26RefreshAllAppsWidgetIntentV",
)
REQUIRED_SIDESTORE_AUTH_ANSWER_MARKERS = (
    b"V3SideStoreService",
    b"execute:reply:",
    b"authRespond",
)


def verify_versioned_picker_markers(version, host_code, bootstrap_code):
    if version in ('3.8.228', '3.8.229'):
        # V155 compiled one LiveProcess route and deleted the Direct handler.
        required_host = (
            b'[SCARLET_V144_GLASS_INSTALLED]',
            b'[SCARLET_V149_TABS] style=system_native',
            b'[SCARLET_V149_ACTION_GLASS] action=',
            b'[SCARLET_V150_OUTSIDE] phase=touch_down',
            b'[SCARLET_V154_OUTSIDE] stage=backdrop_touch',
            b'[SCARLET_V155_SINGLE] stage=guest_launch route=LiveProcess',
        )
        for token in required_host:
            if token not in host_code:
                raise ValueError('V155 compiled LiveProcess marker missing: '+repr(token))
        if b'[SCARLET_V155_SINGLE] stage=bootstrap result=direct_rejected' not in bootstrap_code:
            raise ValueError('V155 Direct bootstrap rejection not compiled')
        for old in (b'SCGuestMorphPresenter', b'scarlet.v105.direct.morph',
                    b'scarletcrystal251://nrg-guest-controls',
                    b'[SCARLET_V154_DIRECT_TAP_RECOGNIZER]'):
            if old in bootstrap_code:
                raise ValueError('V155 retired Direct backend still compiled: '+repr(old))
        for old in (b'[SCARLET_V153_DIRECT] route=host mode=direct',
                    b'[SCARLET_V154_DIRECT] stage=panel_visible'):
            if old in host_code:
                raise ValueError('V155 retired Direct host route compiled: '+repr(old))
        if version == '3.8.229':
            for marker in (
                b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=backdrop_received',
                b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=window_should_receive',
                b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_completed',
            ):
                if marker not in host_code:
                    raise ValueError('V156 compiled outside touch trace missing: '+repr(marker))
        return
    """Validate the compiled picker for each version's ACTUAL surviving routes.

    V149 replaces V147's one-time UIWindow observer with a dynamic window
    observer. Requiring the removed V147 log was causing otherwise successful
    Xcode builds to fail packaging. Do not make V147/V148 weaker: both still
    require their own old observer marker. Do not infer a live UI pass from
    compiled marker presence alone.
    """
    if version not in ('3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227'):
        return
    common_host = (
        b'[SCARLET_V147_GLASS] panel=clear tabs=native rows=native',
        b'[SCARLET_V147_DIRECT] route=host result=presented',
        b'[SCARLET_V147_ACTION_GLASS] button=',
    )
    for marker in common_host:
        if marker not in host_code:
            raise ValueError('Picker compiled host marker missing: '+repr(marker))
    if b'[SCARLET_V147_DIRECT] event=tap' not in bootstrap_code:
        raise ValueError('V147 compiled Direct button marker missing')
    if version in ('3.8.220', '3.8.221'):
        if b'[SCARLET_V147_OUTSIDE] monitors=' not in host_code:
            raise ValueError('V147/V148 compiled original outside observer missing')
    if version in ('3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227'):
        if b'[SCARLET_V148_ACTION_GLASS] action=' not in host_code:
            raise ValueError('V148 compiled native window-action glass missing')
    if version == '3.8.222':
        for marker in (
            b'[SCARLET_V149_TABS] style=system_native',
            b'[SCARLET_V149_ACTION_GLASS] action=',
            b'[SCARLET_V149_OUTSIDE] monitor_attached',
            b'[SCARLET_V149_OUTSIDE] scene_monitor_count=',
        ):
            if marker not in host_code:
                raise ValueError('V149 compiled picker control/observer missing: '+repr(marker))
    if version in ('3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227'):
        # V150 replaces old observer's attachment log and preserves V149
        # count. Demand ACTIVE long press and first-contact observations.
        for marker in (
            b'[SCARLET_V149_TABS] style=system_native',
            b'[SCARLET_V149_ACTION_GLASS] action=',
            b'[SCARLET_V149_OUTSIDE] scene_monitor_count=',
            b'[SCARLET_V150_LONG_PRESS] phase=bulge',
            b'[SCARLET_V150_LONG_PRESS] phase=release',
            b'[SCARLET_V150_OUTSIDE] phase=touch_down',
            b'[SCARLET_V150_TABS_UNIFIED] tint=translucent',
        ):
            if marker not in host_code:
                raise ValueError('V150 compiled touch/glass control missing: '+repr(marker))
    if version in ('3.8.224', '3.8.225', '3.8.226', '3.8.227'):
        # Current binary must keep V150 outside touch + prove the V151
        # capsule tab/row press and the host/guest geometry parity markers.
        for marker in (
            b'[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1',
            b'[SCARLET_V151_ROW_PRESS] phase=pressed',
            b'[SCARLET_V151_ORIENTATION_PARITY] host=',
            b'[SCARLET_V151_FRAME_TOUCH_PARITY] host=',
            b'[SCARLET_V151_CONTENT_STALE] host=',
        ):
            if marker not in host_code:
                raise ValueError('V151 compiled glass/geometry marker missing: '+repr(marker))
    if version in ('3.8.226','3.8.227'):
        # V153 keeps V152's native parent glass and original Direct handle.
        for token in (b'[SCARLET_V153_RECENT_UNCLIPPED] press=native_glass',
                      b'[SCARLET_V153_DIRECT] host_anchor_visible=1'):
            if token not in host_code:
                raise ValueError('V153 compiled picker marker missing: '+repr(token))
        if b'[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked' not in host_code:
            raise ValueError('V153 compiled host Direct routing missing')
    if version == '3.8.227':
        for token in (b'[SCARLET_V154_OUTSIDE] stage=backdrop_touch',
                      b'[SCARLET_V154_DIRECT] stage=panel_visible',
                      b'[SCARLET_V154_DIRECT_TAP_RECOGNIZER]'):
            code = bootstrap_code if b'TAP_RECOGNIZER' in token else host_code
            if token not in code:
                raise ValueError('V154 compiled runtime marker missing: '+repr(token))




def verify_side_store_intent_runtime_symbols(executable):
    missing = [symbol.decode("ascii") for symbol in REQUIRED_SIDESTORE_INTENT_SYMBOLS
               if symbol not in executable]
    if missing:
        raise ValueError("headless backend is missing host App Intent runtime adapters: " + ", ".join(missing))


def verify_host_intent_runtime_symbols(executable):
    missing = [symbol.decode("ascii") for symbol in REQUIRED_HOST_INTENT_SYMBOLS
               if symbol not in executable]
    if missing:
        raise ValueError("SideStoreSupport is missing metadata-targeted App Intent wrappers: " + ", ".join(missing))


def verify_auth_answer_transport(host_executable, side_executable, support_executable):
    """Require linked auth request route, service dispatcher, and XPC endpoint.

    These archive markers only establish that the expected entry points and
    operation route are present in the images. Source-backed contract tests
    verify that the route validates and forwards the bounded answer; marker
    presence alone is not runtime evidence.
    """
    if b"authRespond" not in host_executable:
        raise ValueError("host auth answer request route is missing")
    missing_service = [marker.decode("ascii") for marker in REQUIRED_SIDESTORE_AUTH_ANSWER_MARKERS
                       if marker not in side_executable]
    if missing_service:
        raise ValueError("embedded SideStore is missing current auth answer dispatcher markers: "
                         + ", ".join(missing_service))
    if b"v3Execute:reply:" not in support_executable:
        raise ValueError("XPC command endpoint is missing")


def verify_shared_secret_handoff_group(host_groups, live_process_groups):
    if not isinstance(host_groups, list) or not isinstance(live_process_groups, list):
        raise ValueError("host and LiveProcess Keychain access groups are missing")
    suffix = ".com.kdt.livecontainer.shared"
    shared = [group for group in host_groups
              if isinstance(group, str) and group.endswith(suffix) and group in live_process_groups]
    if len(shared) != 1:
        raise ValueError("host and LiveProcess must share the dedicated entitled Keychain group")
    return shared[0]


def verify_v105_direct_morph_binary(bootstrap_code, *, v137=False):
    """Require the actual compiled entry control expected by the package.

    V137 replaces the legacy Direct-only V105 button with one shared
    Direct/LiveProcess control. Do not accept the old button marker in a
    V137 archive and do not silently fall back to legacy checks.
    """
    if v137:
        required = (b'SCGuestMorphPresenter',
                    b'scarlet.v137.shared.guest.control',
                    b'[SCARLET_V137_FINGER_GLASS]')
        for marker in required:
            if marker not in bootstrap_code:
                raise ValueError("V137 compiled shared guest entry missing: " + marker.decode())
        if b'scarlet.v105.direct.morph' in bootstrap_code:
            raise ValueError("V137 contains obsolete Direct-only guest button")
    else:
        required = (b'SCGuestMorphPresenter',
                    b'scarlet.v105.direct.morph',
                    b'[SCARLET_V105_CONTROL]')
        for marker in required:
            if marker not in bootstrap_code:
                raise ValueError("V105 compiled Direct morph missing: " + marker.decode())
    for retired in (b'LCDirectReturnPresenter', b'LCDirectReturnControl'):
        if retired in bootstrap_code:
            raise ValueError("V107 obsolete Direct guest control was compiled")


def verify_v107_virtual_guest_control_binary(host_code, *, v137=False):
    """Reject retired controls in V137; require the historic owner before V137.

    V137 uses the single compiled SCGuestMorphPresenter verified separately in
    LiveContainerShared. The old V103 virtual marker must not be demanded in
    LiveContainerSwiftUI after its source has been deleted.
    Use null-delimited Objective-C symbols to avoid false positive preference keys.
    """
    required = b'scarlet.v103.virtual.guest.control'
    if v137:
        if required in host_code:
            raise ValueError("V137 obsolete virtual guest control was compiled")
    elif required not in host_code:
        raise ValueError("V107 host-owned virtual guest control missing")
    import re
    legacy = (b'LCReturnControl', b'lcReturnControl', b'lcReturnToHost')
    for symbol in legacy:
        if re.search(rb'(?<![A-Za-z0-9_])' + symbol + rb'\x00', host_code):
            raise ValueError("V107 obsolete native guest return symbol compiled: " + symbol.decode())


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Upstream packaging anchor changed: {old}')
    return text.replace(old, new, 1)


def adapt(text):
    # NRG_V58_DYLIBIFY_HOST_ARCH: the v1.0 release binary is arm64-only.
    # Build its exact tagged source for the CI Mac host (Intel or Apple Silicon).
    # This tool modifies the iOS Mach-O payload but itself runs on macOS.
    if 'wget https://github.com/LiveContainer/dylibify/releases/download/1.0/dylibify' in text:
        text = replace_once(text,
            'wget https://github.com/LiveContainer/dylibify/releases/download/1.0/dylibify\nchmod +x dylibify',
            '''git clone --quiet --depth 1 --branch 1.0 https://github.com/LiveContainer/dylibify.git ./dylibify-src
test "$(git -C ./dylibify-src rev-parse HEAD)" = "5daf713df9fb07724510490c88aa8e00061be14a"
clang -arch "$(uname -m)" -framework Foundation -fobjc-arc ./dylibify-src/main.m -o ./dylibify
lipo ./dylibify -verify_arch "$(uname -m)"
echo "[NRG_V58_DYLIBIFY] macos_host_arch=$(uname -m) source_tag=1.0"''')
    elif '# copy lc' in text:
        raise ValueError("Pinned upstream dylibify tool bootstrap changed")
    text = replace_once(text, 'brew install ldid', 'command -v ldid >/dev/null')
    text = replace_once(text, 'wget https://github.com/LiveContainer/SideStore/releases/download/nightly/SideStore.ipa',
                        'cp "$PATCHED_SIDESTORE_IPA" SideStore.ipa')
    # NRG_WIDGETLESS_V46: the SideStore widget is an independent extension.
    # Drop it from the embedded framework rather than renaming it and creating
    # another free-team App ID. Keep SideStore's host App Intent wrappers.
    widget_copy = '# AltWidgetExtension\nmv ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/PlugIns/AltWidgetExtension.appex ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex\n/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.kdt.livecontainer.LiveWidget"  ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex/Info.plist\n/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable LiveWidgetExtension"  ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex/Info.plist\nmv ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex/AltWidgetExtension ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex/LiveWidgetExtension\n'
    # SCARLET_V107_RETIRE_WIDGET_PATH: no secondary widget App ID or
    # historically retained native-Island packaging route is supported.
    if os.environ.get("NRG_V58_NATIVE_ISLAND") == "1":
        raise ValueError("V107 rejects obsolete native-Island widget packaging")
    if widget_copy in text:
        text = replace_once(text, widget_copy,
            '# NRG_WIDGETLESS_V46: do not install LiveWidget.\n'
            'rm -rf ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/PlugIns/AltWidgetExtension.appex\n')
        text = replace_once(text,
            'ldid -S.github/sidelc/LiveWidgetExtension_adhoc.xml ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex/LiveWidgetExtension',
            'test ! -e ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex')
    elif 'AltWidgetExtension' in text or 'LiveWidgetExtension' in text:
        raise ValueError('Pinned widget packaging changed; refusing to include an unreviewed extension')
    text = replace_once(text, '# package\n',
        'test ! -e ./Payload/LiveContainer.app/PlugIns/LiveWidgetExtension.appex\n'
        'test ! -e ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/PlugIns/AltWidgetExtension.appex\n'
        '# package\n')
    text = replace_once(text, 'rm -r .zsign_cache', '# No zsign cache exists in the fresh packaging workspace.')
    text = replace_once(text, 'find payloadlc/Payload -type d -name "_CodeSignature" -exec rm -r {} +',
                        'find Payload -type d -name "_CodeSignature" -prune -exec rm -r {} +')
    text = replace_once(text,
        '''# copy intents
cp ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Intents.intentdefinition ./Payload/LiveContainer.app/
cp ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/ViewApp.intentdefinition ./Payload/LiveContainer.app/
cp -r ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Metadata.appintents ./Payload/LiveContainer.app/Metadata.appintents
sed -i '' 's/9SideStore20RefreshAllAppsIntentV/16SideStoreSupport20RefreshAllAppsIntentV/g' ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata
sed -i '' 's/9SideStore26RefreshAllAppsWidgetIntentV/16SideStoreSupport26RefreshAllAppsWidgetIntentV/g' ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata
''',
        '''# Stage the host App Intents schemas/metadata from the headless service build,
# then remove these packaging inputs from the embedded backend framework.
cp ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Intents.intentdefinition ./Payload/LiveContainer.app/
cp ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/ViewApp.intentdefinition ./Payload/LiveContainer.app/
cp -r ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Metadata.appintents ./Payload/LiveContainer.app/Metadata.appintents
sed -i '' 's/9SideStore20RefreshAllAppsIntentV/16SideStoreSupport20RefreshAllAppsIntentV/g' ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata
sed -i '' 's/9SideStore26RefreshAllAppsWidgetIntentV/16SideStoreSupport26RefreshAllAppsWidgetIntentV/g' ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata
rm -f ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Intents.intentdefinition
rm -f ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/ViewApp.intentdefinition
rm -rf ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Metadata.appintents
''')
    if os.environ.get("NRG_V66_4IDS") == "1":
        # Preserve host-native App Intent metadata before the upstream SideStore
        # actionsdata replaces the main app's metadata directory.
        text = replace_once(
            text,
            '# Stage the host App Intents schemas/metadata from the headless service build,',
            '# NRG_V66_FOUR_IDS: preserve host AppIntent metadata.\n'
            'test -s ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata\n'
            'cp ./Payload/LiveContainer.app/Metadata.appintents/extract.actionsdata ./tmp/nrg-v66-host.actionsdata\n'
            'rm -rf ./Payload/LiveContainer.app/Metadata.appintents\n'
            '# Stage the host App Intents schemas/metadata from the headless service build,')
        text = replace_once(
            text,
            'rm -rf ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Metadata.appintents\n',
            'rm -rf ./Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/Metadata.appintents\n'
            'python3 "$COMBINED_PACKAGER" --merge-host-intents '
            './Payload/LiveContainer.app ./tmp/nrg-v66-host.actionsdata\n')
        text = replace_once(
            text, '# package\n',
            '# NRG_V66_FOUR_IDS: retain host, LiveProcess, Share, native Island.\n'
            'rm -rf ./Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex\n'
            'test ! -e ./Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex\n'
            '# package\n')
    if os.environ.get('NRG_V67_3IDS') == '1':
        from patch_v67_three_ids import assert_invariants
        assert_invariants()
        text = replace_once(text, '# package\n',
            '# NRG_V67_THREE_IDS: public.item/Files replaces Share sheet target.\n'
            'python3 "$V67_PATCH" --check ./Payload/LiveContainer.app\n'
            'rm -rf ./Payload/LiveContainer.app/PlugIns/ShareExtension.appex\n'
            'test ! -e ./Payload/LiveContainer.app/PlugIns/ShareExtension.appex\n'
            '# package\n')
    text = replace_once(text, '# package\n',
                        'python3 "$COMBINED_PACKAGER" --prepare-entitlements . Payload/LiveContainer.app\n\n# package\n')
    return 'set -eu\n' + text


def merge_host_intents(app: Path, host_metadata: Path) -> None:
    # Xcode's actionsdata is JSON; preserve all SideStore actions and add the
    # app's native AppIntent without blindly swapping the full metadata tree.
    staged = app / 'Metadata.appintents' / 'extract.actionsdata'
    side = json.loads(staged.read_text())
    host = json.loads(host_metadata.read_text())
    actions = host.get('actions', {})
    if 'ScarletCrystalLaunchAppIntent' not in actions:
        raise ValueError('Xcode omitted V66 app-hosted Launch App intent metadata')
    # The SideStore action dictionary uses Xcode-generated action identifiers,
    # NOT the Swift struct name: it is incorrect to require a key literally
    # named RefreshAllAppsIntent. Check the actual runtime binding instead.
    side_actions = side.get('actions')
    if not isinstance(side_actions, dict) or not side_actions:
        raise ValueError('Existing SideStore actions metadata empty')
    serialized = json.dumps(side, ensure_ascii=False)
    for marker in ('16SideStoreSupport20RefreshAllAppsIntentV',
                   '16SideStoreSupport26RefreshAllAppsWidgetIntentV'):
        if marker not in serialized:
            raise ValueError('Existing SideStore runtime action marker missing: ' + marker)
    overlap = set(side_actions) & set(actions)
    if overlap:
        raise ValueError('Colliding App Intent action identifiers: ' + ', '.join(sorted(overlap)))
    side_actions.update(actions)
    # The data extractor's companion definitions may be dictionaries or lists.
    # Do not assume all top-level metadata collections share the same shape.
    for key in ('entities', 'queries', 'enums', 'assistantEntities', 'assistantIntents',
                'assistantDefinedSchemas', 'autoShortcuts', 'assistantIntentNegativePhrases'):
        extra = host.get(key)
        if isinstance(extra, dict):
            target = side.setdefault(key, {})
            if not isinstance(target, dict):
                raise ValueError('Incompatible App Intents metadata shape: ' + key)
            for identifier, entry in extra.items():
                if identifier in target and target[identifier] != entry:
                    raise ValueError('Conflicting App Intents metadata for: ' + identifier)
                target[identifier] = entry
        elif isinstance(extra, list) and extra:
            target = side.setdefault(key, [])
            if not isinstance(target, list):
                raise ValueError('Incompatible App Intents metadata shape: ' + key)
            for entry in extra:
                if entry not in target:
                    target.append(entry)
    staged.write_text(json.dumps(side, separators=(',', ':'), ensure_ascii=False))
    merged = json.loads(staged.read_text())
    if 'ScarletCrystalLaunchAppIntent' not in merged.get('actions', {}):
        raise ValueError('Merged Launch App intent missing')
    for marker in ('16SideStoreSupport20RefreshAllAppsIntentV',
                   '16SideStoreSupport26RefreshAllAppsWidgetIntentV'):
        if marker not in json.dumps(merged):
            raise ValueError('SideStore action damaged during merge: ' + marker)


def prepare_entitlements(root, app):
    sources = {
        '': 'entitlements.xml',
        'PlugIns/LiveProcess.appex': 'LiveProcess/LiveProcess.entitlements',
        **({} if os.environ.get('NRG_V67_3IDS') == '1' else {'PlugIns/ShareExtension.appex': 'ShareExtension/ShareExtension.entitlements'}),
        **({} if os.environ.get('NRG_V66_4IDS') == '1' else {
            'PlugIns/LaunchAppExtension.appex': 'LaunchAppExtension/LaunchAppExtension.entitlements'
        }),
    }
    for relative, source in sources.items():
        bundle = app / relative
        info = plistlib.loads((bundle / 'Info.plist').read_bytes())
        xml = (root / source).read_text()
        values = {'DEVELOPMENT_TEAM': 'AAAAA11111', 'AppIdentifierPrefix': 'AAAAA11111.',
                  'PRODUCT_BUNDLE_IDENTIFIER': info['CFBundleIdentifier'],
                  'APP_GROUP_SIDESTORE': 'group.com.SideStore.SideStore',
                  'APP_GROUP_ALTSTORE': 'group.com.rileytestut.AltStore'}
        for key, value in values.items():
            xml = xml.replace('$(' + key + ')', value)
        if '$(' in xml:
            raise ValueError(f'Unresolved entitlement setting: {source}')
        entitlement = root / 'tmp' / (info['CFBundleExecutable'] + '.entitlements')
        entitlement.write_bytes(plistlib.dumps(plistlib.loads(xml.encode())))
        subprocess.run(['ldid', '-S' + str(entitlement), str(bundle / info['CFBundleExecutable'])], check=True)
    share_packaged_app_groups(app)


def share_packaged_app_groups(app):
    """Give every extension the host's packaged App Group fallback list.

    The host and the embedded service each resolve the shared store from their
    OWN Bundle.main. When the host publishes its selection the service inherits
    it and the fallback never runs, but a launch that published nothing would
    have the host rank its Info.plist ALTAppGroups while the service, running in
    LiveProcess, ranked an empty list and reported no shared store at all. The
    same list in both processes makes the fallback agree, and it is only a
    preference: the ranking still requires the group to be entitled, which
    prepare_entitlements signs in.
    """
    host_info = plistlib.loads((app / 'Info.plist').read_bytes())
    packaged = host_info.get('ALTAppGroups')
    if not isinstance(packaged, list) or not packaged:
        raise ValueError('the host declares no packaged App Group fallback')
    for extension in sorted(p for p in app.glob('PlugIns/*.appex')
                            if (p / 'Info.plist').exists()):
        path = extension / 'Info.plist'
        info = plistlib.loads(path.read_bytes())
        if info.get('ALTAppGroups') == packaged:
            continue
        info['ALTAppGroups'] = packaged
        path.write_bytes(plistlib.dumps(info, sort_keys=False))


def verify(path, side_product=None):
    result = inventory(path)
    bundles = result['bundles']
    base = 'Payload/LiveContainer.app'
    host = bundles[base]['info']
    embedded = base + '/Frameworks/SideStoreApp.framework'
    assert bundles[embedded]['info']['CFBundleIdentifier'] == 'com.SideStore.SideStore', 'iLoader SideStoreLc recognition'
    assert bundles[embedded]['executable_present']
    # Hard-fail if upstream starts shipping the widget again under another path.
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        # SCARLET_V107_WIDGETLESS_RELEASE_ONLY: inspect the actual archive,
        # never let an environment flag re-enable an abandoned extension.
        forbidden_widget = [name for name in names if
                            '/AltWidgetExtension.appex/' in name or
                            '/LiveWidgetExtension.appex/' in name]
    if forbidden_widget:
        raise ValueError('Widget extension leaked into packaged IPA: ' + forbidden_widget[0])
    live_process_path = base + '/PlugIns/LiveProcess.appex'
    shared_keychain_group = verify_shared_secret_handoff_group(
        bundles[base]['signing']['xml_entitlements'].get('keychain-access-groups'),
        bundles[live_process_path]['signing']['xml_entitlements'].get('keychain-access-groups'))
    with zipfile.ZipFile(path) as archive:
        executable = archive.read(embedded + '/SideStore')
        assert executable[:4] == b'\xcf\xfa\xed\xfe', 'Expected arm64 Mach-O'
        assert struct.unpack_from('<I', executable, 12)[0] == 6, 'SideStore must be MH_DYLIB'
        verify_side_store_intent_runtime_symbols(executable)
        assert archive.read(embedded + '/LCAppInfo.plist')
        assert b'liveContainerAutoRefreshVerification' in executable, 'Patched embedded operation missing'
        host_code = archive.read(base + '/Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI')
        assert b'liveContainerAutoRefresh' in host_code, 'Host automation missing'
        assert b'V3_UNIFIED_SHELL_V1' in host_code, 'Unified v3 host shell missing'
        # Optimized Swift may encode short URL strings as SmallString immediate
        # constants instead of contiguous bytes. Test the long runtime log
        # marker added to the compiled guest route instead.
        if b'[NRG_V60_GUEST_ROUTE_EXECUTED]' not in host_code:
            raise ValueError('Shipped host binary lacks executable V60 guest-route diagnostics')
        for diagnostic in (b'NRG_V58_VIEWPORT', b'NRG_V196_PORTRAIT_SAFEAREA'):
            if diagnostic not in host_code:
                raise ValueError('Shipped host binary missing fullscreen runtime: ' + diagnostic.decode())
        assert b'v3SideStoreStatusSnapshot' not in executable, 'Retired status publisher remains'
        # V105: old LCReturnControl was deleted from generated Objective-C.
        # Host virtual guest switches use the retained V102 morph; the separate
        # Classic/Direct fallback is verified in its compiled bootstrap binary.
        bootstrap_code = archive.read(base + '/Frameworks/LiveContainerShared.framework/LiveContainerShared')
        support_code = archive.read(base + '/Frameworks/SideStoreSupport.framework/SideStoreSupport')
        verify_host_intent_runtime_symbols(support_code)
        verify_auth_answer_transport(host_code, executable, support_code)
        assert b'Import Pairing File' in host_code, 'Unified pairing setup missing'
        # Use the installed host's stamped version, NOT a guessed marker,
        # to choose fail-closed V137 versus historical V105 binary contracts.
        version = str(host.get('CFBundleVersion', ''))
        build_label = host.get('ScarletBuildLabel')
        if version == '3.8.210' and build_label != 'V137':
            raise ValueError('V137 packaged version is missing its explicit build identity')
        if version == '3.8.211' and build_label != 'V138':
            raise ValueError('V138 packaged version is missing its explicit build identity')
        if version == '3.8.212' and build_label != 'V139':
            raise ValueError('V139 packaged version is missing its explicit build identity')
        if version == '3.8.213' and build_label != 'V140':
            raise ValueError('V140 packaged version is missing its explicit build identity')
        if version == '3.8.214' and build_label != 'V141':
            raise ValueError('V141 packaged version is missing its explicit build identity')
        if version == '3.8.215' and build_label != 'V142':
            raise ValueError('V142 packaged version is missing its explicit build identity')
        if version == '3.8.216' and build_label != 'V143':
            raise ValueError('V143 packaged version is missing its explicit build identity')
        if version == '3.8.217' and build_label != 'V144':
            raise ValueError('V144 packaged version is missing its explicit build identity')
        if version == '3.8.229' and build_label != 'V156':
            raise ValueError('V156 build identity invalid')
        if version == '3.8.228' and build_label != 'V155':
            raise ValueError('V155 build identity invalid')
        if version == '3.8.227' and build_label != 'V154':
            raise ValueError('V154 build identity invalid')
        if version == '3.8.226' and build_label != 'V153':
            raise ValueError('V153 build identity invalid')
        if version == '3.8.225' and build_label != 'V152':
            raise ValueError('V152 build identity invalid')
        if version == '3.8.224' and build_label != 'V151':
            raise ValueError('V151 build identity invalid')
        if version == '3.8.223' and build_label != 'V150':
            raise ValueError('V150 build identity invalid')
        if version == '3.8.222' and build_label != 'V149':
            raise ValueError('V149 build identity invalid')
        if version == '3.8.221' and build_label != 'V148':
            raise ValueError('V148 package identity invalid')
        if version == '3.8.220' and build_label != 'V147':
            raise ValueError('V147 package identity invalid')
        v137_package = version == '3.8.210' and build_label == 'V137'
        if version not in ('3.8.228','3.8.229'):
            verify_v105_direct_morph_binary(bootstrap_code, v137=v137_package)
        verify_v107_virtual_guest_control_binary(host_code, v137=v137_package)
        if version == '3.8.211':
            # V138 must keep the functioning host-V73 compiled in SwiftUI
            # and an actionable Direct fallback in LiveContainerShared.
            if b'[SCARLET_V138_ACTION] fallback=host_link accepted=' not in bootstrap_code:
                raise ValueError('V138 Direct action fallback missing from actual app binary')
            if b'scarlet.v137.shared.guest.control' in bootstrap_code:
                raise ValueError('V138 inert V137 guest-only handle was compiled')
        if version in ('3.8.212', '3.8.213', '3.8.214', '3.8.215', '3.8.216', '3.8.217', '3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227'):
            # Real compiled markers, not source-only assertions.
            # Direct->host and LiveProcess->host terminate at the SAME picker.
            for label, image, markers in (
                ('Direct', bootstrap_code, (b'scarletcrystal251://nrg-guest-controls',
                    b'scarlet.v139.direct.glass.touch',
                    b'[SCARLET_V139_GLASS]')),
                ('hosted', host_code, (b'scarlet.v139.hosted.glass.touch',
                    b'[SCARLET_V139_GLASS]', b'SCARLET_V139_VIDEO')),
            ):
                for required in markers:
                    if required not in image:
                        raise ValueError(f'V139 compiled {label} action missing: {required!r}')
            if b'scarlet.v137.shared.guest.control' in bootstrap_code:
                raise ValueError('V139 obsolete unresponsive guest button compiled')
        if version in ('3.8.213', '3.8.214', '3.8.215', '3.8.216', '3.8.217', '3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227', '3.8.228'):
            if b'[SCARLET_V140_GLASS] panel=anchored_to_source' not in host_code:
                raise ValueError('V140 compiled host glass morph marker missing')
        if version in ('3.8.214', '3.8.215', '3.8.216', '3.8.217', '3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227', '3.8.228'):
            if b'[SCARLET_V141_PICKER] dismiss=outside_tap' not in host_code:
                raise ValueError('V141 compiled outside-tap dismissal marker missing')
        if version in ('3.8.216', '3.8.217', '3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227', '3.8.228'):
            if b'[SCARLET_V143_WINDOW] phase=clamped_edge' not in host_code:
                raise ValueError('V143 compiled edge-window guard missing')
        if version in ('3.8.217', '3.8.220', '3.8.221', '3.8.222', '3.8.223', '3.8.224', '3.8.225', '3.8.226', '3.8.227', '3.8.228'):
            if b'[SCARLET_V144_PICKER] outside_guard=window_attached' not in host_code:
                raise ValueError('V144 compiled window-level outside dismissal missing')
            if b'[SCARLET_V144_GLASS] phase=finger_moved' not in host_code:
                raise ValueError('V144 compiled finger-reactive glass missing')
            if version != '3.8.228' and b'[SCARLET_V144_BUTTON] lens=finger_response' not in bootstrap_code:
                raise ValueError('V144 compiled Direct button glass response missing')
            if b'[SCARLET_V144_BUTTON] lens=finger_response' not in host_code:
                raise ValueError('V144 compiled hosted button glass response missing')
        verify_versioned_picker_markers(version, host_code, bootstrap_code)
        assert b'finishRefresh:runID:verification:' in support_code, 'XPC result receiver missing'
        assert b'refreshAllAppsWithIdentifier:mangledTypeName:refreshRunID:' in support_code, 'XPC run identity missing'
        assert b'RESULT_RECEIVED' in support_code, 'Host result persistence missing'
        assert b'installSideStoreHooks' in bootstrap_code, 'Embedded SideStore hook invocation missing'
        assert b'EMBEDDED_SIDESTORE_STARTUP_FIX_V1' in support_code, 'Embedded SideStore startup fix missing'
        for name in ('Intents.intentdefinition', 'ViewApp.intentdefinition', 'Metadata.appintents/extract.actionsdata'):
            assert archive.read(base + '/' + name), name
        metadata = archive.read(base + '/Metadata.appintents/extract.actionsdata')
        assert b'16SideStoreSupport20RefreshAllAppsIntentV' in metadata
        assert b'9SideStore20RefreshAllAppsIntentV' not in metadata
        assert b'16SideStoreSupport26RefreshAllAppsWidgetIntentV' in metadata
        assert b'InstallIPAIntent' not in metadata, 'host metadata still exposes SideStore-owned IPA installation'
        if side_product:
            for source in side_product.rglob('*'):
                if not source.is_file() or 'PlugIns' in source.relative_to(side_product).parts:
                    continue
                relative = source.relative_to(side_product).as_posix()
                if relative in {'Intents.intentdefinition', 'ViewApp.intentdefinition'} or \
                        relative.startswith('Metadata.appintents/'):
                    continue
                if relative == 'SideStore' or '_CodeSignature' in relative:
                    continue
                assert archive.read(embedded + '/' + relative) == source.read_bytes(), relative
    registered_extensions = [('LiveProcess', 'LiveProcess')]
    if os.environ.get('NRG_V67_3IDS') != '1':
        registered_extensions.append(('ShareExtension', 'ShareExtension'))
    else:
        assert base + '/PlugIns/ShareExtension.appex' not in bundles, 'V67 Share extension must be absent'
    if os.environ.get('NRG_V66_4IDS') != '1':
        registered_extensions.append(('LaunchAppExtension', 'LaunchAppExtension'))
    else:
        assert base + '/PlugIns/LaunchAppExtension.appex' not in bundles, 'V66 Launcher must be absent'
    for extension, suffix in registered_extensions:
        bundle = bundles[base + '/PlugIns/' + extension + '.appex']
        assert bundle['executable_present']
        assert bundle['info']['CFBundleIdentifier'] == 'com.kdt.livecontainer.' + suffix
        assert bundle['signing']['xml_entitlements'].get('com.apple.security.application-groups')
    assert bundles[base]['signing']['xml_entitlements'].get('keychain-access-groups')
    assert host['ALTAppGroups'] == ['group.com.SideStore.SideStore']
    for extension, suffix in registered_extensions:
        # Every extension resolves the same packaged fallback list as the host,
        # so a launch that published no group cannot split the shared store.
        assert bundles[base + '/PlugIns/' + extension + '.appex']['info']['ALTAppGroups'] == host['ALTAppGroups'], \
            extension + ' packaged App Group fallback differs from the host'
    schemes = {s for entry in host['CFBundleURLTypes'] for s in entry['CFBundleURLSchemes']}
    assert {'livecontainer', 'sidestore', 'sidestore-com.kdt.livecontainer'} <= schemes
    assert {'RefreshAllIntent', 'ViewAppIntent'} <= set(host['INIntentsSupported'])
    assert {'RefreshAllIntent', 'ViewAppIntent'} <= set(host['NSUserActivityTypes'])
    assert len(host['BGTaskSchedulerPermittedIdentifiers']) == 2
    assert 'processing' in host['UIBackgroundModes']
    result['semantic_verification'] = 'passed; device signing and runtime unverified'
    result['iloader_special_app'] = 'SideStoreLc'
    # V66: main-app AppIntent replaces Launcher, retaining the Island widget.
    # Zero additional LiveWidget registrations under every supported build.
    if os.environ.get('NRG_V58_NATIVE_ISLAND') == '1':
        raise ValueError('V107 obsolete native-Island registration is unsupported')
    result['registration_targets_before_reuse'] = 4
    if os.environ.get('NRG_V66_4IDS') == '1':
        result['registration_targets_before_reuse'] -= 1
    if os.environ.get('NRG_V67_3IDS') == '1':
        from patch_v67_three_ids import assert_invariants
        assert_invariants()
        result['registration_targets_before_reuse'] -= 1
        document_types = host.get('CFBundleDocumentTypes', [])
        assert any('public.item' in entry.get('LSItemContentTypes', []) for entry in document_types)
        assert host.get('LSSupportsOpeningDocumentsInPlace') is True
        assert result['registration_targets_before_reuse'] == 2
        with zipfile.ZipFile(path) as package:
            plug_infos = [x for x in package.namelist() if '/PlugIns/' in x and x.endswith('.appex/Info.plist')]
            expected = {'com.kdt.livecontainer.LiveProcess'}
            found = {plistlib.loads(package.read(x))['CFBundleIdentifier'] for x in plug_infos}
            assert found == expected, ('Unexpected App ID', found, expected)
    elif os.environ.get('NRG_V66_4IDS') == '1':
        assert result['registration_targets_before_reuse'] == 3
        with zipfile.ZipFile(path) as package:
            root_metadata = json.loads(package.read(base + '/Metadata.appintents/extract.actionsdata'))
        assert 'ScarletCrystalLaunchAppIntent' in root_metadata['actions'], 'Host shortcut missing'
        assert '16SideStoreSupport20RefreshAllAppsIntentV' in json.dumps(root_metadata), 'Existing refresh runtime binding missing'
        assert '16SideStoreSupport26RefreshAllAppsWidgetIntentV' in json.dumps(root_metadata), 'Widget refresh runtime binding missing'
    return result


def package(root, host, side, output):
    for product in (host, side):
        if not (product / 'Info.plist').exists():
            raise ValueError(f'Build product missing: {product}')
    if (root / 'Payload').exists() or (root / 'tmp').exists():
        raise ValueError('Packaging requires a fresh upstream checkout')
    application_dir = root / 'combined.xcarchive/Products/Applications'
    application_dir.mkdir(parents=True)
    shutil.copytree(host, application_dir / 'LiveContainer.app', symlinks=True)
    side_stage = root / 'patched-side/Payload'
    side_stage.mkdir(parents=True)
    shutil.copytree(side, side_stage / 'SideStore.app', symlinks=True)
    side_ipa = root / 'PatchedSideStore.ipa'
    subprocess.run(['zip', '-qry', str(side_ipa), 'Payload'], cwd=side_stage.parent, check=True)
    upstream = (root / '.github/build_github.sh').read_text()
    script = root / 'combined-build.sh'
    script.write_text(adapt(upstream))
    env = dict(os.environ, archive_path='combined', scheme='LiveContainer',
               PATCHED_SIDESTORE_IPA=str(side_ipa), COMBINED_PACKAGER=str(Path(__file__).resolve()),
               V67_PATCH=str((Path(__file__).resolve().parent / 'patch_v67_three_ids.py')))
    subprocess.run(['bash', str(script)], cwd=root, env=env, check=True)
    ipa = root / 'LiveContainer+SideStore.ipa'
    result = verify(ipa, side)
    result['upstream_packaging_sha256'] = hashlib.sha256(upstream.encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ipa, output)
    output.with_suffix('.verification.json').write_text(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-entitlements', nargs=2, type=Path)
    parser.add_argument('--merge-host-intents', nargs=2, type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--host', type=Path)
    parser.add_argument('--side', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.merge_host_intents:
        merge_host_intents(*(p.resolve() for p in args.merge_host_intents))
    elif args.prepare_entitlements:
        prepare_entitlements(*(p.resolve() for p in args.prepare_entitlements))
    else:
        package(*(p.resolve() for p in (args.root, args.host, args.side, args.output)))

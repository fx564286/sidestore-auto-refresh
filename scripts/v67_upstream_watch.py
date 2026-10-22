"""Read-only provenance watcher for Scarlet Crystal's pinned public upstreams.

Detects new releases/commits; DOES NOT swap pins, run untrusted upstream
scripts, expose signing identities, or push untested binary updates.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

UPSTREAMS = {
    'LIVE_CONTAINER_REF': ('LiveContainer', 'LiveContainer', 'main'),
    'EMBEDDED_SIDESTORE_REF': ('LiveContainer', 'SideStore', 'LiveContainerSupport'),
}


def pinned_sha(workflow: str, variable: str) -> str:
    match = re.search(r'^  ' + re.escape(variable) + r': ([0-9a-f]{40})$', workflow, re.M)
    if not match:
        raise ValueError(f'Missing immutable {variable} pin')
    return match.group(1)


def fetch_head(owner: str, repo: str, ref: str) -> dict:
    url = f'https://api.github.com/repos/{owner}/{repo}/commits/{ref}'
    headers = {'Accept': 'application/vnd.github+json',
               'User-Agent': 'scarlet-crystal-upstream-monitor'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
        payload = json.load(response)
    sha = payload['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid GitHub commit SHA')
    return {'sha': sha,
            'date': payload['commit']['committer']['date'],
            'url': payload['html_url']}


def sdk_probe() -> dict:
    result = {}
    for key, args in {'xcode': ['xcodebuild', '-version'],
                      'iphoneos_sdk': ['xcrun', '--sdk', 'iphoneos', '--show-sdk-version']}.items():
        try:
            output = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15)
            result[key] = output.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            result[key] = 'unavailable on this runner'
    return result


def report(workflow_path: Path) -> dict:
    workflow = workflow_path.read_text()
    refs = {}
    for variable, (owner, repo, branch) in UPSTREAMS.items():
        current = fetch_head(owner, repo, branch)
        pinned = pinned_sha(workflow, variable)
        refs[variable] = {'repository': f'{owner}/{repo}',
                          'branch': branch, 'pinned': pinned,
                          'upstream': current, 'update_available': pinned != current['sha']}
    sdk = sdk_probe()
    expected_xcode_match = re.search(r'xcode-version: ["\'](\d+(?:\.\d+)*)', workflow)
    expected_xcode = expected_xcode_match.group(1) if expected_xcode_match else None
    available_xcode_match = re.search(r'Xcode (\d+(?:\.\d+)*)', sdk['xcode'])
    available_xcode = available_xcode_match.group(1) if available_xcode_match else None
    def numeric_version(value: str) -> tuple[int, ...]:
        return tuple(int(i) for i in value.split('.'))
    newer_sdk = bool(expected_xcode and available_xcode and
                     numeric_version(available_xcode) > numeric_version(expected_xcode))
    return {'schema': 1, 'source': 'github-live-api', 'upstreams': refs,
            'sdk_observed': sdk, 'xcode_builder_pin': expected_xcode,
            'newer_xcode_on_runner': newer_sdk,
            'review_required': (any(entry['update_available'] for entry in refs.values()) or newer_sdk),
            'policy': 'review -> compatibility build -> regression/device tests -> explicit promotion; never auto-release'}


def markdown(data: dict) -> str:
    rows = ['### Scarlet Crystal API and upstream check', '',
            '| Upstream | Candidate head | Pinned | Action |', '|---|---|---|---|']
    for item in data['upstreams'].values():
        rows.append(f"| {item['repository']} ({item['branch']}) | "
                    f"[{item['upstream']['sha'][:12]}]({item['upstream']['url']}) | "
                    f"{item['pinned'][:12]} | {'Review + compatibility tests' if item['update_available'] else 'Current'} |")
    rows += ['', f"Xcode: {data['sdk_observed']['xcode']}",
             f"iPhoneOS SDK: {data['sdk_observed']['iphoneos_sdk']}", '',
             'API updates must preserve the three-App-ID cap and run the device regression suite.',
             'Do not publish or install a new IPA automatically.']
    return '\n'.join(rows) + '\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workflow', type=Path, required=True)
    p.add_argument('--json', type=Path, required=True)
    p.add_argument('--markdown', type=Path, required=True)
    args = p.parse_args()
    value = report(args.workflow)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    args.markdown.write_text(markdown(value))
    print('REVIEW_REQUIRED=' + ('true' if value['review_required'] else 'false'))

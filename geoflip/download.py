"""Download only a declared dataset scope and verify its file hashes."""
from pathlib import Path
import argparse
import json
from .core import digest, inside

SCOPES = {
    'inputs': ['README.md', 'LICENSE.txt', 'dataset_info.json', 'SHA256SUMS.json', 'inputs/**', 'first_frames/**', 'splits/**', 'prompts/**'],
    'evaluation': ['README.md', 'LICENSE.txt', 'dataset_info.json', 'SHA256SUMS.json', 'evaluation/**', 'splits/**', 'prompts/**', 'baselines/**', 'docs/**'],
    'full': ['**'],
}


def download(repo_id, output, revision='main', scope='inputs', token=None):
    from huggingface_hub import HfApi, snapshot_download
    if scope not in SCOPES:
        raise ValueError('Unknown download scope')
    # Resolve once to an immutable commit so concurrent updates cannot mix versions.
    info = HfApi(token=token).dataset_info(repo_id=repo_id, revision=revision)
    commit = info.sha
    output = Path(output)
    marker = output / 'DOWNLOAD_REVISION.json'
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    if previous and (previous.get('repo_id') != repo_id or previous.get('commit') != commit):
        raise ValueError('Output contains a different dataset revision; choose a clean output directory')
    output.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'repo_id': repo_id, 'commit': commit, 'scope': scope, 'status': 'in-progress'}, indent=2) + '\n')
    snapshot_download(repo_id=repo_id, repo_type='dataset', revision=commit,
                      local_dir=str(output), allow_patterns=SCOPES[scope], token=token)
    output = Path(output)
    hashes = json.loads((output / 'SHA256SUMS.json').read_text())
    from fnmatch import fnmatch
    expected = {name: value for name, value in hashes.items() if any(fnmatch(name, p) for p in SCOPES[scope])}
    for name, value in expected.items():
        path = inside(output, name)
        if not path.is_file() or digest(path) != value:
            raise ValueError('Downloaded file failed integrity check: ' + name)
    (output / 'DOWNLOAD_REVISION.json').write_text(json.dumps({'repo_id': repo_id, 'commit': commit, 'scope': scope, 'status': 'verified'}, indent=2) + '\n')
    return {'repo_id': repo_id, 'commit': commit, 'scope': scope, 'verified_files': len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Hugging Face owner/dataset')
    parser.add_argument('--output', type=Path, default=Path('data/geoflip'))
    parser.add_argument('--revision', default='main', help='Release tag or immutable commit')
    parser.add_argument('--scope', choices=SCOPES, default='inputs')
    args = parser.parse_args()
    print(json.dumps(download(args.repo, args.output, args.revision, args.scope), indent=2))


if __name__ == '__main__':
    main()

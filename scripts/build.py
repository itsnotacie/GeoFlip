"""Build only explicitly selected public files. No deployment or network operations."""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = ('support', 'torque', 'gravity', 'contact', 'elastic', 'pulley')
PUBLIC_FILES = ['index.html', 'styles.css', 'app.js', 'assets/favicon.svg',
                'assets/failure-cases.webp', 'assets/paper-results.csv', 'assets/paper-results.json',
                'assets/benchmark-overview.webp', 'assets/evaluation-protocol.webp',
                'assets/category-results.webp', 'assets/judge-comparison.webp',
                'assets/vendor/bulma.min.css', 'assets/vendor/osworld-base.css', 'assets/vendor/osworld-layout.css',
                'assets/vendor/osworld-official-match.css',
                'assets/vendor/Bulma-LICENSE.txt',
                'assets/vendor/NOTICE.txt']
for category in CATEGORIES:
    for side in ('a', 'b'):
        PUBLIC_FILES.extend((f'assets/{category}-{side}-reference.mp4',
                             f'assets/{category}-{side}-model.mp4',
                             f'assets/{category}-{side}-reference.webm',
                             f'assets/{category}-{side}-model.webm',
                             f'assets/{category}-{side}.webp',
                             f'assets/{category}-{side}-model.webp'))


def build():
    source, output = ROOT / 'site', ROOT / 'dist'
    actual = {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}
    expected = set(PUBLIC_FILES)
    if actual != expected:
        raise SystemExit(f'Public file list mismatch: missing={sorted(expected-actual)}, unexpected={sorted(actual-expected)}')
    for name in PUBLIC_FILES:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f'Refusing invalid source: {name}')
    if output.is_symlink():
        raise SystemExit('Refusing symlinked output directory')
    if output.exists():
        shutil.rmtree(output)
    for name in PUBLIC_FILES:
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
    total = sum((output / p).stat().st_size for p in PUBLIC_FILES)
    print(f'Built {len(PUBLIC_FILES)} public files ({total / 1024 / 1024:.2f} MiB).')


if __name__ == '__main__':
    build()

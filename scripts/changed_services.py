"""Select independent image builds from changed paths; no app imports or mutation."""
import argparse
import json
import os
import re
import subprocess

IMAGES = {
    'frontend': ('frontend/Dockerfile', 'frontend'),
    'backend': ('backend/Dockerfile', 'backend'),
    'AI': ('AI/Dockerfile', 'ai'),
    'index-worker': ('infra/index-worker.Dockerfile', 'index-worker'),
}


def plan(paths, all_services=False):
    selected = set(IMAGES) if all_services else set()
    for path in paths:
        if path in {'.dockerignore', '.github/workflows/deployment-builds.yml', 'scripts/changed_services.py'}:
            selected.update(IMAGES)
        if path.startswith('frontend/') or path in {'infra/frontend.conf', 'infra/runtime-config.js'}:
            selected.add('frontend')
        if path.startswith('backend/'):
            selected.update({'backend', 'index-worker'})
        if path.startswith('AI/') or path.startswith('data/') or path == 'output/products_ai.csv':
            selected.update({'AI', 'index-worker'})
        if path.startswith('shared/'):
            selected.update({'backend', 'AI', 'index-worker'})
        if path in {'infra/index-worker.Dockerfile', 'scripts/run_index_worker.py'}:
            selected.add('index-worker')
    return {'include': [{'service': name, 'file': IMAGES[name][0], 'image': IMAGES[name][1]}
                        for name in IMAGES if name in selected]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='')
    parser.add_argument('--github-output', action='store_true')
    args = parser.parse_args()
    if args.base and not re.fullmatch('[0-9a-fA-F]{40}', args.base):
        parser.error('Base must be a full commit SHA')
    paths = []
    if args.base:
        paths = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', args.base, 'HEAD'],
                                        text=True, timeout=20).splitlines()
    matrix = plan(paths, all_services=not args.base)
    value = json.dumps(matrix, separators=(',', ':'))
    if args.github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
            handle.write('matrix=' + value + '\n')
            handle.write('has_changes=' + str(bool(matrix['include'])).lower() + '\n')
    print(value)


if __name__ == '__main__':
    main()

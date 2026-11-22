"""Parse source/config artifacts without importing apps or connecting to services."""
import ast
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    counts = {'python': 0, 'json': 0, 'yaml': 0}
    for folder in ('AI', 'backend', 'scripts', 'shared', 'evaluation'):
        for path in (ROOT / folder).rglob('*.py'):
            if any(part in {'.venv', 'venv', 'node_modules', '__pycache__'} for part in path.parts):
                continue
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            counts['python'] += 1
    for folder in ('docs', 'infra', 'AI/config'):
        for path in (ROOT / folder).rglob('*.json'):
            json.loads(path.read_text(encoding='utf-8-sig'))
            counts['json'] += 1
    for folder in ('infra', '.github/workflows'):
        for extension in ('*.yml', '*.yaml'):
            for path in (ROOT / folder).rglob(extension):
                yaml.safe_load(path.read_text(encoding='utf-8-sig'))
                counts['yaml'] += 1
    for path in ROOT.glob('compose*.yaml'):
        yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        counts['yaml'] += 1
    for line in (ROOT / 'evaluation/queries.draft.jsonl').read_text(encoding='utf-8').splitlines():
        assert json.loads(line)['reviewed'] is False
    print(json.dumps({'syntax_validation': 'passed', 'files': counts,
                      'semantic_code_audit': 'not_claimed_by_parser', 'docker_runtime': 'not_verified'}))


if __name__ == '__main__':
    main()

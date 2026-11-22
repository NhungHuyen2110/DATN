"""Summarize synthetic browser-test errors without exporting trace/body data."""
import json
from pathlib import Path
import re
import sys

data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
def visit(suites):
    for suite in suites:
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                for result in test.get('results', []):
                    messages = [re.sub(r'\x1b\[[0-9;]*m', '', error.get('message', ''))[:700]
                                for error in result.get('errors', [])]
                    yield {'test': spec['title'], 'status': result['status'], 'messages': messages}
        yield from visit(suite.get('suites', []))
print(json.dumps({'stats': data['stats'], 'tests': list(visit(data.get('suites', [])))}, indent=2))

"""Score saved retrieval results; refuses draft/unreviewed labels and incomplete runs."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.scoring import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--k', type=int, default=3)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to overwrite evidence')
    def read(path):
        return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    report = evaluate(read(args.labels), read(args.predictions), args.k)
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report['metrics']))


if __name__ == '__main__':
    main()

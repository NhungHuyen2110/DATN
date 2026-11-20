"""Export human-approved labels to a new CSV; never imports into a database."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "AI"))
from lumiere.label_review import export_reviewed_labels

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_reviewed_labels(args.source, args.review, args.output)
    print(json.dumps(result))
    return 0 if result["exported"] else 2

if __name__ == "__main__":
    raise SystemExit(main())

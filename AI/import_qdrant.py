"""Validated CSV -> versioned Qdrant; dry-run default, never deletes collections."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from knowledge_graph.csv_validation import ROOT, validate_csv, summary
from vector_index import index_products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--lookup-dir', type=Path, default=ROOT / 'data')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--url', help='Explicit isolated Qdrant loopback URL')
    parser.add_argument('--environment', choices=['dev', 'test'])
    parser.add_argument('--confirm-isolated', action='store_true')
    parser.add_argument('--model', default='paraphrase-multilingual-MiniLM-L12-v2')
    parser.add_argument('--model-revision', help='Cached, pinned model revision required for writes')
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 10000 or (args.report and args.report.exists()):
        parser.error('Invalid batch size or report already exists')
    if args.apply:
        url = urlsplit(args.url or '')
        if (not args.confirm_isolated or not args.environment or not args.model_revision
                or url.scheme not in {'http', 'https'} or url.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or url.username or url.password or url.query or url.fragment):
            parser.error('Apply requires explicit isolated dev/test loopback URL and pinned model revision')
    report = None
    try:
        source_sha = hashlib.sha256(args.file.read_bytes()).hexdigest()
        result = validate_csv(args.file, args.lookup_dir)
        report = summary(result, args.file)
        if report['source_sha256'] != source_sha:
            raise ValueError('Source changed while validating')
        code = 1 if result['errors'] else 0
        if args.apply and code == 0:
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer
            encoder = SentenceTransformer(args.model, revision=args.model_revision, local_files_only=True)
            report['mode'], report['write_attempted'] = 'apply', True
            with closing(QdrantClient(url=args.url, timeout=5)) as client:
                report['verification'] = index_products(client, encoder, result['records'], args.model,
                                                        args.model_revision, source_sha, args.batch_size)
            report['completed'] = report['verification']['pass']
            code = 0 if report['completed'] else 1
    except Exception as exc:
        report = report or {'mode': 'apply' if args.apply else 'dry-run'}
        report.update(error_type=type(exc).__name__, completed=False,
                      partial_write_possible=bool(report.get('write_attempted')))
        code = 2
    if args.report:
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

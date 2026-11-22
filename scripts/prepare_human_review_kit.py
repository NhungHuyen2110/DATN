"""Export a local public-field review kit; never supplies labels/reviewer identity or changes catalog facts."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def safe(value):
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def main():
    folder = ROOT / '.local-tmp/human-review-kit-20261122'
    if folder.exists():
        raise ValueError('Review kit exists; never overwrite human work')
    source = ROOT / 'output/products_ai.csv'
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    queries = [json.loads(line) for line in (ROOT / 'evaluation/queries.draft.jsonl').read_text(encoding='utf-8').splitlines()]
    if any(item['dataset_sha256'] != sha or item.get('reviewed') is not False for item in queries):
        raise ValueError('Expected draft questions matching this seed catalog')
    with source.open(encoding='utf-8-sig', newline='') as file:
        products = list(csv.DictReader(file))
    fields = ['ProductID', 'SKU', 'ProductName', 'CategoryID', 'CategoryName', 'BrandName', 'MaterialID',
              'MaterialName', 'GemstoneID', 'GemstoneName', 'CollectionName', 'SalePrice', 'Stock']
    folder.mkdir()
    with (folder / 'catalog-public-seed.csv').open('x', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(fields + ['audience_proposal', 'style_proposal', 'evidence_source', 'reviewer'])
        for row in products:
            writer.writerow([safe(row[field]) for field in fields] + ['', '', '', ''])
    with (folder / 'queries-for-human-review.csv').open('x', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['query_id', 'query', 'group', 'dataset_sha256', 'reviewed', 'reviewer', 'split',
                         'expected_intent', 'expected_status', 'relevance_json', 'expected_constraints_json', 'notes'])
        for item in queries:
            writer.writerow([item['query_id'], safe(item['query']), item['group'], sha, 'false', '', '', '', '', '', '', ''])
    (folder / 'README.txt').write_text(
        'LOCAL HUMAN REVIEW KIT — all questions remain UNREVIEWED.\n'
        'Catalog is CSV seed data, not live price/stock. No CostPrice/WholesalePrice/customer fields exported.\n'
        '1. Review public product facts. Audience/style columns are proposals only; supply an evidence source and reviewer.\n'
        '   Do not infer gender/style from generic category pictures, names or stereotypes.\n'
        '2. Review queries against this exact dataset. Enter relevance_json such as {"79":3,"87":2} only after checking.\n'
        '   Keep unsupported/out-of-scope/clarification cases as behavioral judgments, not fake positive ranking labels.\n'
        '3. Supply a real reviewer and validation/test split. Do not set reviewed=true before review.\n'
        '4. Agent can convert reviewed CSV to scoring JSONL after you finish. No metrics calculated by this exporter.\n', encoding='utf-8')
    report = {'successful': True, 'directory': str(folder.relative_to(ROOT)), 'public_catalog_rows': len(products),
              'draft_queries': len(queries), 'dataset_sha256': sha, 'human_reviewed_queries': 0,
              'quality_metrics_computed': False, 'customer_fields_exported': False, 'cost_fields_exported': False}
    with (ROOT / 'docs/human-review-kit-20261122.json').open('x', encoding='utf-8') as file:
        json.dump(report, file, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()

"""Export a local public-field review kit; never supplies labels/reviewer identity or changes catalog facts."""
import csv
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['ProductID', 'SKU', 'ProductName', 'CategoryID', 'CategoryName', 'BrandName', 'MaterialID',
          'MaterialName', 'GemstoneID', 'GemstoneName', 'CollectionName', 'SalePrice', 'Stock']


def safe(value):
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def load_original_public_catalog():
    """Reuse the actual API adapter, pinned to the serving local original copy."""
    sys.path[:0] = [str(ROOT), str(ROOT / 'AI')]
    from jewelry_agents.business_catalog import fetch_catalog
    previous = os.environ.get('BUSINESS_API_URL')
    os.environ['BUSINESS_API_URL'] = 'http://127.0.0.1:18080/api'
    try:
        live = fetch_catalog()
    finally:
        if previous is None:
            os.environ.pop('BUSINESS_API_URL', None)
        else:
            os.environ['BUSINESS_API_URL'] = previous
    return [{'ProductID': p['ProductID'], 'SKU': p['SKU'], 'ProductName': p['ProductName'],
             'CategoryID': p['CategoryID'], 'CategoryName': p['Category'], 'BrandName': p['Brand'],
             'MaterialID': p['MaterialID'], 'MaterialName': p['Material'],
             'GemstoneID': p['GemstoneID'], 'GemstoneName': p['Gemstone'],
             'CollectionName': p['Collection'], 'SalePrice': p['Price'], 'Stock': p['Stock']}
            for _, p in sorted(live.items())]


def write_review_kit(folder, products, queries, sha, source_description):
    if folder.exists():
        raise ValueError('Review kit exists; never overwrite human work')
    if not products or any(item.get('reviewed') is not False for item in queries):
        raise ValueError('Nonempty catalog and unreviewed draft queries required')
    # Explicit whitelist applies to the snapshot as well as CSV; never dump a
    # raw source row containing cost prices or unrelated private fields.
    public = [{field: row[field] for field in FIELDS} for row in products]
    ids = [row['ProductID'] for row in public]
    if (any(not str(pid).isdigit() or int(pid) < 1 for pid in ids)
            or len({int(pid) for pid in ids}) != len(ids)):
        raise ValueError('Unique positive product IDs required')
    folder.mkdir(parents=True)
    (folder / 'catalog-public-snapshot.json').write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (folder / 'catalog-for-human-review.csv').open('x', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS + ['product_url', 'audience_proposal', 'style_proposal', 'evidence_source',
                                  'reviewer', 'reviewed_at', 'approved'])
        for row in public:
            writer.writerow([safe(row[field]) for field in FIELDS] + [
                'http://127.0.0.1:18080/pages/product-detail.html?id=' + str(int(row['ProductID'])),
                '', '', '', '', '', 'false'])
    with (folder / 'queries-for-human-review.csv').open('x', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['query_id', 'query', 'group', 'dataset_sha256', 'reviewed', 'reviewer', 'split',
                         'expected_intent', 'expected_status', 'relevance_json', 'expected_constraints_json', 'notes'])
        for item in queries:
            writer.writerow([safe(value) for value in [item['query_id'], item['query'], item['group'], sha,
                                                       'false', '', '', '', '', '', '', '']])
    (folder / 'README.txt').write_text(
        'BỘ GÁN NHÃN LUMIÈRE — chưa có nhãn nào được xác nhận.\n'
        'Nguồn: ' + source_description + '\n'
        'Snapshot chỉ có trường sản phẩm công khai tại lúc xuất; không có giá vốn hoặc dữ liệu khách hàng.\n'
        '1. Mở catalog-for-human-review.csv bằng Excel (UTF-8). product_url mở ảnh/chi tiết sản phẩm local.\n'
        '2. Giữ nguyên ProductID và SKU. Có thể bắt đầu với một nhóm nhỏ sản phẩm bạn hiểu rõ.\n'
        '3. audience_proposal: female, male, child_female; style_proposal: elegant, minimalist, refined.\n'
        '   Nhiều nhãn cách nhau bằng |. Để trống khi chưa có căn cứ; không suy giới tính từ loại sản phẩm.\n'
        '4. Ghi evidence_source (tài liệu/nguồn tham chiếu), reviewer (người đánh giá), reviewed_at.\n'
        '   Chỉ đổi approved thành true sau khi bạn đã xác nhận; lưu CSV UTF-8.\n'
        '5. Các nhãn là đề xuất để kiểm tra/import sau, chưa tự ghi database hoặc Neo4j.\n'
        '6. queries-for-human-review.csv là bộ 105 câu hỏi dự thảo, chưa có ground truth.\n'
        '   Chỉ ghi relevance_json (mức liên quan 0..3 theo product ID) sau khi đánh giá đúng snapshot.\n'
        '   Ghi reviewer và split validation/test; reviewed=true chỉ sau khi hoàn tất.\n'
        'Công cụ này không tính điểm chất lượng và không tự nhận là người gán nhãn.\n', encoding='utf-8')
    return {'successful': True, 'public_catalog_rows': len(public), 'draft_queries': len(queries),
            'dataset_sha256': sha, 'human_reviewed_products': 0, 'human_reviewed_queries': 0,
            'source': source_description, 'quality_metrics_computed': False,
            'customer_fields_exported': False, 'cost_fields_exported': False, 'database_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['seed', 'original-api'], default='seed')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    name = 'human-review-original-20261122' if args.source == 'original-api' else 'human-review-kit-20261122'
    folder = (args.output or ROOT / '.local-tmp' / name).resolve()
    report_path = (args.report or ROOT / 'docs' / (name + '.json')).resolve()
    if not folder.is_relative_to(ROOT / '.local-tmp') or not report_path.is_relative_to(ROOT):
        parser.error('Review work belongs inside workspace .local-tmp; report belongs inside workspace')
    if folder.exists() or report_path.exists():
        parser.error('Choose new paths; existing human work/reports are never overwritten')
    queries = [json.loads(line) for line in (ROOT / 'evaluation/queries.draft.jsonl').read_text(encoding='utf-8').splitlines()]
    if args.source == 'original-api':
        products = load_original_public_catalog()
        sha = hashlib.sha256(json.dumps(products, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        description = 'Bản sao database cũ, đọc qua http://127.0.0.1:18080/api/products'
    else:
        source = ROOT / 'output/products_ai.csv'
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if any(item['dataset_sha256'] != sha for item in queries):
            raise ValueError('Draft questions differ from seed catalog')
        with source.open(encoding='utf-8-sig', newline='') as file:
            products = list(csv.DictReader(file))
        description = 'CSV seed output/products_ai.csv; giá/tồn kho không phải snapshot live'
    report = write_review_kit(folder, products, queries, sha, description)
    report['directory'] = str(folder.relative_to(ROOT))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

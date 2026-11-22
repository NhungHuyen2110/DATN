"""Actual PostgreSQL baseline integration on a fresh isolated synthetic database, never relevance scoring."""
import argparse
from contextlib import ExitStack
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    target = make_url(os.environ['LUMIERE_SYNC_TEST_URL'])
    if (target.drivername != 'postgresql+psycopg' or target.host != '127.0.0.1' or target.port != 15439
            or not target.database.startswith('lumiere_test_sql_')):
        parser.error('Dedicated loopback synthetic SQL test DB required')
    os.environ.update({'LUMIERE_LOAD_DOTENV': 'false', 'PRODUCT_INDEX_SYNC_ENABLED': 'false',
        'POSTGRES_DB': target.database, 'POSTGRES_HOST': target.host, 'POSTGRES_PORT': '15439',
        'POSTGRES_USER': target.username, 'POSTGRES_PASSWORD': target.password})
    sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'AI')]
    from app.main import app
    from app.models import Product, Category, Brand, Material, Gemstone, Collection
    from evaluation.sql_keyword import keyword_candidates
    engine = create_engine(target, connect_args={'connect_timeout': 3})
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Target must be empty')
        from alembic import command
        from alembic.config import Config
        config = Config(str(ROOT / 'backend/alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'backend/alembic'))
        command.upgrade(config, 'head')
        with Session(engine) as db, db.begin():
            for model, name in ((Category, 'Nhẫn'), (Brand, 'Synthetic'), (Material, 'Bạc 925'),
                                (Gemstone, 'CZ'), (Collection, 'Synthetic')):
                db.add(model(id=1 if model is not Gemstone else 6, name=name))
            db.flush()
            for pid, sku, price, stock in ((1, 'EXACT_TEST', 7_000_000, 2), (2, 'EXACTXTEST', 9_000_000, 2),
                                            (3, 'OUT_OF_STOCK', 6_000_000, 0), (4, 'SYNTHETIC4', 5_000_000, 2)):
                db.add(Product(id=pid, sku=sku, barcode='SYNTHETIC' + str(pid), name='Nhẫn mẫu ' + str(pid),
                    category_id=1, brand_id=1, material_id=1, gemstone_id=6, collection_id=1,
                    weight=Decimal('1'), sale_price=price, wholesale_price=price, cost_price=price, stock=stock))
        checks = []
        with engine.connect() as connection:
            assert keyword_candidates(connection, 'EXACT_TEST', [1, 2, 3, 4]) == [1]
            checks.append('underscore_in_sku_is_literal_not_sql_wildcard')
            assert keyword_candidates(connection, 'nhẫn', [4, 1], 10) == [1, 4]
            checks.append('eligible_ids_and_deterministic_sql_order')
            assert keyword_candidates(connection, "xyz' OR 1=1 --", [1, 2, 3, 4]) == []
            assert inspect(connection).has_table('products')
            checks.append('bound_query_terms_do_not_execute_injection')
            assert keyword_candidates(connection, 'nhẫn', []) == []
            checks.append('empty_eligibility_returns_no_candidates')
        with Session(engine) as db:
            catalog = {row.id: {'ProductID': row.id, 'ProductName': row.name, 'SKU': row.sku,
                'CategoryID': 1, 'Category': 'Nhẫn', 'MaterialID': 1, 'Material': 'Bạc 925',
                'GemstoneID': 6, 'Gemstone': 'CZ', 'Price': str(row.sale_price), 'Stock': row.stock}
                for row in db.scalars(select(Product))}
        with ExitStack() as stack:
            stack.enter_context(patch('dotenv.load_dotenv', return_value=False))
            from jewelry_agents.search_service import search
            from jewelry_agents.retrieval import extract_price_filter
            def sql(query, eligible_ids, top_k):
                with engine.connect() as connection:
                    return keyword_candidates(connection, query, eligible_ids, top_k)
            result = search('Top 3 nhẫn dưới 8 triệu', 3, dense=lambda *a, **k: (_ for _ in ()).throw(AssertionError('No dense baseline')),
                catalog=lambda: catalog, parse_price=extract_price_filter, sources={'lexical'}, lexical_retriever=sql)
            assert {item['ProductID'] for item in result['products']} == {1, 4}
            assert all(item['retrieval_sources'] == ['lexical'] for item in result['products'])
            checks.append('shared_query_planner_and_final_live_filters_with_actual_sql_baseline')
        report = {'successful': True, 'database': 'actual PostgreSQL 17 isolated synthetic fixtures',
                  'checks': checks, 'production_accessed': False, 'quality_benchmark': False,
                  'sql_baseline': 'parameterized ILIKE, accent-sensitive, no semantic synonyms',
                  'topk_fixture_product_ids': [item['ProductID'] for item in result['products']]}
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

"""Real pg_dump/pg_restore rehearsal; source and target are ONLY synthetic isolated test databases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(r'C:\Program Files\PostgreSQL\17\bin')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists')
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    target = make_url(os.environ['LUMIERE_SYNC_TEST_URL'])
    source_name = 'lumiere_test_browser_10'
    if (target.drivername != 'postgresql+psycopg' or target.host != '127.0.0.1' or target.port != 15439
            or not target.database.startswith('lumiere_test_restore_')):
        parser.error('Only the dedicated test PostgreSQL cluster may be restored')
    parent = ROOT / '.local-tmp/recovery' / target.database
    parent.mkdir(parents=True, exist_ok=False)
    dump = parent / 'fixture.dump'
    source = create_engine(target.set(database=source_name), connect_args={'connect_timeout': 3})
    restored = create_engine(target, connect_args={'connect_timeout': 3})
    try:
        if inspect(restored).get_table_names():
            raise ValueError('Restore target must be empty; no --clean/--create/drop allowed')
        def snapshot(engine):
            inspector = inspect(engine)
            result = {}
            with engine.connect() as db:
                for table in inspector.get_table_names():
                    quoted = engine.dialect.identifier_preparer.quote(table)
                    result[table] = db.scalar(text('SELECT count(*) FROM ' + quoted))
            return result
        before = snapshot(source)
        env = {**os.environ, 'PGPASSWORD': target.password}
        common = ['-h', '127.0.0.1', '-p', '15439', '-U', target.username]
        for name, arguments in [('pg_dump', [*common, '-Fc', '--no-owner', '--no-acl', '-f', str(dump), source_name]),
                                ('pg_restore', [*common, '--no-owner', '--no-acl', '--exit-on-error', '-d', target.database, str(dump)])]:
            result = subprocess.run([str(BIN / (name + '.exe')), *arguments], env=env,
                                     capture_output=True, timeout=60,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            (parent / (name + '.log')).write_bytes((result.stdout or b'') + (result.stderr or b''))
            if result.returncode:
                raise RuntimeError(name + ' failed; test-only log preserved')
        after = snapshot(restored)
        if before != after or snapshot(source) != before:
            raise AssertionError('Restored counts differ or source counts changed')
        with restored.connect() as db:
            orphan = db.scalar(text('''SELECT count(*) FROM order_items i
                LEFT JOIN orders o ON o.id=i.order_id LEFT JOIN products p ON p.id=i.product_id
                WHERE o.id IS NULL OR p.id IS NULL'''))
            arithmetic = db.scalar(text('SELECT count(*) FROM orders WHERE total_vnd <> subtotal_vnd+shipping_vnd-discount_vnd'))
            item_totals = db.scalar(text('''SELECT count(*) FROM orders o WHERE o.subtotal_vnd <>
                (SELECT coalesce(sum(i.line_total_vnd),0) FROM order_items i WHERE i.order_id=o.id)'''))
            payment_mismatch = db.scalar(text('''SELECT count(*) FROM payment_transactions p JOIN orders o ON o.id=p.order_id
                WHERE p.status='succeeded' AND (p.amount_vnd<>o.total_vnd OR o.payment_status<>'paid')'''))
            migration = db.scalar(text('SELECT version_num FROM alembic_version'))
        if any((orphan, arithmetic, item_totals, payment_mismatch)) or migration not in {'20261121_0009','20261122_0010'}:
            raise AssertionError('Restore relational/business invariants failed')
        report = {'successful': True, 'source': source_name, 'restored_target': target.database,
                  'source_modified': False, 'production_accessed': False, 'table_counts': after,
                  'backup_sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
                  'backup_relative_path': str(dump.relative_to(ROOT)), 'migration_head': migration,
                  'orphan_order_items': orphan, 'order_arithmetic_violations': arithmetic,
                  'order_item_total_violations': item_totals, 'payment_invariant_violations': payment_mismatch,
                  'scope': 'actual PostgreSQL restore of synthetic browser fixtures; not a production backup'}
        reference = {'version': 1, 'environment': 'test', 'database_host': '127.0.0.1', 'database_port': 15439,
                     'database_name': source_name, 'format': 'pg_dump_custom', 'backup_file': dump.name,
                     'backup_sha256': report['backup_sha256'], 'restore_rehearsal_passed': True}
        with (parent / 'backup-reference.json').open('x', encoding='utf-8') as handle:
            json.dump(reference, handle, indent=2)
        import sys
        sys.path.insert(0, str(ROOT))
        from shared.recovery import validate_backup_reference
        report['worker_backup_guard'] = validate_backup_reference(
            parent / 'backup-reference.json', 'test', '127.0.0.1', 15439, source_name)
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        source.dispose()
        restored.dispose()


if __name__ == '__main__':
    main()

"""Create a NEW loopback-only test cluster on D, run sync tests, stop only that cluster."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--resume-initialized-test-cluster', action='store_true',
                        help='Only resume the exact script-created cluster after an interrupted initdb')
    parser.add_argument('--projection-test', action='store_true')
    parser.add_argument('--projection-attempt', type=int, choices=range(1, 10), default=1)
    parser.add_argument('--browser-test', action='store_true')
    parser.add_argument('--browser-attempt', type=int, choices=range(1, 100), default=1)
    parser.add_argument('--browser-with-ai', action='store_true')
    parser.add_argument('--browser-with-monitoring', action='store_true')
    parser.add_argument('--sync-attempt', type=int, choices=range(1, 100), default=1)
    parser.add_argument('--browser-native-fault', action='store_true')
    parser.add_argument('--browser-use-migrations', action='store_true')
    parser.add_argument('--backup-restore-test', action='store_true')
    parser.add_argument('--live-catalog-test', action='store_true')
    parser.add_argument('--sql-baseline-test', action='store_true')
    args = parser.parse_args()
    if sum((args.browser_test, args.projection_test, args.backup_restore_test, args.live_catalog_test, args.sql_baseline_test)) > 1:
        parser.error('Choose one integration suite')
    if args.report.exists():
        parser.error('Report exists')
    binaries = Path(r'C:\Program Files\PostgreSQL\17\bin')
    parent = ROOT / '.local-tmp' / 'postgres-sync-20261121'
    if parent.exists() and not args.resume_initialized_test_cluster:
        parser.error('Refusing to reuse existing cluster directory')
    if args.resume_initialized_test_cluster and not parent.is_dir():
        parser.error('No initialized test directory to resume')
    port = 15439
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    parent.mkdir(parents=True, exist_ok=args.resume_initialized_test_cluster)
    password = 'synthetic-only-local-test-2026'
    password_file = parent / 'test-password.txt'
    if not args.resume_initialized_test_cluster:
        password_file.write_text(password + '\n', encoding='ascii')
    elif password_file.read_text(encoding='ascii').strip() != password:
        parser.error('Test cluster marker/password differs; refusing reuse')
    env = {**os.environ, 'TEMP': str(ROOT / '.local-tmp'), 'TMP': str(ROOT / '.local-tmp'),
           'PGPASSWORD': password}
    data = parent / 'data'
    def command(name, arguments, timeout=60):
        with (parent / (name + '.log')).open('a', encoding='utf-8') as log:
            result = subprocess.run([str(binaries / (name + '.exe')), *arguments],
                                    env=env, stdout=log, stderr=log, timeout=timeout,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError(name + ' failed; see isolated log (no existing cluster changed)')
    if args.resume_initialized_test_cluster:
        if ((data / 'PG_VERSION').read_text().strip() != '17'
                or not (data / 'postgresql.conf').is_file()
                or (data / 'global/pg_control').stat().st_size != 8192):
            parser.error('Incomplete cluster; preserving directory without starting')
        command('pg_controldata', [str(data)])
    else:
        command('initdb', ['-D', str(data), '-U', 'lumiere_test', '--auth=scram-sha-256',
                           '--pwfile=' + str(password_file), '--encoding=UTF8', '--locale=C'])
    started = False
    try:
        started = True  # Also stop our cluster if startup succeeds but CLI times out.
        command('pg_ctl', ['-D', str(data), '-l', str(parent / 'server.log'), '-w', '-t', '30',
                           '-o', '-p 15439 -h 127.0.0.1', 'start'])
        database = ('lumiere_test_projection_' + str(args.projection_attempt)) if args.projection_test else ('lumiere_test_sync_' + str(args.sync_attempt))
        if args.browser_test:
            database = 'lumiere_test_browser_' + str(args.browser_attempt)
        if args.backup_restore_test:
            database = 'lumiere_test_restore_' + str(args.sync_attempt)
        if args.live_catalog_test:
            database = 'lumiere_test_catalog_' + str(args.sync_attempt)
        if args.sql_baseline_test:
            database = 'lumiere_test_sql_' + str(args.sync_attempt)
        command('createdb', ['-h', '127.0.0.1', '-p', str(port), '-U', 'lumiere_test', database])
        env['LUMIERE_SYNC_TEST_URL'] = 'postgresql+psycopg://lumiere_test:' + password + '@127.0.0.1:15439/' + database
        script = 'test_projection_integration.py' if args.projection_test else 'test_postgres_sync.py'
        if args.browser_test:
            script = 'test_browser_integration.py'
            env['LUMIERE_BROWSER_WITH_AI'] = '1' if args.browser_with_ai or args.browser_with_monitoring else '0'
            env['LUMIERE_BROWSER_WITH_MONITORING'] = '1' if args.browser_with_monitoring else '0'
            env['LUMIERE_BROWSER_NATIVE_FAULT'] = '1' if args.browser_native_fault else '0'
            env['LUMIERE_BROWSER_USE_MIGRATIONS'] = '1' if args.browser_use_migrations else '0'
        if args.backup_restore_test:
            script = 'test_backup_restore.py'
        if args.live_catalog_test:
            script = 'test_live_catalog_retrieval.py'
        if args.sql_baseline_test:
            script = 'test_sql_keyword_baseline.py'
        test_timeout = 900 if args.browser_test else (360 if args.live_catalog_test or args.projection_test else 120)
        test_log = parent / 'test.log'
        try:
            # Preserve startup/model diagnostics even if the child times out.
            with test_log.open('w', encoding='utf-8') as log:
                test = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / script),
                    '--confirm-isolated', '--report', str(args.report.resolve())], env=env,
                    timeout=test_timeout, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            if not args.report.exists():
                with args.report.open('x', encoding='utf-8') as report:
                    json.dump({'successful': False, 'error_type': 'TimeoutExpired',
                        'timeout_seconds': test_timeout, 'test_log': str(test_log.relative_to(ROOT)),
                        'production_accessed': False}, report, indent=2)
            raise
        tail = test_log.read_text(encoding='utf-8', errors='replace')[-4096:]
        print(tail.encode('ascii', errors='backslashreplace').decode('ascii'))
        if test.returncode:
            print(json.dumps({'successful': False, 'test_log': str(parent / 'test.log')}))
        return test.returncode
    finally:
        if started:
            command('pg_ctl', ['-D', str(data), '-w', '-t', '30', '-m', 'fast', 'stop'])


if __name__ == '__main__':
    raise SystemExit(main())

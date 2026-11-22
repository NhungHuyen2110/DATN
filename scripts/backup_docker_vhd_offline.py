"""User-approved OFFLINE Docker VHD backup to D; no source mutation, move or deletion.

Refuses live Docker host processes/distro, existing backup/report, insufficient
space, and unexpected paths. Holds a Windows read handle that denies writers.
"""
import argparse
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'C:\Users\Admin\AppData\Local\Docker\wsl\disk\docker_data.vhdx')


def output(command):
    result = subprocess.run(command, capture_output=True, timeout=15,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Offline prerequisite probe failed')
    data = result.stdout or b''
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else
                       ('utf-16-le' if b'\x00' in data else 'utf-8'), errors='replace')


def assert_offline():
    for name in ('Docker Desktop.exe', 'com.docker.backend.exe'):
        rows = csv.reader(output(['tasklist', '/FO', 'CSV', '/NH', '/FI', 'IMAGENAME eq ' + name]).splitlines())
        if any(row and row[0].casefold() == name.casefold() for row in rows):
            raise ValueError('Docker Desktop must be completely stopped before backup')
    running = output(['wsl', '--list', '--running', '--quiet'])
    if 'docker-desktop' in {line.strip().replace('\ufeff', '') for line in running.splitlines()}:
        raise ValueError('Docker WSL distro must be stopped before backup')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-approved-backup', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--prepare-relocation-copy', action='store_true',
                        help='After a verified backup, copy the current offline source into the approved D data directory')
    args = parser.parse_args()
    destination = ROOT / ('.local-tmp/docker-desktop-data/disk/docker_data.vhdx' if args.prepare_relocation_copy else
                          '.local-tmp/docker-recovery/20261122/docker_data.before-move.vhdx')
    approved_parent = ROOT / ('.local-tmp/docker-desktop-data' if args.prepare_relocation_copy else '.local-tmp/docker-recovery')
    if (os.name != 'nt' or str(ROOT).casefold() != r'd:\lumiere-final-test'
            or not destination.resolve().is_relative_to(approved_parent)):
        parser.error('Only the explicitly approved source and D workspace backup are supported')
    if args.prepare_relocation_copy:
        verified_backup = json.loads((ROOT / 'docs/docker-vhd-backup-20261122.json').read_text(encoding='utf-8'))
        backup_path = ROOT / '.local-tmp/docker-recovery/20261122/docker_data.before-move.vhdx'
        if (verified_backup.get('successful') is not True or verified_backup['source'] != str(SOURCE)
                or verified_backup['source_sha256'] != verified_backup['backup_sha256']
                or not backup_path.is_file() or backup_path.stat().st_size != verified_backup['bytes']):
            parser.error('An existing verified independent recovery backup is required')
    if args.report.exists() or destination.exists():
        parser.error('Backup/report already exists; never overwrite evidence')
    assert_offline()
    before = SOURCE.stat()
    if shutil.disk_usage(ROOT).free < before.st_size * 3:
        parser.error('Insufficient D free space for backup, relocation and safety margin')
    destination.parent.mkdir(parents=True, exist_ok=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    # GENERIC_READ, FILE_SHARE_READ (deny writers), OPEN_EXISTING, sequential scan.
    handle = kernel.CreateFileW(str(SOURCE), 0x80000000, 1, None, 3, 0x08000000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    import msvcrt
    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    copied, last_log, started = 0, 0, time.monotonic()
    digest = hashlib.sha256()
    with os.fdopen(descriptor, 'rb') as original, destination.open('xb') as backup:
        for chunk in iter(lambda: original.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
            backup.write(chunk)
            copied += len(chunk)
            if copied - last_log >= 1024**3:
                print(json.dumps({'copied_gib': round(copied / 1024**3, 2),
                                  'total_gib': round(before.st_size / 1024**3, 2)}), flush=True)
                last_log = copied
        backup.flush()
        os.fsync(backup.fileno())
    verified = hashlib.sha256()
    with destination.open('rb') as backup:
        for chunk in iter(lambda: backup.read(8 * 1024 * 1024), b''):
            verified.update(chunk)
    after = SOURCE.stat()
    if (copied != before.st_size or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns
            or digest.hexdigest() != verified.hexdigest()):
        raise ValueError('Backup/source verification differs; preserve files and do not relocate')
    report = {'successful': True, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'source': str(SOURCE), 'backup': str(destination), 'bytes': copied,
              'operation': 'prepare_relocation_copy' if args.prepare_relocation_copy else 'independent_recovery_backup',
              'source_sha256': digest.hexdigest(), 'backup_sha256': verified.hexdigest(),
              'source_size_and_mtime_unchanged': True, 'offline_backup': True,
              'source_deleted': False, 'storage_relocated': False,
              'elapsed_seconds': round(time.monotonic() - started, 3)}
    with args.report.open('x', encoding='utf-8') as result:
        json.dump(report, result, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()

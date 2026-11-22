"""Activate an already verified D copy using a directory junction; preserve the old C directory.

No recursive deletion, volume reset, unregister or unsupported Docker setting.
All filesystem moves stay in one native PowerShell command with fixed, checked
source/target paths. Use only after the user's explicit storage-move approval.
"""
import argparse
import json
from pathlib import Path
import subprocess
from backup_docker_vhd_offline import assert_offline

ROOT = Path(__file__).resolve().parents[1]

ACTIVATE = r'''
$ErrorActionPreference='Stop'
$sourceDirectory='C:\Users\Admin\AppData\Local\Docker\wsl\disk'
$retainedDirectory='C:\Users\Admin\AppData\Local\Docker\wsl\disk.before-move-20261122'
$targetDirectory='D:\LUMIERE-FINAL-TEST\.local-tmp\docker-desktop-data\disk'
$approvedSourceParent='C:\Users\Admin\AppData\Local\Docker\wsl\'
$approvedTargetParent='D:\LUMIERE-FINAL-TEST\.local-tmp\docker-desktop-data\'
if (([IO.Path]::GetFullPath($sourceDirectory)) -ne $sourceDirectory -or
    -not ([IO.Path]::GetFullPath($retainedDirectory)).StartsWith($approvedSourceParent,[StringComparison]::OrdinalIgnoreCase) -or
    -not ([IO.Path]::GetFullPath($targetDirectory)).StartsWith($approvedTargetParent,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Resolved paths outside approved Docker locations'
}
if (Test-Path -LiteralPath $retainedDirectory) { throw 'Retained original already exists; no overwrite' }
$sourceItem=Get-Item -LiteralPath $sourceDirectory -Force
$targetItem=Get-Item -LiteralPath $targetDirectory -Force
if (($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    ($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected source/target reparse point' }
$copy=Get-Content -LiteralPath 'D:\LUMIERE-FINAL-TEST\docs\docker-vhd-relocation-copy-20261122.json' -Raw | ConvertFrom-Json
$sourceHash=(Get-FileHash -LiteralPath ($sourceDirectory+'\docker_data.vhdx') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sourceHash -ne $copy.source_sha256 -or
    (Get-Item -LiteralPath ($targetDirectory+'\docker_data.vhdx')).Length -ne $copy.bytes) { throw 'Verified copy differs' }
Rename-Item -LiteralPath $sourceDirectory -NewName 'disk.before-move-20261122' -ErrorAction Stop
try {
    New-Item -ItemType Junction -Path $sourceDirectory -Value $targetDirectory -ErrorAction Stop | Out-Null
} catch {
    # Revert same-volume directory rename if junction creation did not happen.
    if (-not (Test-Path -LiteralPath $sourceDirectory)) {
        Rename-Item -LiteralPath $retainedDirectory -NewName 'disk' -ErrorAction Stop
    }
    throw
}
$junction=Get-Item -LiteralPath $sourceDirectory -Force
if ($junction.LinkType -ne 'Junction' -or @($junction.Target)[0] -ne $targetDirectory) {
    throw 'Unexpected junction; originals retained for manual recovery'
}
[ordered]@{successful=$true;logical_docker_directory=$sourceDirectory;physical_docker_directory=$targetDirectory;
    link_type=$junction.LinkType;retained_original_directory=$retainedDirectory;
    original_removed=$false;existing_settings_modified=$false;runtime_verified=$false} | ConvertTo-Json -Depth 4
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-approved-relocation', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report already exists')
    for name in ('docker-vhd-backup-20261122.json', 'docker-vhd-relocation-copy-20261122.json'):
        evidence = json.loads((ROOT / 'docs' / name).read_text(encoding='utf-8'))
        if not evidence.get('successful') or evidence['source_sha256'] != evidence['backup_sha256']:
            parser.error('Both independent backup and relocation copy must have matching checksums')
    assert_offline()
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ACTIVATE],
                            capture_output=True, timeout=180,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    log = ROOT / '.local-tmp/docker-recovery/20261122/activation.log'
    log.write_bytes((result.stdout or b'') + (result.stderr or b''))
    if result.returncode:
        raise RuntimeError('Storage activation stopped; original directory and backup preserved; see activation.log')
    report = json.loads(result.stdout.decode('utf-8-sig'))
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()

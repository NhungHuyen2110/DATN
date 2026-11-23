param([string]$Model='qwen3:0.6b-q4_K_M', [string]$ModelDirectory='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$stateDir=Join-Path $projectRoot '.local-tmp'
$binary=(Get-Command ollama -ErrorAction Stop).Source
if ($Model -notmatch '^[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+$') { throw 'Explicit model name:tag required.' }
$modelDir=if ($ModelDirectory) { $ModelDirectory } else { Join-Path $stateDir 'dialogue-small-models' }
$modelParts=$Model.Split(':')
$manifest=Join-Path $modelDir ('manifests\registry.ollama.ai\library\'+$modelParts[0]+'\'+$modelParts[1])
if (!(Test-Path -LiteralPath $manifest)) { throw 'Prepared local model required; no automatic download.' }
$listener=Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner=Get-Process -Id $listener[0].OwningProcess
    if ($owner.ProcessName -ne 'ollama' -or $owner.Path -ne $binary) { throw 'Port 11435 belongs to another process.' }
    Write-Output 'Local Ollama already listening; no second instance started.'
    exit 0
}
$env:OLLAMA_HOST='127.0.0.1:11435'
$env:OLLAMA_MODELS=$modelDir
$env:OLLAMA_NUM_PARALLEL='1'
$env:OLLAMA_MAX_LOADED_MODELS='1'
$env:OLLAMA_CONTEXT_LENGTH='1024'
$env:OLLAMA_KEEP_ALIVE='30m'
$env:OLLAMA_NO_CLOUD='1'
$env:TEMP=$stateDir
$env:TMP=$stateDir
$instance=Start-Process -FilePath $binary -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $stateDir 'host-dialogue.stdout.log') `
    -RedirectStandardError (Join-Path $stateDir 'host-dialogue.stderr.log')
$instance.Id | Set-Content -LiteralPath (Join-Path $stateDir 'host-dialogue.pid')
Write-Output "Local Ollama started, PID $($instance.Id). No model downloaded."

param(
    [string]$Neo4jHome = '.cache/runtime/neo4j-community-5.26.33',
    [string]$JavaHome = '.cache/runtime/jdk-21.0.9+10'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cacheRoot = [IO.Path]::GetFullPath((Join-Path $workspaceRoot '.cache'))
$graphHome = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $Neo4jHome))
$jdkRoot = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $JavaHome))
$testRoot = [IO.Path]::GetFullPath((Join-Path $cacheRoot 'neo4j-test'))
foreach ($target in @($graphHome, $jdkRoot, $testRoot)) {
    if (-not $target.StartsWith($cacheRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Test runtime paths must remain inside workspace .cache'
    }
}
$marker = Join-Path $testRoot 'LUMIERE-ISOLATED-TEST'
if ((Test-Path -LiteralPath $testRoot) -and -not (Test-Path -LiteralPath $marker)) {
    throw 'Refusing to use an unmarked existing graph directory'
}
foreach ($directory in @('conf', 'data', 'logs', 'import', 'plugins', 'run')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $testRoot $directory) | Out-Null
}
[IO.File]::WriteAllText($marker, 'Dedicated LUMIERE test data; never production')
$unixRoot = $testRoot.Replace('\', '/')
$configuration = @"
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:17687
server.http.listen_address=127.0.0.1:17474
server.https.enabled=false
server.memory.heap.initial_size=256m
server.memory.heap.max_size=512m
server.memory.pagecache.size=256m
server.directories.data=$unixRoot/data
server.directories.logs=$unixRoot/logs
server.directories.import=$unixRoot/import
server.directories.plugins=$unixRoot/plugins
server.directories.run=$unixRoot/run
dbms.security.auth_enabled=true
dbms.usage_report.enabled=false
"@
[IO.File]::WriteAllText((Join-Path $testRoot 'conf/neo4j.conf'), $configuration, (New-Object Text.UTF8Encoding($false)))
$env:JAVA_HOME = $jdkRoot
$env:NEO4J_HOME = $graphHome
$env:NEO4J_CONF = Join-Path $testRoot 'conf'
$javaExecutable = Join-Path $jdkRoot 'bin/java.exe'
$classPath = Join-Path $graphHome 'lib/*'
$initialized = Join-Path $testRoot 'INITIALIZED'
if (-not (Test-Path -LiteralPath $initialized)) {
    # Public fixture-only password for a private loopback test instance.
    & $javaExecutable -cp $classPath org.neo4j.server.startup.Neo4jAdminBoot dbms set-initial-password lumiere-test-only-password
    if ($LASTEXITCODE -ne 0) { throw 'Neo4j test password initialization failed' }
    [IO.File]::WriteAllText($initialized, 'test-only-initialized')
}
$pidPath = Join-Path $testRoot 'java.pid'
if (Test-Path -LiteralPath $pidPath) {
    $previousPid = [int](Get-Content -LiteralPath $pidPath)
    $previousProcess = Get-Process -Id $previousPid -ErrorAction SilentlyContinue
    if ($previousProcess -and $previousProcess.Path -eq $javaExecutable) {
        Write-Output "Owned test runtime already running: PID $previousPid"
        return
    }
}
$process = Start-Process -FilePath $javaExecutable -ArgumentList @('-cp', ('"' + $classPath + '"'), 'org.neo4j.server.startup.Neo4jBoot', 'console') -WorkingDirectory $graphHome -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $testRoot 'logs/bootstrap.out.log') -RedirectStandardError (Join-Path $testRoot 'logs/bootstrap.err.log')
[IO.File]::WriteAllText($pidPath, [string]$process.Id)
Write-Output "Started isolated test Neo4j PID $($process.Id); Bolt 127.0.0.1:17687, HTTP 127.0.0.1:17474"

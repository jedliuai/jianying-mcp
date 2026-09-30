param(
    [string]$InstallDir,
    [string]$DraftRoot,
    [string]$UserData,
    [switch]$KeepStandaloneMcp
)
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
$entryFile = Join-Path $projectDir 'run_mcp.py'
$configPath = Join-Path $projectDir 'local.config.json'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw '这个插件需要 Windows 本机剪映。' }
Push-Location -LiteralPath $projectDir
try {
    if ($InstallDir -or $DraftRoot -or $UserData -or -not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $configPath)) {
        $setupParams = @{}
        if ($InstallDir) { $setupParams['InstallDir'] = $InstallDir }
        if ($DraftRoot) { $setupParams['DraftRoot'] = $DraftRoot }
        if ($UserData) { $setupParams['UserData'] = $UserData }
        & (Join-Path $projectDir 'setup.ps1') @setupParams
    }
    $doctorText = & $pythonExe -m jianying_bridge.cli doctor
    if ($LASTEXITCODE -ne 0) { throw '本地运行环境检查失败。' }
    $doctor = ($doctorText -join "`n") | ConvertFrom-Json
    if (-not $doctor.native_codec_exists) { throw '剪映 DLL 不存在，请用 -InstallDir 设置正确的版本目录。' }

    $backupDir = Join-Path $projectDir 'work/config-backups'
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $backupId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N'))
    $codexDataRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
    $codexConfig = Join-Path $codexDataRoot 'config.toml'
    if (Test-Path -LiteralPath $codexConfig) {
        Copy-Item -LiteralPath $codexConfig -Destination (Join-Path $backupDir "codex-plugin-$backupId.toml")
    }
    $runtimeRoot = Join-Path $env:LOCALAPPDATA 'jianying-mcp'
    $runtimePath = Join-Path $runtimeRoot 'runtime.json'
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    if (Test-Path -LiteralPath $runtimePath) {
        Copy-Item -LiteralPath $runtimePath -Destination (Join-Path $backupDir "runtime-$backupId.json")
    }
    $runtime = @{
        schema_version = 1
        python = (Resolve-Path -LiteralPath $pythonExe).Path
        entry = (Resolve-Path -LiteralPath $entryFile).Path
        config = (Resolve-Path -LiteralPath $configPath).Path
    }
    $temporaryRuntime = Join-Path $runtimeRoot ('.runtime-{0}.tmp' -f ([guid]::NewGuid().ToString('N')))
    try {
        [System.IO.File]::WriteAllText($temporaryRuntime, ($runtime | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporaryRuntime -Destination $runtimePath -Force
    } finally {
        if (Test-Path -LiteralPath $temporaryRuntime) { Remove-Item -LiteralPath $temporaryRuntime }
    }

    codex plugin marketplace add $projectDir --json
    if ($LASTEXITCODE -ne 0) { throw '登记插件源失败，原独立 MCP 配置保留。' }
    codex plugin add jianying-mcp@jianying-local-plugins --json
    if ($LASTEXITCODE -ne 0) { throw '安装插件失败，原独立 MCP 配置保留。' }
    $listText = codex plugin list --marketplace jianying-local-plugins --json
    if ($LASTEXITCODE -ne 0) { throw '无法检查插件安装状态，原独立 MCP 配置保留。' }
    $pluginList = ($listText -join "`n") | ConvertFrom-Json
    $installed = @($pluginList.installed | Where-Object { $_.pluginId -eq 'jianying-mcp@jianying-local-plugins' -and $_.enabled })
    if ($installed.Count -ne 1) { throw '插件未启用，原独立 MCP 配置保留。' }

    $cacheParent = Join-Path $codexDataRoot 'plugins/cache/jianying-local-plugins/jianying-mcp'
    $installedRoot = Get-ChildItem -LiteralPath $cacheParent -Directory | Sort-Object LastWriteTime -Descending |
        Where-Object { (Test-Path -LiteralPath (Join-Path $_.FullName '.mcp.json')) -and
                       (Test-Path -LiteralPath (Join-Path $_.FullName 'skills/jianying-sound-design/SKILL.md')) } |
        Select-Object -First 1
    if (-not $installedRoot) { throw '没有找到插件安装副本，原独立 MCP 配置保留。' }
    foreach ($relative in @('.mcp.json', '.codex-plugin/plugin.json', 'skills/jianying-sound-design/SKILL.md')) {
        $sourceHash = (Get-FileHash -LiteralPath (Join-Path $projectDir "plugins/jianying-mcp/$relative") -Algorithm SHA256).Hash
        $installedHash = (Get-FileHash -LiteralPath (Join-Path $installedRoot.FullName $relative) -Algorithm SHA256).Hash
        if ($sourceHash -ne $installedHash) { throw '安装副本未刷新，请先移除本插件再重新安装；原独立 MCP 配置保留。' }
    }
    & $pythonExe (Join-Path $projectDir 'tools/smoke_mcp.py') --plugin $installedRoot.FullName
    if ($LASTEXITCODE -ne 0) { throw '插件 MCP 握手失败，原独立 MCP 配置保留。' }

    if (-not $KeepStandaloneMcp) {
        $mcpText = codex mcp list --json
        if ($LASTEXITCODE -ne 0) { throw '插件已安装，但无法检查旧独立 MCP 配置。' }
        $connections = ($mcpText -join "`n") | ConvertFrom-Json
        $duplicate = @($connections | Where-Object {
            $_.name -eq 'jianying-local' -and $_.transport.command -eq $runtime.python -and $_.transport.args -contains $runtime.entry
        })
        if ($duplicate.Count -eq 1) {
            codex mcp remove jianying-local
            if ($LASTEXITCODE -ne 0) { throw '插件已安装，移除重复独立 MCP 失败。' }
        }
    }
    Write-Output '已安装并验证「剪映音效助手」。重启 Codex、开新聊天后可使用插件和音效编排技能。'
    Write-Output '运行指针和配置备份留在本机；安装过程没有修改剪映工程。'
} finally {
    Pop-Location
}

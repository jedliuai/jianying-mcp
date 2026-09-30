$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
$entryFile = Join-Path $projectDir 'run_mcp.py'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw '请先运行 setup.ps1 安装依赖。' }
$codexConfig = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex/config.toml'
if (Test-Path -LiteralPath $codexConfig) {
    $backupDir = Join-Path $projectDir 'work/config-backups'
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $backupName = 'codex-{0}-{1}.toml' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath $codexConfig -Destination (Join-Path $backupDir $backupName)
}
codex mcp add jianying-local --env PYTHONIOENCODING=utf-8 -- $pythonExe $entryFile
if ($LASTEXITCODE -ne 0) { throw 'MCP 配置写入失败。' }
Write-Output '已配置 jianying-local。重启 Codex 后可加载 MCP；当前聊天可直接使用 CLI。'

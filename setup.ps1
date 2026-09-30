param(
    [string]$InstallDir,
    [string]$DraftRoot,
    [string]$UserData
)
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
Push-Location -LiteralPath $projectDir
try {
    uv sync --frozen --extra dev --cache-dir (Join-Path $projectDir '.cache/uv')
    if ($LASTEXITCODE -ne 0) { throw '安装依赖失败。' }
    $configPath = Join-Path $projectDir 'local.config.json'
    $config = @{}
    if (Test-Path -LiteralPath $configPath) {
        $existing = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        foreach ($property in $existing.PSObject.Properties) { $config[$property.Name] = $property.Value }
    }
    if ($InstallDir) { $config['install_dir'] = (Resolve-Path -LiteralPath $InstallDir).Path }
    if ($DraftRoot) { $config['draft_root'] = (Resolve-Path -LiteralPath $DraftRoot).Path }
    if ($UserData) { $config['user_data'] = (Resolve-Path -LiteralPath $UserData).Path }
    if (-not $config.ContainsKey('install_dir')) { throw '首次运行需要 -InstallDir 指定含 videoeditor.dll 的剪映版本目录。' }
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
    & (Join-Path $projectDir '.venv/Scripts/python.exe') -m jianying_bridge.cli doctor
    if ($LASTEXITCODE -ne 0) { throw '环境检查失败。' }
} finally {
    Pop-Location
}

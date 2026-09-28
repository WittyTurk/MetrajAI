$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

foreach ($command in @('py', 'node', 'npm', 'cargo', 'rustc')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command bulunamadı. Python 3.13, Node.js 22 ve Rust araçlarını kurun."
    }
}

& py -3.13 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 bulunamadı.' }

& py -3.13 -m venv .venv-windows
if ($LASTEXITCODE -ne 0) { throw 'Python sanal ortamı oluşturulamadı.' }
$python = Join-Path $root '.venv-windows\Scripts\python.exe'

& $python -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Python bağımlılıkları kurulamadı.' }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Python testleri başarısız.' }
& $python scripts/package_sidecar.py
if ($LASTEXITCODE -ne 0) { throw 'Windows hesap motoru paketlenemedi.' }

Push-Location (Join-Path $root 'desktop')
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Arayüz bağımlılıkları kurulamadı.' }
    & npm test
    if ($LASTEXITCODE -ne 0) { throw 'Arayüz testleri başarısız.' }
    & npm run tauri -- build --config src-tauri/tauri.windows.conf.json
    if ($LASTEXITCODE -ne 0) { throw 'Windows kurulum paketi üretilemedi.' }
} finally {
    Pop-Location
}

$bundleDirectory = Join-Path $root 'desktop\src-tauri\target\release\bundle\nsis'
$installer = Get-ChildItem $bundleDirectory -Filter '*.exe' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $installer) { throw 'NSIS kurulum dosyası bulunamadı.' }

$releaseDirectory = Join-Path $root 'local-releases'
New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null
$destination = Join-Path $releaseDirectory $installer.Name
Copy-Item $installer.FullName $destination -Force
Write-Host "Windows kurulum dosyası: $destination"

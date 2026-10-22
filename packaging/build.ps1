param([Parameter(Mandatory=$true)][string]$IsccPath)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$projectDirectory = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectDirectory
$env:UV_PROJECT_ENVIRONMENT = Join-Path $projectDirectory '.build-venv'
$env:PYTHONPATH = ''
uv sync --frozen --no-dev --group build
$buildPython = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts/python.exe'
$releaseVersion = & $buildPython -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'
& $buildPython -m PyInstaller packaging/smallthings.spec --noconfirm --clean
& $IsccPath /Q "/DAppVersion=$releaseVersion" packaging/installer.iss
$installerFile = Join-Path $projectDirectory "dist/installer/AllTheSmallThings-$releaseVersion-windows-amd64-setup.exe"
$installerHash = (Get-FileHash -LiteralPath $installerFile -Algorithm SHA256).Hash.ToLowerInvariant()
"$installerHash  $(Split-Path $installerFile -Leaf)" | Set-Content -LiteralPath 'dist/installer/SHA256SUMS.txt' -Encoding ascii

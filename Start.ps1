$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\pythonw.exe'
Start-Process -FilePath $pythonExecutable -ArgumentList '-m smallthings.app' -WorkingDirectory $projectDirectory -Verb RunAs -WindowStyle Normal

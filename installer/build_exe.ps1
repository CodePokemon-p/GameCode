# build_exe.ps1 - builds dist\GameCode\GameCode.exe with PyInstaller
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # go to project root

pip install pyinstaller

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

pyinstaller `
  --onedir `
  --name GameCode `
  --paths src `
  --collect-all textual `
  --collect-all rich `
  --collect-submodules gamecode `
  --noconfirm `
  run_gamecode.py

Write-Host ""
Write-Host "Done. Run: .\dist\GameCode\GameCode.exe"
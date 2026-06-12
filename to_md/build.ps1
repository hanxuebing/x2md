#!/usr/bin/env pwsh
# 构建单文件可执行：dist\wx2md.exe (Windows) / dist/wx2md (mac/linux)
# 用法： .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host ">> 同步依赖（含 dev 组：pyinstaller）" -ForegroundColor Cyan
uv sync --group dev

Write-Host ">> 清理旧产物" -ForegroundColor Cyan
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build, wx2md.spec

Write-Host ">> 打包" -ForegroundColor Cyan
uv run pyinstaller `
    --onefile `
    --name wx2md `
    --console `
    --collect-submodules httpx `
    --collect-submodules bs4 `
    --hidden-import lxml `
    --hidden-import lxml._elementpath `
    wx2md/__main__.py

Write-Host ">> 完成" -ForegroundColor Green
Get-ChildItem dist | Format-Table Name, Length, LastWriteTime

#!/usr/bin/env bash
# 构建单文件可执行：dist/wx2md
# 用法：bash build.sh

set -euo pipefail

echo ">> 同步依赖（含 dev 组：pyinstaller）"
uv sync --group dev

echo ">> 清理旧产物"
rm -rf dist build wx2md.spec

echo ">> 打包"
uv run pyinstaller \
    --onefile \
    --name wx2md \
    --console \
    --collect-submodules httpx \
    --collect-submodules bs4 \
    --hidden-import lxml \
    --hidden-import lxml._elementpath \
    wx2md/__main__.py

echo ">> 完成"
ls -lh dist/

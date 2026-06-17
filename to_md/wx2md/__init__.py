"""wx2md —— 微信公众号 / 百度百家号文章转 Markdown + HTML + 本地图片的工具包。

本包对外暴露的核心 API:
    - Article:         单篇文章处理结果的数据类
    - Meta:            文章元信息(标题/作者/发布时间/IP 属地等)
    - process_article: 处理单篇文章的入口函数(抓取 -> 解析 -> 下载 -> 输出)
    - __version__:     当前包版本号
"""
from __future__ import annotations

# 包版本号,通过 `python -m wx2md -V` 或 CLI `--version` 参数显示
__version__ = "0.1.0"

# 仅暴露稳定的公开接口,内部实现(net/parser/templates 等)保持私有
from .core import Article, process_article
from .parser import Meta

__all__ = ["Article", "Meta", "process_article", "__version__"]

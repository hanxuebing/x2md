"""百家号文章的 DOM 解析:提取元信息、收集图片、重写内容。

百家号 (baijiahao.baidu.com) 页面特点:
    - SSR 渲染,正文可从 HTML 直接提取
    - CSS class 名由 CSS Modules 生成(哈希),可能随百度前端部署变化
    - 图片直接走 src(无 data-src 懒加载)
    - 图片 CDN 不设防盗链 Referer 校验
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .common import Meta

# ── 来源接口常量 ──────────────────────────────────────────────

CONTENT_SELECTOR = ".EaCvy"
REFERER = None
BODY_CLASS = "bjh-article-content"

# 需要从容器中删除的元素(评论区、举报按钮、搜索推荐)
_REMOVE_SELECTORS = [
    "#commentModule",
    "._3hMwG",
    '[data-testid="search-rec"]',
    ".bH7m7",
]


def parse_meta(soup: BeautifulSoup) -> Meta:
    """从百家号 SSR HTML 中提取元信息。

    百家号页面结构:
        .EaCvy 容器 > 第一个子 div 为 header 区(标题+作者+日期)
        - .sKHSJ: 标题
        - ._2gGWi (在 <a> 或 <p> 内): 作者/账号名
        - ._2sjh9: 发布时间 "YYYY-MM-DD HH:MM"
        - ._2Wctx: 发布地区
    """
    # 标题:优先从 header 区的标题 class 取,兜底用 <title>
    title_el = soup.select_one(".sKHSJ")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
    # 百度的 title 常带后缀 "_百度百家号"
    title = re.sub(r"\s*[-_|]\s*百.*$", "", title).strip() or "untitled"

    # 作者/账号名
    author_el = soup.select_one("._2gGWi")
    account_name = author_el.get_text(strip=True) if author_el else ""

    # 发布时间
    time_el = soup.select_one("._2sjh9")
    publish_date = ""
    if time_el:
        raw = time_el.get_text(strip=True)
        # 格式通常为 "2026-06-10 17:07"
        m = re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", raw)
        if m:
            publish_date = m.group(0)

    # 发布地区(百家号有时会显示省份)
    location_el = soup.select_one("._2Wctx")
    location = location_el.get_text(strip=True) if location_el else ""

    return Meta(
        title=title,
        account_name=account_name,
        author="",
        publish_date=publish_date,
        location=location,
        is_original=False,
    )


def collect_images(content: Tag) -> list[str]:
    """从百家号正文中收集去重后的图片 URL。

    百家号不使用 data-src 懒加载,图片地址直接在 src 中。
    """
    urls: list[str] = []
    seen: set[str] = set()
    for img in content.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        if src not in seen:
            seen.add(src)
            urls.append(src)
    return urls


def rewrite_content(content: Tag, mapping: dict[str, str]) -> None:
    """就地改写百家号正文 DOM:替换图片路径、删除脚本/不需要的元素。"""
    # 删除需排除的区块
    for sel in _REMOVE_SELECTORS:
        for el in content.select(sel):
            el.decompose()

    # 删危险标签
    for bad in content.find_all(["script", "iframe"]):
        bad.decompose()

    # 替换图片地址为本地路径
    for img in content.find_all("img"):
        src = (img.get("src") or "").strip()
        if src in mapping:
            img["src"] = f"assets/{mapping[src]}"
        elif src:
            img["src"] = src

"""核心编排层:抓取一篇文章 -> 解析 -> 下载图片 -> 输出 MD + HTML + images/。

每篇文章独立产出一个目录:
    <output>/<安全标题>/
        ├── article.md       (含 YAML frontmatter)
        ├── article.html     (保留原文样式,可离线阅读)
        └── images/          (按内容 sha1 命名的图片)
"""
from __future__ import annotations

import html as html_lib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .net import download_image, fetch_article
from .parser import (
    Meta,
    collect_images,
    extract_head_styles,
    parse_meta,
    rewrite_content,
    to_markdown,
)
from .templates import HTML_TEMPLATE

# Windows 文件名非法字符集合(含控制字符 \r \n \t),用于清洗标题
INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

log = logging.getLogger("wx2md.core")


@dataclass
class Article:
    """单篇文章的处理结果,供调用方进一步处理(如入库、生成索引等)。"""

    url: str               # 原文 URL
    title: str             # 文章标题
    account_name: str      # 公众号名称
    author: str            # 个人作者(若与公众号不同)
    publish_date: str      # 发布时间 "YYYY-MM-DD HH:MM"
    location: str          # IP 属地
    is_original: bool      # 是否标记为"原创"
    html: str              # 重写后的正文 HTML(图片指向本地)
    images: dict[str, str] # 原始 URL -> 本地文件名 映射


def safe_filename(name: str, default: str = "untitled") -> str:
    """把标题清洗为 Windows 合法的文件夹名。

    规则:
        1. 非法字符替换为 _
        2. 去掉首尾空格和点(Windows 不允许文件名以点结尾)
        3. 截断到 120 字符,避免触发 Windows 260 路径上限
        4. 若清洗后变空,用 default 兜底
    """
    name = INVALID_CHARS.sub("_", name).strip(" .")
    return name[:120] or default


def _yaml_quote(value: str) -> str:
    """把字符串包装为合法的 YAML 双引号字符串。

    必须转义反斜杠和双引号本身,并把所有连续空白(含换行)压成单个空格,
    避免多行标题破坏 frontmatter 结构。
    """
    cleaned = value.replace("\\", "\\\\").replace('"', '\\"')
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return f'"{cleaned}"'


def _render_frontmatter(meta: Meta, url: str) -> str:
    """生成 Markdown 顶部的 YAML frontmatter 块,空字段不输出。

    frontmatter 字段顺序固定,便于 diff / Git 友好。
    """
    fields: list[tuple[str, str]] = [("title", _yaml_quote(meta.title))]
    # 仅在字段非空时追加,保持输出整洁
    if meta.account_name:
        fields.append(("account", _yaml_quote(meta.account_name)))
    if meta.author:
        fields.append(("author", _yaml_quote(meta.author)))
    if meta.publish_date:
        fields.append(("date", _yaml_quote(meta.publish_date)))
    if meta.location:
        fields.append(("location", _yaml_quote(meta.location)))
    if meta.is_original:
        # 布尔字段不加引号,符合 YAML 规范
        fields.append(("original", "true"))
    # URL 始终输出,便于反查原文
    fields.append(("url", _yaml_quote(url)))

    body = "\n".join(f"{k}: {v}" for k, v in fields)
    return f"---\n{body}\n---\n"


def _render_meta_line(meta: Meta, url: str) -> str:
    """构造 HTML 头部那行 meta 信息,各字段用全角间隔点 ` · ` 分隔。

    输出顺序模拟微信 App 中的展示效果:
        [原创] 公众号 · 作者 · 时间 · 属地 · 原文链接
    """
    parts: list[str] = []
    if meta.is_original:
        # "原创" 用独立 span 包装,便于 CSS 加边框样式
        parts.append('<span class="tag-original">原创</span>')
    if meta.account_name:
        parts.append(html_lib.escape(meta.account_name))
    # 个人作者若与公众号同名则不重复展示
    if meta.author and meta.author != meta.account_name:
        parts.append(html_lib.escape(meta.author))
    if meta.publish_date:
        parts.append(html_lib.escape(meta.publish_date))
    if meta.location:
        parts.append(html_lib.escape(meta.location))
    # 原文链接用新窗口打开,rel=noopener 避免被反向引用 window.opener
    parts.append(f'<a href="{html_lib.escape(url, quote=True)}" target="_blank" rel="noopener">原文链接</a>')
    return " · ".join(parts)


def process_article(
    url: str,
    out_root: Path,
    img_workers: int,
    client: httpx.Client,
) -> Article:
    """处理单篇文章的完整流水线 —— 被 cli.main 的线程池并发调度。"""
    log.info("fetch %s", url)
    # 1) 抓取 SSR HTML
    html = fetch_article(url, client)
    # lxml 解析速度比内置 html.parser 快很多,且对微信不规范的标签更宽容
    soup = BeautifulSoup(html, "lxml")
    # 2) 提取元信息(标题/作者/时间...)与 head 内联样式
    meta = parse_meta(soup)
    head_styles = extract_head_styles(soup)

    # 微信正文统一放在 #js_content 容器中
    content = soup.select_one("#js_content")
    if content is None:
        # 未登录 / 链接失效 / 文章已删除时常见
        raise RuntimeError("content div #js_content not found — login wall or invalid URL?")

    # 3) 准备输出目录:<output>/<安全标题>/images/
    folder = out_root / safe_filename(meta.title)
    img_dir = folder / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 4) 收集正文里所有真实图片 URL
    image_urls = collect_images(content)
    log.info("[%s] %d images", meta.title, len(image_urls))

    # 5) 并发下载图片;mapping 记录 原始 URL -> 本地文件名
    mapping: dict[str, str] = {}
    if image_urls:
        with ThreadPoolExecutor(max_workers=img_workers) as pool:
            futs = [pool.submit(download_image, u, img_dir, client) for u in image_urls]
            for f in as_completed(futs):
                u, fname = f.result()
                if fname:
                    mapping[u] = fname

    # 6) 把 DOM 里的图片地址替换为本地路径,顺便清理 <script> 等不安全标签
    rewrite_content(content, mapping)
    # 用 decode() 而不是 decode_contents():保留 #js_content 这个外层标签,
    # 这样它的 class="rich_media_content" 才会留下,head 中
    # 形如 .rich_media_content xxx 的样式规则才能命中,离线 HTML 排版才会正常。
    body_html = content.decode()
    # 7) HTML 转 Markdown(markdownify 内部会忽略 style/class,只看语义标签)
    md_text = to_markdown(body_html)

    # 8) 写出 article.md(含 frontmatter + 一级标题 + 正文)
    frontmatter = _render_frontmatter(meta, url)
    (folder / "article.md").write_text(
        f"{frontmatter}\n# {meta.title}\n\n{md_text}\n",
        encoding="utf-8",
    )
    # 9) 写出 article.html(用本地模板包裹,保留微信原样式)
    (folder / "article.html").write_text(
        HTML_TEMPLATE.format(
            title=html_lib.escape(meta.title),
            head_styles=head_styles,
            meta_line=_render_meta_line(meta, url),
            body=body_html,
        ),
        encoding="utf-8",
    )

    log.info("done %s -> %s", meta.title, folder)
    return Article(
        url=url,
        title=meta.title,
        account_name=meta.account_name,
        author=meta.author,
        publish_date=meta.publish_date,
        location=meta.location,
        is_original=meta.is_original,
        html=body_html,
        images=mapping,
    )

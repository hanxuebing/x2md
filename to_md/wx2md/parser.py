"""DOM 解析层:提取元信息、收集图片、重写为本地引用、转换 Markdown。

微信文章 SSR 后的 HTML 结构相对稳定,但元信息散落在多个角落
(可见 DOM、隐藏 meta、内联 script 里的 JS 变量),所以每个字段
都有多套兜底策略,确保即使某种渠道失效也能拿到值。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md


@dataclass
class Meta:
    """文章元信息,所有字段都有合理默认值(空字符串 / False)。"""

    title: str                       # 标题,必填
    account_name: str = ""           # 公众号名称
    author: str = ""                 # 个人作者(独立于公众号)
    publish_date: str = ""           # 发布时间 "YYYY-MM-DD HH:MM"
    location: str = ""               # IP 属地
    is_original: bool = False        # 是否带"原创"标识


# 内联 JS 中的 `var ct = "1700000000"` 形式 —— 发布时间的 Unix 秒
_CT_RE = re.compile(r'var\s+ct\s*=\s*"(\d+)"')
# 内联 JS 中的 `var publish_time = "2024-01-01 12:00"` 形式
_PUBLISH_TIME_RE = re.compile(r'var\s+publish_time\s*=\s*"([^"]+)"')


def _text(el) -> str:
    """安全地取 DOM 元素的纯文本;el 为 None 时返回空串。"""
    return el.get_text(strip=True) if el else ""


def _extract_publish_date(soup: BeautifulSoup) -> str:
    """提取发布时间,返回 "YYYY-MM-DD HH:MM" 或空串。

    尝试顺序(逐级兜底):
        1) #publish_time 元素 —— 真实浏览器里由 JS 渲染,但很多页面 SSR 时
           已经把字面值写进来了,优先用它;
        2) 内联 script 里的 `var ct = "<unix秒>"`,自己格式化;
        3) 内联 script 里的 `var publish_time = "..."` 字面值。
    """
    # 兜底 1:可见元素
    raw = _text(soup.select_one("#publish_time"))
    if raw and re.match(r"\d{4}-\d{2}-\d{2}", raw):
        # 截掉秒位,把 ISO 风格的 T 替换为空格
        return raw[:16].replace("T", " ").strip()

    html = str(soup)
    # 兜底 2:Unix 秒,转本地时区
    m = _CT_RE.search(html)
    if m:
        try:
            ts = int(m.group(1))
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            # ts 越界或非法时跳过,继续尝试下一种
            pass

    # 兜底 3:字面值
    m = _PUBLISH_TIME_RE.search(html)
    if m:
        val = m.group(1).strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", val):
            return val[:16].replace("T", " ").strip()

    # 所有渠道都失败 —— 返回空串,frontmatter 里会自动省略
    return ""


def _extract_author(soup: BeautifulSoup, account_name: str) -> str:
    """提取个人作者名(注意:不等同于公众号名)。

    部分公众号会同时挂"公众号名"和"作者名",二者不同时才有意义。
    """
    # 优先用专门的作者元素
    el = soup.select_one("#js_author_name")
    name = _text(el)
    if name:
        return name

    # 兜底:meta_content 区域里第一个不是版权 logo / 公众号名的文本块
    for el in soup.select("#meta_content .rich_media_meta_text"):
        if el.get("id") in {"copyright_logo", "js_name"}:
            continue
        txt = _text(el)
        # 与公众号同名时视作没有独立作者,避免重复显示
        if txt and txt != account_name:
            return txt

    # 最后兜底:内联 JS 中的 `var author = "..."`
    m = re.search(r'var\s+author\s*=\s*"([^"]+)"', str(soup))
    if m:
        return m.group(1).strip()

    return ""


def _extract_location(soup: BeautifulSoup) -> str:
    """提取 IP 属地,去掉冗余前缀("发表于"、"IP属地:" 等)。"""
    raw = _text(soup.select_one("#js_ip_wording")) or _text(soup.select_one("#js_ip_wording_wrp"))
    # 微信展示文案常带"发表于 北京"或"IP 属地:北京",一律去掉前缀,只留地名
    return re.sub(r"^(发表于|IP\s*属地[:：]?)\s*", "", raw).strip()


def parse_meta(soup: BeautifulSoup) -> Meta:
    """从微信 SSR 后的 DOM 中一次性抽取所有元信息。"""
    # 标题:优先用页面可见标题,兜底 og:title
    title_el = soup.select_one("#activity-name") or soup.select_one("meta[property='og:title']")
    if title_el and title_el.name == "meta":
        title = title_el.get("content", "").strip()
    else:
        title = _text(title_el)
    # 没标题就给个占位,避免后面创建文件夹失败
    title = title or "untitled"

    # 公众号名:优先用 #js_name,兜底 <meta name="author">
    account_el = soup.select_one("#js_name") or soup.select_one("meta[name='author']")
    if account_el and account_el.name == "meta":
        account_name = account_el.get("content", "").strip()
    else:
        account_name = _text(account_el)

    author = _extract_author(soup, account_name)
    publish_date = _extract_publish_date(soup)
    location = _extract_location(soup)

    # 是否原创:页面有 #copyright_logo 这个标记元素即代表原创
    is_original = soup.select_one("#copyright_logo") is not None

    return Meta(
        title=title,
        account_name=account_name,
        author=author,
        publish_date=publish_date,
        location=location,
        is_original=is_original,
    )


def extract_head_styles(soup: BeautifulSoup) -> str:
    """把 <head> 里所有 <style> 内联样式拼成一段字符串,直接塞回输出 HTML。

    刻意不抓 <link rel="stylesheet"> 引用的外链 CSS,因为:
        - 外链多数指向 wx.qlogo.cn / res.wx.qq.com,只为视觉精细化;
        - 离线场景下这些请求会失败,反而增加首次加载错误;
        - 微信文章的关键样式其实绝大多数已经写进了内联 <style>。
    """
    head = soup.head
    if head is None:
        return ""
    parts: list[str] = []
    for style in head.find_all("style"):
        # decode_contents() 取标签内 raw CSS 文本,保留原始空白与注释
        css = style.decode_contents()
        if css.strip():
            parts.append(f"<style>\n{css}\n</style>")
    return "\n".join(parts)


def collect_images(content: Tag) -> list[str]:
    """从正文中收集去重后的图片真实 URL 列表。

    微信图片是懒加载的:真实地址放在 `data-src`,`src` 是占位用的 1×1 gif。
    所以必须优先取 `data-src`,只有它缺失时才退而取 `src`。
    """
    urls: list[str] = []
    # 用 set 做 O(1) 去重判断,list 保留首次出现顺序(方便排查)
    seen: set[str] = set()
    for img in content.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        src = src.strip()
        # 跳过空值和 data: URI(base64 内嵌图)
        if not src or src.startswith("data:"):
            continue
        if src not in seen:
            seen.add(src)
            urls.append(src)
    return urls


def rewrite_content(content: Tag, mapping: dict[str, str]) -> None:
    """对正文 DOM 做最小限度的就地改写。

    刻意保留 inline `style` / `class` / `<section>` 嵌套结构,这样导出的 HTML
    看起来仍然是一篇典型的微信文章。但必须做两件事:

        1. 把 `<img>` 的 src 指向已下载到本地的文件;
        2. 删除 `<script>` / `<iframe>`,确保离线页面安全可控。

    markdownify 在转 Markdown 时只看语义标签(h1/p/ul/...),style/class
    会被自然忽略,所以同一份 DOM 既能输出 HTML 也能输出 Markdown。
    """
    # 先删危险标签(脚本会被浏览器执行,iframe 可能加载外部内容)
    for bad in content.find_all(["script", "iframe"]):
        bad.decompose()

    for img in content.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        src = src.strip()
        if src in mapping:
            # 命中本地映射:替换为相对路径,article.html 旁边的 assets/
            img["src"] = f"assets/{mapping[src]}"
        elif src:
            # 没下载下来的图片,保留远程地址作为兜底(可能能在线显示)
            img["src"] = src
        # data-src 已经不需要了,删掉以减小输出体积
        img.attrs.pop("data-src", None)


def to_markdown(html: str) -> str:
    """HTML 转 Markdown,使用 ATX 风格标题(# 前缀)。

    - bullets="-":列表项统一用 -,避免 *、+ 混用;
    - code_language="":代码块不强行加语言标签,由 markdownify 推断;
    - strip=["span"]:微信正文里 span 多半只是承载样式,转 MD 时直接拍平,
      避免把 `<span>foo</span>` 转成多余的空白节点。
    """
    return md(
        html,
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=["span"],
    ).strip()

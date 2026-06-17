"""来源无关的共用工具:数据结构、HTML 工具函数、Markdown 转换。

所有来源模块(parser_wx / parser_bjh)和核心编排层(core)共同依赖此模块,
它本身不含任何来源特定的选择器或解析逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup
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


def _text(el) -> str:
    """安全地取 DOM 元素的纯文本;el 为 None 时返回空串。"""
    return el.get_text(strip=True) if el else ""


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
        css = style.decode_contents()
        if css.strip():
            parts.append(f"<style>\n{css}\n</style>")
    return "\n".join(parts)


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

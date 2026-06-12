"""网络层:抓取文章 HTML,以及下载图片(处理微信防盗链)。

微信图片服务 mmbiz.qpic.cn 会校验 Referer 头,缺失会直接返回 403,
所以下载图片时必须显式带上 WX_REFERER。
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

# 通用浏览器 UA,避免被简单的反爬规则拦截
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# mmbiz.qpic.cn 必须带这个 Referer,否则所有图片请求都会被拒绝 403
WX_REFERER = "https://mp.weixin.qq.com/"

# MIME 类型 -> 扩展名映射,用于根据 Content-Type 推断图片格式
EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}

log = logging.getLogger("wx2md.net")


def pick_ext(url: str, content_type: str | None) -> str:
    """推断图片扩展名,优先级:Content-Type -> URL 中的 wx_fmt 参数 -> URL 后缀 -> .jpg。

    微信图片 URL 通常没有显式后缀,例如:
        https://mmbiz.qpic.cn/sz_mmbiz_jpg/xxx/640?wx_fmt=jpeg
    因此需要多套兜底策略,确保至少能落地为 .jpg。
    """
    if content_type:
        # Content-Type 可能附带 charset 等参数,只取前半段
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct in EXT_BY_MIME:
            return EXT_BY_MIME[ct]
        # 部分图床即便 Content-Type 不规范,URL 里仍带 wx_fmt=jpeg/png/...
        m = re.search(r"wx_fmt=(\w+)", url)
        if m:
            # 统一把 jpeg 归一化为 jpg,与 Windows 资源管理器习惯一致
            return "." + m.group(1).lower().replace("jpeg", "jpg")
    # 最后看 URL 路径里的后缀
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext == ".jpeg":
        return ".jpg"
    if path_ext in {".jpg", ".png", ".gif", ".webp", ".svg", ".bmp"}:
        return path_ext
    # 兜底:微信文章中绝大多数都是 jpg
    return ".jpg"


def fetch_article(url: str, client: httpx.Client) -> str:
    """抓取文章 SSR HTML。

    follow_redirects=True 是必须的 —— 短链通常先跳到带 __biz 的真实地址,
    再跳到最终 mp.weixin.qq.com/s/xxx。timeout=30 给慢网络留出余量。
    """
    r = client.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
    # 抓取失败直接抛 HTTPStatusError,由上层 cli.main 捕获并计入失败列表
    r.raise_for_status()
    return r.text


def download_image(url: str, dest_dir: Path, client: httpx.Client) -> tuple[str, str | None]:
    """下载单张图片,返回 (url, 本地文件名),失败时文件名为 None。

    文件命名策略:sha1(图片字节)前 16 位 + 扩展名。这样做的好处:
        1. 同一内容的图片在不同文章中复用同一份本地文件(天然去重);
        2. 重复运行幂等 —— 已存在的文件不会再写一遍;
        3. 不依赖 URL 中可能变化的 query 参数。

    单张图片失败只记 warning,不抛异常,避免因一张图坏了整篇文章前功尽弃。
    """
    try:
        # 必须显式带 Referer,否则 mmbiz.qpic.cn 直接返回 403
        r = client.get(
            url,
            headers={"User-Agent": UA, "Referer": WX_REFERER},
            follow_redirects=True,
            timeout=30,
        )
        r.raise_for_status()
        data = r.content
        ext = pick_ext(url, r.headers.get("content-type"))
        # sha1 16 位足以避免实际冲突,同时让文件名足够短
        digest = hashlib.sha1(data).hexdigest()[:16]
        fname = f"{digest}{ext}"
        path = dest_dir / fname
        # 已存在则跳过写盘,既加速又避免 Windows 上的文件占用冲突
        if not path.exists():
            path.write_bytes(data)
        return url, fname
    except Exception as exc:
        # 单图失败不致命,记日志后继续
        log.warning("image failed %s: %s", url, exc)
        return url, None

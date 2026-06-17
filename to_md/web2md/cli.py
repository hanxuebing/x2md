"""命令行入口:负责 argparse 参数解析与"文章级"线程池调度。

整体并发模型为两级线程池:
    外层:本文件控制,每个 worker 负责一篇文章;
    内层:core.process_article 内部控制,每个 worker 下载一张图片。

二者乘积决定了 HTTP 连接池上限,所以 httpx.Limits 也要据此放大。
"""
from __future__ import annotations

import argparse
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from . import __version__
from .core import process_article

log = logging.getLogger("web2md")


def load_urls(args: argparse.Namespace) -> list[str]:
    """合并位置参数与 -i 指定的文件,保留顺序并去重。

    -i 文件中:
        - 每行一个 URL
        - 以 # 开头的行视为注释,直接跳过
        - 空行忽略
    最后用 set 去重,保证同一个 URL 不会被重复抓取。
    """
    urls: list[str] = []
    if args.input:
        # 显式指定 utf-8,避免在中文 Windows 上被默认 gbk 解码失败
        for line in Path(args.input).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    # 命令行位置参数追加到文件中 URL 之后
    urls.extend(args.urls)
    # 用 set 记录已见过的 URL,同时保留首次出现的顺序
    seen, dedup = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup


def build_parser() -> argparse.ArgumentParser:
    """构造 argparse 解析器,所有 CLI 参数集中在此声明。"""
    p = argparse.ArgumentParser(
        prog="web2md",
        description="Convert WeChat / Baidu Baijiahao articles to Markdown + HTML + local images.",
    )
    # 位置参数:可以一次性传多个 URL,nargs="*" 允许 0 个(此时必须配合 -i)
    p.add_argument("urls", nargs="*", help="one or more article URLs")
    p.add_argument("-i", "--input", help="text file with URLs (one per line, # for comments)")
    p.add_argument("-o", "--output", default="output", help="output root dir (default: output)")
    # 文章级并发:同时处理几篇文章
    p.add_argument("-w", "--workers", type=int, default=4, help="parallel articles (default 4)")
    # 图片级并发:每篇文章内部同时下载几张图片
    p.add_argument(
        "-t", "--img-workers", type=int, default=8, help="parallel images per article (default 8)"
    )
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG level logging")
    p.add_argument(
        "--debug",
        action="store_true",
        help="debug mode: full tracebacks, HTTP diagnostics, dump failed HTML to _debug/",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main() -> int:
    """CLI 入口,返回进程退出码(0 表示全部成功,非 0 表示存在失败)。"""
    args = build_parser().parse_args()

    # --debug 会自动启用 --verbose,因为调试一定需要详细日志
    debug = args.debug
    verbose = args.verbose or debug

    # 日志格式:debug 模式附带 logger 名,便于定位是哪一层(net/parser/core)报错
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s" if debug
        else "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if debug:
        # 让 httpx 的请求/响应明细也打印出来,排查 403/重定向时非常有用
        logging.getLogger("httpx").setLevel(logging.DEBUG)

    urls = load_urls(args)
    if not urls:
        # 既没有位置参数也没有 -i 文件,argparse.error 会以非 0 码退出
        build_parser().error("no URLs given (positional or -i)")
    out_root = Path(args.output)
    out_root.mkdir(parents=True, exist_ok=True)

    # debug 模式下额外创建 _debug 目录,集中存放失败诊断信息
    debug_dir = out_root / "_debug" if debug else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    # 连接池上限 = 文章并发 × 单篇图片并发 + 额外的 8 个余量(给 HTML 抓取等)
    # 关闭 HTTP/2:微信服务器对 H2 的兼容性不稳定,HTTP/1.1 反而更可靠
    limits = httpx.Limits(
        max_connections=args.workers * args.img_workers + 8,
        max_keepalive_connections=16,
    )
    ok, fail = 0, 0
    failures: list[dict] = []

    # 全程共用一个 httpx.Client,复用 TCP 连接,显著提升大批量抓取速度
    with httpx.Client(http2=False, limits=limits) as client:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            # 一次性提交所有任务,as_completed 按完成顺序逐个收割结果
            futs = {
                pool.submit(process_article, u, out_root, args.img_workers, client): u
                for u in urls
            }
            for f in as_completed(futs):
                u = futs[f]
                try:
                    f.result()
                    ok += 1
                except Exception as exc:
                    # 单篇失败不影响其它文章,只在最后汇总报错
                    fail += 1
                    if debug:
                        # debug 模式记录完整 traceback,便于离线分析
                        tb = traceback.format_exc()
                        log.error("article failed %s:\n%s", u, tb)
                        failures.append({"url": u, "error": str(exc), "traceback": tb})
                    else:
                        log.error("article failed %s: %s", u, exc)

    # debug 模式:把失败列表与 traceback 落盘,方便用户事后排查
    if debug_dir and failures:
        # failed.txt:每行 "URL<TAB>错误概要",可被脚本继续消费
        failed_txt = debug_dir / "failed.txt"
        failed_txt.write_text(
            "\n".join(f"{f['url']}\t{f['error']}" for f in failures) + "\n",
            encoding="utf-8",
        )
        # report.txt:人类可读的详细报告,含完整 traceback
        report_path = debug_dir / "report.txt"
        lines = []
        for f in failures:
            lines.append(f"{'='*60}")
            lines.append(f"URL: {f['url']}")
            lines.append(f"Error: {f['error']}")
            lines.append(f"Traceback:\n{f['traceback']}")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info("debug report written to %s", debug_dir)

    log.info("finished: %d ok / %d failed / %d total", ok, fail, len(urls))
    # 只要有一篇失败就返回 1,方便 CI/脚本判断
    return 0 if fail == 0 else 1

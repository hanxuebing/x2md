"""Click CLI — pdf2md 命令行入口。

用法对齐 pdf2x 风格：单文件 / 批量 / 目录三种模式。
"""

from __future__ import annotations

import sys

import click

from pdf2md import __version__


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--config", "config_path", default=None, help="配置文件路径（默认 ./config.toml）")
@click.option("--md", default=None, help="单文件模式：Markdown 输出路径")
@click.option("--out-dir", default=None, help="批量模式：输出目录（默认 output）")
@click.option("-r", "--recursive", is_flag=True, help="输入为目录时递归扫描子目录")
@click.option("--vision-model", default=None, help="覆盖多模态模型（如 claude-opus-4-8）")
@click.option("--text-model", default=None, help="覆盖文本模型（如 claude-sonnet-4-6）")
@click.option("--base-url", default=None, help="覆盖 API 网关地址")
@click.option("--auth-token", default=None, help="覆盖鉴权令牌")
@click.option("--pages", default=None, help="页码范围（1-5,8,12-15）")
@click.option("--dpi", default=None, type=int, help="渲染 DPI（默认 150）")
@click.option("--lang", default=None, help="输出语言（auto/zh/en）")
@click.option("--pagebreak", is_flag=True, default=None, help="页间插入 --- 分隔线")
@click.option("-q", "--quiet", is_flag=True, help="抑制进度信息")
@click.option("-v", "--verbose", is_flag=True, help="详细日志")
@click.version_option(version=__version__, prog_name="pdf2md")
def main(
    inputs: tuple[str, ...],
    config_path: str | None,
    md: str | None,
    out_dir: str | None,
    recursive: bool,
    vision_model: str | None,
    text_model: str | None,
    base_url: str | None,
    auth_token: str | None,
    pages: str | None,
    dpi: int | None,
    lang: str | None,
    pagebreak: bool | None,
    quiet: bool,
    verbose: bool,
) -> None:
    """多模态大模型 PDF → 人性化 Markdown 转换器。

    两阶段：多模态模型识别 PDF 页面 → 文本模型整理 Markdown 排版。

    \b
    单文件模式：pdf2md paper.pdf --md paper.md
    批量模式：  pdf2md a.pdf b.pdf --out-dir out
    目录模式：  pdf2md ./pdfs -r --out-dir out
    """
    from pdf2md.api import convert, convert_batch

    overrides = {}
    if vision_model:
        overrides["vision_model"] = vision_model
    if text_model:
        overrides["text_model"] = text_model
    if base_url:
        overrides["base_url"] = base_url
    if auth_token:
        overrides["auth_token"] = auth_token
    if dpi is not None:
        overrides["dpi"] = dpi
    if lang:
        overrides["lang"] = lang
    if pagebreak is not None:
        overrides["pagebreak"] = pagebreak

    input_list = list(inputs)

    try:
        # 单文件模式：1 个 PDF + --md
        if md and len(input_list) == 1:
            result = convert(
                input_list[0],
                md=md,
                config=config_path,
                pages=pages,
                quiet=quiet,
                verbose=verbose,
                **overrides,
            )
            if not quiet:
                print(f"\n完成: {result}", file=sys.stderr)
        else:
            # 批量模式
            results = convert_batch(
                input_list,
                out_dir=out_dir or "output",
                recursive=recursive,
                config=config_path,
                quiet=quiet,
                verbose=verbose,
                **overrides,
            )
            if not quiet:
                print(f"\n完成: 共 {len(results)} 个文件", file=sys.stderr)
    except Exception as exc:
        click.echo(f"错误: {exc}", err=True)
        raise SystemExit(1) from exc

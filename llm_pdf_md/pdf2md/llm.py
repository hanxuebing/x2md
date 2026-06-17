"""LLM 客户端封装：两阶段管线。

Stage 1 (vision): 多模态模型 — 页面图片 → 原始参考文章（忠实转录）
Stage 2 (text):   文本模型   — 原始文章 → 人性化 Markdown
"""

from __future__ import annotations

import base64
import re
from typing import TYPE_CHECKING

import anthropic

from pdf2md.prompts import (
    VISION_SYSTEM,
    TEXT_SYSTEM,
    build_vision_user,
    build_text_user,
)

if TYPE_CHECKING:
    from pdf2md.config import ModelConfig


def _make_client(mcfg: "ModelConfig") -> anthropic.Anthropic:
    """根据 ModelConfig 构建 Anthropic 客户端（Bearer 令牌鉴权）。"""
    return anthropic.Anthropic(
        auth_token=mcfg.auth_token,
        base_url=mcfg.base_url,
    )


def _strip_fences(text: str) -> str:
    """兜底剥掉模型偶尔多包的 ```markdown ... ``` 围栏。"""
    stripped = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*?)```\s*$", stripped, re.DOTALL)
    if m:
        return m.group(1).strip()
    return stripped


def _call(
    client: anthropic.Anthropic,
    mcfg: "ModelConfig",
    system: str,
    user_content: list[dict],
) -> str:
    """流式调用 Claude，返回首个 text block 的文本。"""
    kwargs: dict = {
        "model": mcfg.model,
        "max_tokens": mcfg.max_tokens,
        "system": [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_content}],
    }
    if mcfg.thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    with client.messages.stream(**kwargs) as stream:
        msg = stream.get_final_message()

    for block in msg.content:
        if block.type == "text":
            return _strip_fences(block.text)
    return ""


# ── 公开 API ─────────────────────────────────────────────────────


def transcribe_page(
    vision_cfg: "ModelConfig",
    png_bytes: bytes,
    page_no: int,
    total_pages: int,
    prev_tail: str,
    asset_names: list[str],
) -> str:
    """Stage 1: 多模态模型看页面图片，输出忠实转录文本。"""
    vision_cfg.require_auth("vision")
    client = _make_client(vision_cfg)

    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    user_prompt = build_vision_user(page_no, total_pages, prev_tail, asset_names)

    user_content: list[dict] = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        },
        {"type": "text", "text": user_prompt},
    ]

    return _call(client, vision_cfg, VISION_SYSTEM, user_content)


def refine_page(
    text_cfg: "ModelConfig",
    raw_text: str,
    page_no: int,
    total_pages: int,
    prev_md_tail: str,
    lang: str,
) -> str:
    """Stage 2: 文本模型把原始转录整理成人性化 Markdown。"""
    text_cfg.require_auth("text")
    client = _make_client(text_cfg)

    user_prompt = build_text_user(raw_text, page_no, total_pages, prev_md_tail, lang)
    user_content: list[dict] = [{"type": "text", "text": user_prompt}]

    return _call(client, text_cfg, TEXT_SYSTEM, user_content)

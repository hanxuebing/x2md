"""LLM 客户端封装：两阶段管线（claude-agent-sdk）。

Stage 1 (vision): 多模态模型 — 页面图片 → 原始参考文章（忠实转录）
Stage 2 (text):   文本模型   — 原始文章 → 人性化 Markdown

底层走 claude-agent-sdk（Claude Code CLI 子进程），而非直接 Messages API。
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from pdf2md.prompts import (
    TEXT_SYSTEM,
    VISION_SYSTEM,
    build_text_user,
    build_vision_user,
)

if TYPE_CHECKING:
    from pdf2md.config import ModelConfig


def _build_env(mcfg: "ModelConfig") -> dict[str, str]:
    """把 ModelConfig 的鉴权信息映射为环境变量。"""
    env: dict[str, str] = {}
    if mcfg.auth_token:
        env["ANTHROPIC_AUTH_TOKEN"] = mcfg.auth_token
    if mcfg.base_url:
        env["ANTHROPIC_BASE_URL"] = mcfg.base_url
    return env


def _strip_fences(text: str) -> str:
    """兜底剥掉模型偶尔多包的 ```markdown ... ``` 围栏。"""
    stripped = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*?)```\s*$", stripped, re.DOTALL)
    if m:
        return m.group(1).strip()
    return stripped


async def _run_query(prompt: str, options: ClaudeAgentOptions) -> str:
    """调用 claude-agent-sdk 的 query()，收集所有 TextBlock 文本。"""
    parts: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return _strip_fences("".join(parts))


def _sync_run(prompt: str, options: ClaudeAgentOptions) -> str:
    """同步包装异步 _run_query，供外部同步调用。"""
    return asyncio.run(_run_query(prompt, options))


# ── 公开 API ─────────────────────────────────────────────────────


def transcribe_page(
    vision_cfg: "ModelConfig",
    png_bytes: bytes,
    page_no: int,
    total_pages: int,
    prev_tail: str,
    asset_names: list[str],
) -> str:
    """Stage 1: 多模态模型看页面图片，输出忠实转录文本。

    把 PNG 写入临时文件，让 agent 通过 Read 工具读取图片后转录。
    """
    vision_cfg.require_auth("vision")

    with tempfile.TemporaryDirectory(prefix="pdf2md_") as tmpdir:
        img_name = f"page_{page_no}.png"
        img_path = Path(tmpdir) / img_name
        img_path.write_bytes(png_bytes)

        user_prompt = build_vision_user(page_no, total_pages, prev_tail, asset_names)
        # 在 prompt 前追加读图指令
        prompt = (
            f"请先用 Read 工具读取当前目录下的图片文件 {img_name}，"
            f"然后根据图片内容完成以下任务。\n\n{user_prompt}"
        )

        options = ClaudeAgentOptions(
            model=vision_cfg.model,
            system_prompt=VISION_SYSTEM,
            allowed_tools=["Read"],
            disallowed_tools=[],
            max_turns=3,
            cwd=tmpdir,
            env=_build_env(vision_cfg),
            permission_mode="acceptEdits",
        )

        return _sync_run(prompt, options)


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

    user_prompt = build_text_user(raw_text, page_no, total_pages, prev_md_tail, lang)

    options = ClaudeAgentOptions(
        model=text_cfg.model,
        system_prompt=TEXT_SYSTEM,
        allowed_tools=[],
        disallowed_tools=[],
        max_turns=1,
        env=_build_env(text_cfg),
        permission_mode="acceptEdits",
    )

    return _sync_run(user_prompt, options)

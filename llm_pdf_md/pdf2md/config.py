"""配置加载与合并。

优先级：CLI 覆盖 > 环境变量（ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL）
        > config.toml > 内置默认。

鉴权走 ANTHROPIC_AUTH_TOKEN（Bearer 令牌）+ ANTHROPIC_BASE_URL（网关地址），
而非传统 api_key。可配置多个大模型：

- vision：多模态大模型，看页面图片 → 转录成「原始参考文章」（忠实文字）
- text  ：纯文本大模型，把原始参考文章整理成排版友好、人性化的 Markdown
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_VISION_MODEL = "claude-opus-4-8"
DEFAULT_TEXT_MODEL = "claude-sonnet-4-6"


class ConfigError(RuntimeError):
    """配置缺失或非法。"""


@dataclass
class ModelConfig:
    """单个大模型的接入配置。

    base_url / auth_token 为空时回退到共享的 [api]，再回退到环境变量。
    """

    model: str
    max_tokens: int = 8000
    thinking: bool = False
    base_url: str = ""
    auth_token: str = ""

    def resolve(self, shared_base_url: str, shared_auth_token: str) -> "ModelConfig":
        """把共享 [api] 与环境变量补进空缺字段，返回新对象。"""
        base_url = (
            self.base_url
            or shared_base_url
            or os.environ.get("ANTHROPIC_BASE_URL", "")
            or DEFAULT_BASE_URL
        )
        auth_token = (
            self.auth_token
            or shared_auth_token
            or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        )
        return ModelConfig(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking=self.thinking,
            base_url=base_url,
            auth_token=auth_token,
        )

    def require_auth(self, role: str) -> None:
        if not self.auth_token:
            raise ConfigError(
                f"{role} 模型缺少鉴权令牌。请在 config.toml 的 [api].auth_token "
                f"或 [models.{role}].auth_token 填写，或设置环境变量 ANTHROPIC_AUTH_TOKEN。"
            )


@dataclass
class RenderConfig:
    dpi: int = 150


@dataclass
class OutputConfig:
    lang: str = "auto"
    pagebreak: bool = False


@dataclass
class Config:
    vision: ModelConfig = field(
        default_factory=lambda: ModelConfig(model=DEFAULT_VISION_MODEL)
    )
    text: ModelConfig = field(
        default_factory=lambda: ModelConfig(model=DEFAULT_TEXT_MODEL)
    )
    render: RenderConfig = field(default_factory=RenderConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def _find_config(path: str | None) -> Path | None:
    if path:
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"指定的配置文件不存在：{path}")
        return p
    for cand in (
        Path.cwd() / "config.toml",
        Path.home() / ".config" / "pdf2md" / "config.toml",
    ):
        if cand.is_file():
            return cand
    return None


def _model_from(raw: dict, default_model: str) -> ModelConfig:
    return ModelConfig(
        model=str(raw.get("model", default_model)),
        max_tokens=int(raw.get("max_tokens", 8000)),
        thinking=bool(raw.get("thinking", False)),
        base_url=str(raw.get("base_url", "")),
        auth_token=str(raw.get("auth_token", "")),
    )


def load_config(path: str | None = None, **overrides) -> Config:
    """加载配置并应用 CLI 覆盖。

    支持的 overrides（None 表示不覆盖）：
        vision_model, text_model, base_url, auth_token, dpi, lang, pagebreak
    """
    found = _find_config(path)
    data: dict = {}
    if found is not None:
        with found.open("rb") as f:
            data = tomllib.load(f)

    api = data.get("api", {})
    shared_base_url = str(api.get("base_url", ""))
    shared_auth_token = str(api.get("auth_token", ""))

    models = data.get("models", {})
    vision = _model_from(models.get("vision", {}), DEFAULT_VISION_MODEL)
    text = _model_from(models.get("text", {}), DEFAULT_TEXT_MODEL)

    render_raw = data.get("render", {})
    render = RenderConfig(dpi=int(render_raw.get("dpi", 150)))

    output_raw = data.get("output", {})
    output = OutputConfig(
        lang=str(output_raw.get("lang", "auto")),
        pagebreak=bool(output_raw.get("pagebreak", False)),
    )

    # CLI 覆盖
    if overrides.get("vision_model"):
        vision.model = overrides["vision_model"]
    if overrides.get("text_model"):
        text.model = overrides["text_model"]
    if overrides.get("base_url"):
        shared_base_url = overrides["base_url"]
    if overrides.get("auth_token"):
        shared_auth_token = overrides["auth_token"]
    if overrides.get("dpi"):
        render.dpi = int(overrides["dpi"])
    if overrides.get("lang"):
        output.lang = overrides["lang"]
    if overrides.get("pagebreak") is not None:
        output.pagebreak = bool(overrides["pagebreak"])

    # 把共享接入信息补进每个模型
    vision = vision.resolve(shared_base_url, shared_auth_token)
    text = text.resolve(shared_base_url, shared_auth_token)

    return Config(vision=vision, text=text, render=render, output=output)

# pdf2md

通过**多模态大模型**把 PDF 转成排版友好、人性化的 **Markdown**。

与 `pdf2x`（传统管线）互补：`pdf2x` 走 PyMuPDF + pdfplumber + OCR，适合规整版式；
`pdf2md` 让大模型「看图理解」，对**复杂版式、扫描件、图文混排、表格/公式**效果更好。

---

## 核心特性

- **两阶段管线**：
  1. 多模态大模型（vision）看页面图片 → 忠实转录「原始参考文章」
  2. 文本大模型（text）→ 整理成排版优美的 Markdown
- **配置驱动**：`config.toml` 配置模型、网关地址、鉴权令牌，CLI 参数可覆盖
- **多模型分离**：vision 和 text 可用不同模型甚至不同网关
- **图片本地化**：PDF 嵌入图片自动抽取到 `assets/`（sha1 命名去重），Markdown 中正确引用
- **跨页连续**：顺序处理，上页上下文传入下页，标题层级和内容不断裂
- **x2md 导出标准**：`output/<安全标题>/article.md` + YAML frontmatter，天然被 `gen_link` 索引

---

## 1. 环境要求

| 依赖 | 用途 | 是否必须 |
|---|---|---|
| Python ≥ 3.13 | 运行环境 | 必须 |
| [uv](https://docs.astral.sh/uv/) | 依赖与虚拟环境管理 | 必须 |
| `ANTHROPIC_AUTH_TOKEN` | Bearer 鉴权令牌 | 必须（config.toml 或环境变量） |
| `ANTHROPIC_BASE_URL` | API 网关地址 | 选填（默认官方地址） |

---

## 2. 安装

```bash
cd llm_pdf_md
uv sync                    # 创建 .venv 并安装依赖
uv run pdf2md --help       # 验证 CLI
```

---

## 3. 配置

```bash
cp config.example.toml config.toml
# 编辑 config.toml，填入鉴权令牌和网关地址
```

也可通过环境变量：

```bash
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_BASE_URL="https://your-gateway.example.com"
```

### config.toml 结构

```toml
[api]
base_url   = ""    # 共享网关地址
auth_token = ""    # 共享鉴权令牌

[models.vision]           # 多模态大模型
model      = "claude-opus-4-8"
max_tokens = 8000

[models.text]             # 文本大模型
model      = "claude-sonnet-4-6"
max_tokens = 8000
thinking   = false        # 复杂文档可设 true

[render]
dpi = 150

[output]
lang      = "auto"
pagebreak = false
```

优先级：**CLI 参数 > 环境变量 > config.toml > 内置默认**

---

## 4. CLI 用法

```bash
# 单文件
uv run pdf2md paper.pdf --md paper.md

# 批量（每个 PDF 在 out/ 下生成同名文件夹）
uv run pdf2md a.pdf b.pdf --out-dir out

# 目录（递归扫描）
uv run pdf2md ./pdfs -r --out-dir out

# 只转 1-3 页，用指定模型
uv run pdf2md report.pdf --pages 1-3 --vision-model claude-opus-4-8

# 覆盖鉴权
uv run pdf2md doc.pdf --auth-token sk-xxx --base-url https://gateway.example.com
```

### 完整参数表

| 参数 | 说明 |
|---|---|
| `INPUT...` | 一个或多个 PDF 路径或目录 |
| `--config PATH` | 指定配置文件 |
| `--md PATH` | 单文件模式：Markdown 输出路径 |
| `--out-dir DIR` | 批量模式：输出目录（默认 output） |
| `-r / --recursive` | 递归扫描子目录 |
| `--vision-model` | 覆盖多模态模型 |
| `--text-model` | 覆盖文本模型 |
| `--base-url` | 覆盖网关地址 |
| `--auth-token` | 覆盖鉴权令牌 |
| `--pages TEXT` | 页码范围（1-5,8） |
| `--dpi INT` | 渲染 DPI（默认 150） |
| `--lang TEXT` | 输出语言（auto/zh/en） |
| `--pagebreak` | 页间插入 --- 分隔线 |
| `-q / --quiet` | 抑制进度 |
| `-v / --verbose` | 详细日志 |
| `--version` | 版本号 |

---

## 5. Python 库 API

```python
from pdf2md import convert, convert_batch

# 单文件
result = convert("paper.pdf", out_dir="output")

# 批量
results = convert_batch(
    ["a.pdf", "b.pdf", "./pdfs"],
    out_dir="out",
    recursive=True,
)
```

---

## 6. 输出格式

遵循 x2md 导出标准：

```
output/
└── <安全标题>/
    ├── article.md      ← YAML frontmatter + Markdown 正文
    └── assets/
        ├── 7f3a1c9b2e4d5601.png
        └── a1b2c3d4e5f60718.jpg
```

`article.md` frontmatter：

```yaml
---
title: "文档标题"
date: "2026-06-15"
source: "原始文件名.pdf"
generator: "pdf2md (multimodal LLM)"
---
```

---

## 7. 与 pdf2x 的对比

| | pdf2x（传统管线） | pdf2md（多模态 LLM） |
|---|---|---|
| 方法 | PyMuPDF + pdfplumber + OCR | 页面图片 → 大模型视觉理解 |
| 优势 | 快速、确定、零成本 | 复杂版式、扫描件、公式表格更准 |
| 劣势 | 复杂版式/手写/公式识别弱 | 需要 API 调用，有成本和延迟 |
| 适合 | 规整 PDF、大批量、低成本 | 高质量要求、复杂文档、少量精品 |

建议：先用 `pdf2x` 快速批量处理，对效果不满意的文档再用 `pdf2md` 精细转换。

---

## 8. 项目结构

```
llm_pdf_md/
├── pyproject.toml
├── config.example.toml
├── README.md
├── pdf2md/
│   ├── __init__.py       # 公开 API
│   ├── api.py            # convert / convert_batch 协调器
│   ├── cli.py            # Click CLI
│   ├── __main__.py       # python -m pdf2md
│   ├── config.py         # 配置加载与合并
│   ├── render.py         # PyMuPDF 渲染 + 图片抽取
│   ├── llm.py            # Anthropic SDK 客户端封装
│   ├── prompts.py        # 提示词模板
│   └── output.py         # 安全标题、frontmatter、写文件
└── tests/
    └── test_smoke.py
```

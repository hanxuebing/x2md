# pdf2x

把 PDF 同时转换成 **HTML** 和 **Markdown** 的 Python 库 + CLI 工具。

- **HTML（默认 exact 模式）**：用绝对定位、嵌入字体的方式尽可能 1:1 还原 PDF 视觉效果——浏览器里打开像看 PDF。
- **HTML（flow 模式）**：丢弃绝对定位，输出语义 HTML（`<h1>/<p>/<table>/<img>`），便于可重排阅读。
- **Markdown**：样式无法逐像素还原，但**文档结构**（标题层级、段落、列表、表格、图片顺序）按 PDF 阅读顺序对齐。
- 同时是 **Python 库** 和 **CLI**——任何语言/脚本都可以通过 `subprocess` 调用。

---

## 1. 环境要求

| 依赖 | 用途 | 是否必须 |
|---|---|---|
| Python ≥ 3.10 | 运行环境 | 必须 |
| [uv](https://docs.astral.sh/uv/) | 依赖与虚拟环境管理 | 必须 |
| `tesseract` 命令行 | 扫描件 OCR | 仅在用 `--ocr always` 或 `auto` 触发回退时需要 |

### 安装 uv

macOS / Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows（PowerShell）：

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装后 `uv --version` 应能跑通。

### 安装 tesseract（仅 OCR 时需要）

| 系统 | 命令 |
|---|---|
| macOS | `brew install tesseract` |
| Ubuntu / Debian | `sudo apt install tesseract-ocr tesseract-ocr-chi-sim` |
| Windows | 下载 https://github.com/UB-Mannheim/tesseract/wiki 安装包，把 `tesseract.exe` 加入 PATH |

不使用 OCR 时不需要装。

---

## 2. 安装 pdf2x

### 方式 A：作为全局 CLI 安装（最常见）

```bash
git clone <this-repo> pdf2x
cd pdf2x
uv tool install .
# 想要 OCR 支持：
uv tool install ".[ocr]"
```

之后 shell 里直接：

```bash
pdf2x --help
```

### 方式 B：在其它项目里作为库依赖

```bash
# 在目标项目目录
uv add pdf2x
# 或本地路径：
uv add /path/to/pdf2x
```

### 方式 C：本地开发模式

```bash
git clone <this-repo> pdf2x
cd pdf2x
uv sync                  # 创建 .venv 并安装依赖
uv sync --extra ocr      # 也安装 OCR 可选依赖
uv run pdf2x --help      # 通过 uv 跑 CLI
uv run pytest            # 跑测试
```

---

## 3. CLI 用法

pdf2x 有两种工作模式：

- **单文件模式**：传**一个** PDF，并用 `--html` / `--md` 指定确切输出路径。
- **批量模式**：传**多个** PDF、传**目录**，或带上 `--out-dir`。每个 PDF 会生成一个**以文件名命名的文件夹**，里面包含 `<名字>.html`、`<名字>.md` 和 `assets/`（外置的图片/字体）。

最常用的命令：

```bash
# 单文件：同时输出 HTML（默认 exact 模式）和 Markdown
pdf2x paper.pdf --html paper.html --md paper.md

# 单文件：只要像素级 HTML，并把图片/字体外置到 assets/ 目录
pdf2x report.pdf --html report.html --assets-dir assets

# 单文件：扫描件，开启中英双语 OCR
pdf2x scan.pdf --md scan.md --ocr always --ocr-lang chi_sim+eng

# 批量：单个 PDF 也能生成同名文件夹（这里输出到 ./paper/）
pdf2x paper.pdf

# 批量：多个 PDF，统一放到 out/ 下（out/a/、out/b/、out/c/）
pdf2x a.pdf b.pdf c.pdf --out-dir out

# 批量：转换某目录下所有 PDF（-r 递归子目录）
pdf2x ./pdfs --out-dir out -r
```

批量模式下每个文件夹结构如下：

```
out/
└── paper/
    ├── paper.html
    ├── paper.md
    └── assets/        # 图片、字体
```

> 用本地开发模式时把每条命令前面加 `uv run`，例如 `uv run pdf2x paper.pdf --md paper.md`。

> 批量模式不接受 `--html` / `--md` / `--assets-dir`（这些是单文件模式专用的）；输出名固定由 PDF 文件名决定。

### 完整参数表

| 参数 | 默认值 | 说明 |
|---|---|---|
| `INPUT...` | 必填 | 一个或多个 PDF 路径或目录（位置参数）。传多个、传目录或带 `--out-dir` 即进入批量模式 |
| `--html PATH` | — | 输出 HTML 路径（仅单文件模式） |
| `--md PATH` | — | 输出 Markdown 路径（仅单文件模式） |
| `--out-dir DIR` | 当前目录 | 批量模式：每个 PDF 在此目录下生成同名文件夹 |
| `-r / --recursive` | 关闭 | 输入为目录时递归扫描子目录里的 PDF |
| `--mode [exact\|flow]` | `exact` | HTML 渲染模式；`exact`=绝对定位+嵌入字体，`flow`=语义 HTML |
| `--assets-dir DIR` | 不外置 | 单文件模式：把图片/字体写到此目录并用相对链接引用；不指定则内联为 `data:` URL |
| `--ocr [auto\|always\|off]` | `auto` | OCR 策略；`auto` 仅在原页文本极少时回退到 OCR |
| `--ocr-lang TEXT` | `eng` | Tesseract 语言代号，例如 `chi_sim+eng` |
| `--pages TEXT` | 全部 | 页码范围，1 起始，例如 `1-5,8,12-15` |
| `--md-pagebreak` | 关闭 | 在 Markdown 每页之间插入 `---` 分隔线 |
| `-q / --quiet` | 关闭 | 抑制进度信息 |
| `-v / --verbose` | 关闭 | 输出详细日志 |
| `--version` | — | 打印版本号 |
| `-h / --help` | — | 显示帮助 |

单文件模式下至少需提供 `--html` 或 `--md` 之一；批量模式自动同时输出 HTML 与 Markdown。

---

## 4. Python 库 API

```python
from pdf2x import convert, convert_batch, parse

# 一站式（单文件）
convert(
    "paper.pdf",
    html="paper.html",
    md="paper.md",
    mode="exact",
    assets_dir="paper_assets",
)

# 批量：每个 PDF 在 out/ 下生成同名文件夹（含 html / md / assets）
folders = convert_batch(
    ["a.pdf", "b.pdf", "./pdfs"],   # 文件与目录混传都行
    out_dir="out",
    recursive=True,                  # 递归扫描传入的目录
)
# folders == [Path("out/a"), Path("out/b"), ...]

# 想自己处理 IR
doc = parse("paper.pdf", ocr="auto")
for page in doc.pages:
    for block in page.blocks:
        ...   # TextBlock / TableBlock / ImageBlock
```

IR 关键类型：

```python
from pdf2x import Document, Page, TextBlock, TableBlock, ImageBlock, Line, Span
```

详见 `pdf2x/ir.py`。

---

## 5. 从其它语言通过 CLI 调用

CLI 退出码：`0` 成功，`1` 运行时错误（错误消息写到 stderr），`2` 参数错误。

```python
# 任意 Python 项目，无需安装 pdf2x 为库
import subprocess
subprocess.run(
    ["pdf2x", "input.pdf", "--html", "out.html", "--md", "out.md"],
    check=True,
)
```

```bash
# 任意 shell
pdf2x input.pdf --md out.md --pages 1-3 --quiet

# 批量：把一个目录里所有 PDF 转换到 out/ 下的同名文件夹
pdf2x ./pdfs --out-dir out --quiet
```

```javascript
// Node.js
const { execFileSync } = require("child_process");
execFileSync("pdf2x", ["input.pdf", "--html", "out.html"], { stdio: "inherit" });
```

---

## 6. 常见问题

**Q：HTML 打开后字体不对劲，是回退到 serif 了。**
A：源 PDF 的字体没能嵌入或转换 WOFF2 失败。pdf2x 只能导出 PDF 中**嵌入的** TTF/OTF 字体；非嵌入字体只能靠浏览器本地字体回退。可以试 `--mode=flow` 走结构化 HTML。

**Q：执行时报 `tesseract not found`。**
A：你要么没装系统级 tesseract，要么 `pdf2x` 没装 OCR 可选依赖。前者按本文第 1 节装，后者跑 `uv tool install ".[ocr]"`（或 `uv sync --extra ocr`）。

**Q：扫描件输出乱码或缺字。**
A：带上 `--ocr-lang`，例如简体中文 `--ocr-lang chi_sim` 或中英混合 `--ocr-lang chi_sim+eng`，并确认 tesseract 的语言数据已下载（apt 下是 `tesseract-ocr-chi-sim` 包）。

**Q：多栏 PDF 的 Markdown 顺序错乱。**
A：pdf2x 走 PyMuPDF 的 `sort=True` 块排序，多数情况下能正确处理多栏，但极复杂版式可能错；对这类内容建议优先使用 `--mode=exact` 输出 HTML。

**Q：能不能只导出一部分页？**
A：可以，`--pages 1-3,7,10-12`，1 起始且包含两端。

---

## 7. 限制

- Markdown 无法保留字体、颜色、坐标等视觉信息——这是 MD 语法本身的限制，不是 pdf2x 的取舍。
- 数学公式、手写笔迹、复杂矢量图当前不识别。
- 表格识别依赖 pdfplumber，对无边框/嵌套表格效果有限。
- OCR 模式下不保留原文字体；行坐标基于 OCR 估算，HTML exact 模式视觉可能略有偏移。

---

## 8. 项目结构

```
pdf2x/
├── pyproject.toml          # uv 管理：依赖、CLI 入口、构建后端
├── README.md
├── pdf2x/
│   ├── __init__.py         # 公开 API：convert, parse, IR
│   ├── api.py
│   ├── cli.py              # click CLI
│   ├── ir.py               # Document / Page / *Block / Span 等数据类
│   ├── fonts.py            # 嵌入字体抽取 → WOFF2
│   ├── parser/
│   │   ├── __init__.py     # 顶层 parse_pdf 协调器
│   │   ├── text.py         # PyMuPDF 文本 + heading 推断
│   │   ├── tables.py       # pdfplumber 表格
│   │   ├── images.py       # 图片资源
│   │   └── ocr.py          # 扫描件 OCR 回退
│   └── render/
│       ├── html_exact.py   # 像素级 HTML
│       ├── html_flow.py    # 语义 HTML
│       └── markdown.py     # 结构化 Markdown
└── tests/
    └── test_smoke.py
```

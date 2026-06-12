# wx2md

把微信公众号文章（`mp.weixin.qq.com/s/...`）批量转换成本地可离线阅读的 **Markdown + HTML**，并自动下载所有图片到本地（绕过防盗链）。

- 文章级 + 图片级 **双层多线程**，下载快
- 自动处理懒加载 `data-src`、`Referer` 防盗链
- HTML 输出 **尽量忠于公众号原样式**（保留 inline `style`、`<section>` 排版结构）
- 输出三件套：`article.md`、`article.html`、`assets/`
- 三种使用形态：**Python 包 / 全局 CLI 命令 / 单文件 .exe**
- 内置 `--debug` 模式：完整 traceback + 失败诊断 dump
- 用 [uv](https://docs.astral.sh/uv/) 管理依赖与虚拟环境

---

## 目录

- [系统要求](#系统要求)
- [安装 uv](#安装-uv)
- [快速开始](#快速开始)
- [三种运行方式](#三种运行方式)
- [批量 + 多线程](#批量--多线程)
- [所有命令行参数](#所有命令行参数)
- [--debug 模式](#--debug-模式)
- [输出结构](#输出结构)
- [打包成单文件 .exe](#打包成单文件-exe)
- [开发指南](#开发指南)
- [常见问题排查](#常见问题排查)
- [实现原理](#实现原理)
- [License](#license)

---

## 系统要求

| 项 | 要求 |
|----|------|
| 操作系统 | Windows / macOS / Linux 均可 |
| Python | 3.13+（由 uv 自动管理，无需自己装） |
| 网络 | 能访问 `mp.weixin.qq.com` 和 `mmbiz.qpic.cn` |

---

## 安装 uv

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 用包管理器（可选）

```bash
# macOS
brew install uv

# Windows
winget install --id=astral-sh.uv -e
scoop install uv
```

安装后**重开终端**，验证：

```powershell
uv --version
```

---

## 快速开始

```powershell
# 1. 进入项目目录
cd D:\projects\to_md

# 2. 同步依赖（uv 自动下载 Python 3.13、创建 .venv、装好所有依赖）
uv sync

# 3. 跑一篇试试
uv run wx2md https://mp.weixin.qq.com/s/oKi8k-GTyL6ggSo4rqY3hw
```

第一次 `uv sync` 大概 10–30 秒。完成后会有：

```
.venv/             ← uv 创建的虚拟环境（Python 3.13）
uv.lock            ← 锁定依赖版本（建议提交到 git）
```

> **不需要** `pip install`、不需要 `python -m venv`、不需要手动 `activate`。

---

## 三种运行方式

### 方式 1：`uv run`（开发期最方便）

不用 activate，uv 自动选 .venv：

```powershell
uv run wx2md https://mp.weixin.qq.com/s/xxx
```

### 方式 2：`python -m wx2md`（在已激活的虚拟环境里）

```powershell
.venv\Scripts\Activate.ps1
python -m wx2md https://mp.weixin.qq.com/s/xxx
```

### 方式 3：`uv tool install`（全局命令）

```powershell
uv tool install .
# 现在任何目录都能用：
wx2md https://mp.weixin.qq.com/s/xxx

# 卸载
uv tool uninstall wx2md
```

### 方式 4：单文件 `.exe`（分发给不装 Python 的同事）

见下方 [打包成单文件 .exe](#打包成单文件-exe)。

---

## 批量 + 多线程

### 1. 准备 URL 列表

复制 `urls.txt.example` 为 `urls.txt`，每行一个 URL，`#` 开头是注释：

```text
# 我的收藏
https://mp.weixin.qq.com/s/oKi8k-GTyL6ggSo4rqY3hw
https://mp.weixin.qq.com/s/another-article
# https://mp.weixin.qq.com/s/skip-this-one
```

### 2. 跑起来

```powershell
uv run wx2md -i urls.txt -o output -w 4 -t 8
```

含义：

- `-i urls.txt` 从文件读 URL
- `-o output` 输出到 `output/` 目录
- `-w 4` **4 篇文章并行**抓取
- `-t 8` 每篇文章内 **8 张图片并行**下载

→ 理论并发 = 4 × 8 = 32 个图片下载同时跑，所有线程共用一个 `httpx.Client` 连接池。

### 性能调优建议

| 场景 | 推荐参数 |
|------|----------|
| 几篇文章、图多 | `-w 1 -t 16` |
| 几十篇、图少 | `-w 8 -t 4` |
| 网络一般 / 怕被风控 | `-w 2 -t 4` |
| 内网带宽足 | `-w 4 -t 8`（默认） |

并发不是越高越好。`-w` 超过 8 时微信侧可能限速；图片域名 `mmbiz.qpic.cn` 对单 IP 也有阈值。

---

## 所有命令行参数

```
wx2md [-h] [-i INPUT] [-o OUTPUT] [-w WORKERS] [-t IMG_WORKERS]
      [-v] [--debug] [-V] [urls ...]

位置参数:
  urls                 一个或多个文章 URL

可选参数:
  -h, --help           显示帮助
  -i, --input INPUT    URL 列表文件（每行一个，# 注释）
  -o, --output OUTPUT  输出根目录（默认 output）
  -w, --workers N      文章级并发数（默认 4）
  -t, --img-workers N  每篇文章内的图片并发数（默认 8）
  -v, --verbose        DEBUG 级别日志
  --debug              调试模式：完整 traceback + HTTP 诊断 + 失败 dump
  -V, --version        显示版本号
```

---

## --debug 模式

普通运行只看到一行错误：

```
[ERROR] article failed https://mp.weixin.qq.com/s/xxx: 404 Not Found
```

加 `--debug` 后：

1. **完整 Python traceback** 输出到终端
2. **HTTP 层日志**（httpx 的请求/响应详情）打开
3. 在 `输出目录/_debug/` 下写两份文件：

```
output/
├── 文章A/
└── _debug/
    ├── failed.txt    # 每行：URL<TAB>错误消息
    └── report.txt    # 每个失败 URL 的完整 traceback
```

示例：

```powershell
uv run wx2md --debug https://mp.weixin.qq.com/s/INVALID_URL -o test
```

事后看 `test/_debug/report.txt` 就能定位"为什么这篇抓不下来"。

> `--debug` 自动包含 `-v`（DEBUG 级别日志），所以排错时只用 `--debug` 即可。

---

## 输出结构

```
output/
├── 文章标题A/
│   ├── article.md      ← Markdown，相对路径引用 assets/
│   ├── article.html    ← 极简骨架 + 公众号原样式，浏览器直接打开
│   └── assets/
│       ├── 7f3a1c9b2e4d5601.jpg
│       ├── a1b2c3d4e5f60718.png
│       └── ...
├── 文章标题B/
│   └── ...
└── _debug/             ← 只在 --debug 时存在
    ├── failed.txt
    └── report.txt
```

- 图片文件名 = `sha1(图片字节)[:16] + 扩展名`，**天然去重**：跨文章相同图片只存一份；重跑也不会重复下载（文件已存在则跳过）
- 标题里的 `\/:*?"<>|` 等非法字符会被替换成 `_`，长度截到 120
- `article.md` 顶部带原文链接与作者
- `article.html` 是个独立 HTML 文件，最小化外壳样式 + 公众号正文的 inline style 共同决定外观

---

## 打包成单文件 .exe

用 PyInstaller 把所有依赖、Python 解释器、源码都打进**一个**可执行文件，
发给同事可以**直接运行，不需要装 Python**。

### Windows

```powershell
# 1. 装 PyInstaller（已在 dev 依赖组里）
uv sync --group dev

# 2. 一键构建
.\build.ps1

# 产物：dist\wx2md.exe（约 25–40 MB）
```

### macOS / Linux

```bash
uv sync --group dev
./build.sh

# 产物：dist/wx2md
```

### 用产物

```powershell
# Windows
.\dist\wx2md.exe https://mp.weixin.qq.com/s/oKi8k-GTyL6ggSo4rqY3hw
.\dist\wx2md.exe --debug -i urls.txt -o output

# macOS/Linux
./dist/wx2md https://mp.weixin.qq.com/s/xxx
```

> **PyInstaller 不能跨平台**：Windows 上构建出 `.exe`，macOS 上构建出 mach-o
> 二进制，Linux 上构建出 ELF。要支持多平台需要分别在对应 OS 上构建。

---

## 开发指南

### 项目结构

```
to_md/
├── wx2md/                    包源码
│   ├── __init__.py           公开 API：Article、process_article、__version__
│   ├── __main__.py           支持 python -m wx2md
│   ├── cli.py                argparse + 文章级并发 + --debug
│   ├── core.py               process_article 主流程，Article dataclass
│   ├── net.py                fetch_article、download_image、UA、Referer
│   ├── parser.py             parse_meta、collect_images、rewrite_content、to_markdown
│   └── templates.py          HTML 模板
├── docs/
│   └── TECHNICAL.md          技术细节文档
├── pyproject.toml            项目元数据 + 依赖声明
├── uv.lock                   锁定的依赖版本
├── .python-version           3.13
├── build.ps1                 Windows 打包脚本
├── build.sh                  macOS/Linux 打包脚本
├── urls.txt.example          URL 列表样例
└── README.md                 本文件
```

### 添加 / 升级依赖

```powershell
# 加运行时依赖
uv add requests

# 加开发依赖
uv add --group dev pytest ruff

# 升级所有
uv lock --upgrade
uv sync
```

### 进入虚拟环境

```powershell
# 不用 activate，直接跑：
uv run python

# 或传统 activate：
.venv\Scripts\Activate.ps1     # Windows
source .venv/bin/activate      # macOS/Linux
```

### 锁文件与团队协作

- `uv.lock` **建议提交** 到 git，保证团队成员/CI 装到一模一样的版本
- 别人 clone 后只需 `uv sync` 即可复刻环境

### 重置环境

```powershell
Remove-Item -Recurse -Force .venv
uv sync
```

### 代码风格（可选）

```powershell
uv add --group dev ruff
uv run ruff check .
uv run ruff format .
```

---

## 常见问题排查

### 1. `content div #js_content not found`

可能原因：

- URL 已失效 / 文章被删
- 文章设置了"分享给好友才能看"的登录墙
- 服务器返回了反爬验证页

**对策**：浏览器打开同一 URL 确认能正常访问，或加 `--debug` 看完整响应。

### 2. 图片全部 403 / 下载失败

理论上脚本已带 `Referer: https://mp.weixin.qq.com/`，应该不会发生。如果发生：

- 检查是否被 IP 限流（短时间内抓太多）→ 降低 `-w` 和 `-t`
- 个别老图片地址已失效，脚本会跳过并打 warning，不影响其他

### 3. 中文文件夹乱码

Windows 终端建议使用 PowerShell 7+ 或 Windows Terminal，并把代码页设为 UTF-8：

```powershell
chcp 65001
```

### 4. `httpx.ConnectTimeout`

网络问题。可在 `wx2md/net.py` 把 `timeout=30` 改大，或加重试。

### 5. uv 找不到 Python

```powershell
uv python install 3.13
uv sync
```

### 6. 想看更详细日志 / traceback

加 `--debug`：

```powershell
uv run wx2md --debug -i urls.txt
```

### 7. PyInstaller 打包后跑不起来

- 先用 `uv run wx2md` 确认源码版本能跑
- 看 `build/wx2md/warn-*.txt` 里的缺失模块警告
- 检查 lxml：PyInstaller 偶尔抓不全 lxml 内部模块，
  build 脚本里已加 `--hidden-import lxml._elementpath`

---

## 实现原理

| 步骤 | 关键点 | 所在模块 |
|------|--------|----------|
| 抓 HTML | `httpx` + UA，公众号正文是 SSR，不需要浏览器 | `net.fetch_article` |
| 提取正文 | 锁定 `div#js_content`（公众号固定容器） | `core.process_article` |
| 提取标题 | `#activity-name` 或 `meta[property=og:title]` | `parser.parse_meta` |
| 提取作者 | `#js_name` 或 `meta[name=author]` | `parser.parse_meta` |
| 收集图片 | 优先 `data-src`（懒加载），回退 `src`；跳过 `data:` base64 | `parser.collect_images` |
| **绕过防盗链** | 下载时 header 必须带 `Referer: https://mp.weixin.qq.com/`，否则 `mmbiz.qpic.cn` 直接 403 | `net.download_image` |
| 图片命名 | `sha1(bytes)[:16]` + 扩展名，从 `Content-Type` / `wx_fmt=` 参数 / 路径后缀推断 | `net.download_image` / `net.pick_ext` |
| HTML 改写 | 只做不可避免的：`data-src→src`、删 `<script>/<iframe>`；保留 inline `style`、`<section>` 嵌套 | `parser.rewrite_content` |
| 转 Markdown | `markdownify`（ATX 标题、`-` 列表项），干掉 `<span>` | `parser.to_markdown` |
| 写出 HTML | 最小化页面骨架 + 公众号自带 inline style | `templates.HTML_TEMPLATE` |
| 并发 | 外层 `ThreadPoolExecutor(workers)` 跑文章；内层 `ThreadPoolExecutor(img_workers)` 跑图片；共用一个 `httpx.Client` 连接池 | `cli.main` + `core.process_article` |
| `--debug` | 捕获每次失败的 traceback，最后写出 `_debug/failed.txt` + `_debug/report.txt` | `cli.main` |

详细架构和设计权衡见 [`docs/TECHNICAL.md`](docs/TECHNICAL.md)。

---

## License

MIT — 个人使用、学习研究随便用。**请勿用于商业转载** —— 公众号原作者保留版权。

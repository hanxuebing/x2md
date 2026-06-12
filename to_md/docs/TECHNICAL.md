# 技术文档：wx2md

> 本文档讲解 `wx2md` 包是如何把微信公众号文章
> 完整地（含图片）转成本地可离线阅读的 Markdown + HTML 的，
> 以及背后的设计权衡。

## 目录

- [1. 问题场景](#1-问题场景)
- [2. 微信公众号文章的特殊性](#2-微信公众号文章的特殊性)
- [3. 整体架构](#3-整体架构)
- [4. 包结构与模块职责](#4-包结构与模块职责)
- [5. 关键函数解析](#5-关键函数解析)
- [6. 并发模型](#6-并发模型)
- [7. --debug 模式实现](#7---debug-模式实现)
- [8. 打包成 .exe（PyInstaller）](#8-打包成-exepyinstaller)
- [9. 设计决策](#9-设计决策)
- [10. 已知限制](#10-已知限制)
- [11. 扩展点](#11-扩展点)

---

## 1. 问题场景

很多人想"收藏"公众号文章，但微信的收藏夹：

- 不能搜索全文
- 不能跨设备稳定同步
- **作者删稿后链接就失效了**

目标：拿到 URL 就能把整篇文章（含所有图）落地成本地文件，
可以扔进 Obsidian / Notion / 静态站，永久保留。

输出形态：

| 格式 | 用途 |
|------|------|
| Markdown | 复制到任意笔记软件 |
| HTML | 浏览器直接打开，视觉上接近原文 |
| images/ | 图片本地化，断网也能看 |

分发形态：

| 形态 | 适合场景 |
|------|----------|
| Python 包 (`uv run`) | 开发期、自己用 |
| 全局命令 (`uv tool install`) | 装了 uv 的同事 |
| 单文件 .exe (PyInstaller) | 完全不装 Python 的同事 |

---

## 2. 微信公众号文章的特殊性

### 2.1 防盗链（Referer 校验）

公众号正文里所有图片的域名都是 `mmbiz.qpic.cn`，这个 CDN 会校验
`Referer` 请求头。直接 `curl` 取图片：

```bash
curl https://mmbiz.qpic.cn/mmbiz_jpg/xxx
# → 403 Forbidden
```

带上 Referer：

```bash
curl -H "Referer: https://mp.weixin.qq.com/" https://mmbiz.qpic.cn/mmbiz_jpg/xxx
# → 200 OK
```

**这是程序能跑通的最关键一行**（`wx2md/net.py`）：

```python
client.get(url, headers={"User-Agent": UA, "Referer": WX_REFERER}, ...)
```

### 2.2 图片懒加载

公众号正文里的 `<img>` 长这样：

```html
<img class="rich_pages wxw-img"
     data-src="https://mmbiz.qpic.cn/mmbiz_png/真实地址"
     data-w="800"
     data-ratio="0.66"
     src="data:image/svg+xml;utf8,<svg ...>">  <!-- 占位 SVG -->
```

照搬 `src` 会下载一堆占位 SVG。正确做法（`wx2md/parser.py`）：

```python
src = img.get("data-src") or img.get("src") or ""
```

### 2.3 HTML 结构：大量 `<section>` 嵌套 + inline style

公众号编辑器的输出长这样：

```html
<div id="js_content">
  <section style="text-align: center;">
    <section style="display: inline-block; ...">
      <section style="border-left: 4px solid #ddd;">
        <p style="font-size: 16px;">实际内容</p>
      </section>
    </section>
  </section>
  ...
</div>
```

每个 `<section>` 都没有语义，纯粹是承载 `style` 做排版。
对 HTML 输出：**保留** 它们，视觉就接近原文。
对 Markdown 输出：`markdownify` 看不懂 `<section>`，会当透明容器处理。

### 2.4 正文容器固定

`<div id="js_content">` 是所有公众号文章的正文锚点，
一句 `soup.select_one("#js_content")` 就够。

### 2.5 元数据位置

| 字段 | 主选 | 备选 |
|------|------|------|
| 标题 | `#activity-name` | `<meta property="og:title">` |
| 作者 | `#js_name` | `<meta name="author">` |

---

## 3. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│              wx2md/cli.py :: main()                       │
│  1. 解析 CLI 参数（含 --debug）                            │
│  2. 汇总 URL（位置参数 + -i 文件）                          │
│  3. 创建共享 httpx.Client                                  │
│  4. 启动文章级 ThreadPoolExecutor                          │
│  5. 收集失败的 traceback                                   │
│  6. --debug 时写出 _debug/{failed.txt, report.txt}        │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼ 对每个 URL
┌──────────────────────────────────────────────────────────┐
│          wx2md/core.py :: process_article()               │
│                                                           │
│  net.fetch_article() ──► BeautifulSoup ──► parse_meta()   │
│        │                                                  │
│        ▼                                                  │
│  parser.collect_images()                                  │
│        │                                                  │
│        ▼                                                  │
│  ┌────────────────────────────────────────────────┐      │
│  │  图片级 ThreadPoolExecutor                       │      │
│  │  并发跑 net.download_image() × N                 │      │
│  │  → {远程 URL: 本地文件名} mapping                 │      │
│  └────────────────────────────────────────────────┘      │
│        │                                                  │
│        ▼                                                  │
│  parser.rewrite_content()  (改 <img src> 为本地路径)       │
│        │                                                  │
│        ▼                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐      │
│  │ parser.to_markdown   │  │ templates.HTML_TEMPLATE │   │
│  └──────────────────────┘  └──────────────────────┘      │
│        │                            │                     │
│        ▼                            ▼                     │
│   article.md                   article.html               │
└──────────────────────────────────────────────────────────┘
```

---

## 4. 包结构与模块职责

```
wx2md/
├── __init__.py        公开 API：Article、process_article、__version__
├── __main__.py        让 `python -m wx2md` 跑得起来
├── cli.py             argparse、--debug、文章级线程池、失败汇总
├── core.py            process_article 主流程、Article dataclass、safe_filename
├── net.py             HTTP 层：fetch_article、download_image、UA、WX_REFERER、pick_ext
├── parser.py          DOM 层：parse_meta、collect_images、rewrite_content、to_markdown
└── templates.py       HTML 模板（含极简骨架 CSS）
```

| 模块 | 职责 | 不依赖谁 |
|------|------|----------|
| `net.py` | 只管 HTTP，不碰 DOM | 业务无关 |
| `parser.py` | 只管 DOM 解析/改写，不碰网络 | 业务无关 |
| `templates.py` | 只是字符串，纯数据 | 业务无关 |
| `core.py` | 编排：net + parser + templates | 依赖以上三个 |
| `cli.py` | argparse + 文章级并发 + 收集失败 | 依赖 core |
| `__main__.py` | 给 `python -m wx2md` 用 | 依赖 cli |
| `__init__.py` | re-export 公开 API | 依赖 core |

**单向依赖**：`cli → core → {net, parser, templates}`。便于单测和复用。

---

## 5. 关键函数解析

### 5.1 `net.fetch_article(url, client)`

拿一篇文章页 HTML。`follow_redirects=True` 因为公众号短链/分享链
有时候会 302。复用传入的 `client`，让连接池命中。

### 5.2 `net.download_image(url, dest_dir, client)`

最核心的函数。三件事：

1. 带 Referer 下载
2. 用 `sha1(bytes)[:16]` 给文件命名
3. 失败只 warn，**不抛出**

**为什么用 hash 命名而不是 URL 命名？**

- URL 命名要做 URL 编码反查，麻烦
- 公众号同一张图在不同文章里 URL 可能不同（路径里带时间戳），
  hash 命名天然跨文章去重
- 16 字符 = 64 bit，碰撞概率几乎为零
- 文件已存在则跳过，**重跑天然幂等**

**为什么失败不抛？**

- 一篇文章几十张图，一张挂了不该让整篇失败
- 失败的图 mapping 里没记录，`rewrite_content` 会保留远程 URL，
  浏览器还可能加载到（如果带 Referer）

### 5.3 `net.pick_ext(url, content_type)`

推断扩展名的回退链：

```
Content-Type → URL 里的 wx_fmt= 参数 → URL 路径后缀 → .jpg
```

`?wx_fmt=jpeg` 这种是公众号自家的格式标记，比路径靠谱。

### 5.4 `parser.parse_meta(soup)`

CSS selector 取标题/作者，对 `meta` 标签特殊处理（meta 用 `content`
属性而不是 text）。

### 5.5 `parser.collect_images(content)`

从正文 DOM 抓所有 `<img>` 的真实地址，按出现顺序去重。
跳过 `data:` 开头（base64 内联图）。

### 5.6 `parser.rewrite_content(content, mapping)`

**最克制的清洗**。只做两件事：

1. `<img>` src 替换成本地路径（如果下载成功）
2. 删 `<script>` 和 `<iframe>`（安全）

**故意保留**：

- inline `style` / `class` —— 决定视觉效果
- `<section>` 嵌套 —— 决定布局
- `<style>` 标签 —— 公众号偶尔会注入内联样式

这样导出的 HTML 视觉上接近原文截屏。

### 5.7 `parser.to_markdown(html)`

| markdownify 参数 | 选择 | 理由 |
|------------------|------|------|
| `heading_style="ATX"` | `# h1` | 现代 Markdown 通用 |
| `bullets="-"` | `-` 而非 `*` | GitHub 风格 |
| `strip=["span"]` | 去掉 span | 公众号 span 全是装饰用 |

markdownify 对未知标签（`<section>`）的处理是"透明继续"，
所以即使保留了 section 嵌套也能正确转出 MD。

### 5.8 `templates.HTML_TEMPLATE`

最小化页面骨架，**让公众号自己的 inline style 主导正文外观**：

- 居中容器，宽 677px（公众号 PC 版默认正文宽）
- 顶部 `<h1>` 标题 + 作者 + 原文链接
- **一条防御性 CSS**：`.page-body img { max-width: 100% !important }`
  —— inline width 设得过大时强制不溢出
- 其他都不管，由公众号的 inline style 决定

### 5.9 `core.process_article(url, out_root, img_workers, client)`

整篇文章的编排器。流程见 §3 架构图。
注意 `content` 和 `soup` 共享引用，`rewrite_content` 是原地修改。

### 5.10 `core.safe_filename(name)`

Windows 文件名兼容化：

- 替换 `\/:*?"<>|` 以及换行/制表符为 `_`
- 去掉首尾空格和点号（Windows 会出问题）
- 截到 120 字符（避开 260 路径上限）

---

## 6. 并发模型

### 6.1 两层并发

```
ThreadPoolExecutor(max_workers=W) ─── 文章并发
  └─ process_article(url1)
  └─ process_article(url2)        每个内部又起一个：
  └─ ...                          ThreadPoolExecutor(max_workers=T)
                                    └─ download_image(img1)
                                    └─ download_image(img2)
                                    └─ ...
```

理论最大并发：`W × T` 个图片下载 + `W` 个文章页同时跑。

### 6.2 共享 `httpx.Client`

所有线程共用一个 client，好处：

- 连接池复用 → 少了 TCP/TLS 握手成本
- `max_connections` 在 client 层面统一调度

`httpx.Client` 是线程安全的，可以直接共享。

`cli.main()` 里：

```python
limits = httpx.Limits(
    max_connections=args.workers * args.img_workers + 8,
    max_keepalive_connections=16,
)
with httpx.Client(http2=False, limits=limits) as client:
    ...
```

### 6.3 为什么用 threads 而非 asyncio？

- 工作负载 100% IO bound，threads 足够
- asyncio 要把整个调用栈染成 async，逻辑复杂度上升
- BeautifulSoup 没有 async 版本，asyncio 也会被解析阻塞
- threads 不需要 `await`，代码更直观

代价：受 OS 线程数和 Python GIL 影响，但 IO 阶段会释放 GIL，
对吞吐没实际影响。

### 6.4 错误隔离

| 失败级别 | 行为 |
|----------|------|
| 单张图片 | `download_image` 内 catch，log.warning，返回 None |
| 单篇文章 | `cli.main` 外层 catch，`fail += 1`，继续下一篇 |
| 汇总 | 最后输出 `finished: N ok / M failed / total`，退出码非零 |

---

## 7. --debug 模式实现

### 7.1 行为对比

| 选项 | 日志级别 | 失败输出 | 诊断 dump |
|------|----------|----------|-----------|
| 默认 | INFO | 单行 message | 无 |
| `-v / --verbose` | DEBUG | 单行 message | 无 |
| `--debug` | DEBUG（含 httpx） | **完整 traceback** | `_debug/{failed.txt, report.txt}` |

`--debug` 实际就是 `-v` + traceback 收集 + 失败报告。两者可以叠加，
单 `--debug` 就够了。

### 7.2 关键代码段（`wx2md/cli.py`）

```python
# --debug implies --verbose
debug = args.debug
verbose = args.verbose or debug

logging.basicConfig(
    level=logging.DEBUG if verbose else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if debug else "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
if debug:
    logging.getLogger("httpx").setLevel(logging.DEBUG)
```

捕获每次失败：

```python
for f in as_completed(futs):
    u = futs[f]
    try:
        f.result()
        ok += 1
    except Exception as exc:
        fail += 1
        if debug:
            tb = traceback.format_exc()
            log.error("article failed %s:\n%s", u, tb)
            failures.append({"url": u, "error": str(exc), "traceback": tb})
        else:
            log.error("article failed %s: %s", u, exc)
```

收集完写出：

```
output/_debug/failed.txt   每行：<URL>\t<错误消息>
output/_debug/report.txt   每个失败 URL 的完整 traceback
```

### 7.3 为什么没把 raw HTML 也 dump 出来？

文章解析失败时 (`#js_content not found`) 把整页 HTML 落地很有用，
但当前实现先不写，避免上来就让 `_debug/` 体积膨胀。
真要排查这种登录墙问题，加 `--debug` 看 httpx 的请求响应就够。
后续如果排查不够用，可以加 `dump_html` 到 `core.process_article`。

---

## 8. 打包成 .exe（PyInstaller）

### 8.1 为什么选 PyInstaller？

- 单文件输出，开箱即用
- 文档充分，社区大
- 对小项目体积可接受（~30 MB）

候选方案对比：

| 工具 | 优点 | 缺点 |
|------|------|------|
| **PyInstaller** | 简单成熟、文档充分 | 体积较大，启动稍慢 |
| Nuitka | 真正编译，运行更快 | 配置复杂、编译慢 |
| py2exe | Windows 老牌 | macOS/Linux 不支持 |
| shiv / pex | 不需要 OS 二进制 | 仍需目标机有 Python |

### 8.2 构建脚本

`build.ps1`（Windows）和 `build.sh`（macOS/Linux）大致都是：

```bash
pyinstaller \
    --onefile \
    --console \
    --name wx2md \
    --hidden-import lxml._elementpath \
    -p . \
    wx2md/__main__.py
```

关键选项：

| 选项 | 作用 |
|------|------|
| `--onefile` | 打成单文件而不是文件夹 |
| `--console` | 终端程序（保留 stdin/stdout） |
| `--hidden-import lxml._elementpath` | PyInstaller 抓不全 lxml 的内部模块，要手动加 |
| `-p .` | 让 PyInstaller 能找到 `wx2md` 这个包 |
| `wx2md/__main__.py` | 入口点 |

### 8.3 跨平台陷阱

PyInstaller **不能交叉编译**：

| 在哪里跑 build | 产物 |
|----------------|------|
| Windows | `dist/wx2md.exe` |
| macOS | `dist/wx2md`（mach-o） |
| Linux | `dist/wx2md`（ELF） |

要同时支持多平台，最简单的办法是 GitHub Actions 三平台矩阵 build。

### 8.4 体积优化（未做）

如果 30 MB 还嫌大，可以：

- `--exclude-module pytest --exclude-module setuptools` 等
- UPX 压缩：装 [upx](https://upx.github.io/) 再 `--upx-dir`
- 切到 nuitka 编译，能压到 15–20 MB

目前没做，因为对一个个人工具不必。

---

## 9. 设计决策

### 9.1 为什么不用 Playwright/Puppeteer？

公众号文章是 SSR（服务端渲染）的，HTML 已经包含正文，
不需要浏览器执行 JS。用 `httpx` 取 HTML 体积小 10 倍，
启动快 50 倍。

### 9.2 为什么不用 `wechatsogou`？

- 该库依赖搜狗微信搜索入口，那个入口早已不稳定
- 该库维护停滞
- 我们的需求只是单篇 URL → 文件，自己写 ~250 行更可控

### 9.3 为什么不用 `html2text`？

- `markdownify` 对 GFM 表格、嵌套列表、代码块支持更现代
- API 简洁

### 9.4 为什么用 sha1 而不是 md5？

性能差不多，sha1 摘要更安全（虽然这里不涉及安全）。
换成 sha256 体感无差异。

### 9.5 为什么 HTML 保留 inline style？

- 公众号编辑器输出的视觉就靠 inline style
- 剥掉后 HTML 像光秃秃的 Markdown，失去原文味道
- markdownify 反正会忽略它们，不影响 MD 输出

### 9.6 为什么按 net / parser / templates 拆模块？

每个模块的**外部依赖不同**：

- `net.py` 只依赖 `httpx`
- `parser.py` 只依赖 `bs4` 和 `markdownify`
- `templates.py` 纯 Python，零依赖

未来要换 HTTP 库（比如换成 `requests`）只动 `net.py`；要换 HTML 解析器
（比如换成 `selectolax`）只动 `parser.py`。这种"换零件不伤主体"的能力
是模块化的核心收益。

### 9.7 为什么 `--debug` 不引入额外配置文件？

诊断信息越简单越好。`failed.txt` 是机器可读的 TSV，
`report.txt` 是人可读的纯文本。不用 JSON 是因为查 traceback 时
直接 cat 看比 jq 看顺手。

---

## 10. 已知限制

| 限制 | 说明 |
|------|------|
| 视频/音频 | 公众号视频是嵌入式播放器，本地化困难，目前会被 `<iframe>` 清洗删掉 |
| 小程序卡片 | 同上，丢弃 |
| 阅读原文链接 | 保留在 HTML 头部的"原文链接" |
| 留言 | 公众号留言通过单独的 API 加载，不在文章 HTML 里，**不抓取** |
| 付费内容 | 需要登录态，工具无登录，付费墙后内容不可达 |
| 强反爬 | 极少数账号开启了"分享给好友才能看"，会返回登录墙 → `#js_content not found` |
| Referer 失效 | 如果未来腾讯换防盗链策略，需要更新 `net.WX_REFERER` 或加签名 |
| 视频号 | 完全不支持（不是公众号文章） |

---

## 11. 扩展点

按改动成本从低到高排列：

### 11.1 加 `--retry` 重试

`httpx` 自带 transport 层重试，改 `cli.main`：

```python
transport = httpx.HTTPTransport(retries=args.retry)
client = httpx.Client(transport=transport, ...)
```

### 11.2 加 `--limit` 限速

在 `net.download_image` 前后用信号量控制：

```python
from threading import Semaphore
_throttle = Semaphore(value=8)

def download_image(...):
    with _throttle:
        ...
```

### 11.3 dump 失败页面的原 HTML

在 `core.process_article` 找不到 `#js_content` 时，
把整页 HTML 写到 `out_root/_debug/<safe_url>.html`，
便于事后看是不是登录墙。需要让 `core.process_article` 接受一个
可选的 `debug_dir: Path | None`。

### 11.4 输出 EPUB

抓完一批后，用 `ebooklib` 把每篇文章包成 EPUB：

```python
from ebooklib import epub
book = epub.EpubBook()
for article in articles:
    chap = epub.EpubHtml(title=article.title, file_name=f"{idx}.xhtml")
    chap.content = article.html
    book.add_item(chap)
```

`Article` dataclass 已经携带了所有所需字段。

### 11.5 接入 LLM 做摘要 / 翻译

写完 `.md` 后再走一遍 LLM，写出 `.summary.md`：

```python
from anthropic import Anthropic
client = Anthropic()
msg = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=500,
    messages=[{"role": "user", "content": f"用 200 字总结：\n{md_text}"}],
)
```

### 11.6 GitHub Actions 三平台 release

```yaml
strategy:
  matrix:
    os: [windows-latest, macos-latest, ubuntu-latest]
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v3
  - run: uv sync --group dev
  - run: ./build.sh        # macOS/Linux
  - run: .\build.ps1       # Windows
  - uses: actions/upload-artifact@v4
    with: { path: dist/wx2md* }
```

### 11.7 增量抓某账号全部历史

需要登录态（微信公众号后台 token 或代理 PC 端微信），
**门槛高且不稳定**，不建议加进本工具。
真有此需求建议接入 wxread/wechat-mp-spider 这类专门库。

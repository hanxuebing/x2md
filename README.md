# x2md

把各种来源的文档统一转换成本地可离线阅读的 **Markdown + HTML**（含本地化资源）的工具集合。
每个子目录是一个独立的 Python 项目（用 [uv](https://docs.astral.sh/uv/) 管理依赖），按输入来源拆分。

---

## 子目录一览

| 目录 | 项目名 | 作用 | 形态 |
|------|--------|------|------|
| [`to_md/`](to_md/) | **wx2md** | 微信公众号文章 → Markdown + HTML，自动下载图片（绕过防盗链） | Python 包 / CLI / 单文件 .exe |
| [`pdf_md/`](pdf_md/) | **pdf2x** | PDF → 像素级还原 HTML（exact）/ 语义 HTML（flow）+ 结构对齐 Markdown，可选 OCR | Python 库 / CLI |
| [`gen_link/`](gen_link/) | **gen_readme** | 扫描 `output/` 下每篇 `article.md` 的 YAML frontmatter，生成文章索引 | 单脚本 |

> `to_md` / `pdf_md` 是**转换器**；`gen_link` 是**后处理器**（对转换产物建索引），不关心来源是什么，只依赖下面的导出标准。

---

## 导出文件结构与命名标准

所有转换器（现有的及未来新增的）都应遵循同一套输出约定，
这样 `gen_link` 等下游工具无需为每个库单独适配，产物也可以混放在同一个 `output/` 里。

### 目录结构

```
output/
├── <安全标题A>/
│   ├── article.md          ← Markdown，带 YAML frontmatter
│   ├── article.html        ← 离线 HTML，浏览器双击即看
│   └── assets/             ← 该条目的所有本地化资源（图片等）
│       ├── 7f3a1c9b2e4d5601.jpg
│       └── a1b2c3d4e5f60718.png
├── <安全标题B>/
│   └── ...
└── _debug/                 ← 仅调试模式且有失败时出现
    ├── failed.txt
    └── report.txt
```

### 命名约定

| 项 | 标准 |
|----|------|
| 文档主文件 | 固定叫 `article.md` / `article.html`（下游靠这个名字发现条目） |
| 资源目录 | 统一叫 **`assets/`** |
| 资源文件名 | `sha1(内容字节)[:16]` + 扩展名 → 天然去重 + 重跑幂等（已存在则跳过） |
| 文档目录名 | 由标题派生，经安全化处理：剔除 `\/:*?"<>|`，长度截断到 120 |

### article.md frontmatter

```yaml
---
title: "文章标题"          # 必填；gen_link 用它做链接文字
url: "https://..."        # 选填；原始来源链接
author: "作者"             # 选填
date: "2026-06-12"        # 选填；gen_link 按此倒序排列
---
```

新字段保持向后兼容：`gen_link` 只读它认识的键，多余的忽略。

---

## 新增转换器检查清单

1. 在 `x2md/` 下建子目录，`uv init` 起项目
2. 输出遵循上面的结构：`output/<安全标题>/{article.md, article.html, assets/}`
3. `article.md` 写好 frontmatter（至少 `title`）
4. 资源走 sha1 命名，目录名走安全化处理
5. 在本文件「子目录一览」表里加一行

照这套来，新库的产物天然能被 `gen_link` 索引。

---

## 各子项目详情

- [`to_md/README.md`](to_md/README.md) — 安装、批量抓取、多线程调优、打包 .exe
- [`pdf_md/README.md`](pdf_md/README.md) — 环境要求、exact/flow 模式、OCR 配置
- [`gen_link/gen_readme.py`](gen_link/gen_readme.py) — `uv run gen_readme.py [output_dir]`

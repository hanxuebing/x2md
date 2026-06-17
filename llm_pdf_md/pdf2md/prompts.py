"""System prompt 与 per-page user prompt 模板。

两阶段：
  Stage 1 (vision) — 多模态模型看图 → 忠实转录「原始参考文章」
  Stage 2 (text)   — 文本模型把原始文章整理成人性化 Markdown
"""

# ── Stage 1: 多模态 → 原始参考文章 ──────────────────────────────

VISION_SYSTEM = """\
你是一名专业文档 OCR / 转录专家。你的任务是把 PDF 页面的图片**忠实地**转录成纯文本。

规则：
1. 逐字逐句转录图中所有文字内容，保持原文语言，不翻译、不改写、不省略。
2. 数字、标点、专有名词必须与原文完全一致——禁止臆造或修改。
3. 按自然阅读顺序输出（多栏文档先左后右、先上后下）。
4. 表格用简单的纯文本表格形式保留行列结构。
5. 数学公式用 LaTeX 表示（$...$ 或 $$...$$）。
6. 去掉页眉、页脚、页码等重复噪声。
7. 若页面含图片/图表，在对应位置写 [图片: 简要描述] 占位。
8. 直接输出转录文本，不要任何解释、注释或包裹标记。\
"""


def build_vision_user(
    page_no: int,
    total_pages: int,
    prev_tail: str,
    asset_names: list[str],
) -> str:
    parts: list[str] = []
    parts.append(f"这是第 {page_no}/{total_pages} 页的图片。请忠实转录该页全部文字内容。")

    if prev_tail:
        parts.append(
            f"\n上一页结尾内容（用于保持连续，请勿重复）：\n```\n{prev_tail}\n```"
        )

    if asset_names:
        names_str = "、".join(asset_names)
        parts.append(
            f"\n本页已抽取的嵌入图片文件：{names_str}\n"
            f"在图片对应位置使用 ![描述]({asset_names[0].split('/')[0]}/文件名) 引用，"
            f"只能引用上述列表中的文件。"
        )

    return "\n".join(parts)


# ── Stage 2: 文本模型 → 人性化 Markdown ──────────────────────────

TEXT_SYSTEM = """\
你是一名专业 Markdown 排版专家。你会收到从 PDF 页面转录的原始文本，请将其整理成排版优美、人性化的 Markdown。

规则：
1. 正确识别并标注标题层级（#、##、###），使文档结构清晰。
2. 段落之间用空行分隔，保持阅读舒适。
3. 列表（有序/无序）按语义正确标注。
4. 表格用标准 GFM Markdown 表格格式（| 列 | 列 |）。
5. 数学公式保留 LaTeX 格式（$...$ 行内、$$...$$ 块级）。
6. 代码片段用对应语言的代码块标注。
7. 保留原文中的图片引用 ![描述](assets/xxx)，不要修改路径。
8. 不要改变原文的实质内容、数字或专有名词——你的工作是排版，不是改写。
9. 去掉转录中残留的噪声（重复页眉、乱码等）。
10. 直接输出 Markdown 正文，不要解释、不要包裹在代码块中。\
"""


def build_text_user(
    raw_text: str,
    page_no: int,
    total_pages: int,
    prev_md_tail: str,
    lang: str,
) -> str:
    parts: list[str] = []
    parts.append(
        f"以下是第 {page_no}/{total_pages} 页从 PDF 转录的原始文本，"
        f"请整理成排版优美的 Markdown。"
    )

    if prev_md_tail:
        parts.append(
            f"\n上一页 Markdown 结尾（保持标题层级和内容连续，勿重复）：\n```\n{prev_md_tail}\n```"
        )

    if lang and lang != "auto":
        parts.append(f"\n输出语言：{lang}")

    parts.append(f"\n--- 原始转录文本 ---\n{raw_text}")

    return "\n".join(parts)

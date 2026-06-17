"""HTML 输出模板。

注意:`{{` 和 `}}` 是 str.format() 的转义写法,代表字面量的左右花括号(CSS 用);
而 `{name}` 形式才是真正的占位符,由 core.py 在 format() 时替换。

本模板只负责"外壳" —— 容器宽度、页头标题、字体等。文章正文的样式完全
交给:
    1) 微信原文里 inline 的 style/class;
    2) `{head_styles}` 占位符注入的 <head> 内的 <style> 块。
这样导出的离线 HTML 与微信 App 中的展示效果基本一致。
"""
from __future__ import annotations

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    margin: 0;
    padding: 20px 20px 40px;
    /* 中文优先字体栈:macOS / iOS 用苹方,Windows 用微软雅黑,
       最后兜底通用 sans-serif,保证各平台都有合适字形 */
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB",
                 "Microsoft YaHei", BlinkMacSystemFont, "Segoe UI",
                 Roboto, Helvetica, Arial, sans-serif;
    color: #222;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  .page {{
    /* 677px 是微信 App 内文章正文的标准宽度,这里对齐保证排版一致 */
    max-width: 677px;
    margin: 0 auto;
    background: #fff;
    box-sizing: border-box;
  }}
  .page-header {{
    padding-bottom: 16px;
    margin-bottom: 24px;
    border-bottom: 1px solid #eee;
  }}
  .page-header h1 {{ margin: 0 0 8px; font-size: 22px; line-height: 1.4; }}
  .page-meta {{ color: #999; font-size: 14px; }}
  .page-meta a {{ color: #576b95; text-decoration: none; }}
  .page-meta a:hover {{ text-decoration: underline; }}
  /* "原创"标签:橙色描边小徽章,模拟微信原生样式 */
  .page-meta .tag-original {{
    display: inline-block;
    padding: 1px 6px;
    margin-right: 6px;
    font-size: 12px;
    color: #fa9d3b;
    border: 1px solid #fa9d3b;
    border-radius: 2px;
    vertical-align: 1px;
  }}
  /* 强制图片不超出容器宽度,避免长图撑破布局;
     !important 用来覆盖微信原文里可能的 inline 宽度声明 */
  .page-body img {{ max-width: 100% !important; height: auto !important; }}
</style>
{head_styles}
<style>
  /* 兜底:微信原文中部分 class 默认 visibility:hidden + opacity:0,
     依赖 JS 触发渐入动画。离线 HTML 已经移除 <script>(parser.py 中处理),
     这里在 head_styles 之后再写一段,通过源码顺序 + !important 强制可见。 */
  .rich_media_content,
  .rich_media_content *,
  .js_underline_content,
  [class*="autoTypeSetting"] {{
    visibility: visible !important;
    opacity: 1 !important;
  }}
</style>
</head>
<body>
<div class="page">
  <div class="page-header">
    <h1>{title}</h1>
    <div class="page-meta">{meta_line}</div>
  </div>
  <!-- rich_media_content 这个 class 必须保留:微信内联 CSS 中
       大量选择器以 .rich_media_content xxx 为前缀,缺它样式不生效 -->
  <div class="page-body {body_class}">
{body}
  </div>
</div>
</body>
</html>
"""

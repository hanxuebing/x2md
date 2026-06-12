# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`wx2md` — converts WeChat official-account articles (`mp.weixin.qq.com/s/...`) into local Markdown + HTML with downloaded images. Python 3.13+, dependency-managed by **uv**.

## Common commands

```powershell
# Install / sync deps (creates .venv, installs Python 3.13 if missing)
uv sync
uv sync --group dev        # also installs pyinstaller

# Run during development
uv run wx2md <URL>
uv run wx2md -i urls.txt -o output -w 4 -t 8
uv run wx2md --debug <URL>          # full traceback + HTTP logs + _debug/ dump
uv run python -m wx2md <URL>        # equivalent module form

# Install globally as a CLI
uv tool install .
uv tool uninstall wx2md

# Build single-file executable (PyInstaller)
.\build.ps1                 # Windows -> dist\wx2md.exe
./build.sh                  # macOS/Linux -> dist/wx2md

# Dependency management
uv add <pkg>                # runtime dep
uv add --group dev <pkg>    # dev dep
uv lock --upgrade && uv sync
```

There is no test suite, linter, or formatter configured. Don't invent commands.

## Architecture

The package is a small pipeline; understanding it requires reading across modules.

**Entry → concurrency → per-article pipeline → output**

- `cli.py` — argparse + the **outer** `ThreadPoolExecutor(workers)` that fans out *articles*. Constructs a single shared `httpx.Client` (with `Limits`) that is reused by every thread. Owns `--debug` reporting: catches per-article exceptions and writes `output/_debug/failed.txt` + `report.txt`.
- `core.process_article` — orchestrates one article: fetch HTML → `parse_meta` → locate `#js_content` → spin up the **inner** `ThreadPoolExecutor(img_workers)` for images → `rewrite_content` → write `article.md` (with YAML frontmatter), `article.html`, and `images/`. Both pools share the same `httpx.Client` so connections pool naturally.
- `net.py` — HTTP layer. Two non-obvious constraints encoded here:
  - `mmbiz.qpic.cn` rejects requests without `Referer: https://mp.weixin.qq.com/` (anti-hotlink). Every image GET must include it.
  - Image filename = `sha1(bytes)[:16] + ext`. Same content → same name → cross-article dedup *and* idempotent re-runs (skip if file exists). Extension inferred from `Content-Type` → `wx_fmt=` URL param → URL suffix → `.jpg`.
  - Image download failures only log a warning; the article still completes.
- `parser.py` — DOM extraction. Key behaviors:
  - WeChat lazy-loads images: real URL is in `data-src`, `src` is a placeholder gif. `collect_images` and `rewrite_content` both honor this.
  - Metadata extraction has multiple fallbacks per field (e.g. publish date tries `#publish_time` → `var ct = "<unix>"` → `var publish_time = "..."`); WeChat's SSR HTML is inconsistent, so don't drop fallbacks when refactoring.
  - `rewrite_content` is deliberately *minimal*: it only rewrites `<img>` src and drops `<script>`/`<iframe>`. Inline `style`, `class`, and `<section>` nesting are preserved so the exported HTML still looks like a WeChat article — and so the head `<style>` rules (which target `.rich_media_content ...`) still match.
  - `extract_head_styles` copies inline `<style>` blocks but intentionally does *not* fetch `<link rel="stylesheet">` hrefs (avoid extra network calls).
- `templates.py` — `HTML_TEMPLATE` is a `str.format()` template. `{{` / `}}` are literal-brace escapes; `{name}` are placeholders. The outer shell is intentionally minimal because article styling is delegated to the copied-in head `<style>` blocks plus WeChat's inline styles. Keep `class="rich_media_content"` on the body wrapper — head styles depend on it.

### One DOM, two outputs

`core.process_article` parses the article once and produces both Markdown and HTML from the same `BeautifulSoup` tree. `markdownify` only consumes semantic tags (h1/p/ul/...) and ignores `style`/`class`, so the same tree serves both outputs without a separate "strip for markdown" pass.

### Concurrency model

Outer pool size = `-w` (default 4), inner pool size = `-t` (default 8). Connection pool limit is set to `workers * img_workers + 8`. When tuning, remember WeChat may rate-limit aggressive concurrency — the README's tuning table is the project's lived-in guidance.

## Conventions worth following

- New code should keep the "why" in comments and let names carry the "what" — the existing modules follow this. Comments in this codebase explain WeChat quirks (anti-hotlink, lazy-load, SSR field fallbacks), not control flow.
- Don't introduce a synchronous-only path or remove the shared `httpx.Client` — the connection pool is a real performance win at the default settings.
- `safe_filename` in `core.py` is Windows-aware (strips `\/:*?"<>|`, truncates to 120). Any new path component derived from article content should go through it.
- `--debug` implies `-v`. Don't gate diagnostic-only behavior on `-v` alone.

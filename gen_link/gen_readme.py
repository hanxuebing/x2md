#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan each subfolder of OUTPUT_DIR for an `article.md`, read its YAML
frontmatter, and generate two files:
  - OUTPUT_DIR/README.md     local file links: [title](<dir/article.md>)
  - OUTPUT_DIR/README_URL.md plain text: url line, then title line (or just
                             title if no url), blank line after each entry.

Usage:
    uv run gen_readme.py [output_dir]
    python gen_readme.py [output_dir]
Defaults output_dir to the `output` folder next to this script.
"""
import os
import sys
import re


def parse_frontmatter(path):
    """Return a dict of the YAML frontmatter at the top of a markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.startswith("---"):
        return {}

    # Split out the block between the first two `---` fences.
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}

    data = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes.
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        data[key] = value
    return data


def md_link_path(rel):
    """Wrap a relative path for markdown; use <> when it has spaces/special chars."""
    if re.search(r"[ ()]", rel):
        return "<" + rel + ">"
    return rel


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, "output")

    if not os.path.isdir(output_dir):
        print("Output dir not found: %s" % output_dir, file=sys.stderr)
        sys.exit(1)

    articles = []
    for name in sorted(os.listdir(output_dir)):
        sub = os.path.join(output_dir, name)
        if not os.path.isdir(sub):
            continue
        article = os.path.join(sub, "article.md")
        if not os.path.isfile(article):
            continue
        fm = parse_frontmatter(article)
        title = fm.get("title") or name
        articles.append({
            "dir": name,
            "title": title,
            "fm": fm,
            "rel": "%s/article.md" % name,
        })

    # Sort newest first by frontmatter date when available.
    articles.sort(key=lambda a: a["fm"].get("date", ""), reverse=True)

    # README.md: local file links [title](<dir/article.md>)
    link_lines = []
    for a in articles:
        link_lines.append("- [%s](%s)" % (a["title"], md_link_path(a["rel"])))

    readme = os.path.join(output_dir, "README.md")
    with open(readme, "w", encoding="utf-8") as f:
        f.write("\n".join(link_lines).rstrip() + "\n")

    # README_URL.md: plain text, url on its own line then title on the next line
    # (just title if no url), with a blank line after each entry.
    url_lines = []
    for a in articles:
        url = a["fm"].get("url", "")
        if url:
            url_lines.append(url)
        url_lines.append(a["title"])
        url_lines.append("")

    readme_url = os.path.join(output_dir, "README_URL.md")
    with open(readme_url, "w", encoding="utf-8") as f:
        f.write("\n".join(url_lines).rstrip() + "\n")

    print("Wrote %s and %s (%d articles)" % (readme, readme_url, len(articles)))


if __name__ == "__main__":
    main()

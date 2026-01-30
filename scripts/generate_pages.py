#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

import yaml


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_paper(p: dict) -> str:
    summary = p.get("summary") or {}
    title = p.get("title", "")
    url = p.get("url", "")
    authors = ", ".join(p.get("authors", [])[:8])
    pub = p.get("published", "")
    journal = p.get("journal", "")
    score = p.get("score")

    score_html = f'<span class="score-badge">相关性 {int(score)}/100</span>' if isinstance(score, (int, float)) else ""

    parts = []
    parts.append('<article class="paper-card">')
    parts.append("  <div class=\"paper-header\">")
    parts.append("    <div class=\"left\">")
    if journal:
        parts.append(f"      <span class=\"journal\">{journal}</span>")
    if pub:
        parts.append(f"      <span class=\"date\">{pub}</span>")
    parts.append("    </div>")
    if score_html:
        parts.append(f"    {score_html}")
    parts.append("  </div>")

    parts.append("  <h3 class=\"title\">")
    if url:
        parts.append(f"    <a href=\"{url}\" target=\"_blank\">{title}</a>")
    else:
        parts.append(f"    {title}")
    parts.append("  </h3>")

    if summary.get("title_zh"):
        parts.append(f"  <p class=\"title-zh\">{summary['title_zh']}</p>")

    if authors:
        parts.append(f"  <p class=\"authors\">{authors}</p>")

    blocks = []
    if summary.get("tool_type"):
        blocks.append(f"<div class=\"summary-block\"><strong>工具类型:</strong> {summary['tool_type']}</div>")
    if summary.get("design"):
        blocks.append(f"<div class=\"summary-block\"><strong>设计思路:</strong> {summary['design']}</div>")
    if summary.get("functions"):
        blocks.append(f"<div class=\"summary-block\"><strong>功能与应用:</strong> {summary['functions']}</div>")
    if summary.get("key_results"):
        blocks.append(f"<div class=\"summary-block\"><strong>关键结果:</strong> {summary['key_results']}</div>")

    if blocks:
        parts.append('  <div class="summary">')
        parts.extend(["    " + b for b in blocks])
        parts.append("  </div>")

    abstract = p.get("abstract")
    if abstract:
        parts.append('  <details class="abstract">')
        parts.append('    <summary>查看摘要</summary>')
        parts.append(f"    <p>{abstract}</p>")
        parts.append("  </details>")

    parts.append("</article>")
    return "\n".join(parts)


def build_index_html(papers: list[dict], config: dict, date_str: str) -> str:
    site = config.get("site", {})
    title = site.get("title", "PubMed RNA Editing Daily Digest")
    desc = site.get("description", "最近 30 天内 RNA 编辑工具相关论文")

    cards = "\n\n".join(render_paper(p) for p in papers)

    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: #050816;
      color: #e5e7eb;
      margin: 0;
      padding: 1.5rem;
      max-width: 900px;
      margin-inline: auto;
    }}
    header {{
      margin-bottom: 2rem;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 1.5rem;
    }}
    h1 {{
      margin: 0 0 .5rem;
      font-size: 1.9rem;
    }}
    .desc {{
      color: #9ca3af;
      font-size: .95rem;
    }}
    .date {{
      margin-top: .75rem;
      color: #a5b4fc;
      font-weight: 500;
    }}
    .count {{
      font-size: .9rem;
      color: #9ca3af;
      margin-top: .25rem;
    }}
    .archive-top {{
      margin-top: .5rem;
      font-size: .9rem;
    }}
    .archive-top a {{
      color: #a5b4fc;
      text-decoration: none;
    }}
    .paper-card {{
      background: #020617;
      border-radius: .75rem;
      border: 1px solid #1f2937;
      padding: 1.25rem 1.4rem;
      margin-bottom: 1rem;
    }}
    .paper-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: .4rem;
      font-size: .8rem;
      color: #9ca3af;
      gap: .75rem;
    }}
    .paper-header .left {{
      display: flex;
      align-items: center;
      gap: .5rem;
    }}
    .journal {{
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .date {{
      font-variant-numeric: tabular-nums;
    }}
    .score-badge {{
      border-radius: 999px;
      border: 1px solid #4f46e5;
      padding: 0.15rem 0.6rem;
      font-size: 0.78rem;
      color: #a5b4fc;
      background: rgba(79, 70, 229, 0.12);
    }}
    .title {{
      margin: .2rem 0 .4rem;
      font-size: 1.05rem;
      line-height: 1.4;
    }}
    .title a {{
      color: #e5e7eb;
      text-decoration: none;
    }}
    .title a:hover {{
      color: #a5b4fc;
    }}
    .title-zh {{
      margin: 0 0 .4rem;
      color: #9ca3af;
      font-size: .92rem;
    }}
    .authors {{
      margin: 0 0 .7rem;
      color: #9ca3af;
      font-size: .85rem;
    }}
    .summary {{
      background: #020617;
      border-radius: .5rem;
      border: 1px solid #1f2937;
      padding: .7rem .8rem;
      font-size: .86rem;
      margin-bottom: .5rem;
    }}
    .summary-block {{
      margin-bottom: .35rem;
    }}
    .summary-block:last-child {{
      margin-bottom: 0;
    }}
    .summary-block strong {{
      color: #a5b4fc;
      margin-right: .25rem;
    }}
    details.abstract {{
      margin-top: .3rem;
      font-size: .85rem;
    }}
    details.abstract summary {{
      cursor: pointer;
      color: #9ca3af;
    }}
    details.abstract p {{
      margin-top: .4rem;
      color: #9ca3af;
    }}
    footer {{
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid #1f2937;
      font-size: .8rem;
      color: #6b7280;
    }}
    footer a {{
      color: #a5b4fc;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p class=\"desc\">{desc}</p>
    <div class=\"date\">📅 {date_str}</div>
    <div class=\"count\">共 {len(papers)} 篇精选论文</div>
    <div class=\"archive-top\"><a href=\"archive.html\">查看历史归档 →</a></div>
  </header>

  <main>
  {cards}
  </main>

  <footer>
    <p>数据来源: <a href=\"https://pubmed.ncbi.nlm.nih.gov/\" target=\"_blank\">PubMed</a></p>
    <p>AI 排序/总结: DeepSeek</p>
  </footer>
</body>
</html>
"""


def build_archive_html(dates: list[str], config: dict) -> str:
    site = config.get("site", {})
    title = site.get("title", "PubMed RNA Editing Daily Digest")

    links = "\n".join(
        f'<a class="archive-link" href="{d}.html">{d}</a>' for d in dates
    )

    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>归档 - {title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: #050816;
      color: #e5e7eb;
      margin: 0;
      padding: 1.5rem;
      max-width: 600px;
      margin-inline: auto;
    }}
    h1 {{
      margin: 0 0 1.5rem;
      font-size: 1.6rem;
    }}
    .archive-link {{
      display: block;
      padding: .75rem 1rem;
      margin-bottom: .5rem;
      border-radius: .5rem;
      border: 1px solid #1f2937;
      background: #020617;
      color: #e5e7eb;
      text-decoration: none;
      font-size: .95rem;
    }}
    .archive-link:hover {{
      border-color: #4f46e5;
    }}
    .back {{
      margin-bottom: 1rem;
      font-size: .9rem;
    }}
    .back a {{
      color: #a5b4fc;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class=\"back\"><a href=\"index.html\">← 返回今日</a></div>
  <h1>🧬 历史归档</h1>
  {links}
</body>
</html>
"""


def main():
    config = load_config()
    data_dir = Path(__file__).parent.parent / "data" / "papers"
    today = datetime.now().strftime("%Y-%m-%d")
    papers_file = data_dir / f"{today}.json"

    output_dir = Path(__file__).parent.parent / "public"
    output_dir.mkdir(parents=True, exist_ok=True)
    papers: list[dict] = []
    if papers_file.exists():
        with open(papers_file, "r", encoding="utf-8") as f:
            papers = json.load(f)

    # 今日页面：index.html + YYYY-MM-DD.html
    html = build_index_html(papers, config, today)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / f"{today}.html").write_text(html, encoding="utf-8")
    print(f"[pages] Generated index.html and {today}.html with {len(papers)} papers")

    # 归档页面：扫描所有日期
    dates = sorted([p.stem for p in data_dir.glob("*.json")], reverse=True)
    if dates:
        archive_html = build_archive_html(dates, config)
        (output_dir / "archive.html").write_text(archive_html, encoding="utf-8")
        print(f"[pages] Generated archive.html with {len(dates)} days")


if __name__ == "__main__":
    main()

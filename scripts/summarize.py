#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pathlib import Path

import yaml

try:
    from openai import OpenAI
except ImportError:
    import subprocess

    subprocess.check_call(["pip", "install", "openai"])
    from openai import OpenAI


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_client(config: dict):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")

    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


SUMMARY_PROMPT = """你是一名专注于 RNA 编辑工具与可编程 RNA 调控系统的学术助手。
请用中文对下面这篇 PubMed 论文做结构化总结，重点关注其作为"工具"或"平台"的价值。

需要输出的要点：
1. 中文标题：将英文标题翻译为简明的中文标题。
2. 工具/系统类型：说明这是哪一类工具（例如 RNA base editor、Cas13 系统、ADAR 结合工具、RNA 传感器等）。
3. 设计思路：用 2-3 句概括核心工程设计/模块化组合的思路（例如酶结构域 + gRNA 设计、招募机制等）。
4. 功能与应用：列出该工具可以实现的功能（如位点特异性编辑、剪接调控、翻译抑制/激活、RNA 检测与追踪等）。
5. 重要实验结果：用 1-2 句总结最关键的性能指标（如编辑效率、脱靶情况、体内/体外验证等）。

论文标题: {title}

论文摘要:
{abstract}

请严格按以下 JSON 结构返回（确保是有效 JSON）：
{{
  "title_zh": "中文标题",
  "tool_type": "工具/系统类型",
  "design": "设计思路",
  "functions": "功能与应用",
  "key_results": "重要实验结果"
}}
"""


def summarize_paper(client: OpenAI, paper: dict, config: dict):
    ds_cfg = config.get("deepseek", {})
    prompt = SUMMARY_PROMPT.format(title=paper.get("title", ""), abstract=paper.get("abstract", ""))

    try:
        resp = client.chat.completions.create(
            model=ds_cfg.get("model", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=ds_cfg.get("max_tokens", 600),
            temperature=ds_cfg.get("temperature", 0.2),
        )
        content = resp.choices[0].message.content.strip()

        if content.startswith("```"):
            parts = content.split("```", 2)
            if len(parts) >= 2:
                content = parts[1]
            content = content.lstrip()
            if content.lower().startswith("json"):
                content = content.split("\n", 1)[1] if "\n" in content else ""

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start : end + 1]
        else:
            json_str = content

        data = json.loads(json_str)
        return data
    except Exception as e:
        print(f"[summary] Failed to summarize PMID {paper.get('id')}: {e}")
        return None


def process_papers(papers_file: Path):
    config = load_config()
    with open(papers_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    if not papers:
        print("[summary] No papers to summarize")
        return

    client = create_client(config)

    for i, paper in enumerate(papers):
        if paper.get("summary"):
            print(f"[summary] Skip already summarized: {paper.get('id')}")
            continue
        print(f"[summary] ({i+1}/{len(papers)}) Summarizing PMID {paper.get('id')}...")
        summary = summarize_paper(client, paper, config)
        if summary:
            paper["summary"] = summary
        time.sleep(0.5)

    with open(papers_file, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"[summary] Updated {papers_file}")


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    papers_file = Path(__file__).parent.parent / "data" / "papers" / f"{today}.json"
    if not papers_file.exists():
        print(f"[summary] Papers file not found: {papers_file}")
        print("[summary] Run fetch_papers.py first")
        return
    process_papers(papers_file)


if __name__ == "__main__":
    main()

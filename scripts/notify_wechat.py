#!/usr/bin/env python3
import json
import os
from datetime import datetime
from pathlib import Path
from urllib import parse, request

import yaml


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_today_file() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return Path(__file__).parent.parent / "data" / "papers" / f"{today}.json"


def count_papers(file_path: Path) -> int:
    if not file_path.exists():
        return 0
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        return 0
    except Exception:
        return 0


def resolve_site_url(config: dict) -> str:
    base = config.get("site", {}).get("base_url") or ""
    if base:
        return base.rstrip("/") + "/"

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"

    return ""


def send_serverchan(key: str, title: str, desp: str) -> None:
    url = f"https://sctapi.ftqq.com/{key}.send"
    payload = parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
    req = request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    try:
        with request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f"[notify] send failed: {e}")


def main():
    key = os.environ.get("SERVERCHAN_KEY")
    if not key:
        print("[notify] SERVERCHAN_KEY not set, skip WeChat notification")
        return

    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")
    papers_file = get_today_file()
    count = count_papers(papers_file)
    site_url = resolve_site_url(config)

    if count > 0:
        title = f"PubMed RNA Editing Digest {today} 已更新 ({count} 篇)"
        lines = [
            f"今日共 {count} 篇与 programmable RNA editing / RNA 工具相关的候选论文。",
        ]
    else:
        title = f"PubMed RNA Editing Digest {today} 暂无候选论文"
        lines = ["今天没有满足筛选条件的 RNA 编辑工具相关论文。"]

    if site_url:
        lines.append("")
        lines.append(f"点击查看：{site_url}")

    desp = "\n".join(lines)
    send_serverchan(key, title, desp)
    print(f"[notify] sent notification for {today}, count={count}")


if __name__ == "__main__":
    main()

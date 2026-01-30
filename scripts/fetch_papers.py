#!/usr/bin/env python3
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import yaml

try:
    from openai import OpenAI
except ImportError:  # 安装缺失的 openai 依赖
    import subprocess

    subprocess.check_call(["pip", "install", "openai"])
    from openai import OpenAI


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def esearch_pubmed(base_query: str, retmax: int = 300) -> list[str]:
    """使用 PubMed E-utilities esearch 获取最近文献的 PMID 列表。"""

    # 构造带时间限制的查询：base_query AND last 30 days
    term = f"({base_query}) AND (\"last 30 days\"[dp])"

    params = {
        "db": "pubmed",
        "retmode": "json",
        "sort": "pub+date",
        "retmax": str(retmax),
        "term": term,
    }
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    id_list = data.get("esearchresult", {}).get("idlist", [])
    return id_list


def efetch_pubmed(pmids: list[str]) -> list[dict]:
    """通过 efetch 获取 PMID 对应的标题、摘要、作者等信息。"""

    if not pmids:
        return []

    ids_param = ",".join(pmids)
    params = {
        "db": "pubmed",
        "retmode": "xml",
        "id": ids_param,
    }
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=60) as resp:
        xml_data = resp.read().decode("utf-8")

    root = ET.fromstring(xml_data)
    papers: list[dict] = []

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        if pmid_el is None:
            continue
        pmid = pmid_el.text.strip()

        title_el = article.find(".//ArticleTitle")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        abstract_texts = []
        for ab in article.findall(".//AbstractText"):
            if ab.text:
                abstract_texts.append(ab.text.strip())
        abstract = " ".join(abstract_texts)

        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName") or ""
            initials = author.findtext("Initials") or ""
            name = (last + " " + initials).strip()
            if name:
                authors.append(name)

        # 发布时间
        pub_date = ""
        date_el = article.find(".//PubDate")
        if date_el is not None:
            year = date_el.findtext("Year") or ""
            month = date_el.findtext("Month") or "01"
            day = date_el.findtext("Day") or "01"
            # Month 可能是英文缩写，简单映射
            month_map = {
                "Jan": "01",
                "Feb": "02",
                "Mar": "03",
                "Apr": "04",
                "May": "05",
                "Jun": "06",
                "Jul": "07",
                "Aug": "08",
                "Sep": "09",
                "Oct": "10",
                "Nov": "11",
                "Dec": "12",
            }
            month = month_map.get(month, month)
            if len(month) == 1:
                month = "0" + month
            if len(day) == 1:
                day = "0" + day
            if year:
                pub_date = f"{year}-{month}-{day}"

        paper = {
            "id": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": pub_date,
            "journal": (article.findtext(".//Journal/Title") or "").strip(),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
        papers.append(paper)

    return papers


def filter_recent(papers: list[dict], days: int = 30) -> list[dict]:
    now = datetime.utcnow()
    threshold = now - timedelta(days=days)

    filtered: list[dict] = []
    for p in papers:
        pub_str = p.get("published")
        try:
            pub_dt = datetime.strptime(pub_str, "%Y-%m-%d")
        except Exception:
            continue
        if pub_dt < threshold:
            continue
        filtered.append(p)

    filtered.sort(key=lambda x: x.get("published", ""), reverse=True)
    return filtered


def load_seen_ids() -> set[str]:
    path = Path(__file__).parent.parent / "data" / "seen_ids.json"
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception:
        return set()
    return set()


def save_seen_ids(seen: set[str]) -> None:
    path = Path(__file__).parent.parent / "data" / "seen_ids.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def select_unseen(papers: list[dict], seen: set[str], limit: int) -> tuple[list[dict], set[str]]:
    selected: list[dict] = []
    new_seen: set[str] = set()
    for p in papers:
        pid = p.get("id")
        if not pid or pid in seen:
            continue
        selected.append(p)
        new_seen.add(pid)
        if len(selected) >= limit:
            break
    return selected, new_seen


def load_scores() -> dict[str, int]:
    path = Path(__file__).parent.parent / "data" / "scores.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def save_scores(scores: dict[str, int]) -> None:
    path = Path(__file__).parent.parent / "data" / "scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


RANK_PROMPT_TEMPLATE = """你是一个论文筛选与打分助手，请判断一篇论文是否"高度符合"下面这位研究者的兴趣。

研究者画像：
{profile}

打分标准（0-100 分）：
- 80-100：聚焦于可编程 RNA 编辑工具 / RNA 调控系统的工程设计，例如将酶/蛋白结构域与 gRNA 结合，实现位点特异性的 RNA 修饰、切割、剪接、翻译调控、RNA 检测与追踪等；具有清晰的工具属性或平台化设计。
- 40-79：与 RNA 编辑 / RNA 调控相关，但更多是机制研究、间接相关工具，或与可编程、工程化设计的关系不够直接；仍然可能对研究者有启发。
- 0-39：与 RNA 编辑或可编程 RNA 调控关联很弱（例如纯临床描述、与 RNA 无关的分子生物学研究），或者完全不在该领域，应当给低分。

在主题相关性的基础上，如果作者列表中包含在 RNA 编辑 / RNA 工具领域有明显影响力的研究者或团队
（例如你在相关综述、经典工具论文中经常看到的名字），可以适当上调分数（例如 +5~15 分），但总分仍需控制在 0-100 范围内。

请主要依据："是否值得向一名做 programmable RNA editing / RNA 工具开发的研究生重点推荐" 来给出最终分数。

论文标题: {title}

作者列表: {authors}

论文摘要:
{abstract}

现在请**只输出一个 JSON 对象**，不要输出任何解释文字、不要使用代码块、不要添加额外内容。
JSON 格式严格如下（注意 score 必须是 0 到 100 之间的整数）：

{{
  "score": 0-100
}}
"""


def create_ds_client(config: dict):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[rank] DEEPSEEK_API_KEY not set, skip DeepSeek ranking")
        return None

    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def score_with_deepseek(client: OpenAI, paper: dict, config: dict):
    profile = config.get("preference", {}).get("profile") or ""
    authors_str = ", ".join(paper.get("authors", []))
    prompt = RANK_PROMPT_TEMPLATE.format(
        profile=profile,
        title=paper.get("title", ""),
        authors=authors_str,
        abstract=paper.get("abstract", ""),
    )

    ds_cfg = config.get("deepseek", {})
    try:
        resp = client.chat.completions.create(
            model=ds_cfg.get("model", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()

        # 处理可能的代码块包裹和多余说明文本，只保留第一个 JSON 对象
        if content.startswith("```"):
            parts = content.split("```", 2)
            if len(parts) >= 2:
                content = parts[1]
            content = content.lstrip()
            if content.lower().startswith("json"):
                content = content.split("\n", 1)[1] if "\n" in content else ""

        # 抽取第一个 {...} 作为 JSON
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start : end + 1]
        else:
            json_str = content

        data = json.loads(json_str)
        score = int(data.get("score", 0))
        score = max(0, min(100, score))
        return score
    except Exception as e:
        print(f"[rank] DeepSeek scoring failed for PMID {paper.get('id')}: {e}")
        return None


def save_papers(papers: list[dict], date_str: str):
    data_dir = Path(__file__).parent.parent / "data" / "papers"
    data_dir.mkdir(parents=True, exist_ok=True)

    out_path = data_dir / f"{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(papers)} papers to {out_path}")
    return out_path


def main():
    config = load_config()
    pm_conf = config.get("pubmed", {})

    base_query = pm_conf.get("base_query", "RNA editing")
    retmax = pm_conf.get("retmax", 300)

    print(f"[pubmed] Searching with base_query: {base_query}")
    pmids = esearch_pubmed(base_query, retmax=retmax)
    print(f"[pubmed] Got {len(pmids)} PMIDs from esearch")

    papers = efetch_pubmed(pmids)
    print(f"[pubmed] Fetched {len(papers)} articles via efetch")

    recent = filter_recent(papers, days=30)
    print(f"[pubmed] {len(recent)} articles within last 30 days")

    scores = load_scores()
    seen = load_seen_ids()
    limit = config.get("max_papers_per_day", 5)

    client = create_ds_client(config)
    if client is not None:
        new_scores = 0
        for p in recent:
            pid = p.get("id")
            if not pid or pid in scores:
                continue
            s = score_with_deepseek(client, p, config)
            if s is not None:
                scores[pid] = s
                new_scores += 1
        if new_scores:
            print(f"[rank] Scored {new_scores} new papers with DeepSeek")
            save_scores(scores)
        else:
            print("[rank] No new papers to score with DeepSeek")
    else:
        print("[rank] DeepSeek client not available, using recency only")

    def paper_score(p: dict) -> float:
        pid = p.get("id")
        if pid in scores:
            return float(scores[pid])
        return 0.0

    ranked = sorted(recent, key=paper_score, reverse=True)

    today_papers, new_seen = select_unseen(ranked, seen, limit)
    print(f"[pubmed] Selected {len(today_papers)} unseen papers (limit={limit})")

    # 写入 DeepSeek 分数，方便页面展示
    for p in today_papers:
        pid = p.get("id")
        if pid in scores:
            p["score"] = scores[pid]

    today = datetime.now().strftime("%Y-%m-%d")
    save_papers(today_papers, today)

    if new_seen:
        updated_seen = seen.union(new_seen)
        save_seen_ids(updated_seen)
        print(f"[pubmed] Updated seen_ids.json with {len(new_seen)} new ids (total={len(updated_seen)})")
    else:
        print("[pubmed] No new unseen papers to add to seen_ids.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent


def run(cmd: list[str], desc: str) -> None:
    print("\n" + "=" * 60)
    print(desc)
    print("=" * 60)
    result = subprocess.run([sys.executable] + cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    run(["scripts/fetch_papers.py"], "[step 1] Fetch + rank PubMed RNA editing papers")
    run(["scripts/summarize.py"], "[step 2] Summarize selected papers with DeepSeek")
    run(["scripts/generate_pages.py"], "[step 3] Generate static HTML page")


if __name__ == "__main__":
    main()

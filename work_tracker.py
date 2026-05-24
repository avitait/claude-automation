#!/usr/bin/env python3
"""
work_tracker.py
Fetches your GitHub PRs from the past 7 days and creates a Notion page.

Usage:
    python work_tracker.py

Cron (every Friday at 6pm):
    0 18 * * 5 cd /path/to/script && python work_tracker.py
"""

import os
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta


def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        f = open(env_path, encoding="utf-8")
    except FileNotFoundError:
        return
    with f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env()

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DS_ID = os.environ["NOTION_DS_ID"]
# ──────────────────────────────────────────────────────────────────────────────

GH_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_week_bounds():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_num = today.isocalendar().week
    return monday, sunday, week_num


def categorize(title: str) -> str:
    t = title.lower()
    if t.startswith("fix") or "fix(" in t:
        return "fix"
    if t.startswith("chore") or "chore(" in t:
        return "chore"
    return "feat"


def fmt_date(d: datetime) -> str:
    return d.strftime("%d %b")


# ── GitHub ────────────────────────────────────────────────────────────────────


def _gh_search(query: str) -> list[dict]:
    resp = requests.get(
        f"https://api.github.com/search/issues?q={query}&per_page=100",
        headers=GH_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["items"]


def fetch_my_prs(since: datetime) -> list[dict]:
    since_str = since.strftime("%Y-%m-%d")
    return _gh_search(f"author:{GITHUB_USERNAME}+type:pr+created:>={since_str}")


def fetch_my_reviews(since: datetime) -> list[dict]:
    since_str = since.strftime("%Y-%m-%d")
    return _gh_search(
        f"reviewed-by:{GITHUB_USERNAME}+-author:{GITHUB_USERNAME}+type:pr+updated:>={since_str}"
    )


# ── Notion block builders ─────────────────────────────────────────────────────


def _t(content: str, bold: bool = False, italic: bool = False) -> dict:
    node: dict = {"type": "text", "text": {"content": content}}
    if bold or italic:
        node["annotations"] = {"bold": bold, "italic": italic}
    return node


def _block(kind: str, rich_text: list[dict]) -> dict:
    return {"object": "block", "type": kind, kind: {"rich_text": rich_text}}


def _pr_bullet(p: dict) -> dict:
    return _block(
        "bulleted_list_item", [_t(f"#{p['number']}", bold=True), _t(f" — {p['title']}")]
    )


# ── Summary builder ───────────────────────────────────────────────────────────


def build_summary(prs: list[dict], reviews: list[dict]) -> list[dict]:
    merged = [p for p in prs if p["pull_request"]["merged_at"]]
    open_prs = [p for p in prs if not p["pull_request"]["merged_at"]]

    by_cat: defaultdict[str, list] = defaultdict(list)
    for p in merged:
        by_cat[categorize(p["title"])].append(p)
    feats, fixes, chores = by_cat["feat"], by_cat["fix"], by_cat["chore"]

    highlight = max(merged, key=lambda p: p.get("comments", 0)) if merged else None

    blocks: list[dict] = []

    blocks.append(_block("heading_2", [_t("Résumé")]))
    blocks.append(
        _block(
            "paragraph",
            [
                _t(
                    f"{len(prs)} PRs cette semaine — {len(merged)} mergées, {len(open_prs)} ouvertes."
                )
            ],
        )
    )

    if highlight:
        blocks.append(
            _block(
                "paragraph",
                [
                    _t("Highlight : ", bold=True),
                    _t(f"#{highlight['number']}", bold=True),
                    _t(f" — {highlight['title']}"),
                ],
            )
        )

    if merged:
        blocks.append(_block("heading_2", [_t("PRs mergées ✅")]))
        if feats:
            blocks.append(_block("heading_3", [_t("Features")]))
            blocks.extend(_pr_bullet(p) for p in feats)
        if fixes:
            blocks.append(_block("heading_3", [_t("Fixes")]))
            blocks.extend(_pr_bullet(p) for p in fixes)
        if chores:
            blocks.append(_block("heading_3", [_t("Chores / Refacto")]))
            blocks.extend(_pr_bullet(p) for p in chores)

    if open_prs:
        blocks.append(_block("heading_2", [_t("PRs ouvertes 🔄")]))
        blocks.extend(_pr_bullet(p) for p in open_prs)

    if reviews:
        blocks.append(_block("heading_2", [_t(f"Reviews ({len(reviews)})")]))
        for r in reviews:
            blocks.append(
                _block(
                    "bulleted_list_item",
                    [
                        _t(f"#{r['number']}", bold=True),
                        _t(f" — {r['title']} "),
                        _t(f"par {r['user']['login']}", italic=True),
                    ],
                )
            )

    blocks.append(_block("heading_2", [_t("Stats")]))
    blocks.append(_block("bulleted_list_item", [_t(f"Total PRs : {len(prs)}")]))
    blocks.append(_block("bulleted_list_item", [_t(f"Mergées : {len(merged)}")]))
    blocks.append(_block("bulleted_list_item", [_t(f"Ouvertes : {len(open_prs)}")]))
    blocks.append(
        _block(
            "bulleted_list_item",
            [
                _t(
                    f"Features : {len(feats)} | Fixes : {len(fixes)} | Chores : {len(chores)}"
                )
            ],
        )
    )
    blocks.append(
        _block("bulleted_list_item", [_t(f"Reviews faites : {len(reviews)}")])
    )

    return blocks


# ── Notion ────────────────────────────────────────────────────────────────────


def create_notion_page(title: str, blocks: list[dict]):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DS_ID},
        "icon": {"type": "emoji", "emoji": "📋"},
        "properties": {
            "week": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": blocks,
    }
    resp = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=30)
    if not resp.ok:
        raise requests.HTTPError(
            f"Notion {resp.status_code}: {resp.text}", response=resp
        )
    return resp.json()["url"]


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    monday, sunday, week_num = get_week_bounds()

    print(
        f"📦 Fetching PRs for week {week_num} ({fmt_date(monday)} → {fmt_date(sunday)})..."
    )
    with ThreadPoolExecutor() as pool:
        prs_future = pool.submit(fetch_my_prs, monday)
        reviews_future = pool.submit(fetch_my_reviews, monday)
        prs = prs_future.result()
        reviews = reviews_future.result()
    print(f"   {len(prs)} PRs, {len(reviews)} reviews found")

    blocks = build_summary(prs, reviews)
    title = (
        f"Semaine {week_num} — {fmt_date(monday)} au {fmt_date(sunday)} {sunday.year}"
    )

    print(f"📝 Creating Notion page: {title}...")
    notion_url = create_notion_page(title, blocks)
    print(f"✅ Done! {notion_url}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
standup.py
Fetches your Linear tickets + GitHub PRs from the last 24h
and prints a ready-to-paste standup message.

Usage:
    python standup.py

Cron (every weekday at 9am):
    0 9 * * 1-5 cd /path/to/script && python standup.py | pbcopy
    (pbcopy = copies to clipboard on macOS, use xclip on Linux)
"""

import os
from datetime import datetime, timedelta, timezone

import requests

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
LINEAR_TOKEN = os.environ["LINEAR_TOKEN"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
# ──────────────────────────────────────────────────────────────────────────────

GH_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def _lookback_days() -> int:
    """Return 3 on Monday (to cover Fri→Mon), 1 otherwise."""
    return 3 if datetime.now().weekday() == 0 else 1


# ── GitHub ────────────────────────────────────────────────────────────────────


def fetch_yesterday_prs() -> dict:
    since = (datetime.now() - timedelta(days=_lookback_days())).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    merged_url = (
        f"https://api.github.com/search/issues"
        f"?q=author:{GITHUB_USERNAME}+type:pr+merged:{since}..{today}"
        f"&per_page=20"
    )
    opened_url = (
        f"https://api.github.com/search/issues"
        f"?q=author:{GITHUB_USERNAME}+type:pr+created:{since}..{today}"
        f"&per_page=20"
    )

    merged = requests.get(merged_url, headers=GH_HEADERS).json().get("items", [])
    opened = requests.get(opened_url, headers=GH_HEADERS).json().get("items", [])

    return {"merged": merged, "opened": opened}


# ── Linear ────────────────────────────────────────────────────────────────────

LINEAR_QUERY = """
query MyIssues($updatedAt: DateTimeOrDuration) {
  viewer {
    assignedIssues(
      filter: { updatedAt: { gt: $updatedAt } }
      orderBy: updatedAt
    ) {
      nodes {
        identifier
        title
        state { name type }
        updatedAt
      }
    }
  }
}
"""


def fetch_linear_issues() -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=_lookback_days())).isoformat()
    resp = requests.post(
        "https://api.linear.app/graphql",
        headers={
            "Authorization": LINEAR_TOKEN,
            "Content-Type": "application/json",
        },
        json={"query": LINEAR_QUERY, "variables": {"updatedAt": since}},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["viewer"]["assignedIssues"]["nodes"]


# ── Standup builder ───────────────────────────────────────────────────────────


def build_standup(issues: list[dict], prs: dict) -> str:
    done_issues = [
        i for i in issues if i["state"]["type"] in ("completed", "cancelled")
    ]
    in_progress = [i for i in issues if i["state"]["type"] == "started"]
    blockers = [
        i
        for i in issues
        if i["state"]["type"] == "backlog" and "block" in i["title"].lower()
    ]

    merged_prs = prs["merged"]
    opened_prs = prs["opened"]

    lines = []
    today_str = datetime.now().strftime("%A %d %b")
    lines.append(f"*Standup — {today_str}*\n")

    # ✅ Done
    period = "vendredi" if datetime.now().weekday() == 0 else "hier"
    lines.append(f"✅ *Done {period}*")
    if not done_issues and not merged_prs:
        lines.append("— rien de completé")
    for i in done_issues:
        lines.append(f"- {i['identifier']} — {i['title']}")
    for p in merged_prs:
        lines.append(f"- PR #{p['number']} mergée — {p['title']}")

    # 🔨 Doing
    lines.append("\n🔨 *En cours aujourd'hui*")
    if not in_progress and not opened_prs:
        lines.append("— à définir")
    for i in in_progress:
        lines.append(f"- {i['identifier']} — {i['title']}")
    for p in opened_prs:
        lines.append(f"- PR #{p['number']} ouverte — {p['title']}")

    # 🚧 Blockers
    if blockers:
        lines.append("\n🚧 *Blockers*")
        for i in blockers:
            lines.append(f"- {i['identifier']} — {i['title']}")

    return "\n".join(lines)


# ── Slack ─────────────────────────────────────────────────────────────────────


def post_to_slack(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        print("⚠️  SLACK_WEBHOOK_URL not set, skipping Slack post")
        return
    resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text})
    resp.raise_for_status()
    print("✅ Standup posté sur Slack !")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print("🔄 Fetching Linear issues...")
    try:
        issues = fetch_linear_issues()
        days = _lookback_days()
        print(f"   {len(issues)} issues updated in last {days * 24}h")
    except Exception as e:
        print(f"   ⚠️  Linear error: {e}")
        issues = []

    print("🔄 Fetching GitHub PRs...")
    try:
        prs = fetch_yesterday_prs()
        print(f"   {len(prs['merged'])} merged, {len(prs['opened'])} opened yesterday")
    except Exception as e:
        print(f"   ⚠️  GitHub error: {e}")
        prs = {"merged": [], "opened": []}

    standup = build_standup(issues, prs)

    print("\n" + "─" * 50)
    print(standup)
    print("─" * 50)

    post_to_slack(standup)


if __name__ == "__main__":
    main()

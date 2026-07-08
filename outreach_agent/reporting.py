"""Campaign reporting: builds a funnel summary from scored leads and posts it
to Slack (Block Kit) when SLACK_BOT_TOKEN is set; always writes a markdown
report alongside the workbook. n8n WF-3 calls this daily via
`python -m outreach_agent.cli report`.
"""
import json
import os
import urllib.request
from collections import Counter
from datetime import date

from .models import ScoredLead


def summarize(scored: list[ScoredLead]) -> dict:
    grades = Counter(s.score.grade for s in scored)
    statuses = Counter(s.status for s in scored)
    industries = Counter(s.lead.industry or "unknown" for s in scored)
    sent = sum(v for k, v in statuses.items() if k.startswith("Sent")) + statuses.get("Replied", 0)
    replied = statuses.get("Replied", 0)
    return {
        "date": date.today().isoformat(),
        "total": len(scored),
        "avg_score": round(sum(s.score.total for s in scored) / len(scored), 1) if scored else 0,
        "grades": dict(grades.most_common()),
        "statuses": dict(statuses.most_common()),
        "top_industries": dict(industries.most_common(8)),
        "in_sequence_eligible": sum(1 for s in scored if s.score.enters_sequence),
        "sent": sent,
        "replied": replied,
        "reply_rate": round(replied / sent, 3) if sent else 0.0,
        "top_leads": [
            {"name": s.lead.full_name, "title": s.lead.title,
             "company": s.lead.company, "score": s.score.total}
            for s in sorted(scored, key=lambda x: -x.score.total)[:10]
        ],
    }


def to_markdown(summary: dict) -> str:
    lines = [
        f"# Outreach Campaign Report — {summary['date']}",
        "",
        f"**Total leads:** {summary['total']}  ·  **Avg score:** {summary['avg_score']}  ·  "
        f"**Sequence-eligible (≥55):** {summary['in_sequence_eligible']}",
        "",
        "## Grades",
        "| Grade | Leads |", "|---|---|",
        *[f"| {g} | {n} |" for g, n in summary["grades"].items()],
        "",
        "## Funnel",
        "| Status | Leads |", "|---|---|",
        *[f"| {s} | {n} |" for s, n in summary["statuses"].items()],
        f"\n**Sent:** {summary['sent']}  ·  **Replied:** {summary['replied']}  ·  "
        f"**Reply rate:** {summary['reply_rate']:.1%}",
        "",
        "## Top industries",
        "| Industry | Leads |", "|---|---|",
        *[f"| {i} | {n} |" for i, n in summary["top_industries"].items()],
        "",
        "## Top 10 leads by score",
        "| Score | Name | Title | Company |", "|---|---|---|---|",
        *[f"| {t['score']} | {t['name']} | {t['title']} | {t['company']} |"
          for t in summary["top_leads"]],
    ]
    return "\n".join(lines) + "\n"


def post_to_slack(summary: dict, channel: str | None = None,
                  token: str | None = None) -> bool:
    token = token or os.environ.get("SLACK_BOT_TOKEN")
    channel = channel or os.environ.get("SLACK_REPORTS_CHANNEL", "#outreach-reports")
    if not token:
        return False
    grades = " · ".join(f"{g}: *{n}*" for g, n in summary["grades"].items())
    statuses = " · ".join(f"{s}: *{n}*" for s, n in summary["statuses"].items())
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"Outreach report — {summary['date']}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            f"*{summary['total']}* leads · avg score *{summary['avg_score']}* · "
            f"*{summary['in_sequence_eligible']}* sequence-eligible\n"
            f"{grades}\n{statuses}\n"
            f"Sent *{summary['sent']}* · Replied *{summary['replied']}* · "
            f"Reply rate *{summary['reply_rate']:.1%}*"}},
    ]
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": channel, "blocks": blocks,
                         "text": f"Outreach report {summary['date']}"}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("ok", False)

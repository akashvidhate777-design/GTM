# GTM Outreach Agent — AI on ERP for Retail Ecosystems

End-to-end outbound system: reads leads from Google Sheets, **scores each lead
against the ICP** (CEO/CFO/CTO/Founder/VP/Director/Operations), generates a
personalized **LinkedIn connection message + 2 follow-ups** and a **3-step
email sequence**, builds an Excel campaign workbook with `Lead Score` and
`Status` columns, automates sending through **self-hosted n8n** (Gmail +
Slack + HubSpot), and reports campaign performance daily.

**Start here:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system
orchestration, workflow diagram, scoring model.
API matrix: [docs/API_REQUIREMENTS.md](docs/API_REQUIREMENTS.md).
Credential wiring (Google service account, Slack, HubSpot, Anthropic):
[docs/SETUP_CREDENTIALS.md](docs/SETUP_CREDENTIALS.md).

## Repo layout

```
docs/ARCHITECTURE.md        System orchestration + workflow diagram + scoring model
docs/API_REQUIREMENTS.md    Every API: auth, scopes, endpoints, rate limits
outreach_agent/             The agent (scoring, messaging, Excel, reporting, Sheets I/O)
n8n/                        3 importable workflows (intake+scoring, sequence engine, reporting)
data/leads.csv              Lead snapshot exported from the Google Sheet (176 leads)
output/outreach_campaign.xlsx  Generated campaign workbook (scores + all 6 messages + status)
docker-compose.yml          Local-server hosting: n8n + agent containers
gtm_agent.py                (v1) simple Sheets -> Claude -> Gmail sender, kept for reference
```

## Quick start (local, no credentials needed)

```bash
pip install -r requirements.txt
python -m outreach_agent.cli run --input data/leads.csv --out output/outreach_campaign.xlsx
```

This scores all leads, generates every message with the offline template
engine, and writes:

- `output/outreach_campaign.xlsx` — **Leads & Sequences** (sorted by score,
  Status dropdown: Draft/Approved/Sent-Step 1-3/Replied/Bounced/Do Not Contact),
  **Campaign Report** (live COUNTIF funnel), **Config** (weights & cadence)
- `output/outreach_campaign.csv` — same data, n8n/HubSpot-friendly
- `output/campaign_report.md` — snapshot report

### Claude-written copy (recommended for production)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m outreach_agent.cli run --use-claude
```

### Google Sheets in/out

```bash
# service account (headless server) — share the sheet with the SA email
export GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/service-account.json
python -m outreach_agent.cli run --sheet-id $GOOGLE_SHEET_ID --push-sheet
```

`--push-sheet` writes the added columns (Lead Score, Lead Grade, ICP Tier,
Persona, News Signal, 3 LinkedIn messages, 3 email subjects+bodies, Status)
back to the sheet starting at column O.

### Campaign report to Slack

```bash
export SLACK_BOT_TOKEN=xoxb-...
python -m outreach_agent.cli report --input data/leads.csv --slack
```

## Hosting on your local server

```bash
cp .env.example .env   # fill in tokens
docker compose up -d   # n8n at http://localhost:5678 + agent container
```

Then in n8n: **Workflows → Import from file** for each JSON in `n8n/`, attach
credentials (Google Sheets, Gmail, Slack, HubSpot, Anthropic header auth), and
activate:

| Workflow | Trigger | What it does |
|---|---|---|
| WF-1 Lead Intake & Scoring | every 6 h + webhook | scores new rows via Claude (with web-search news signal), writes messages back, posts Slack approval |
| WF-2 Sequence Engine | weekdays 09:30 | Day 0/3/7 cadence: sends email steps via Gmail, DMs you each LinkedIn message to send (no ToS-violating automation), updates Status, syncs HubSpot |
| WF-3 Campaign Reporting | daily 18:00 | Slack funnel report + HubSpot snapshot note |

## Safety rails

- Nothing sends until Status = **Approved** (Slack approval or sheet edit)
- Stops on Replied / Bounced / Do Not Contact; opt-out line in email 3
- Daily send cap (default 30) protects deliverability
- LinkedIn messages are prepared, never auto-sent

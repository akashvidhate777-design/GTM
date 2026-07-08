# API Requirements

Full matrix of every external API the outreach system touches, what it is used
for, credentials, scopes, key endpoints, and practical rate limits.

All secrets are provided through environment variables (see `.env.example`).
None are ever written to the repo, the sheet, or n8n workflow JSON.

---

## 1. Anthropic (Claude) — scoring rationale, message generation, news enrichment

| Item | Value |
|---|---|
| Auth | `ANTHROPIC_API_KEY` (header `x-api-key`) |
| Endpoint | `POST https://api.anthropic.com/v1/messages` |
| Models | `claude-sonnet-5` for message generation, `claude-haiku-4-5` for cheap bulk classification |
| Tools used | Structured output via forced tool call (`generate_outreach`), `web_search` server tool for "latest news" enrichment |
| Rate limits | Tier-based; batch leads sequentially, ~50 req/min is safe. Use the Message Batches API for >500 leads |
| Cost control | Offline template engine is the default; `--use-claude` opt-in per run |

Request skeleton used by the agent and by n8n WF-1 (HTTP Request node):

```json
{
  "model": "claude-sonnet-5",
  "max_tokens": 2048,
  "tools": [{ "name": "generate_outreach", "input_schema": { "...": "see outreach_agent/messaging.py" } }],
  "tool_choice": { "type": "tool", "name": "generate_outreach" },
  "messages": [{ "role": "user", "content": "<lead context + offering + persona rules>" }]
}
```

## 2. Google Sheets API v4 — lead source & system of record

| Item | Value |
|---|---|
| Auth (interactive) | OAuth2 Desktop-app client (`credentials.json` → cached token) |
| Auth (local server / n8n) | **Service account** JSON key; share the sheet with the service-account email as Editor |
| Scope | `https://www.googleapis.com/auth/spreadsheets` |
| Endpoints | `spreadsheets.values.get` (read `Leads!A:N`), `spreadsheets.values.update` / `batchUpdate` (write score, messages, status columns O:AF) |
| Rate limits | 300 read + 300 write req/min/project — batch writes per run, never per cell |
| Sheet ID | `1bk7SBnxjX444jIhsg1-uI8Oe-SrPy2T1IDHtge0Fy50` (gid `831505807`) |

## 3. Gmail API — email sequence sending + reply/bounce detection

| Item | Value |
|---|---|
| Auth | Same Google OAuth client / service account with domain-wide delegation, or n8n Gmail OAuth2 credential |
| Scopes | `gmail.send` (send steps), `gmail.readonly` (reply & bounce detection in WF-2) |
| Endpoints | `users.messages.send`, `users.messages.list?q=from:<lead> newer_than:7d` |
| Limits | Consumer Gmail ≈ 500 recipients/day, Workspace 2,000/day. Agent enforces `DAILY_SEND_CAP=30` for cold outreach deliverability |
| Alt | Any SMTP server via n8n Email node if you outgrow Gmail |

## 4. Slack Web API — approvals, LinkedIn send-assist, reporting

| Item | Value |
|---|---|
| Auth | Bot token `SLACK_BOT_TOKEN` (`xoxb-…`) |
| Bot scopes | `chat:write`, `chat:write.public`, `channels:read`, `users:read` |
| Endpoints | `chat.postMessage` (Block Kit approval buttons + reports), interactivity request URL → n8n webhook `POST /webhook/slack-approval` |
| Channels | `#outreach-approvals`, `#outreach-reports` (configurable via env) |
| Rate limits | ~1 msg/sec/channel — fine at this volume |

## 5. HubSpot CRM v3 — contact sync & campaign log

| Item | Value |
|---|---|
| Auth | Private App token `HUBSPOT_ACCESS_TOKEN` (`pat-…`) |
| Scopes | `crm.objects.contacts.read/write`, `crm.objects.notes.write` (engagements) |
| Endpoints | `POST /crm/v3/objects/contacts` (upsert by email via `idProperty=email`), `POST /crm/v3/objects/notes` + association to contact, `PATCH` lifecycle stage |
| Custom properties to create once | `lead_score` (number), `lead_grade` (enum A–D), `outreach_status`, `sequence_step` |
| Rate limits | 100 req/10s (private app) — batch endpoints (`/batch/upsert`) used in WF-2 |

## 6. n8n (self-hosted) — orchestration layer

| Item | Value |
|---|---|
| Hosting | Docker `n8nio/n8n` on your local server, port 5678 (see `docker-compose.yml`) |
| Auth | `N8N_BASIC_AUTH_USER/PASSWORD` for UI; `N8N_API_KEY` for REST; webhook URLs unguessable path tokens |
| Webhooks | `POST /webhook/lead-intake` (manual trigger), `POST /webhook/slack-approval` (Slack interactivity) |
| Credentials stored in n8n | Google Sheets OAuth2/service account, Gmail OAuth2, Slack API, HubSpot API, Anthropic (header auth generic credential) |

## 7. News enrichment ("latest news" signal)

Primary: **Claude `web_search` server tool** inside the Anthropic call — no extra
API key, one bill. The agent asks: *"Any news in the last 90 days about
<Company> (expansion, digital transformation, ERP/tech investment, funding)?"*
and maps the answer to a 0–5 score bonus + one-line `News Signal` column.

Optional fallback: NewsAPI.org (`NEWSAPI_KEY`, free tier 100 req/day) via n8n
HTTP node if you want news polling decoupled from Claude.

## 8. LinkedIn — deliberate non-API

LinkedIn's official API does **not** permit automated messaging/connection
requests for this use case, and unofficial automation risks account bans.
Design decision: the system **generates** LinkedIn messages and delivers them
to Slack with the profile link for one-click manual sending, then you (or WF-2
via the Slack action) mark the step done. Zero ToS risk, same personalization.

---

## Environment variables (`.env.example`)

```bash
ANTHROPIC_API_KEY=
GOOGLE_SHEET_ID=1bk7SBnxjX444jIhsg1-uI8Oe-SrPy2T1IDHtge0Fy50
GOOGLE_SERVICE_ACCOUNT_JSON=/secrets/service-account.json
SLACK_BOT_TOKEN=
SLACK_APPROVALS_CHANNEL=#outreach-approvals
SLACK_REPORTS_CHANNEL=#outreach-reports
HUBSPOT_ACCESS_TOKEN=
SENDER_NAME=
SENDER_EMAIL=
CALENDLY_URL=
DAILY_SEND_CAP=30
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=
GENERIC_TIMEZONE=Asia/Kolkata
```

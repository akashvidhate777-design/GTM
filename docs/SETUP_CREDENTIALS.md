# Credential Wiring Guide — n8n on your local server

Step-by-step for the three integrations: **Google service account**, **Slack**,
**HubSpot**. Do these once; everything lands in `.env` + n8n's credential store.

Already done for you (via this session):
- ✅ Slack channels created: **#outreach-approvals** (`C0BFZ8C5LN9`) and
  **#outreach-reports** (`C0BG68ZVDL4`)
- ✅ HubSpot account verified (contact read/write available). The four custom
  properties do **not** exist yet — step 3c creates them.

---

## 1. Google service account (Sheets access for n8n + the agent)

A service account is the right auth for a headless local server — no browser
OAuth dance, no token expiry.

1. Go to https://console.cloud.google.com/ → select (or create) your project.
2. **APIs & Services → Library** → enable **Google Sheets API**.
3. **IAM & Admin → Service Accounts → Create service account**
   - Name: `outreach-agent` → Create → skip the optional role screens → Done.
4. Open the new service account → **Keys → Add key → Create new key → JSON**.
   Save the downloaded file as `secrets/service-account.json` in this repo
   (`secrets/` is gitignored).
5. **Share the Google Sheet with the service account**: open the sheet →
   Share → paste the service-account email (looks like
   `outreach-agent@<project>.iam.gserviceaccount.com`) → role **Editor**.
6. In n8n (`http://localhost:5678`): **Credentials → Add credential →
   Google Service Account API**
   - Service Account Email: from the JSON (`client_email`)
   - Private Key: from the JSON (`private_key`, paste the whole
     `-----BEGIN PRIVATE KEY-----...` block)
   - Enable **"Impersonate a user"**: leave off.
7. Open each imported workflow → every **Google Sheets** node → Credential →
   pick the service-account credential. In the node's *Authentication*
   dropdown choose **Service Account** where offered.

> **Gmail caveat**: the Gmail node cannot use a plain service account unless
> you're on Google Workspace with domain-wide delegation. For a personal
> Gmail, create an **OAuth2** credential for the Gmail node instead:
> APIs & Services → Credentials → OAuth client ID → Web application →
> authorized redirect URI `http://localhost:5678/rest/oauth2-credential/callback`
> → paste client ID/secret into n8n's **Gmail OAuth2** credential and click
> *Connect*.

## 2. Slack (approvals, LinkedIn send-assist, reports)

Channels already exist — you just need a bot token:

1. https://api.slack.com/apps → **Create New App → From scratch** →
   name `outreach-agent`, pick your workspace.
2. **OAuth & Permissions → Bot Token Scopes**: add
   `chat:write`, `chat:write.public`, `channels:read`.
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-…`).
4. In Slack, invite the bot to both channels:
   `/invite @outreach-agent` in **#outreach-approvals** and **#outreach-reports**.
5. `.env`: set `SLACK_BOT_TOKEN=xoxb-…` (used by the agent's `--slack` reporting).
6. In n8n: **Credentials → Add credential → Slack API** → paste the same
   token → attach it to every Slack node in WF-1/2/3.

Channel env vars are already defaulted in `.env.example`
(`#outreach-approvals` / `#outreach-reports`) — keep the names or switch to
IDs `C0BFZ8C5LN9` / `C0BG68ZVDL4` if you rename the channels later.

## 3. HubSpot (contact sync + campaign notes)

1. HubSpot → **Settings (gear) → Integrations → Private Apps → Create a
   private app** → name `outreach-agent`.
2. **Scopes** tab, add:
   - `crm.objects.contacts.read` + `crm.objects.contacts.write`
   - `crm.schemas.contacts.write` (needed once, for step 3c)
   - `crm.objects.notes.write` (reporting snapshot notes)
3. Create app → copy the token (`pat-…`) → `.env`: `HUBSPOT_ACCESS_TOKEN=pat-…`

   a. In n8n: **Credentials → Add credential → HubSpot App Token** → paste →
      attach to the *HubSpot: upsert contact* node in WF-2.
   b. Also create a **Header Auth** generic credential (name
      `HubSpot Bearer token`, header `Authorization`, value `Bearer pat-…`) →
      attach to the *HubSpot: log campaign snapshot* HTTP node in WF-3.
   c. Create the custom contact properties (one-time, idempotent):

      ```bash
      export HUBSPOT_ACCESS_TOKEN=pat-...
      python scripts/hubspot_bootstrap.py
      # created: lead_score, lead_grade, outreach_status, sequence_step
      ```

## 4. Anthropic (WF-1 scoring + copy)

n8n: **Credentials → Add credential → Header Auth** — name
`Anthropic x-api-key`, header name `x-api-key`, value your `sk-ant-…` key →
attach to the *Claude: news + score + sequence* HTTP node in WF-1.

## 5. Bring it up

```bash
cp .env.example .env    # fill in everything above
docker compose up -d
# n8n → import n8n/*.json → attach credentials per node → toggle Active
```

Smoke test order:
1. WF-1: run manually once → sheet gets score/message columns → approval post
   appears in #outreach-approvals.
2. Flip one lead's Status to `Approved` → run WF-2 manually → email sends to
   that lead, LinkedIn assist appears in Slack, HubSpot contact is upserted.
3. Run WF-3 manually → report lands in #outreach-reports.

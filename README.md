# GTM Outbound Agent

Reads contacts from a Google Sheet, analyzes each contact's persona from their
title/company, drafts a personalized cold email with Claude, sends it via
Gmail, and logs a "Sent <timestamp>" status back to the sheet.

## Sheet format

| Name | Company | Title | LinkedIn URL | Email | Status |
|------|---------|-------|--------------|-------|--------|

`Status` is created automatically if missing. Rows already marked `Sent ...`
are skipped on re-runs.

## Setup

1. **Google Cloud OAuth credentials** (used by both Sheets and Gmail):
   - Go to https://console.cloud.google.com/ → create/select a project.
   - Enable the **Google Sheets API** and **Gmail API** (APIs & Services → Library).
   - APIs & Services → Credentials → Create Credentials → OAuth client ID →
     Application type **Desktop app**.
   - Download the JSON, save it as `~/.gtm-agent/credentials.json`
     (or pass `--credentials /path/to/file.json`).
   - On first run, a browser window opens for you to grant access; the
     resulting token is cached at `~/.gtm-agent/google-token.json`.
   - If your Google Cloud OAuth consent screen is in "Testing" mode, add your
     Gmail address as a test user under OAuth consent screen → Test users.

2. **Anthropic API key**:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
# Preview drafted emails without sending
python gtm_agent.py --sheet-id <YOUR_SHEET_ID> --dry-run

# Send for real
python gtm_agent.py --sheet-id <YOUR_SHEET_ID>

# Limit to first N unprocessed contacts
python gtm_agent.py --sheet-id <YOUR_SHEET_ID> --limit 5
```

The Sheet ID is the long string in the sheet's URL:
`https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.

## SEO / AEO / GEO analysis agent

`seo_aeo_geo_agent.py` fetches a target website or product page plus one or
more competitor URLs, extracts on-page ranking signals by scraping
(`requests` + `BeautifulSoup`, no API keys needed for this part), and scores
each site across three lenses:

- **SEO** — classic search: title/meta tags, canonical, HTTPS, mobile
  viewport, image alt coverage, Open Graph tags, structured data, sitemap,
  content length.
- **AEO** (Answer Engine Optimization) — featured snippets / voice search:
  `FAQPage`/`HowTo` schema, question-formatted headings, concise
  direct-answer paragraphs, lists, comparison tables.
- **GEO** (Generative Engine Optimization) — AI answers (ChatGPT,
  Perplexity, Google AI Overviews, Claude): `llms.txt`, AI-crawler access in
  `robots.txt` (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, ...),
  entity structured data, author/E-E-A-T signals, freshness, quotable
  statistics/definitions, comparison content.

It then builds a **gap report**: every parameter the target fails that at
least one competitor passes, prioritized by weight. If `ANTHROPIC_API_KEY`
is set, Claude synthesizes an executive summary, quick wins, and a
prioritized, effort-tagged recommendation list on top of the scored data.

```bash
python seo_aeo_geo_agent.py \
  --url https://yoursite.com/product \
  --competitors https://competitor-a.com/product https://competitor-b.com/product

# Skip the Claude synthesis step and just get the scored comparison tables
python seo_aeo_geo_agent.py --url https://yoursite.com --no-llm
```

Output is a Markdown gap report at `reports/<your-domain>-gap-report.md`
(override with `--output`) containing the score summary, prioritized
parameter gaps, and the full signal-by-signal breakdown vs. every
competitor.

## MCP servers (for interactive use inside Claude Code)

`.claude/settings.json` registers two MCP servers so you can read sheets /
send mail directly from a Claude Code session, separate from the standalone
script above (a Python script can't call IDE-level MCP tools, so
`gtm_agent.py` talks to the Google APIs directly instead):

- `google-sheets` (`mcp-google-sheets`)
- `gmail` (`@gongrzhe/server-gmail-autoauth-mcp`)

Both reuse `~/.gtm-agent/credentials.json` for OAuth. The first time either
server starts inside Claude Code, it will run its own OAuth flow and cache a
token under `~/.gtm-agent/`.

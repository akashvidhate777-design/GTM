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

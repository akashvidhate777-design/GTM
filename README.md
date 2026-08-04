# Alepo Outbound Email Agent

Modular pipeline that reads telecom CSP leads from Google Sheets, drafts
personalized Alepo Digital BSS pitches with OpenAI `gpt-4o`, sends them via
Gmail, and writes `Email Body` + `Outreach Status` back to the sheet
line-by-line.

## Sheet format

| First Name | Company Name | Country | Services | LinkedIn Profile | Email | Email Body | Outreach Status |
|------------|--------------|---------|----------|------------------|-------|------------|-----------------|

Rows with a blank `Outreach Status` are processed. After each attempt the
agent writes `Sent`, `Failed`, or (in dry-run) `Drafted`.

Default spreadsheet:
`https://docs.google.com/spreadsheets/d/1pDcQrVToC-bsnCjR_X5FpaiP3bKO0Ka-zy9B2V3fOFU`

## Project layout

```
src/
  config/
    settings.py          # dotenv, paths, sheet defaults
    credentials.json     # Google OAuth Desktop client (you add this)
    token.json           # created on first auth (gitignored)
  services/
    sheets_worker.py     # gspread fetch + status updates
    gmail_worker.py      # OAuth + Gmail send
  agents/
    copywriter.py        # gpt-4o personalized pitch
  main.py                # orchestration loop
.cursorrules             # Alepo business + copy rules for Cursor
.env                     # OPENAI_API_KEY (gitignored)
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Cloud credentials

1. Create a Google Cloud project (e.g. `Alepo-Outbound-Agent`).
2. Enable **Google Sheets API** and **Gmail API**.
3. Configure the **OAuth consent screen** (External):
   - Add scopes: `.../auth/gmail.send` and `.../auth/spreadsheets`
   - Add your sending Gmail as a **Test user**
4. Create **OAuth client ID** → Application type **Desktop App**.
5. Download the JSON, rename to `credentials.json`, place at:
   `src/config/credentials.json`

Share the Google Sheet with the same Google account you authorize.

### 3. Environment variables

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

## Usage

```bash
# First run opens a browser for Google OAuth, then caches token.json
python src/main.py

# Preview pitches without sending (writes Outreach Status = Drafted)
python src/main.py --dry-run --no-delay

# Limit volume / override sheet
python src/main.py --limit 3 --sheet-id 1pDcQrVToC-bsnCjR_X5FpaiP3bKO0Ka-zy9B2V3fOFU
```

Between leads the agent sleeps a random **30–90 seconds** (override with
`--min-delay` / `--max-delay`, or skip with `--no-delay`).

## Copy structure (from `.cursorrules`)

1. Greeting: `Hi [First Name],`
2. Local research on the operator’s market / services in-country
3. Fit to Alepo Digital BSS — Omnichannel Customer Engagement
4. Carrier-grade hook + CTA for a live / discovery demo

## Legacy

`gtm_agent.py` is the earlier single-file Claude + Sheets/Gmail agent kept for
reference. Prefer `src/main.py` for the Alepo campaign.

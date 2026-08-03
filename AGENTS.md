# AGENTS.md

## Cursor Cloud specific instructions

### What this is
Single-file Python CLI (`gtm_agent.py`): a GTM outbound agent that reads contacts
from a Google Sheet, drafts persona-based cold emails with the Anthropic SDK,
sends them via Gmail, and writes a `Sent <timestamp>` status back to the sheet.
There is no server or web UI — everything runs from the command line. See
`README.md` for usage and the Google Cloud OAuth setup steps.

### Environment
- Python 3.12. Dependencies are installed into a virtualenv at `.venv/` by the
  startup update script. Activate it with `. .venv/bin/activate` before running
  anything. (Ubuntu's system pip is PEP-668 externally-managed, so a venv is
  required rather than a bare `pip install`.)

### Lint / build / run
- No linter is configured in the repo. Use `python -m py_compile gtm_agent.py`
  as the syntax/build check.
- Run: `python gtm_agent.py --help` (offline). A real run needs the secrets below:
  `python gtm_agent.py --sheet-id <SHEET_ID> --dry-run` (dry-run still calls the
  Anthropic API and reads the sheet; it only skips the Gmail send + status write).

### Secrets / external setup required for a real end-to-end run
These are NOT in the environment by default and cannot be self-provisioned:
- `ANTHROPIC_API_KEY` — required; the script exits immediately if unset.
- Google OAuth desktop client `credentials.json` at `~/.gtm-agent/` (Sheets +
  Gmail APIs enabled). First run opens an interactive browser OAuth flow and
  caches a token at `~/.gtm-agent/google-token.json`. This interactive flow does
  not work headless — it needs the Desktop pane / a real browser.
- A Google Sheet ID with columns `Name | Company | Title | LinkedIn URL | Email`
  (a `Status` column is auto-created if missing).

### Testing without live secrets
The pure/offline logic (`is_valid_email`, `read_sheet_rows`, `write_status`,
`send_gmail` MIME construction) can be exercised with a fake in-memory Sheets/
Gmail service — no network needed. The Anthropic drafting (`analyze_and_draft`)
and the Google API network calls cannot be exercised without the secrets above.

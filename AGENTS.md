# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
Single-file Python CLI (`gtm_agent.py`): reads contacts from a Google Sheet,
drafts a persona-based cold email with the Anthropic API, sends it via Gmail,
and writes a `Sent <timestamp>` status back to the sheet. See `README.md` for
the sheet format and the standard setup/usage commands.

### Runtime / dependencies
- Python 3.12 (system `python3`). There is no service to keep running; this is a
  run-on-demand CLI.
- Dependencies are installed at user level via `pip install -r requirements.txt`
  (the startup update script already does this). A virtualenv is NOT used here:
  `python3 -m venv` fails because `python3.12-venv` has no apt install candidate
  in this image, so `pip` falls back to a `--user` install into
  `~/.local`. Just run `python3 gtm_agent.py ...` directly.
- `pip` user scripts land in `~/.local/bin`, which is not on `PATH`; this is
  harmless for this project (no console-script entry points are needed).

### Running it
- Syntax check (closest thing to a linter — no flake8/ruff/pylint configured):
  `python3 -m py_compile gtm_agent.py`.
- There is no automated test suite in the repo.
- Real run requires: `ANTHROPIC_API_KEY` env var AND Google OAuth
  `credentials.json` (Desktop-app client) at `~/.gtm-agent/credentials.json`,
  plus a Google Sheet ID. Example:
  `ANTHROPIC_API_KEY=sk-ant-... python3 gtm_agent.py --sheet-id <ID> --dry-run`.

### Non-obvious gotchas for end-to-end runs
- Google auth uses an INTERACTIVE OAuth flow (`InstalledAppFlow.run_local_server`)
  that opens a browser on first run. This cannot complete headlessly — a human
  must complete consent once so the token caches to `~/.gtm-agent/google-token.json`.
- `--dry-run` still calls the Anthropic API (it drafts emails, just doesn't send
  or write status), so it requires a valid `ANTHROPIC_API_KEY`. Only the Gmail
  send and the sheet status write are skipped in dry-run.
- To exercise the full orchestration WITHOUT external services, drive `main()`
  with the Google `build`/`get_google_credentials` and `anthropic.Anthropic`
  boundaries stubbed (the internal parsing, loop, dry-run rendering, and
  skip/validation logic are all real).

---
name: run-gtm
description: Build, run, and drive the GTM outbound agent CLI (gtm_agent.py). Use when asked to run gtm_agent.py, start the GTM agent, smoke-test it, do a dry-run, or verify a change to the email-drafting pipeline works.
---

`gtm_agent.py` is a single-file Python CLI: it reads contacts from a Google
Sheet, drafts cold emails with the Anthropic API, and sends them via Gmail.
Drive it with the smoke driver `.claude/skills/run-gtm/smoke.py`, which
exercises the real CLI surface and then runs the full pipeline in-process
with the Google/Anthropic boundaries stubbed — no credentials needed.

All paths are relative to the repo root.

## Prerequisites

Python 3.11 is preinstalled in the container. No apt packages needed.

```bash
pip install -r requirements.txt
pip install cffi   # see Gotchas — the container's system cryptography is broken without it
```

## Run (agent path)

```bash
python .claude/skills/run-gtm/smoke.py
```

Expected output: 5 `PASS` lines ending in
`SMOKE OK: CLI surface + offline end-to-end dry-run all passed`, exit 0.

What it covers:

| check | layer |
|---|---|
| `--help` exits 0 with usage | CLI entrypoint / imports |
| missing `--sheet-id` exits 2 | argparse validation |
| missing `ANTHROPIC_API_KEY` exits 1 with error log | env guard in `main()` |
| offline `--dry-run` prints a drafted email | `read_sheet_rows` → `analyze_and_draft` → dry-run printer, end-to-end with fake Sheets/Anthropic |
| Sent-status and invalid-email rows skipped | row-filtering logic |

The offline run monkeypatches `gtm_agent.get_google_credentials`,
`gtm_agent.build`, and `gtm_agent.anthropic` before calling
`gtm_agent.main()`. If a PR touches the drafting prompt, sheet parsing, or
the processing loop, this driver executes that code; only the literal
Google/Anthropic HTTP calls are stubbed.

## Direct invocation

For a PR touching one internal function, import it directly — the module
has no import-time side effects beyond logging config:

```bash
python -c "import gtm_agent; print(gtm_agent.is_valid_email('a@b.co'))"
```

## Run (human path — real credentials)

Requires `~/.gtm-agent/credentials.json` (Google OAuth client, Desktop app
type) and a real `ANTHROPIC_API_KEY`. The OAuth flow opens a browser
(`flow.run_local_server`), so this is **impossible headless** — it's for a
real machine only:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python gtm_agent.py --sheet-id <SHEET_ID> --dry-run   # preview, no sends
python gtm_agent.py --sheet-id <SHEET_ID>             # sends via Gmail
```

## Test

There is no test suite in this repo. The smoke driver above is the
verification path.

## Gotchas

- **The container's Debian `cryptography` package is broken** — importing
  `google.auth` crashes with `ModuleNotFoundError: No module named
  '_cffi_backend'` followed by a pyo3 `PanicException`. `pip install cffi`
  fixes it (the pip-installed cffi satisfies the system cryptography's rust
  bindings). Without this, even `--help` exits 1.
- **Credentialed runs cannot work in this container.** Missing
  `~/.gtm-agent/credentials.json` fails with `FileNotFoundError` inside
  `get_google_credentials`, and the OAuth flow needs an interactive
  browser. Don't chase it; use the smoke driver's stubbed path.
- **Sheet format is strict-ish**: rows missing `Name` or `Email` are
  skipped, as are rows whose `Status` starts with `Sent`. A sheet with
  different headers (e.g. the lifecycle `customers.csv` with `First_Name`)
  processes zero rows rather than erroring.

## Troubleshooting

- **`ModuleNotFoundError: No module named '_cffi_backend'` + pyo3 panic on
  any invocation**: broken system cryptography. Run `pip install cffi`.
- **`gtm_agent.py: error: the following arguments are required: --sheet-id`
  (exit 2)**: expected — `--sheet-id` has no default.
- **`[ERROR] ANTHROPIC_API_KEY environment variable is not set.` (exit 1)**:
  expected without the key; the smoke driver checks this guard on purpose.
- **`FileNotFoundError: ... /.gtm-agent/credentials.json`**: you reached the
  Google OAuth boundary without credentials — normal in the container.

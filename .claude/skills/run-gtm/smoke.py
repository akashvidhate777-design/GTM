#!/usr/bin/env python3
"""Smoke driver for gtm_agent.py.

Runs the CLI at its real surface (subprocess: help / arg validation /
env guard), then drives the full pipeline in-process with the external
boundaries (Google OAuth, Sheets API, Anthropic API) stubbed, so the
sheet-parsing -> drafting -> dry-run-print loop runs end-to-end with no
credentials. Exits 0 iff every check passes.

Usage (from repo root):
    python .claude/skills/run-gtm/smoke.py
"""
import contextlib
import io
import os
import subprocess
import sys
import types

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
AGENT = os.path.join(REPO, "gtm_agent.py")

failures = []


def check(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- CLI surface
env_no_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

r = subprocess.run([sys.executable, AGENT, "--help"], capture_output=True, text=True)
check("--help exits 0 and prints usage", r.returncode == 0 and "usage:" in r.stdout, r.stderr[-200:])

r = subprocess.run([sys.executable, AGENT], capture_output=True, text=True)
check("missing --sheet-id rejected (exit 2)", r.returncode == 2 and "--sheet-id" in r.stderr, r.stderr[-200:])

r = subprocess.run([sys.executable, AGENT, "--sheet-id", "X", "--dry-run"],
                   capture_output=True, text=True, env=env_no_key)
check("missing ANTHROPIC_API_KEY guard fires (exit 1)",
      r.returncode == 1 and "ANTHROPIC_API_KEY" in r.stderr, r.stderr[-200:])

# ------------------------------------------- offline end-to-end (stubbed I/O)
sys.path.insert(0, REPO)
import gtm_agent  # noqa: E402

FAKE_SHEET = [
    ["Name", "Company", "Title", "LinkedIn URL", "Email", "Status"],
    ["Jane Doe", "Acme Corp", "VP Sales", "https://linkedin.com/in/janedoe", "jane@acme.test", ""],
    ["Already Sent", "Old Co", "CEO", "", "old@old.test", "Sent 2026-01-01"],
    ["Bad Email", "Typo Inc", "CTO", "", "not-an-email", ""],
]

FAKE_DRAFT = {
    "seniority": "VP",
    "function": "Sales",
    "pain_points": ["pipeline visibility"],
    "subject": "Quick idea for Acme Corp's pipeline",
    "body": "Offline smoke body - under 100 words.",
}


class FakeValues:
    def get(self, spreadsheetId=None, range=None):
        return types.SimpleNamespace(execute=lambda: {"values": FAKE_SHEET})

    def update(self, **kw):
        raise AssertionError("dry-run must not write back to the sheet")


class FakeSheets:
    def spreadsheets(self):
        return types.SimpleNamespace(values=lambda: FakeValues())


class FakeMessages:
    @staticmethod
    def create(**kw):
        block = types.SimpleNamespace(type="tool_use", name="submit_persona_and_email", input=FAKE_DRAFT)
        return types.SimpleNamespace(content=[block])


gtm_agent.get_google_credentials = lambda cred_path, token_path: None
gtm_agent.build = lambda name, version, credentials=None: FakeSheets() if name == "sheets" else None
gtm_agent.anthropic = types.SimpleNamespace(Anthropic=lambda: types.SimpleNamespace(messages=FakeMessages()))

os.environ["ANTHROPIC_API_KEY"] = "offline-smoke"
sys.argv = ["gtm_agent.py", "--sheet-id", "OFFLINE", "--dry-run"]

stdout = io.StringIO()
try:
    with contextlib.redirect_stdout(stdout):
        gtm_agent.main()
    out = stdout.getvalue()
    check("offline dry-run drafts and prints the valid contact",
          FAKE_DRAFT["subject"] in out and "jane@acme.test" in out, out[-300:])
    check("offline dry-run skips Sent + invalid-email rows",
          "old@old.test" not in out and "not-an-email" not in out, out[-300:])
except Exception as e:  # noqa: BLE001
    check("offline dry-run completes without error", False, repr(e))

print("---")
if failures:
    print(f"SMOKE FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("SMOKE OK: CLI surface + offline end-to-end dry-run all passed")

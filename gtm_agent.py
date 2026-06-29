#!/usr/bin/env python3
"""GTM outbound agent: reads contacts from Google Sheets, drafts personalized
emails with the Anthropic SDK, sends them via Gmail, and logs status back.

Setup:
  1. pip install -r requirements.txt
  2. Create OAuth credentials (Desktop app) in Google Cloud Console with the
     Sheets + Gmail APIs enabled, download as credentials.json next to this
     script (or pass --credentials).
  3. export ANTHROPIC_API_KEY=...
  4. python gtm_agent.py --sheet-id <SHEET_ID> --dry-run
"""
import argparse
import base64
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText

import anthropic
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]

EXPECTED_HEADERS = ["Name", "Company", "Title", "LinkedIn URL", "Email", "Status"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("gtm_agent")

PERSONA_TOOL = {
    "name": "submit_persona_and_email",
    "description": "Submit the persona analysis and the drafted outbound email for a contact.",
    "input_schema": {
        "type": "object",
        "properties": {
            "seniority": {
                "type": "string",
                "enum": ["C-Suite", "VP", "Director", "Manager", "IC"],
            },
            "function": {
                "type": "string",
                "enum": [
                    "Sales", "Marketing", "Engineering", "Product",
                    "Finance", "HR", "Operations", "Other",
                ],
            },
            "pain_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 likely pain points inferred from role and company.",
            },
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {"type": "string", "description": "Email body, under 100 words."},
        },
        "required": ["seniority", "function", "pain_points", "subject", "body"],
    },
}

PERSONA_RULES = """\
Persona-based email angle rules:
- C-Suite/VP: lead with business outcomes, revenue/growth angle.
- Directors/Managers: lead with team efficiency, process improvement.
- ICs/Individual contributors: lead with making their job easier.
Always:
- Mention the contact's company by name.
- Vary sentence structure across contacts; never sound templated.
- Subject line references their specific role or a likely challenge.
- Opening line shows understanding of their world.
- 2-3 sentence value proposition tailored to their persona.
- End with a soft CTA (e.g. open to a 15-min call?).
- Body must be under 100 words.
"""


def get_google_credentials(credentials_path: str, token_path: str) -> Credentials:
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def read_sheet_rows(sheets_service, sheet_id: str, range_name: str = "A:F"):
    result = (
        sheets_service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=range_name)
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return [], []
    headers = values[0]
    rows = []
    for i, row in enumerate(values[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        rows.append({"row_index": i, **dict(zip(headers, padded))})
    return headers, rows


def write_status(sheets_service, sheet_id: str, headers: list, row_index: int, status: str):
    if "Status" not in headers:
        status_col = len(headers)
        headers.append("Status")
        col_letter = chr(ord("A") + status_col)
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{col_letter}1",
            valueInputOption="RAW",
            body={"values": [["Status"]]},
        ).execute()
    else:
        status_col = headers.index("Status")
    col_letter = chr(ord("A") + status_col)
    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{col_letter}{row_index}",
        valueInputOption="RAW",
        body={"values": [[status]]},
    ).execute()


def analyze_and_draft(client: anthropic.Anthropic, contact: dict) -> dict:
    name = contact.get("Name", "").strip()
    company = contact.get("Company", "").strip()
    title = contact.get("Title", "").strip()
    linkedin = contact.get("LinkedIn URL", "").strip()

    prompt = f"""Analyze this outbound sales contact and draft a personalized cold email.

Name: {name}
Company: {company}
Title/Designation: {title}
LinkedIn URL: {linkedin or "N/A"}

{PERSONA_RULES}

Call submit_persona_and_email with your analysis and the drafted email."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[PERSONA_TOOL],
        tool_choice={"type": "tool", "name": "submit_persona_and_email"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_persona_and_email":
            return block.input
    raise RuntimeError(f"Model did not return a tool call for contact {name}")


def send_gmail(gmail_service, to_addr: str, subject: str, body: str):
    message = MIMEText(body)
    message["to"] = to_addr
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()


def is_valid_email(addr: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr))


def main():
    parser = argparse.ArgumentParser(description="GTM outbound agent")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--range", default="A:F", help="Sheet range to read (default A:F)")
    parser.add_argument(
        "--credentials",
        default=os.path.expanduser("~/.gtm-agent/credentials.json"),
        help="Path to OAuth client credentials.json",
    )
    parser.add_argument(
        "--token",
        default=os.path.expanduser("~/.gtm-agent/google-token.json"),
        help="Path to store/read the OAuth token",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print emails instead of sending")
    parser.add_argument("--limit", type=int, default=None, help="Max number of contacts to process")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    creds = get_google_credentials(args.credentials, args.token)
    sheets_service = build("sheets", "v4", credentials=creds)
    gmail_service = build("gmail", "v1", credentials=creds)
    claude = anthropic.Anthropic()

    headers, rows = read_sheet_rows(sheets_service, args.sheet_id, args.range)
    if not rows:
        log.info("No contact rows found.")
        return

    log.info("Loaded %d contact rows from sheet %s", len(rows), args.sheet_id)

    processed = 0
    for contact in rows:
        if args.limit and processed >= args.limit:
            break

        name = contact.get("Name", "").strip()
        email_addr = contact.get("Email", "").strip()
        existing_status = contact.get("Status", "").strip()

        if not name or not email_addr:
            log.warning("Skipping row %d: missing Name or Email", contact["row_index"])
            continue
        if existing_status.lower().startswith("sent"):
            log.info("Skipping %s: already marked %s", name, existing_status)
            continue
        if not is_valid_email(email_addr):
            log.warning("Skipping %s: invalid email %r", name, email_addr)
            continue

        log.info("Analyzing %s (%s @ %s)", name, contact.get("Title", ""), contact.get("Company", ""))
        draft = analyze_and_draft(claude, contact)
        subject, body = draft["subject"], draft["body"]

        log.info(
            "Persona: seniority=%s function=%s pain_points=%s",
            draft["seniority"], draft["function"], draft["pain_points"],
        )

        if args.dry_run:
            print("=" * 70)
            print(f"To: {email_addr}")
            print(f"Subject: {subject}")
            print()
            print(body)
            print("=" * 70)
            log.info("[DRY RUN] Would send email to %s", email_addr)
        else:
            send_gmail(gmail_service, email_addr, subject, body)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            write_status(sheets_service, args.sheet_id, headers, contact["row_index"], f"Sent {timestamp}")
            log.info("Sent email to %s and logged status", email_addr)

        processed += 1

    log.info("Done. Processed %d contacts.", processed)


if __name__ == "__main__":
    main()

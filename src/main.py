#!/usr/bin/env python3
"""Alepo Outbound Campaign orchestrator.

Pipeline per lead:
  1. Fetch unprocessed rows from Google Sheets (blank Outreach Status)
  2. Generate personalized pitch with gpt-4o
  3. Send via Gmail API
  4. Update Email Body + Outreach Status (Sent / Failed) immediately
  5. Sleep 30–90s between actions to respect Gmail volume guidelines
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path

# Allow `python src/main.py` from the repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.copywriter import generate_personalized_pitch
from src.config.settings import (
    DEFAULT_EMAIL_SUBJECT,
    DEFAULT_SHEET_ID,
    DEFAULT_SHEET_NAME,
    MAX_DELAY_SECONDS,
    MIN_DELAY_SECONDS,
    require_openai_api_key,
    validate_google_credentials_file,
)
from src.services.gmail_worker import get_google_credentials, send_raw_email
from src.services.sheets_worker import SheetsWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("alepo.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Alepo Outbound Email Agent — Sheets → gpt-4o → Gmail",
    )
    parser.add_argument(
        "--sheet-id",
        default=DEFAULT_SHEET_ID,
        help=f"Google Spreadsheet ID (default: {DEFAULT_SHEET_ID})",
    )
    parser.add_argument(
        "--sheet-name",
        default=DEFAULT_SHEET_NAME,
        help="Worksheet/tab name (default: first sheet in the workbook)",
    )
    parser.add_argument(
        "--subject",
        default=DEFAULT_EMAIL_SUBJECT,
        help="Email subject line for all outbound messages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate copy and update the sheet with Drafted status; do not send",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N unprocessed leads",
    )
    parser.add_argument(
        "--min-delay",
        type=int,
        default=MIN_DELAY_SECONDS,
        help=f"Minimum sleep seconds between leads (default {MIN_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--max-delay",
        type=int,
        default=MAX_DELAY_SECONDS,
        help=f"Maximum sleep seconds between leads (default {MAX_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Skip inter-lead delays (useful for dry-run testing)",
    )
    return parser.parse_args()


def process_lead(
    sheets: SheetsWorker,
    sheet_id: str,
    sheet_name: str | None,
    lead: dict,
    subject: str,
    credentials,
    dry_run: bool,
) -> str:
    """Generate → send → update status. Returns final status string."""
    row_index = lead["row_index"]
    first_name = lead["First Name"]
    company = lead["Company Name"]
    country = lead["Country"]
    services = lead["Services"]
    to_email = lead["Email"]

    email_body = ""
    try:
        email_body = generate_personalized_pitch(
            first_name=first_name,
            company=company,
            country=country,
            services=services,
        )

        if dry_run:
            logger.info(
                "[DRY RUN] Would send to %s (%s @ %s)",
                to_email,
                first_name,
                company,
            )
            print("=" * 70)
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print()
            print(email_body)
            print("=" * 70)
            status = "Drafted"
        else:
            send_raw_email(
                to_email=to_email,
                subject=subject,
                body_content=email_body,
                credentials=credentials,
            )
            status = "Sent"

        sheets.update_lead_row(
            sheet_id=sheet_id,
            row_index=row_index,
            email_body=email_body,
            status=status,
            sheet_name=sheet_name,
        )
        return status

    except Exception as exc:
        logger.exception(
            "Failed processing row %d (%s <%s>): %s",
            row_index,
            first_name,
            to_email,
            exc,
        )
        try:
            sheets.update_lead_row(
                sheet_id=sheet_id,
                row_index=row_index,
                email_body=email_body or f"[generation/send error: {exc}]",
                status="Failed",
                sheet_name=sheet_name,
            )
        except Exception:
            logger.exception(
                "Could not write Failed status for row %d",
                row_index,
            )
        return "Failed"


def main() -> int:
    args = parse_args()

    logger.info("=== Alepo Outbound Email Agent starting ===")
    try:
        require_openai_api_key()
        validate_google_credentials_file()
        credentials = get_google_credentials()
    except (RuntimeError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1

    sheets = SheetsWorker(credentials)

    leads = sheets.fetch_unprocessed_leads(args.sheet_id, args.sheet_name)
    if not leads:
        logger.info("No unprocessed leads. Exiting.")
        return 0

    if args.limit is not None:
        leads = leads[: args.limit]
        logger.info("Limiting run to %d lead(s)", len(leads))

    sent = failed = drafted = 0
    for i, lead in enumerate(leads):
        logger.info(
            "── Processing %d/%d: %s <%s> @ %s (%s)",
            i + 1,
            len(leads),
            lead["First Name"],
            lead["Email"],
            lead["Company Name"],
            lead["Country"],
        )

        status = process_lead(
            sheets=sheets,
            sheet_id=args.sheet_id,
            sheet_name=args.sheet_name,
            lead=lead,
            subject=args.subject,
            credentials=credentials,
            dry_run=args.dry_run,
        )

        if status == "Sent":
            sent += 1
        elif status == "Drafted":
            drafted += 1
        else:
            failed += 1

        # Random delay between actions (skip after the last lead)
        if i < len(leads) - 1 and not args.no_delay:
            delay = random.randint(args.min_delay, args.max_delay)
            logger.info("Sleeping %d seconds before next lead…", delay)
            time.sleep(delay)

    logger.info(
        "=== Done. Sent=%d Drafted=%d Failed=%d Total=%d ===",
        sent,
        drafted,
        failed,
        len(leads),
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

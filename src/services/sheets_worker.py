"""Google Sheets worker for reading leads and writing outreach status."""

from __future__ import annotations

import logging
from typing import Any

import gspread
from google.oauth2.credentials import Credentials

from src.config.settings import GOOGLE_SCOPES

logger = logging.getLogger(__name__)

# Columns we read from / write to (per .cursorrules)
READ_COLUMNS = [
    "First Name",
    "Company Name",
    "Country",
    "Services",
    "LinkedIn Profile",
    "Email",
]
WRITE_COLUMNS = ["Email Body", "Outreach Status"]


class SheetsWorker:
    """Thin wrapper around gspread for the Alepo outbound sheet."""

    def __init__(self, credentials: Credentials):
        logger.info("Initializing Google Sheets client via gspread + OAuth")
        self.client = gspread.authorize(credentials)

    def open_sheet(self, sheet_id: str, sheet_name: str | None = None) -> gspread.Worksheet:
        """Open a worksheet by spreadsheet ID and optional tab name."""
        spreadsheet = self.client.open_by_key(sheet_id)
        if sheet_name:
            logger.info("Opened spreadsheet %s / worksheet '%s'", sheet_id, sheet_name)
            return spreadsheet.worksheet(sheet_name)
        worksheet = spreadsheet.sheet1
        logger.info(
            "Opened spreadsheet %s / first worksheet '%s'",
            sheet_id,
            worksheet.title,
        )
        return worksheet

    def _ensure_write_columns(self, worksheet: gspread.Worksheet, headers: list[str]) -> list[str]:
        """Append Email Body / Outreach Status headers if they are missing."""
        updated = list(headers)
        for col in WRITE_COLUMNS:
            if col not in updated:
                updated.append(col)
                col_index = len(updated)
                worksheet.update_cell(1, col_index, col)
                logger.info("Added missing column '%s' at index %d", col, col_index)
        return updated

    def fetch_unprocessed_leads(
        self,
        sheet_id: str,
        sheet_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Download rows where the 'Outreach Status' column is blank.

        Returns a list of dicts with lead fields plus `row_index` (1-based sheet row).
        """
        worksheet = self.open_sheet(sheet_id, sheet_name)
        all_values = worksheet.get_all_values()
        if not all_values:
            logger.warning("Sheet is empty — no leads found")
            return []

        headers = all_values[0]
        headers = self._ensure_write_columns(worksheet, headers)

        # Re-fetch if we just added headers so column indices stay correct
        all_values = worksheet.get_all_values()
        headers = all_values[0]

        status_col = headers.index("Outreach Status") if "Outreach Status" in headers else None
        unprocessed: list[dict[str, Any]] = []

        for i, row in enumerate(all_values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded))
            status = (record.get("Outreach Status") or "").strip()
            if status:
                continue

            email = (record.get("Email") or "").strip()
            first_name = (record.get("First Name") or "").strip()
            if not email or not first_name:
                logger.warning(
                    "Skipping row %d: missing First Name or Email",
                    i,
                )
                continue

            lead = {
                "row_index": i,
                "First Name": first_name,
                "Company Name": (record.get("Company Name") or "").strip(),
                "Country": (record.get("Country") or "").strip(),
                "Services": (record.get("Services") or "").strip(),
                "LinkedIn Profile": (record.get("LinkedIn Profile") or "").strip(),
                "Email": email,
            }
            unprocessed.append(lead)

        logger.info(
            "Found %d unprocessed lead(s) (Outreach Status blank)",
            len(unprocessed),
        )
        # Keep status_col available for update helpers via worksheet headers
        self._last_headers = headers
        self._last_worksheet = worksheet
        return unprocessed

    def update_lead_row(
        self,
        sheet_id: str,
        row_index: int,
        email_body: str,
        status: str,
        sheet_name: str | None = None,
    ) -> None:
        """Immediately write Email Body and Outreach Status for a single row."""
        # Prefer cached worksheet from fetch; otherwise reopen
        worksheet = getattr(self, "_last_worksheet", None)
        headers = getattr(self, "_last_headers", None)
        if worksheet is None or headers is None:
            worksheet = self.open_sheet(sheet_id, sheet_name)
            headers = worksheet.row_values(1)
            headers = self._ensure_write_columns(worksheet, headers)

        if "Email Body" not in headers or "Outreach Status" not in headers:
            headers = self._ensure_write_columns(worksheet, list(headers))

        body_col = headers.index("Email Body") + 1  # gspread is 1-based
        status_col = headers.index("Outreach Status") + 1

        # Update each write column independently (they may not be adjacent)
        worksheet.update_cell(row_index, body_col, email_body)
        worksheet.update_cell(row_index, status_col, status)
        logger.info(
            "Updated row %d → Outreach Status=%r",
            row_index,
            status,
        )


# Module-level convenience functions matching the Composer prompt API


def get_sheets_worker(credentials: Credentials) -> SheetsWorker:
    return SheetsWorker(credentials)


def fetch_unprocessed_leads(
    credentials: Credentials,
    sheet_id: str,
    sheet_name: str | None = None,
) -> list[dict[str, Any]]:
    worker = SheetsWorker(credentials)
    return worker.fetch_unprocessed_leads(sheet_id, sheet_name)


def update_lead_row(
    credentials: Credentials,
    sheet_id: str,
    row_index: int,
    email_body: str,
    status: str,
    sheet_name: str | None = None,
) -> None:
    worker = SheetsWorker(credentials)
    worker.update_lead_row(sheet_id, row_index, email_body, status, sheet_name)

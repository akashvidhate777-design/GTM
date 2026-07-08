"""Lead input/output: local CSV always works; Google Sheets read/write-back is
available when google-api-python-client is installed and credentials exist
(OAuth desktop flow for laptops, service-account JSON for the local server).
"""
import csv
import os

from .models import Lead, ScoredLead

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

WRITEBACK_HEADERS = [
    "Lead Score", "Lead Grade", "ICP Tier", "Persona", "News Signal",
    "LinkedIn Connection Message", "LinkedIn Follow-Up 1", "LinkedIn Follow-Up 2",
    "Email 1 Subject", "Email 1 Body", "Email 2 Subject", "Email 2 Body",
    "Email 3 Subject", "Email 3 Body", "Status",
]


def read_csv(path: str) -> list[Lead]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [Lead.from_row(row, row_index=i)
                for i, row in enumerate(csv.DictReader(f), start=2)]


def write_csv(scored: list[ScoredLead], path: str):
    """Flat CSV export mirroring the workbook's Leads & Sequences sheet —
    handy as an n8n-friendly interchange format."""
    from .excel_export import HEADERS  # single source of truth for layout
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for item in sorted(scored, key=lambda s: -s.score.total):
            l, s, q = item.lead, item.score, item.sequence
            w.writerow([
                l.first_name, l.last_name, l.title, l.company, l.email,
                l.employees, l.industry, l.person_linkedin, l.website,
                l.city, l.state, l.country, l.annual_revenue,
                s.total, s.grade, s.icp_tier, s.persona, s.news_signal,
                q.linkedin_connection, q.linkedin_followup_1, q.linkedin_followup_2,
                q.email_1_subject, q.email_1_body, q.email_2_subject, q.email_2_body,
                q.email_3_subject, q.email_3_body,
                item.status, 0, "", "", "",
            ])


def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if sa_path and os.path.exists(sa_path):
        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=SHEETS_SCOPES)
        return build("sheets", "v4", credentials=creds)

    # Fall back to the interactive OAuth flow used by gtm_agent.py
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred_file = os.path.expanduser("~/.gtm-agent/credentials.json")
    token_file = os.path.expanduser("~/.gtm-agent/google-token.json")
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SHEETS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_file, SHEETS_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


def read_google_sheet(sheet_id: str, tab: str | None = None) -> list[Lead]:
    service = _sheets_service()
    rng = f"'{tab}'!A:N" if tab else "A:N"
    values = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng).execute().get("values", [])
    if not values:
        return []
    headers = values[0]
    leads = []
    for i, row in enumerate(values[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        leads.append(Lead.from_row(dict(zip(headers, padded)), row_index=i))
    return leads


def write_back_google_sheet(sheet_id: str, scored: list[ScoredLead],
                            tab: str | None = None, start_col: str = "O"):
    """Appends the agent columns (score, messages, status) to the right of the
    raw lead data, starting at `start_col`, in one batch update."""
    service = _sheets_service()
    prefix = f"'{tab}'!" if tab else ""
    data = [{
        "range": f"{prefix}{start_col}1",
        "values": [WRITEBACK_HEADERS],
    }]
    for item in scored:
        l, s, q = item.lead, item.score, item.sequence
        data.append({
            "range": f"{prefix}{start_col}{l.row_index}",
            "values": [[
                s.total, s.grade, s.icp_tier, s.persona, s.news_signal,
                q.linkedin_connection, q.linkedin_followup_1, q.linkedin_followup_2,
                q.email_1_subject, q.email_1_body, q.email_2_subject, q.email_2_body,
                q.email_3_subject, q.email_3_body, item.status,
            ]],
        })
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()

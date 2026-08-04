"""Gmail worker: OAuth token handling and raw email send via Gmail API."""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config.settings import CREDENTIALS_PATH, GOOGLE_SCOPES, TOKEN_PATH

logger = logging.getLogger(__name__)


def get_google_credentials(
    credentials_path: Path | None = None,
    token_path: Path | None = None,
) -> Credentials:
    """Load or refresh OAuth credentials; trigger browser login if needed.

    Saves the authorized user token to token.json for future headless runs.
    """
    credentials_path = credentials_path or CREDENTIALS_PATH
    token_path = token_path or TOKEN_PATH

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {credentials_path}. "
            "Place your Google Cloud Desktop OAuth client JSON there."
        )

    creds: Credentials | None = None
    if token_path.exists():
        logger.info("Loading existing OAuth token from %s", token_path)
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired OAuth token")
            creds.refresh(Request())
        else:
            logger.info(
                "No valid token found — starting browser OAuth login flow "
                "(Desktop app). Approve access in the browser window."
            )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                GOOGLE_SCOPES,
            )
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Saved OAuth token to %s for headless future runs", token_path)

    return creds


def send_raw_email(
    to_email: str,
    subject: str,
    body_content: str,
    credentials: Credentials | None = None,
) -> dict:
    """Send a plain-text email via the Gmail API.

    Encodes the MIME message as base64url before calling users.messages.send.
    """
    if credentials is None:
        credentials = get_google_credentials()

    logger.info("Sending email to %s | subject=%r", to_email, subject)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    message = MIMEText(body_content, "plain", "utf-8")
    message["to"] = to_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    logger.info("Gmail send OK — message id=%s", result.get("id"))
    return result

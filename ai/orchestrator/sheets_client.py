from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = "1E8_Q4uat1TWR9_HjrNwOH-Zb3oVSoMyf_fByEorsmdE"

_DEFAULT_CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials" / "service_account.json"


def _get_client(credentials_path: Path = _DEFAULT_CREDENTIALS_PATH) -> gspread.Client:
    creds = Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(sheet_name: str, credentials_path: Path = _DEFAULT_CREDENTIALS_PATH) -> gspread.Worksheet:
    client = _get_client(credentials_path)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)


def append_row(sheet_name: str, row: list[Any]) -> None:
    sheet = get_sheet(sheet_name)
    sheet.append_row(row, value_input_option="USER_ENTERED")


def read_all_records(sheet_name: str) -> list[dict[str, Any]]:
    sheet = get_sheet(sheet_name)
    return sheet.get_all_records()

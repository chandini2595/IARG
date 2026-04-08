#!/usr/bin/env python3
"""
Obtain GOOGLE_DRIVE_REFRESH_TOKEN for the IARG Guardian Drive ACL monitor.

Prerequisites:
  - Google Cloud project with OAuth consent + Drive API enabled
  - OAuth client type "Desktop app" (or use this script's loopback flow)

Usage (from app/guardian, after pip install -r requirements.txt):

  export GOOGLE_DRIVE_CLIENT_ID="....apps.googleusercontent.com"
  export GOOGLE_DRIVE_CLIENT_SECRET="..."
  python scripts/google_drive_oauth_refresh_token.py

Then add the printed GOOGLE_DRIVE_REFRESH_TOKEN to .env and set:
  GOOGLE_DRIVE_MONITOR_ENABLED=true
  GOOGLE_DRIVE_MONITORED_IDS=your_folder_or_file_id
"""
from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main() -> None:
    client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Set GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET in the environment.", file=sys.stderr)
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    rt = creds.refresh_token
    if not rt:
        print("No refresh token returned. Try revoking app access in Google Account and retry.", file=sys.stderr)
        sys.exit(1)
    print("\nAdd these to your .env:\n")
    print(f"GOOGLE_DRIVE_REFRESH_TOKEN={rt}\n")


if __name__ == "__main__":
    main()

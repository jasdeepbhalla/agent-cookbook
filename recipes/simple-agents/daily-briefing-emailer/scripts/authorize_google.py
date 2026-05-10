"""
One-time script to authorize Google Calendar access and print the OAuth tokens
needed for Secrets Manager. Run this locally — not in Lambda.

Usage:
    pip install google-auth-oauthlib
    python scripts/authorize_google.py
"""

import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\nCopy the JSON below into AWS Secrets Manager (daily-briefing/google-calendar):\n")
print(
    json.dumps(
        {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
        },
        indent=2,
    )
)

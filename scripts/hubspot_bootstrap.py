#!/usr/bin/env python3
"""One-time HubSpot setup: creates the four custom contact properties the
sequence engine (n8n WF-2) writes to. Idempotent — existing properties are
left untouched.

Usage:
    export HUBSPOT_ACCESS_TOKEN=pat-...   # private app with crm.schemas.contacts.write
    python scripts/hubspot_bootstrap.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN")
BASE = "https://api.hubapi.com/crm/v3/properties/contacts"

PROPERTIES = [
    {
        "name": "lead_score",
        "label": "Lead Score (Outreach Agent)",
        "type": "number",
        "fieldType": "number",
        "groupName": "contactinformation",
        "description": "0-100 ICP fit score from the outreach agent (title tier, function, industry, scale, revenue, news).",
    },
    {
        "name": "lead_grade",
        "label": "Lead Grade",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "A - Hot (>=90), B - Warm (75-89), C - Nurture (55-74), D - Low (<55).",
        "options": [
            {"label": "A - Hot", "value": "A - Hot"},
            {"label": "B - Warm", "value": "B - Warm"},
            {"label": "C - Nurture", "value": "C - Nurture"},
            {"label": "D - Low", "value": "D - Low"},
        ],
    },
    {
        "name": "outreach_status",
        "label": "Outreach Status",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "description": "Mirror of the campaign sheet Status column.",
        "options": [
            {"label": s, "value": s} for s in [
                "Draft", "Approved", "Sent - Step 1", "Sent - Step 2",
                "Sent - Step 3", "Replied", "Bounced", "Do Not Contact",
            ]
        ],
    },
    {
        "name": "sequence_step",
        "label": "Sequence Step",
        "type": "number",
        "fieldType": "number",
        "groupName": "contactinformation",
        "description": "Last completed step of the 3-step LinkedIn + email cadence (0-3).",
    },
]


def request(method: str, url: str, payload: dict | None = None):
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    if not TOKEN:
        sys.exit("HUBSPOT_ACCESS_TOKEN is not set")
    for prop in PROPERTIES:
        try:
            request("GET", f"{BASE}/{prop['name']}")
            print(f"exists, skipping: {prop['name']}")
            continue
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        try:
            request("POST", BASE, prop)
            print(f"created: {prop['name']}")
        except urllib.error.HTTPError as err:
            print(f"FAILED {prop['name']}: {err.code} {err.read().decode()[:300]}")
            sys.exit(1)
    print("HubSpot bootstrap complete.")


if __name__ == "__main__":
    main()

"""Shared helpers: talk to Supabase's REST API using the service role key (server-side only)."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def _base():
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"


def _headers(prefer=None):
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def get_table(name, select="*"):
    r = requests.get(f"{_base()}/{name}", params={"select": select}, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def upsert(table, rows, conflict, batch=500):
    """Insert rows, updating any that already exist on the `conflict` columns."""
    for i in range(0, len(rows), batch):
        r = requests.post(
            f"{_base()}/{table}",
            params={"on_conflict": conflict},
            headers=_headers("resolution=merge-duplicates,return=minimal"),
            data=json.dumps(rows[i:i + batch]),
            timeout=60,
        )
        r.raise_for_status()
    print(f"Upserted {len(rows)} rows into {table}")

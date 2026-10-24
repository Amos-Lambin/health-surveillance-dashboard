"""Find out what the DHIS2 demo actually contains before writing a loader.

Set DHIS2_URL to the demo server address you use in your browser (no trailing slash),
and DHIS2_USER / DHIS2_PASSWORD to the demo login shown on play.dhis2.org.
Prints weekly datasets, matching data elements and org unit levels.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.environ["DHIS2_URL"].rstrip("/")
AUTH = (os.environ["DHIS2_USER"], os.environ["DHIS2_PASSWORD"])
KEYWORDS = ["malaria", "measles", "cholera", "typhoid"]


def get(path, **params):
    r = requests.get(f"{BASE}/api/{path}", params=params, auth=AUTH, timeout=60)
    r.raise_for_status()
    return r.json()


print("== Org unit levels ==")
for lv in get("organisationUnitLevels", fields="level,name", paging="false")["organisationUnitLevels"]:
    print(lv["level"], lv["name"])

print("\n== Data sets by period type ==")
for ds in get("dataSets", fields="id,name,periodType", paging="false")["dataSets"]:
    print(f'{ds["periodType"]:10} {ds["id"]}  {ds["name"]}')

print("\n== Data elements matching disease keywords ==")
for kw in KEYWORDS:
    found = get("dataElements", fields="id,name", filter=f"name:ilike:{kw}", paging="false")["dataElements"]
    print(f"-- {kw}: {len(found)} found")
    for de in found[:15]:
        print("  ", de["id"], de["name"])

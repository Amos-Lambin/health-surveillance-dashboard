"""Load real weekly IDSR case counts from the DHIS2 demo into weekly_cases.

Real: case counts (Malaria, Measles, Cholera, Yellow fever) by district and week.
Simulated: reports_received. The demo has 0 actual reports registered everywhere, so
completeness cannot be taken from DHIS2. reports_expected IS real (facility count).
Rows are tagged in the `source` column so this is visible and must be stated in the report.

  python load_dhis2_idsr.py --dry-run     # fetch and summarise, write idsr_snapshot.csv
  python load_dhis2_idsr.py               # upsert into Supabase
"""
import argparse
import csv
import datetime as dt
import os
import random
import re
import sys
from collections import defaultdict

import requests
from dotenv import load_dotenv

from common import get_table, upsert

load_dotenv()
BASE = os.environ["DHIS2_URL"].rstrip("/")
AUTH = (os.environ["DHIS2_USER"], os.environ["DHIS2_PASSWORD"])
DS = "Nyh6laLdBEJ"  # IDSR Weekly
ELEMENTS = {"vq2qO3eTrNi": "Malaria", "YazgqXbizv1": "Measles",
            "UsSUX0cpKsH": "Cholera", "noIzB569hTM": "Yellow fever"}
SOURCE = "dhis2-demo (completeness simulated)"


def analytics(dx, weeks=52):
    r = requests.get(f"{BASE}/api/analytics", auth=AUTH, timeout=180, params={
        "dimension": [f"dx:{';'.join(dx)}", f"pe:LAST_{weeks}_WEEKS", "ou:LEVEL-2"],
        "skipMeta": "true"})
    r.raise_for_status()
    return r.json()["rows"]


def week_start(pe):
    m = re.fullmatch(r"(\d{4})W(\d{1,2})", pe)
    if not m:
        raise ValueError(f"Unexpected period format: {pe}")
    return dt.date.fromisocalendar(int(m[1]), int(m[2]), 1)  # Monday of the ISO week


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    uid_to_id = {d["dhis2_uid"]: d["id"] for d in get_table("districts", "id,name,dhis2_uid")
                 if d.get("dhis2_uid")}
    if not uid_to_id:
        sys.exit("No districts with a dhis2_uid. Run fix_districts.sql in Supabase first.")
    name_to_id = {d["name"]: d["id"] for d in get_table("diseases", "id,name")}
    missing = [n for n in ELEMENTS.values() if n not in name_to_id]
    if missing:
        sys.exit(f"Diseases missing in database: {missing}. Run switch_to_yellow_fever.sql first.")

    expected = {}
    try:
        for _dx, pe, ou, v in analytics([f"{DS}.EXPECTED_REPORTS"]):
            expected[(pe, ou)] = float(v)
    except requests.HTTPError as e:
        print("Warning: could not fetch expected reports, using 20:", e)

    rows, unmatched = [], set()
    for dx, pe, ou, v in analytics(list(ELEMENTS)):
        if ou not in uid_to_id:
            unmatched.add(ou)
            continue
        exp = max(1, int(expected.get((pe, ou), 20)))
        recv = min(exp, max(0, round(exp * random.uniform(0.8, 1.0))))
        rows.append({
            "district_id": uid_to_id[ou], "disease_id": name_to_id[ELEMENTS[dx]],
            "week_start": week_start(pe).isoformat(), "cases": max(0, round(float(v))),
            "reports_received": recv, "reports_expected": exp, "source": SOURCE,
        })

    weeks = sorted({r["week_start"] for r in rows})
    print(f"{len(rows)} rows | weeks {weeks[0]} to {weeks[-1]} ({len(weeks)} weeks)")
    totals = defaultdict(int)
    inv = {v: k for k, v in name_to_id.items()}
    for r in rows:
        totals[inv[r["disease_id"]]] += r["cases"]
    print("Total cases per disease:", dict(totals))
    if unmatched:
        print("Skipped org units not in your districts table:", unmatched)

    if args.dry_run:
        with open("idsr_snapshot.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=rows[0].keys())
            wr.writeheader()
            wr.writerows(rows)
        print("Wrote idsr_snapshot.csv (nothing sent to Supabase)")
    else:
        upsert("weekly_cases", rows, "district_id,disease_id,week_start")


if __name__ == "__main__":
    main()

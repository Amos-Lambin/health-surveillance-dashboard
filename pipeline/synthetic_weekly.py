"""Generate synthetic weekly case counts so dashboard work is never blocked.

Counts are fabricated: seasonal malaria, low-level measles/cholera/typhoid and one
measles outbreak in the last 4 weeks (so the alert and control chart have something to find).
Rows are tagged source='synthetic'. Say so in your report.

  python synthetic_weekly.py --dry-run     # writes weekly_cases_synthetic.csv, no database
  python synthetic_weekly.py               # upserts into Supabase
"""
import argparse
import csv
import datetime as dt
import math
import random


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def poisson(lam):
    if lam > 30:  # normal approximation for large means
        return max(0, round(random.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= random.random()
        if p <= limit:
            return k
        k += 1


BASE = {"Malaria": 120, "Measles": 3, "Cholera": 1.5, "Typhoid fever": 8}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=52)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    random.seed(args.seed)

    if args.dry_run:
        districts = [{"id": i, "name": f"District {i}"} for i in range(1, 15)]
        diseases = [{"id": i, "name": n} for i, n in enumerate(BASE, 1)]
    else:
        from common import get_table
        districts = get_table("districts")
        diseases = get_table("diseases")

    last = monday(dt.date.today()) - dt.timedelta(weeks=1)  # last complete week
    size = {d["id"]: random.uniform(0.3, 2.0) for d in districts}
    expected = {d["id"]: random.randint(8, 30) for d in districts}
    outbreak_district = random.choice(districts)["id"]

    rows = []
    for w in range(args.weeks):
        week = last - dt.timedelta(weeks=args.weeks - 1 - w)
        woy = week.isocalendar()[1]
        weeks_from_end = args.weeks - 1 - w
        for d in districts:
            exp = expected[d["id"]]
            received = min(exp, max(0, round(exp * random.uniform(0.75, 1.0))))
            for ds in diseases:
                lam = BASE.get(ds["name"], 2) * size[d["id"]]
                if ds["name"] == "Malaria":
                    lam *= 1 + 0.3 * math.sin(2 * math.pi * (woy - 10) / 52)
                if ds["name"] == "Measles" and d["id"] == outbreak_district and weeks_from_end < 4:
                    lam *= [18, 14, 10, 6][weeks_from_end]
                rows.append({
                    "district_id": d["id"], "disease_id": ds["id"],
                    "week_start": week.isoformat(), "cases": poisson(lam),
                    "reports_received": received, "reports_expected": exp,
                    "source": "synthetic",
                })

    if args.dry_run:
        with open("weekly_cases_synthetic.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=rows[0].keys())
            wr.writeheader()
            wr.writerows(rows)
        print(f"Wrote {len(rows)} rows. Outbreak district id: {outbreak_district}")
    else:
        from common import upsert
        upsert("weekly_cases", rows, "district_id,disease_id,week_start")
        print(f"Outbreak seeded in district id {outbreak_district} (measles, last 4 weeks)")


if __name__ == "__main__":
    main()

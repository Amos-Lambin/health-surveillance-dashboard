"""How much real weekly data does the DHIS2 demo hold? Run from the pipeline folder:
    python check_coverage.py | Tee-Object coverage_output.txt
"""
import os
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.environ["DHIS2_URL"].rstrip("/")
AUTH = (os.environ["DHIS2_USER"], os.environ["DHIS2_PASSWORD"])
DS = "Nyh6laLdBEJ"
ELEMENTS = {"vq2qO3eTrNi": "Malaria", "YazgqXbizv1": "Measles", "UsSUX0cpKsH": "Cholera",
            "noIzB569hTM": "Yellow fever", "HS9zqaBdOQ4": "Plague"}


def analytics(dx, weeks):
    r = requests.get(f"{BASE}/api/analytics", auth=AUTH, timeout=180, params={
        "dimension": [f"dx:{';'.join(dx)}", f"pe:LAST_{weeks}_WEEKS", "ou:LEVEL-2"],
        "skipMeta": "true"})
    r.raise_for_status()
    return r.json()["rows"]


for weeks in (52, 104):
    print(f"\n===== Case counts, last {weeks} weeks =====")
    try:
        by = defaultdict(list)
        for dx, pe, ou, v in analytics(list(ELEMENTS), weeks):
            by[dx].append((pe, ou, float(v)))
        for dx, name in ELEMENTS.items():
            rows = by.get(dx, [])
            if not rows:
                print(f"{name:13} no data")
                continue
            pes = sorted({r[0] for r in rows})
            print(f"{name:13} rows={len(rows):4} districts={len({r[1] for r in rows}):2} "
                  f"weeks={len(pes):3} range={pes[0]}..{pes[-1]} total_cases={sum(r[2] for r in rows):.0f}")
    except Exception as e:
        print("Error:", repr(e))

print("\n===== Reporting rates, last 52 weeks =====")
try:
    act, exp = {}, {}
    for dx, pe, ou, v in analytics([f"{DS}.ACTUAL_REPORTS", f"{DS}.EXPECTED_REPORTS"], 52):
        (act if dx.endswith("ACTUAL_REPORTS") else exp)[(pe, ou)] = float(v)
    with_reports = sum(1 for k, v in act.items() if v > 0)
    print(f"district-weeks with expected reports: {len(exp)}")
    print(f"district-weeks with at least 1 actual report: {with_reports}")
    print("sample expected:", list(exp.items())[:3])
except Exception as e:
    print("Error:", repr(e))

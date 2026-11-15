"""Daily threshold alerts, sent as ONE digest email.

Alert-fatigue rules (all configurable):
  1. Threshold = average of the earlier reported weeks + SIGMA standard deviations.
  2. The latest PERSIST reported weeks must ALL be above the threshold (not one-off spikes).
  3. The latest week must have at least MIN_CASES cases (tiny numbers are noise).
  4. Needs at least 8 earlier weeks to set a threshold.
  5. One email per run, strongest signals first, never the same district/disease/week twice.

Only aggregated counts are used or sent. No patient data exists in this system.

  python send_alerts.py --dry-run                       # show what would be sent
  python send_alerts.py --dry-run --sigma 0.5 --persist 1   # relaxed, for demos
  python send_alerts.py                                  # send for real and log to alert_log
Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, RESEND_API_KEY, ALERT_TO (comma-separated),
ALERT_FROM_EMAIL (default onboarding@resend.dev), DASHBOARD_URL (optional).
"""
import argparse
import html
import math
import os
import sys
from collections import defaultdict


def stats(values):
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return mean, sd


def find_alerts(rows, sigma=2.0, persist=2, min_cases=5, min_baseline=8):
    series = defaultdict(dict)
    for r in rows:
        series[(r["district_id"], r["disease_id"])][r["week_start"]] = r["cases"]
    out = []
    for (dist, dis), wk in series.items():
        weeks = sorted(wk)
        if len(weeks) < min_baseline + persist:
            continue
        recent = weeks[-persist:]
        st = stats([wk[w] for w in weeks[:-persist]])
        if not st:
            continue
        thr = st[0] + sigma * st[1]
        vals = [wk[w] for w in recent]
        if all(v > thr for v in vals) and vals[-1] >= min_cases:
            out.append({"district_id": dist, "disease_id": dis, "week_start": recent[-1],
                        "cases": vals[-1], "previous": vals[-2] if persist > 1 else None,
                        "threshold": thr, "mean": st[0], "n": len(weeks) - persist})
    return sorted(out, key=lambda a: a["cases"] / max(a["threshold"], 1), reverse=True)


def build_digest(alerts, districts, diseases, sigma, persist, dashboard_url=""):
    dn = {d["id"]: d["name"] for d in districts}
    ds = {d["id"]: d for d in diseases}
    subject = f"Surveillance alert digest: {len(alerts)} district-disease signal(s)"
    lines, rows_html = [], []
    for a in alerts:
        dis = ds[a["disease_id"]]
        prev = f" (previous reported week: {a['previous']})" if a["previous"] is not None else ""
        text = (f"- {dn[a['district_id']]}, {dis['name']} (ICD-10 {dis['icd10']}): {a['cases']} cases in the week "
                f"starting {a['week_start']}{prev}. Threshold {a['threshold']:.0f} "
                f"(average {a['mean']:.0f} over {a['n']} earlier reported weeks + {sigma:g} SD).")
        lines.append(text)
        rows_html.append(f"<li>{html.escape(text[2:])}</li>")
    note = (f"Rule: the latest {persist} reported week(s) were all above the threshold. "
            "Counts are aggregated and come from demo data. Reported weeks can be irregular.")
    link = f"\nOpen the dashboard: {dashboard_url}" if dashboard_url else ""
    body_text = "\n".join(lines) + "\n\n" + note + link + "\n"
    body_html = ("<p>New signals above threshold, strongest first:</p><ul>" + "".join(rows_html) + "</ul><p>" +
                 html.escape(note) + "</p>" +
                 (f'<p><a href="{html.escape(dashboard_url)}">Open the dashboard</a></p>' if dashboard_url else ""))
    return subject, body_text, body_html


def _session():
    """A session that retries dropped connections and temporary server errors."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))))
    return s


def fetch_all(table, select):
    from common import _base, _headers
    session = _session()
    out, offset = [], 0
    while True:
        r = session.get(f"{_base()}/{table}", headers=_headers(), timeout=60,
                        params={"select": select, "limit": 1000, "offset": offset, "order": "id"})
        r.raise_for_status()
        chunk = r.json()
        out += chunk
        if len(chunk) < 1000:
            return out
        offset += 1000


def send_email(api_key, sender, to, subject, text, body_html):
    import requests
    r = requests.post("https://api.resend.com/emails", timeout=30,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                      json={"from": sender, "to": to, "subject": subject, "text": text, "html": body_html})
    r.raise_for_status()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sigma", type=float, default=2.0)
    ap.add_argument("--persist", type=int, default=2)
    ap.add_argument("--min-cases", type=int, default=5)
    ap.add_argument("--force", action="store_true", help="ignore the alert log (resend)")
    a = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    rows = fetch_all("weekly_cases", "id,district_id,disease_id,week_start,cases")
    districts = fetch_all("districts", "id,name")
    diseases = fetch_all("diseases", "id,name,icd10")
    alerts = find_alerts(rows, a.sigma, a.persist, a.min_cases)
    if not a.force:
        logged = {(x["district_id"], x["disease_id"], x["week_start"])
                  for x in fetch_all("alert_log", "id,district_id,disease_id,week_start")}
        alerts = [x for x in alerts if (x["district_id"], x["disease_id"], x["week_start"]) not in logged]
    if not alerts:
        print("No new alerts.")
        return
    subject, text, body_html = build_digest(alerts, districts, diseases, a.sigma, a.persist,
                                            os.environ.get("DASHBOARD_URL", ""))
    print(subject + "\n" + text)
    if a.dry_run:
        print("(dry run: nothing sent, nothing logged)")
        return
    to = [x.strip() for x in os.environ["ALERT_TO"].split(",") if x.strip()]
    sender = os.environ.get("ALERT_FROM_EMAIL") or "onboarding@resend.dev"
    send_email(os.environ["RESEND_API_KEY"], sender, to, subject, text, body_html)
    from common import upsert
    upsert("alert_log", [{"district_id": x["district_id"], "disease_id": x["disease_id"],
                          "week_start": x["week_start"], "cases": int(x["cases"]),
                          "threshold": round(x["threshold"], 2)} for x in alerts],
           "district_id,disease_id,week_start")
    print(f"Sent to {len(to)} recipient(s) and logged {len(alerts)} alert(s).")


if __name__ == "__main__":
    main()

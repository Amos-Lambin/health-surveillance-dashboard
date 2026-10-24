"""Load weekly Wikipedia pageviews for disease articles into web_interest.

Source: Wikimedia REST API (per-article pageviews, human users). Public interest in a
disease is a rough early-warning signal, not a case count. Say that in your report.
"""
import datetime as dt
from collections import defaultdict

import requests

from common import upsert

ARTICLES = {"Malaria": "Malaria", "Measles": "Measles", "Cholera": "Cholera",
            "Yellow fever": "Yellow_fever"}
# Wikimedia asks for a descriptive User-Agent with contact details. Edit this.
HEADERS = {"User-Agent": "capstone-dashboard/1.0 (student project; amoslambin@gmail.com)"}


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def main(weeks=52):
    end = monday(dt.date.today()) - dt.timedelta(days=1)       # last Sunday
    start = end - dt.timedelta(weeks=weeks) + dt.timedelta(days=1)  # a Monday
    rows = []
    for term, article in ARTICLES.items():
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
               f"en.wikipedia/all-access/user/{article}/daily/"
               f"{start:%Y%m%d}/{end:%Y%m%d}")
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        views, days = defaultdict(int), defaultdict(int)
        for item in r.json()["items"]:
            day = dt.datetime.strptime(item["timestamp"][:8], "%Y%m%d").date()
            views[monday(day)] += item["views"]
            days[monday(day)] += 1
        for wk, v in views.items():
            if days[wk] == 7:  # skip partial weeks
                rows.append({"term": term, "week_start": wk.isoformat(), "views": v,
                             "source": "wikipedia-pageviews"})
    upsert("web_interest", rows, "term,week_start")


if __name__ == "__main__":
    main()

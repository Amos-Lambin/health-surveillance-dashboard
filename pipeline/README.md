# Pipeline

```
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Add these to your `.env` (repo root or this folder):

```
DHIS2_URL=https://play.dhis2.org/<the-sierra-leone-demo-path-you-use>
DHIS2_USER=<demo login>
DHIS2_PASSWORD=<demo password>
```

| Script | What it does |
|---|---|
| `explore_dhis2.py` | Lists org unit levels, data sets and matching data elements in the DHIS2 demo |
| `synthetic_weekly.py` | Fills `weekly_cases` with synthetic weekly counts (tagged `synthetic`) |
| `wikipedia_views.py` | Fills `web_interest` with weekly Wikipedia pageviews |

Never commit `.env`. The service role key must never appear in `public/`.

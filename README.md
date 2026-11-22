# Disease Surveillance Dashboard

A secure, accessible weekly disease surveillance dashboard for malaria, measles, cholera and yellow fever, shown by district. Built as a university capstone project (Introduction to Information Technology).

**Live site:** https://health-surveillance-dashboard.pages.dev/  
**Public information page:** https://health-surveillance-dashboard.pages.dev/about

The dashboard needs an account. Demo logins are provided to the course lecturer with the submission, not in this repository.

> **Data notice.** All data is aggregated, public or simulated. No patient-level data is used. Case counts come from the public DHIS2 demo database (Sierra Leone) and are not epidemiologically realistic. Reporting completeness is **simulated** (see below).

## What it does

- **Six visualisations:** headline numbers, weekly trend line, district map, cases by disease, cases by district (national view), control chart with outbreak threshold, plus a Wikipedia pageviews panel for public interest.
- **Interaction:** disease and district filters, map hover and click to drill down, and a CSV export of aggregated counts only.
- **Two roles, enforced in the database:** a *national manager* sees all districts; a *district officer* sees only their own district.
- **Email alerts:** a daily digest when a district's latest reported weeks exceed its mean + 2 standard deviations, with rules to prevent alert fatigue.
- **Honest charts:** axes start at zero, denominators are shown, counts under 5 are flagged, and missing weeks appear as breaks instead of being joined.
- **Security:** HTTPS only with HSTS, Content Security Policy and other security headers (securityheaders.com grade A+, SSL Labs grade A+).

## Architecture

| Part | Technology |
|---|---|
| Front end | HTML5, CSS3, JavaScript, Chart.js, plain SVG map (no mapping library) |
| Hosting | Cloudflare Pages (static, CDN), headers in `public/_headers` |
| Database and login | Supabase: Postgres, Auth, row-level security (RLS) |
| Data loading | Python scripts in `pipeline/` |
| Alerts | `pipeline/send_alerts.py` run daily by GitHub Actions; email via Resend |

Access control lives in the database: each user has a `profiles` row with a role and, for officers, a district. RLS policies filter every query, and logged-in users cannot write. Only the pipeline, using a secret service key that never reaches the browser, writes data.

## Repository layout

```
public/      Front end deployed to Cloudflare Pages (index, about, css, js, data, _headers)
db/          Postgres schema with RLS, reference data, one-off fix scripts
pipeline/    Python scripts: DHIS2 loader, Wikipedia loader, boundary download, alerts
.github/     GitHub Actions workflows (daily alerts, weekly Wikipedia refresh)
docs/        Notes and evidence
```

## Data sources

| Source | Used for | Notes |
|---|---|---|
| DHIS2 demo database (Sierra Leone) | Weekly IDSR case counts, expected reports, district boundaries | Public demo. 16 irregular reported weeks, Nov 2025 to Oct 2026. |
| Wikimedia pageviews API | Weekly English Wikipedia views per disease | Public data. Worldwide interest, not local cases. |
| Simulated | Reports *received* per district-week | The demo registers zero actual reports, so completeness is simulated (80 to 100 percent) and labelled in the `source` column. |

## Setup

1. Create a Supabase project. In the SQL editor run `db/schema.sql`, then `db/seed_reference.sql`, then `db/fix_districts.sql` and `db/switch_to_yellow_fever.sql`.
2. Copy `.env.example` to `.env` and fill in your keys (never commit `.env`).
3. Create users in Supabase Auth and add matching rows to `profiles` with a role (`national_manager` or `district_officer`) and, for officers, a district.
4. Load data from the `pipeline` folder:

```
python -m venv .venv
.venv\Scripts\activate          # Windows; on Mac or Linux: source .venv/bin/activate
pip install -r pipeline/requirements.txt
cd pipeline
python load_dhis2_idsr.py
python wikipedia_views.py
python fetch_boundaries.py
```

5. Put your Supabase URL and **anon** key in `public/js/config.js`. The anon key is designed to be public. Never put the service role key there.
6. Deploy `public/` to Cloudflare Pages (no build command, output directory `public`).

Local preview: `cd public && python -m http.server 8000`.

## Alerts

`pipeline/send_alerts.py` computes, per district and disease, a threshold of the mean plus 2 standard deviations of earlier reported weeks. An alert needs the latest reported weeks above the threshold, at least 5 cases, and at least 8 earlier weeks. It sends one digest email, and logs each alert in `alert_log` so none repeats. Useful options:

```
python send_alerts.py --dry-run                      # preview only
python send_alerts.py --dry-run --sigma 1 --persist 1  # relaxed settings for demos
```

The scheduled workflow (`.github/workflows/alerts.yml`) needs these repository secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, `ALERT_FROM_EMAIL`, `ALERT_TO`, `DASHBOARD_URL`.

## Known limitations

- Demo data only. Reported weeks are irregular and magnitudes are unrealistic.
- Reporting completeness is simulated.
- No custom domain, so SPF, DKIM and DMARC are not configured. Alert email uses the email provider's shared test sender.
- HL7 FHIR is not implemented. The data is aggregated counts, not clinical records.
- Mobile Lighthouse performance is below 85 on the signed-in dashboard. Desktop passes.
- The front end loads all rows in the browser; at larger scale aggregation should move into the database.

## Commit style

Short imperative subject, then why. Example: `Add RLS policy so district officers only read their district`.

# Disease Surveillance Dashboard

Weekly notifiable-disease dashboard (malaria, measles, cholera, typhoid) by district,
with role-based access (national manager / district officer), threshold email alerts
and honest-data rules (zero-based axes, denominators, small-number flags).

Course: Introduction to Information Technology, Mini Capstone (due 1 Dec 2026).

## Data
All data is aggregated and de-identified. No patient-level records are used.

| Source | Use | Licence / terms |
|---|---|---|
| DHIS2 demo database (Sierra Leone) | Weekly district case counts | Record from databases.dhis2.org |
| WHO Global Health Observatory | Reference indicators | Record from WHO |
| Wikipedia pageviews API | Public interest in symptoms | Record from Wikimedia |
| geoBoundaries | District boundaries (GeoJSON) | Record from geoboundaries.org |

Fill in the exact licence text and access date for each source as you download it.

## Structure
```
public/     Static front end (deployed to Cloudflare Pages)
db/         Postgres schema, row-level security, reference seed
pipeline/   Python scripts that load aggregated data (Phase: step 3)
docs/       Diagrams, indicator definitions, user stories, test notes
```

## Setup
1. Create a Supabase project. In the SQL editor run `db/schema.sql`, then `db/seed_reference.sql`.
2. Copy `.env.example` to `.env` and fill in the keys.
3. Create a Cloudflare Pages project from this repo. Build command: none. Output directory: `public`.
4. Point your domain at it and confirm HTTPS and the headers in `public/_headers`.

## Local preview
```
cd public && python3 -m http.server 8000
```

## Commit style
Short imperative subject, then why. Example: `Add RLS policy so district officers only read their district`.

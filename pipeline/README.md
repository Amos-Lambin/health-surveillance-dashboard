Step 3 goes here: a Python script that pulls DHIS2 weekly counts, WHO reference
data and Wikipedia pageviews, aggregates them, and upserts into Postgres using the
service role key from `.env`. Never put that key in `public/`.

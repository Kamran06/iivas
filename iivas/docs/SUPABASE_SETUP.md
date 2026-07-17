# Supabase + Biannual Auto-Refresh Setup

This wires the IIVAS pipeline to a managed Supabase PostgreSQL database and
schedules it to refresh automatically twice a year via GitHub Actions. No
server administration required.

---

## Part 1 — Create the Supabase database

1. Go to https://supabase.com and sign in (GitHub login is easiest).
2. **New project.** Pick an org, name it `iivas`, choose a region close to you
   (e.g. `eu-central-1` for Europe), and set a strong database password.
   **Save that password**, you will not see it again.
3. Wait ~2 minutes for provisioning.
4. Open **Project Settings (gear icon) -> Database -> Connection string ->
   URI**. Copy the string. It looks like:
   ```
   postgresql://postgres.abcxyzref:YOUR-PASSWORD@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```
   Replace `YOUR-PASSWORD` with the password from step 2.

## Part 2 — Create the schema

Two ways; pick one.

**A. Supabase SQL Editor (no local tools).** In the dashboard open
**SQL Editor -> New query**, paste the contents of `sql/01_create_tables.sql`,
run it; repeat for `sql/02_indexes.sql` then `sql/03_views.sql`.

**B. From your machine with psql:**
```bash
export DATABASE_URL="postgresql://postgres.ref:PASSWORD@...pooler.supabase.com:5432/postgres"
psql "$DATABASE_URL" -f sql/01_create_tables.sql
psql "$DATABASE_URL" -f sql/02_indexes.sql
psql "$DATABASE_URL" -f sql/03_views.sql
```

## Part 3 — Point the pipeline at Supabase (local runs)

```bash
cp .env.example .env
# edit .env:
#   DATABASE_URL="postgresql://postgres.ref:PASSWORD@...pooler.supabase.com:5432/postgres"
#   SEC_USER_AGENT="IIVAS Research <your name> <your email>"
```
The code auto-detects `DATABASE_URL`, normalises the scheme for SQLAlchemy, and
appends `sslmode=require` (Supabase requires TLS). Test it:
```bash
python -c "from src.database.db_connection import get_engine; \
print('connected:', get_engine().connect().closed == False)"
```
Then run the whole thing once by hand:
```bash
python -m src.run_pipeline
```

## Part 4 — Schedule the twice-a-year auto-refresh (GitHub Actions)

The workflow `.github/workflows/refresh_data.yml` runs the full pipeline on
**1 March** and **1 September** at 06:00 UTC, and can be run on demand.

1. Push the repo to GitHub.
2. In the repo: **Settings -> Secrets and variables -> Actions -> New
   repository secret.** Add two secrets:
   - `DATABASE_URL` = your Supabase URI (with the password).
   - `SEC_USER_AGENT` = `IIVAS Research <your name> <your email>`.
3. Open the **Actions** tab, enable workflows if prompted.
4. Test it now without waiting: **Actions -> "IIVAS biannual data refresh" ->
   Run workflow.** Watch the log; on success your Supabase tables are populated
   and the processed CSVs are attached as a downloadable artefact.

### Two operational caveats (read these)
1. **GitHub pauses rarely-touched schedules.** Scheduled workflows are
   disabled after ~60 days without repo activity (public/free repos). With a
   biannual cadence, either push an occasional commit, re-enable from the
   Actions tab when GitHub emails you, or add a monthly no-op keepalive
   workflow.
2. **Data volume vs. the free tier.** A full Big-Three, multi-year pull spans
   dozens of fund trusts and millions of vote rows — beyond Supabase's free
   500MB. Either scope the run (e.g. `start_year: 2024`, or a subset of
   trusts/issuers) or budget for the paid tier. Scoping to the 2024+
   structured-filing window is the recommended portfolio configuration anyway
   (cleaner data, see PROJECT_EVALUATION.md).

### Why twice a year (and why these dates)
N-PX is an annual filing due by 31 August for the year ending 30 June. The
1 September run captures the new season; the 1 March run sweeps up late filings
and `N-PX/A` amendments. To change the cadence, edit the `cron` line
(`"0 6 1 3,9 *"` = minute 0, hour 6, day 1, months 3 and 9).

## Part 5 — Connect the dashboard (optional)
- **Power BI:** Get Data -> PostgreSQL, host = your Supabase host, database =
  `postgres`, then import the `v_*` views (see `docs/POWER_BI_DASHBOARD.md`).
- **HTML dashboard:** export the `data/processed/*.csv` (or the GitHub Actions
  artefact) and paste the values into the `DATA` object in
  `dashboard/iivas_dashboard.html`.

## Security notes
- `.env` is git-ignored; never commit real credentials. In CI, credentials live
  only in encrypted GitHub Secrets.
- The Supabase URI contains your DB password; treat it like one.
- All analysed data is public SEC filings, so the DB holds nothing sensitive,
  but the credentials still must be protected.

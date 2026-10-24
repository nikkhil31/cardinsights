# CardWise

Local-first credit card statement analyzer. Drop SBI (more banks soon) statement PDFs in — transactions land in SQLite, dashboard shows category/trend/per-card analysis. No cloud, no LLM calls; data never leaves your machine.

## Setup (on your laptop)

```bash
git clone https://github.com/nikkhil31/cardinsights.git
cd cardinsights
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Run

```bash
streamlit run src/cardwise/dashboard/app.py
```

Open http://localhost:8501 → upload a PDF from the sidebar → done. Data stored at `~/.cardwise/`.

## Postgres (optional)

SQLite is the default and is fine for single-user local use. Switch to Postgres when you want multi-device access, concurrent writers, or a hosted DB.

```bash
# 1. start a local Postgres
docker compose up -d

# 2. install the driver
pip install -e ".[postgres]"

# 3. point the app at it
export DATABASE_URL=postgresql+psycopg://cardwise:cardwise@localhost:5432/cardwise
streamlit run src/cardwise/dashboard/app.py
```

URL resolution order: explicit arg > `DATABASE_URL` > `CARDWISE_DB` > `~/.cardwise/cardwise.db`. Both `postgres://` and `postgresql://` schemes are normalised to the psycopg3 driver. Schema is created on first connect; additive columns (`channel`, `cashback`, `cashback_rate`) are added automatically on both dialects — see `_migrate()` in `db.py`.

Migrating existing SQLite data to Postgres: re-ingest the PDFs (the archive is in `~/.cardwise/statements/`, and dedup makes this safe) — or `pgloader ~/.cardwise/cardwise.db postgresql://...` if you want the rows copied verbatim.

## How it works

- `parsers/sbi.py` — SBI Card PDF → transactions + summary (reconciles parsed sums against statement totals)
- `ingest.py` — SHA-256 dedup, fingerprint per transaction (re-uploads are no-ops)
- `categorize.py` — keyword rules from `categories.yaml` (edit freely; longest match wins)
- `dashboard/app.py` — Streamlit UI: upload, KPIs, category pie, monthly trend, per-card, top merchants, filterable table

## Adding a new bank parser

1. Create `src/cardwise/parsers/<bank>.py` with `detect(path) -> bool` and `parse(path) -> ParsedStatement`
2. Register it in `src/cardwise/parsers/__init__.py`

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ --pdf=/path/to/real_statement.pdf
```

## Roadmap

- [ ] HDFC / ICICI / Axis / Amex parsers
- [ ] Due-date reminders
- [ ] Watch-folder auto-ingest
- [ ] Export to CSV

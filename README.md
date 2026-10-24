# CardWise

Local-first credit card statement analyzer. Drop SBI (more banks soon) statement PDFs in — transactions land in SQLite, dashboard shows category/trend/per-card analysis. No cloud, no LLM calls; data never leaves your machine.

## Setup (on your laptop)

```bash
git clone https://github.com/nikkhil31/cardinsights.git
cd cardinsights
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## What it answers

The dashboard leads with **spend vs. rewards**, using the figures the statement itself reports — nothing is estimated from merchant keywords:

| Metric | Definition |
|---|---|
| Total spend | sum of debit transactions in the current filter |
| Eligible spend | total spend minus `Fuel` and `Finance & Fees` — the honest denominator for a reward rate, since those never earn |
| Rewards earned | cashback accrued this cycle, from the statement's Savings & Benefits section |
| Rewards credited | cashback actually posted to the account (₹ credits whose description mentions cashback) |
| Return on spend | rewards earned ÷ eligible spend |
| Net spend | total spend − cashback credited |

Cashback accrues **one cycle before** it is credited, so on any single statement "earned" and "credited" legitimately differ — both are shown rather than netted, so the lag stays visible.

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

URL resolution order: explicit arg > `DATABASE_URL` > `CARDWISE_DB` > `~/.cardwise/cardwise.db`. Both `postgres://` and `postgresql://` schemes are normalised to the psycopg3 driver. The schema is created on first connect by SQLAlchemy's `create_all()`.

Migrating existing SQLite data to Postgres: re-ingest the PDFs (the archive is in `~/.cardwise/statements/`, and dedup makes this safe) — or `pgloader ~/.cardwise/cardwise.db postgresql://...` if you want the rows copied verbatim.

## How it works

- `parsers/sbi.py` — SBI Card PDF → transactions + summary + statement-reported cashback (reconciles parsed sums against statement totals)
- `ingest.py` — SHA-256 dedup, fingerprint per transaction (re-uploads are no-ops)
- `categorize.py` — keyword rules from `categories.yaml` (edit freely; longest match wins)
- `analysis.py` — spend/reward aggregation; every definition documented in the module docstring
- `dashboard/app.py` — Streamlit UI: spend vs rewards, per-statement detail, category/month/card splits, top merchants, filterable table

## Adding a new bank parser

1. Create `src/cardwise/parsers/<bank>.py` with `detect(path) -> bool` and `parse(path) -> ParsedStatement`
2. Register it in `src/cardwise/parsers/__init__.py`

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ --pdf=/path/to/real_statement.pdf
```

The suite **asserts reconciliation**: parsed debit and credit sums must equal the statement's own "Purchases & Other Debits" and "Payments & Credits" totals. If a bank changes the PDF layout, this fails loudly instead of quietly storing partial data. Verified by mutation test (`tools/verify_guard.py` drops a transaction and confirms the suite fails).

PDFs and `.env` files are gitignored — never commit statements.

## Roadmap

- [ ] HDFC / ICICI / Axis / Amex parsers
- [ ] Due-date reminders
- [ ] Watch-folder auto-ingest
- [ ] Export to CSV

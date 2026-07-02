# Tariff Risk Disclosures: Report-Year Seed Panel

This repository contains a cleaner, balanced 10-K Item 1A Risk Factors dataset for studying tariff-related risk disclosure among trade-exposed public firms from fiscal/report years 2022 through 2025.

The primary dataset is:

```text
data/risk_factors_report_year_2022_2025_seed_only.csv
```

It covers 34 seed firms, 4 report years, and 136 10-K filings. Each row has a successful Item 1A extraction.

## How This Differs From The Earlier Repo

The earlier repository at `kamran-py/tariff-risk-disclosures` used a different workflow and included older exploratory outputs. This repository is intended as the cleaner research panel.

Main differences:

- Uses fiscal/report year as the study year, not filing calendar year.
- Includes fiscal 2025 10-Ks filed in calendar 2026.
- Excludes supplemental SEC full-text search rows from the primary dataset.
- Provides a balanced seed-firm-only panel: 34 firms x 4 report years.
- Hardens Item 1A extraction against table-of-contents entries, cross-references, short anchors, and 52/53-week fiscal-year edge cases.
- Removes broad standalone `duties` from the tariff term list and keeps contextual phrases such as `customs duties`, `import duties`, and `duties on imports`.
- Stores extraction status and failure reason fields in the output schema, even though all rows in the primary seed-only CSV succeeded.

## Data Sources

The workflow uses SEC EDGAR public endpoints:

- ticker/CIK lookup: `https://www.sec.gov/files/company_tickers.json`
- company submissions: `https://data.sec.gov/submissions/CIK##########.json`
- filing documents from SEC Archives: `https://www.sec.gov/Archives/edgar/data/...`

The script still supports supplemental SEC full-text search through `efts.sec.gov/LATEST/search-index`, but the checked-in primary CSV was generated with `--no-include-sec-search`.

## Reproduce The Primary Dataset

```powershell
cd C:\Users\kanop\tariff-risk-disclosures-report-year-panel
$env:SEC_USER_AGENT = "TariffRiskStudy/0.1 kamranahmed.8796@gmail.com"
python scripts\build_tariff_risk_dataset.py --no-include-sec-search --output data\risk_factors_report_year_2022_2025_seed_only.csv
```

SEC access behavior:

- descriptive User-Agent
- caching under `data/cache`
- retries/backoff
- default throttle of 8 requests/second
- hard cap check rejecting values above 10 requests/second

## Dataset Fields

The CSV includes:

- firm identifiers and metadata
- SEC filing metadata
- SEC filing URL
- extraction status and failure reason
- full extracted Item 1A Risk Factors text
- risk-factor word and character counts
- tariff-term hit count
- matched terms
- context excerpts

Use `report_year` as the study year. `filing_year` may be 2026 for fiscal 2025 10-Ks filed in 2026.

## Firm Universe

The seed universe is in `config/trade_exposed_firms.csv`.

It includes:

- manufacturing: 15 firms
- retail: 9 firms
- tech hardware: 10 firms

## Tariff Terms

The term list is in `config/tariff_terms.txt`.

Representative terms include:

- `tariff`, `tariffs`
- `trade restrictions`, `trade barriers`
- `section 301`
- `china tariffs`
- `retaliatory tariffs`
- `reciprocal tariffs`
- `liberation day`, `liberation day tariff`, `liberation day tariffs`
- contextual duty phrases such as `customs duties` and `import duties`

## Tests

```powershell
python -m unittest discover -s tests
```

The tests cover CIK/URL construction, report-year selection, early-January fiscal-year normalization, Item 1A extraction boundaries, table-of-contents false positives, AMD-like cross-reference false starts, Kohl's-style body starts without repeated Item headings, and tariff-term matching.

## Research Summary

See `DATASET_SUMMARY.md` for descriptive statistics and research caveats.

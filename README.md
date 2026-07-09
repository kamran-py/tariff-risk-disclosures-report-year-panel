# Tariff Risk Disclosures: Report-Year Seed Panel

Balanced 10-K Item 1A Risk Factors panel for studying tariff-risk disclosure
among trade-exposed public firms, fiscal years 2022–2025.

The primary dataset is:

```text
data/risk_factors_report_year_2022_2025_seed_only.csv
```

It covers 34 seed firms, four report years, and 136 successfully extracted 10-Ks.

## How This Differs From The Earlier Repo

`kamran-py/tariff-risk-disclosures` used an earlier exploratory workflow. This
repository is its cleaner research panel.

Main differences:

- Uses fiscal/report year as the study year, not filing calendar year.
- Includes fiscal 2025 10-Ks filed in calendar 2026.
- Excludes supplemental SEC full-text search rows from the primary dataset.
- Provides a balanced seed-only panel: 34 firms × 4 report years.
- Handles table-of-contents entries, cross-references, short anchors, and 52/53-week fiscal-year edge cases.
- Removes broad standalone `duties` from the tariff term list and keeps contextual phrases such as `customs duties`, `import duties`, and `duties on imports`.
- Stores extraction status and failure reason, though every primary-panel row succeeded.

## Data Sources

The workflow uses SEC EDGAR public endpoints:

- ticker/CIK lookup: `https://www.sec.gov/files/company_tickers.json`
- company submissions: `https://data.sec.gov/submissions/CIK##########.json`
- filing documents from SEC Archives: `https://www.sec.gov/Archives/edgar/data/...`

The script also supports supplemental SEC full-text search; the committed CSV
uses `--no-include-sec-search`.

## Reproduce The Primary Dataset

```powershell
cd tariff-risk-disclosures-v2
$env:SEC_USER_AGENT = "TariffRiskStudy/0.1 contact@example.com"
python scripts\build_tariff_risk_dataset.py --no-include-sec-search --output data\risk_factors_report_year_2022_2025_seed_only.csv
```

SEC access:

- descriptive `User-Agent`, caching, and retries
- default throttle of 8 requests/second; hard cap of 10

## Dataset Fields

The CSV includes:

- firm identifiers and metadata
- SEC filing metadata
- SEC filing URL
- extraction status and failure reason
- extracted Item 1A text and word/character counts
- tariff-term hit count
- matched terms
- context excerpts

Use `report_year` as the study year; `filing_year` may be 2026 for fiscal-2025 filings.

## Repository Structure

- `data/`: committed panel and generated cache/output paths.
- `config/`: seed universe and term lists.
- `scripts/`: EDGAR collection, extraction, and panel construction.
- `tests/`: extraction and date-normalization checks.
- `DATASET_SUMMARY.md`: descriptive statistics and research caveats.

## Firm Universe

The seed universe is in `config/trade_exposed_firms.csv`.

It includes:

- manufacturing: 15 firms
- retail: 9 firms
- tech hardware: 10 firms

## Tariff Terms

The term list is in `config/tariff_terms.txt`.

Representative terms:

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

Tests cover CIK/URL construction, report-year selection, fiscal-year normalization,
Item 1A boundaries, false starts, and tariff matching.

## Research Summary

See `DATASET_SUMMARY.md` for descriptive statistics and research caveats.

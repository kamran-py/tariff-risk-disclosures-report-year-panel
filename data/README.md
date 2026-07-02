# Data Files

Primary dataset:

```text
risk_factors_report_year_2022_2025_seed_only.csv
```

This is the balanced seed-firm-only panel:

- 34 trade-exposed firms
- report years 2022-2025
- 136 10-K filings
- no supplemental SEC full-text search rows
- all rows have successful Item 1A extraction

The script may create `data/cache/` when rerun. That cache is intentionally ignored by git.

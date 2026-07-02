# Dataset Summary

Primary file summarized:

```text
data/risk_factors_report_year_2022_2025_seed_only.csv
```

## Coverage

- Firms: 34
- Report years: 2022, 2023, 2024, 2025
- Filings: 136
- Panel structure: 34 firms x 4 report years
- Non-seed firms: 0

Firm buckets:

- Manufacturing: 15
- Retail: 9
- Tech hardware: 10

## Extraction Quality

- Successful Item 1A extractions: 136 / 136
- Success rate: 100.0%
- Extraction failures: 0
- Missing firm-years: 0
- Rows under 1,000 extracted Risk Factor words: 0

## Tariff-Related Hits

- Filings with at least one tariff-related hit: 133 / 136
- Hit rate: 97.8%

Most common terms:

| Term | Count |
|---|---:|
| tariffs | 623 |
| trade restrictions | 165 |
| trade barriers | 48 |
| tariff | 44 |
| export restrictions | 36 |
| protectionist | 26 |
| retaliatory tariffs | 25 |
| protectionism | 15 |
| import duties | 9 |
| import restrictions | 7 |
| reciprocal tariffs | 5 |
| section 301 | 2 |

## Year-Level Pattern

| Report year | Filings | Filings with hits | Total hits | Avg. hits / filing |
|---:|---:|---:|---:|---:|
| 2022 | 34 | 33 | 196 | 5.76 |
| 2023 | 34 | 33 | 184 | 5.41 |
| 2024 | 34 | 33 | 211 | 6.21 |
| 2025 | 34 | 34 | 417 | 12.26 |

The 2025 increase is broad and large relative to 2022-2024.

## High And Low Mention Firms

Highest firm totals across 2022-2025:

| Firm | Total hits |
|---|---:|
| LULU | 70 |
| NKE | 56 |
| F | 50 |
| HON | 48 |
| INTC | 46 |
| DE | 45 |
| NVDA | 43 |
| AMD | 41 |
| HD | 38 |
| SWK | 38 |

Lowest firm totals:

| Firm | Total hits |
|---|---:|
| TGT | 8 |
| CSCO | 11 |
| EMR | 11 |
| CAT | 15 |
| COST | 16 |
| TSLA | 17 |
| KSS | 18 |
| DELL | 20 |
| MMM | 20 |
| WMT | 20 |

Highest single firm-year rows:

| Firm | Report year | Hits |
|---|---:|---:|
| HPQ | 2025 | 22 |
| F | 2025 | 21 |
| GM | 2025 | 21 |
| HPE | 2025 | 20 |
| AMD | 2025 | 19 |
| DE | 2025 | 19 |
| SWK | 2025 | 18 |
| HON | 2025 | 18 |

Zero-hit rows:

- CAT 2022
- CAT 2023
- CAT 2024

## Representative Excerpt Themes

The generated excerpts include disclosure language about:

- restrictions on international trade, including tariffs and controls on imports or exports
- supply-chain disruptions from tariffs or other trade restrictions
- unpredictable trade policy limiting long-term planning and capital allocation
- import tariffs or tariff-related measures affecting global operations
- higher manufacturing costs and expected future tariff impacts
- quotas, duties, tariffs, sanctions, and trade restrictions affecting sourcing and merchandise profitability

## Caveats

- Counts are exact term matches, not severity scores.
- More hits may reflect longer Item 1A sections or repeated boilerplate.
- The sample is intentionally trade-exposed and not representative of all public companies.
- The primary dataset uses fiscal/report year; some fiscal 2025 filings were filed in calendar 2026.
- Early-January 52/53-week fiscal year ends are normalized to the prior fiscal year when appropriate.
- The term list is intentionally conservative but still keyword-based.
- Policy interpretation should use manual review of excerpts and underlying filings.
- The broader workflow can generate supplemental SEC-search rows, but those are excluded from the primary balanced panel.

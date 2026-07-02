import unittest
from pathlib import Path

from scripts.build_tariff_risk_dataset import (
    Firm,
    build_filing_url,
    build_submissions_url,
    count_terms,
    extract_item_1a,
    fiscal_report_year,
    format_cik,
    parse_display_name,
    read_terms,
    select_10k_filings,
)


class RiskFactorExtractionTests(unittest.TestCase):
    def test_report_year_selection_includes_2025_10k_filed_in_2026(self):
        firm = Firm("AMD", "Advanced Micro Devices Inc.", "tech hardware", "Semiconductors")
        submissions = {
            "sic": "3674",
            "sicDescription": "Semiconductors",
            "filings": {
                "recent": {
                    "form": ["10-K", "10-K", "10-K/A"],
                    "filingDate": ["2022-02-03", "2026-02-04", "2026-02-10"],
                    "reportDate": ["2021-12-25", "2025-12-27", "2025-12-27"],
                    "accessionNumber": [
                        "0000002488-22-000016",
                        "0000002488-26-000010",
                        "0000002488-26-000011",
                    ],
                    "primaryDocument": [
                        "amd-20211225.htm",
                        "amd-20251227.htm",
                        "amd-20251227x10ka.htm",
                    ],
                }
            },
        }

        filings = select_10k_filings(
            client=None,
            firm=firm,
            cik=2488,
            submissions=submissions,
            start_year=2022,
            end_year=2025,
            date_basis="report",
            include_amended=False,
        )

        self.assertEqual([filing.accession_number for filing in filings], ["0000002488-26-000010"])
        self.assertEqual(filings[0].filing_year, 2026)
        self.assertEqual(filings[0].report_year, 2025)

    def test_early_january_report_date_maps_to_prior_fiscal_year(self):
        self.assertEqual(fiscal_report_year("2026-01-03"), 2025)
        self.assertEqual(fiscal_report_year("2026-01-08"), 2026)

        firm = Firm("SWK", "Stanley Black & Decker Inc.", "manufacturing", "Tools")
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-K"],
                    "filingDate": ["2025-02-18", "2026-02-24"],
                    "reportDate": ["2024-12-28", "2026-01-03"],
                    "accessionNumber": ["0000093556-25-000007", "0000093556-26-000009"],
                    "primaryDocument": ["swk-20241228.htm", "swk-20260103.htm"],
                }
            }
        }

        filings = select_10k_filings(
            client=None,
            firm=firm,
            cik=93556,
            submissions=submissions,
            start_year=2025,
            end_year=2025,
            date_basis="report",
            include_amended=False,
        )

        self.assertEqual([filing.accession_number for filing in filings], ["0000093556-26-000009"])
        self.assertEqual(filings[0].report_year, 2025)

    def test_filing_year_selection_excludes_2026_filing_when_end_year_is_2025(self):
        firm = Firm("AMD", "Advanced Micro Devices Inc.", "tech hardware", "Semiconductors")
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2026-02-04"],
                    "reportDate": ["2025-12-27"],
                    "accessionNumber": ["0000002488-26-000010"],
                    "primaryDocument": ["amd-20251227.htm"],
                }
            }
        }

        filings = select_10k_filings(
            client=None,
            firm=firm,
            cik=2488,
            submissions=submissions,
            start_year=2022,
            end_year=2025,
            date_basis="filing",
            include_amended=False,
        )

        self.assertEqual(filings, [])

    def test_formats_cik_for_submissions_endpoint(self):
        self.assertEqual(format_cik(320193), "0000320193")
        self.assertEqual(
            build_submissions_url("320193"),
            "https://data.sec.gov/submissions/CIK0000320193.json",
        )

    def test_builds_archives_filing_document_url(self):
        self.assertEqual(
            build_filing_url(320193, "0000320193-25-000008", "aapl-20240928.htm"),
            "https://www.sec.gov/Archives/edgar/data/320193/000032019325000008/aapl-20240928.htm",
        )

    def test_chooses_long_item_1a_over_table_of_contents(self):
        body = " ".join(["Tariffs and import duties may affect margins."] * 90)
        html = f"""
        <html><body>
          <p>Table of Contents Item 1A. Risk Factors Item 1B. Unresolved Staff Comments</p>
          <h2>ITEM 1A. RISK FACTORS</h2>
          <p>{body}</p>
          <h2>Item 1B. Unresolved Staff Comments</h2>
        </body></html>
        """

        extracted = extract_item_1a(html)

        self.assertIn("Tariffs and import duties", extracted)
        self.assertTrue(extracted.startswith("ITEM 1A. RISK FACTORS"))
        self.assertGreater(len(extracted), 1000)

    def test_skips_cross_reference_before_item_1a_body(self):
        body = " ".join(["The risks and uncertainties described below may affect tariffs."] * 90)
        html = f"""
        <html><body>
          <p>For a discussion of the factors that could cause actual results to differ
          materially from forward-looking statements, see “Part I, Item 1A-Risk Factors”
          and the “Financial Condition” section set forth in “Part II, Item 7-Management’s
          Discussion and Analysis of Financial Condition and Results of Operations.”</p>
          <h2>ITEM 1A. RISK FACTORS</h2>
          <p>{body}</p>
          <h2>ITEM 1B. UNRESOLVED STAFF COMMENTS</h2>
        </body></html>
        """

        extracted = extract_item_1a(html)

        self.assertTrue(extracted.startswith("ITEM 1A. RISK FACTORS"))
        self.assertNotIn("forward-looking statements, see", extracted[:300])
        self.assertGreater(len(extracted), 1000)

    def test_extracts_normal_item_1a_section(self):
        body = " ".join(["Carefully consider these risk factors before investing."] * 80)
        html = f"""
        <html><body>
          <h2>ITEM 1. BUSINESS</h2>
          <p>Business overview.</p>
          <h2>ITEM 1A. RISK FACTORS</h2>
          <p>{body}</p>
          <h2>ITEM 2. PROPERTIES</h2>
          <p>Facilities discussion.</p>
        </body></html>
        """

        extracted = extract_item_1a(html)

        self.assertTrue(extracted.startswith("ITEM 1A. RISK FACTORS"))
        self.assertIn("Carefully consider these risk factors", extracted)
        self.assertNotIn("ITEM 2. PROPERTIES", extracted)

    def test_skips_amd_like_forward_looking_statement_reference(self):
        body = " ".join(["Risk Factors Summary The following summarizes tariffs and trade restrictions."] * 70)
        html = f"""
        <html><body>
          <p>For a discussion of the factors that could cause actual results to differ
          materially from the forward-looking statements, see “Part I, Item 1A-Risk Factors”
          and the “Financial Condition” section set forth in “Part II, Item 7-Management’s
          Discussion and Analysis of Financial Condition and Results of Operations,” or MD&amp;A,
          and such other risks and uncertainties as set forth below in this report.</p>
          <p>Additional business text before the real section.</p>
          <h2>ITEM 1A. RISK FACTORS</h2>
          <p>The risks and uncertainties described below are not the only ones we face.</p>
          <p>{body}</p>
          <h2>ITEM 1B. UNRESOLVED STAFF COMMENTS</h2>
        </body></html>
        """

        extracted = extract_item_1a(html)

        self.assertTrue(extracted.startswith("ITEM 1A. RISK FACTORS"))
        self.assertNotIn("Financial Condition", extracted[:300])
        self.assertIn("Risk Factors Summary", extracted)

    def test_extracts_kohls_like_body_without_repeated_item_heading(self):
        body = " ".join(["Many of these risk factors are outside of our control."] * 80)
        html = f"""
        <html><body>
          <p>KOHL'S CORPORATION INDEX PART I Item 1. Business 3
          Item 1A. Risk Factors 7 Item 1B. Unresolved Staff Comments 15
          Item 2. Properties 17</p>
          <p>Forward-looking statements are based on management's then current views
          and assumptions and are subject to risks and uncertainties. As such,
          forward-looking statements are qualified by those risk factors described below.
          Forward-looking statements relate to the date made.</p>
          <p>Our sales, revenues, gross margin, expenses, and operating results could be
          negatively impacted by a number of factors including, but not limited to those
          described below.</p>
          <p>{body}</p>
          <h2>Item 1B. Unresolved Staff Comments</h2>
        </body></html>
        """

        extracted = extract_item_1a(html)

        self.assertTrue(
            extracted.startswith("risk factors described below")
            or extracted.startswith("risk factors are outside of our control")
        )
        self.assertNotIn("Item 1A. Risk Factors 7", extracted[:100])
        self.assertGreater(len(extracted), 1000)

    def test_counts_multiword_terms(self):
        text = "Tariffs, China tariffs, import duties, and Section 301 tariffs are material."
        total, matched = count_terms(
            text,
            ["china tariffs", "tariff", "tariffs", "import duties", "section 301"],
        )

        self.assertEqual(total, 5)
        self.assertEqual(matched, ["china tariffs", "tariffs", "import duties", "section 301"])

    def test_matches_requested_tariff_phrases(self):
        text = (
            "Customs duties, trade restrictions, retaliatory tariffs, "
            "and reciprocal tariffs could affect imports."
        )
        total, matched = count_terms(
            text,
            ["customs duties", "trade restrictions", "retaliatory tariffs", "reciprocal tariffs"],
        )

        self.assertEqual(total, 4)
        self.assertEqual(
            matched,
            ["customs duties", "trade restrictions", "retaliatory tariffs", "reciprocal tariffs"],
        )

    def test_prefers_longest_non_overlapping_term(self):
        text = "Higher customs duties and import duties may increase costs."
        total, matched = count_terms(text, ["customs duties", "import duties", "duties"])

        self.assertEqual(total, 2)
        self.assertEqual(matched, ["customs duties", "import duties"])

    def test_term_config_uses_contextual_duties_not_standalone_duties(self):
        terms = read_terms(Path("config/tariff_terms.txt"))

        self.assertNotIn("duties", terms)
        self.assertIn("customs duties", terms)
        self.assertIn("import duties", terms)
        self.assertIn("duties on imports", terms)

    def test_parses_sec_display_name_with_optional_ticker(self):
        company, ticker = parse_display_name(
            "A-Mark Precious Metals, Inc.  (AMRK)  (CIK 0001591588)"
        )
        self.assertEqual(company, "A-Mark Precious Metals, Inc.")
        self.assertEqual(ticker, "AMRK")

        company, ticker = parse_display_name("Kingfish Holding Corp  (CIK 0001374881)")
        self.assertEqual(company, "Kingfish Holding Corp")
        self.assertEqual(ticker, "")


if __name__ == "__main__":
    unittest.main()

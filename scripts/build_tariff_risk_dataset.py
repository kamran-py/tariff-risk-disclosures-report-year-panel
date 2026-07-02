#!/usr/bin/env python3
"""Build a 10-K Item 1A Risk Factors dataset from SEC EDGAR."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
DEFAULT_SEC_USER_AGENT = "TariffRiskStudy/0.1 kamranahmed.8796@gmail.com"
RETRY_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}

START_RE = re.compile(r"\bitem\s+1a[\.\s:\-]*risk\s+factors?\b", re.IGNORECASE)
RISK_HEADING_RE = re.compile(r"\brisk\s+factors?\b", re.IGNORECASE)
END_RE = re.compile(
    r"\b(?:"
    r"item\s+(?:1b|1c|2)[\.\s:\-]*(?:unresolved|cybersecurity|properties)?|"
    r"unresolved\s+staff\s+comments|"
    r"properties|"
    r"legal\s+proceedings|"
    r"quantitative\s+and\s+qualitative\s+disclosures\s+about\s+market\s+risks?"
    r")\b",
    re.IGNORECASE,
)
WHITESPACE_RE = re.compile(r"\s+")
DEFAULT_SEARCH_REQUIRED_TERMS = {
    "liberation day",
    "liberation day tariff",
    "liberation day tariffs",
}
MIN_ITEM_1A_CHARS = 1000
ITEM_1A_BODY_MARKERS = (
    "the risks and uncertainties described below",
    "risk factors described below",
    "many of these risk factors are outside of our control",
    "the following summarizes",
    "risk factors summary",
    "the following risk factors",
    "these risk factors",
    "set forth below",
    "carefully consider",
    "material risks",
    "material factors",
)
REFERENCE_START_MARKERS = (
    "see ",
    "refer to ",
    "within ",
    "under ",
    "caption ",
    "section titled ",
    "described in ",
    "included in ",
    "particularly in ",
    "discussion of the factors",
    "forward-looking statements",
)


@dataclass(frozen=True)
class Firm:
    ticker: str
    company_name: str
    industry_bucket: str
    notes: str
    cik: int | None = None


@dataclass(frozen=True)
class Filing:
    cik: int
    ticker: str
    company_name: str
    sic: str
    sic_description: str
    form: str
    accession_number: str
    filing_date: str
    report_date: str
    primary_document: str

    @property
    def filing_year(self) -> int:
        return int(self.filing_date[:4])

    @property
    def report_year(self) -> int:
        return fiscal_report_year(self.report_date) if self.report_date else self.filing_year

    @property
    def accession_nodashes(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def url(self) -> str:
        return build_filing_url(self.cik, self.accession_number, self.primary_document)


@dataclass(frozen=True)
class SearchFiling:
    cik: int
    ticker: str
    company_name: str
    sic: str
    form: str
    accession_number: str
    filing_date: str
    report_date: str
    primary_document: str
    search_query: str
    search_display_name: str

    @property
    def filing_year(self) -> int:
        return int(self.filing_date[:4])

    @property
    def report_year(self) -> int:
        return fiscal_report_year(self.report_date) if self.report_date else self.filing_year

    @property
    def accession_nodashes(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def url(self) -> str:
        return build_filing_url(self.cik, self.accession_number, self.primary_document)


class SecClient:
    def __init__(self, user_agent: str, cache_dir: Path, max_rps: float) -> None:
        self.user_agent = user_agent
        self.cache_dir = cache_dir
        self.min_interval = 1.0 / max_rps
        self.last_request_at = 0.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_text(self, url: str, *, cache_name: str | None = None) -> str:
        cache_path = self._cache_path(url, cache_name)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="replace")

        data = self._request(url)
        text = data.decode("utf-8", errors="replace")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text

    def get_json(self, url: str, *, cache_name: str | None = None) -> dict:
        return json.loads(self.get_text(url, cache_name=cache_name))

    def _request(self, url: str) -> bytes:
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
            },
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRY_HTTP_STATUS_CODES or attempt == 3:
                    raise
                last_error = exc
                retry_after = parse_retry_after(exc.headers.get("Retry-After"))
                sleep_seconds = retry_after if retry_after is not None else min(2**attempt, 8)
                time.sleep(sleep_seconds)
            except urllib.error.URLError as exc:
                if attempt == 3:
                    raise
                last_error = exc
                time.sleep(min(2**attempt, 8))
            finally:
                self.last_request_at = time.monotonic()

        if last_error:
            raise last_error
        raise RuntimeError(f"SEC request failed for {url}")

    def _cache_path(self, url: str, cache_name: str | None) -> Path:
        if cache_name:
            return self.cache_dir / cache_name
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.txt"


def parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        return None


def format_cik(cik: int | str) -> str:
    return f"{int(cik):010d}"


def build_submissions_url(cik: int | str) -> str:
    return f"{SEC_SUBMISSIONS_URL}/CIK{format_cik(cik)}.json"


def build_filing_url(cik: int | str, accession_number: str, primary_document: str) -> str:
    accession_nodashes = accession_number.replace("-", "")
    return f"{SEC_ARCHIVES_URL}/{int(cik)}/{accession_nodashes}/{primary_document}"


def fiscal_report_year(report_date: str) -> int:
    """Map 52/53-week fiscal years ending in early January to the prior fiscal year."""
    year, month, day = (int(part) for part in report_date[:10].split("-"))
    if month == 1 and day <= 7:
        return year - 1
    return year


def read_firms(path: Path) -> list[Firm]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            Firm(
                ticker=row["ticker"].strip().upper(),
                company_name=row["company_name"].strip(),
                industry_bucket=row["industry_bucket"].strip(),
                notes=row["notes"].strip(),
                cik=int(row["cik"]) if row.get("cik", "").strip() else None,
            )
            for row in rows
        ]


def read_terms(path: Path) -> list[str]:
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = line.strip().lower()
        if term and not term.startswith("#"):
            terms.append(term)
    return sorted(set(terms), key=lambda item: (-len(item), item))


def read_search_queries(path: Path) -> list[str]:
    if not path.exists():
        return []
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        query = line.strip()
        if query and not query.startswith("#"):
            queries.append(query)
    return sorted(set(queries))


def ticker_to_cik(client: SecClient) -> dict[str, dict]:
    data = client.get_json(SEC_COMPANY_TICKERS_URL, cache_name="company_tickers.json")
    return {entry["ticker"].upper(): entry for entry in data.values()}


def fetch_submissions(client: SecClient, cik: int) -> dict:
    return client.get_json(
        build_submissions_url(cik),
        cache_name=f"submissions/CIK{format_cik(cik)}.json",
    )


def fetch_additional_submission_file(client: SecClient, filename: str) -> dict:
    return client.get_json(
        f"{SEC_SUBMISSIONS_URL}/{filename}",
        cache_name=f"submissions/{filename}",
    )


def search_sec_filings(
    client: SecClient,
    query: str,
    form: str,
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> list[dict]:
    hits: list[dict] = []
    offset = 0

    while True:
        params = {
            "q": query,
            "forms": form,
            "dateRange": "custom",
            "startdt": start_date,
            "enddt": end_date,
            "from": str(offset),
            "size": str(page_size),
        }
        url = f"{SEC_FULL_TEXT_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        try:
            data = client.get_json(
                url,
                cache_name=(
                    "efts/"
                    f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"
                ),
            )
        except urllib.error.HTTPError as exc:
            print(f"WARNING: SEC full-text search failed for {query!r}: HTTP {exc.code}", file=sys.stderr)
            break

        page_hits = data.get("hits", {}).get("hits", [])
        if not page_hits:
            break
        hits.extend(page_hits)
        if len(page_hits) < page_size:
            break
        offset += page_size

    return hits


def iter_recent_filings(submissions: dict) -> Iterable[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    keys = list(recent.keys())
    if not keys:
        return
    count = len(recent[keys[0]])
    for index in range(count):
        yield {key: recent[key][index] for key in keys}


def iter_all_filing_rows(client: SecClient, submissions: dict) -> Iterable[dict]:
    yield from iter_recent_filings(submissions)
    for item in submissions.get("filings", {}).get("files", []):
        filename = item.get("name")
        if not filename:
            continue
        more = fetch_additional_submission_file(client, filename)
        yield from iter_recent_filings({"filings": {"recent": more}})


def select_10k_filings(
    client: SecClient,
    firm: Firm,
    cik: int,
    submissions: dict,
    start_year: int,
    end_year: int,
    date_basis: str,
    include_amended: bool,
) -> list[Filing]:
    selected: list[Filing] = []
    seen_accessions: set[str] = set()
    sic = str(submissions.get("sic", "") or "")
    sic_description = str(submissions.get("sicDescription", "") or "")

    for row in iter_all_filing_rows(client, submissions):
        form = str(row.get("form", "")).upper()
        if form == "10-K/A" and not include_amended:
            continue
        if form not in {"10-K", "10-K/A"}:
            continue

        filing_date = str(row.get("filingDate", "") or "")
        report_date = str(row.get("reportDate", "") or "")
        if date_basis == "report" and report_date:
            year = fiscal_report_year(report_date)
        elif filing_date:
            year = int(filing_date[:4])
        else:
            continue
        if year < start_year or year > end_year:
            continue

        accession = str(row.get("accessionNumber", "") or "")
        primary_document = str(row.get("primaryDocument", "") or "")
        if not accession or not primary_document or accession in seen_accessions:
            continue

        seen_accessions.add(accession)
        selected.append(
            Filing(
                cik=cik,
                ticker=firm.ticker,
                company_name=firm.company_name,
                sic=sic,
                sic_description=sic_description,
                form=form,
                accession_number=accession,
                filing_date=filing_date,
                report_date=report_date,
                primary_document=primary_document,
            )
        )

    return sorted(selected, key=lambda filing: (filing.filing_date, filing.accession_number))


def parse_display_name(display_name: str) -> tuple[str, str]:
    ticker_match = re.search(r"\(([A-Z][A-Z0-9.\-]{0,9})\)\s+\(CIK\s+\d+\)", display_name)
    ticker = ticker_match.group(1) if ticker_match else ""
    company_name = re.sub(r"\s+\([A-Z][A-Z0-9.\-]{0,9}\)\s+\(CIK\s+\d+\)$", "", display_name)
    company_name = re.sub(r"\s+\(CIK\s+\d+\)$", "", company_name).strip()
    return company_name, ticker


def search_hit_to_filing(hit: dict, query: str) -> SearchFiling | None:
    source = hit.get("_source", {})
    hit_id = str(hit.get("_id", ""))
    if ":" not in hit_id:
        return None

    accession, primary_document = hit_id.split(":", 1)
    ciks = source.get("ciks") or []
    if not ciks:
        return None

    display_name = (source.get("display_names") or [""])[0]
    company_name, ticker = parse_display_name(display_name)
    return SearchFiling(
        cik=int(str(ciks[0])),
        ticker=ticker,
        company_name=company_name,
        sic=";".join(source.get("sics") or []),
        form=str(source.get("form") or source.get("root_forms", ["10-K"])[0]),
        accession_number=accession,
        filing_date=str(source.get("file_date") or ""),
        report_date=str(source.get("period_ending") or ""),
        primary_document=primary_document,
        search_query=query,
        search_display_name=display_name,
    )


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</(?:p|div|tr|h[1-6]|li|table|section)>", "\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    return WHITESPACE_RE.sub(" ", html.unescape(raw)).strip()


def extract_item_1a(raw_document: str) -> str:
    text = html_to_text(raw_document)
    starts = sorted(set(iter_risk_factor_starts(text)))
    if not starts:
        return ""

    candidates: list[tuple[int, int, str]] = []
    for start in starts:
        end = find_section_end(text, start)
        candidate = text[start:end].strip()
        if len(candidate) >= MIN_ITEM_1A_CHARS:
            candidates.append((score_item_1a_candidate(text, start, end), start, candidate))

    if not candidates:
        start = starts[-1]
        end = find_section_end(text, start)
        candidate = text[start:end].strip()
        return candidate if len(candidate) >= MIN_ITEM_1A_CHARS else ""

    _score, _start, candidate = max(candidates, key=lambda item: (item[0], item[1]))
    return candidate


def score_item_1a_candidate(text: str, start: int, end: int) -> int:
    before = text[max(0, start - 300) : start].lower()
    after = text[start : min(len(text), start + 1000)].lower()
    length = end - start
    score = min(length // 1000, 150)

    if has_body_start_marker(after):
        score += 1000
    if is_reference_item_1a_start(before, after):
        score -= 1000
    if is_table_of_contents_item_1a_start(before, after, length):
        score -= 1000

    heading_line = text[start : min(len(text), start + 80)]
    if re.search(r"\bITEM\s+1A[\.\s:\-]*RISK\s+FACTORS\b", heading_line):
        score += 200
    return score


def find_section_end(text: str, start: int) -> int:
    for match in END_RE.finditer(text, start + 20):
        if is_valid_end_heading(text, match):
            return match.start()
    return len(text)


def is_valid_end_heading(text: str, match: re.Match[str]) -> bool:
    heading = match.group(0).lower()
    before = text[max(0, match.start() - 120) : match.start()].lower()
    after = text[match.end() : match.end() + 250].lower().lstrip()

    if re.match(r"item\s+2\b", heading):
        if "properties" in heading:
            return True
        return after.startswith((".", "properties")) and "properties" in after[:30]

    if "legal proceedings" in heading:
        return match.group(0).isupper() or re.search(r"item\s+3[\.\s:\-]*$", before) is not None

    if heading != "properties":
        return True

    properties_body_markers = (
        "our principal",
        "we own",
        "we lease",
        "information",
        "the company",
        "as of",
    )
    return "table of contents" in before and after.startswith(properties_body_markers)


def iter_risk_factor_starts(text: str) -> Iterable[int]:
    item_spans = list(START_RE.finditer(text))
    for match in item_spans:
        yield match.start()

    for match in RISK_HEADING_RE.finditer(text):
        if any(item.start() <= match.start() <= item.end() for item in item_spans):
            continue
        if is_probable_body_risk_heading(text, match):
            yield match.start()


def is_probable_body_risk_heading(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 120) : match.start()].lower()
    after = text[match.end() : match.end() + 700].lower()

    if has_body_start_marker(match.group(0).lower() + after):
        return True

    # Cross-references and forward-looking-statement references often mention
    # Risk Factors long before the actual section body.
    if any(marker in before for marker in REFERENCE_START_MARKERS):
        return False

    body_markers = ITEM_1A_BODY_MARKERS + (
        "the following discussion",
        "our business",
        "when any one",
        "the risks described",
        "subject to the",
    )
    return any(marker in after for marker in body_markers)


def has_body_start_marker(after: str) -> bool:
    return any(marker in after for marker in ITEM_1A_BODY_MARKERS)


def is_reference_item_1a_start(before: str, after: str) -> bool:
    if any(marker in before for marker in REFERENCE_START_MARKERS):
        return True
    if re.search(r"risk\s+factors[”\"']?\s+(?:and|in|under|or|,)", after[:120]):
        return True
    if "financial condition" in after[:250] and "management" in after[:300]:
        return True
    return False


def is_table_of_contents_item_1a_start(before: str, after: str, length: int) -> bool:
    if length < 1000:
        return True
    if "table of contents" not in before and "index" not in before[-80:]:
        return False
    if "item 1b" in after[:300] or "item 2" in after[:300]:
        return not has_body_start_marker(after)
    return False


def find_term_matches(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    spans: list[tuple[int, int, str]] = []
    for term in terms:
        pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
        spans.extend((match.start(), match.end(), term) for match in re.finditer(pattern, lowered))

    selected: list[tuple[int, int, str]] = []
    occupied_until = -1
    for start, end, term in sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start < occupied_until:
            continue
        selected.append((start, end, term))
        occupied_until = end
    return selected


def count_terms(text: str, terms: list[str]) -> tuple[int, list[str]]:
    matches = find_term_matches(text, terms)
    matched = sorted({term for _, _, term in matches}, key=terms.index)
    return len(matches), matched


def excerpts(text: str, terms: list[str], max_excerpts: int = 5, window: int = 260) -> list[str]:
    results: list[str] = []
    used_until = -1
    for start, end, _term in find_term_matches(text, terms):
        if start < used_until:
            continue
        left = max(0, start - window)
        right = min(len(text), end + window)
        snippet = text[left:right].strip()
        if left > 0:
            snippet = "..." + snippet
        if right < len(text):
            snippet += "..."
        results.append(snippet)
        used_until = right
        if len(results) >= max_excerpts:
            break
    return results


def filing_base_row(filing: Filing, firm: Firm) -> dict:
    return {
        "sample_source": "seed_firm",
        "ticker": filing.ticker,
        "company_name": filing.company_name,
        "industry_bucket": firm.industry_bucket,
        "notes": firm.notes,
        "cik": format_cik(filing.cik),
        "sic": filing.sic,
        "sic_description": filing.sic_description,
        "form": filing.form,
        "accession_number": filing.accession_number,
        "filing_date": filing.filing_date,
        "filing_year": filing.filing_year,
        "report_date": filing.report_date,
        "report_year": filing.report_year,
        "primary_document": filing.primary_document,
        "filing_url": filing.url,
        "sec_search_query": "",
        "sec_search_display_name": "",
    }


def search_filing_base_row(filing: SearchFiling, sic_description: str) -> dict:
    return {
        "sample_source": "sec_full_text_search",
        "ticker": filing.ticker,
        "company_name": filing.company_name,
        "industry_bucket": "SEC full-text search hit",
        "notes": "2025 10-K matched Liberation Day search query",
        "cik": format_cik(filing.cik),
        "sic": filing.sic,
        "sic_description": sic_description,
        "form": filing.form,
        "accession_number": filing.accession_number,
        "filing_date": filing.filing_date,
        "filing_year": filing.filing_year,
        "report_date": filing.report_date,
        "report_year": filing.report_year,
        "primary_document": filing.primary_document,
        "filing_url": filing.url,
        "sec_search_query": filing.search_query,
        "sec_search_display_name": filing.search_display_name,
    }


def add_risk_factor_fields(
    base: dict,
    risk_text: str,
    terms: list[str],
    extraction_status: str = "success",
    failure_reason: str = "",
) -> dict:
    tariff_count, matched_terms = count_terms(risk_text, terms)
    excerpt_list = excerpts(risk_text, matched_terms)
    return {
        **base,
        "extraction_status": extraction_status,
        "failure_reason": failure_reason,
        "risk_factor_chars": len(risk_text),
        "risk_factor_words": len(risk_text.split()),
        "tariff_term_count": tariff_count,
        "tariff_terms_matched": "; ".join(matched_terms),
        "tariff_excerpt_count": len(excerpt_list),
        "tariff_excerpts": " || ".join(excerpt_list),
        "risk_factor_text": risk_text,
    }


def add_dry_run_fields(base: dict) -> dict:
    return add_risk_factor_fields(
        base,
        "",
        [],
        extraction_status="not_downloaded_dry_run",
        failure_reason="dry run selected filing metadata only",
    )


def add_failure_fields(base: dict, reason: str) -> dict:
    return add_risk_factor_fields(base, "", [], extraction_status="failed", failure_reason=reason)


def extract_row_from_filing(client: SecClient, filing: Filing | SearchFiling, base: dict, terms: list[str]) -> dict:
    try:
        raw = client.get_text(
            filing.url,
            cache_name=(
                f"filings/{format_cik(filing.cik)}/"
                f"{filing.accession_nodashes}/{filing.primary_document}"
            ),
        )
        risk_text = extract_item_1a(raw)
    except (OSError, UnicodeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return add_failure_fields(base, f"{type(exc).__name__}: {exc}")

    if not risk_text:
        return add_failure_fields(base, "Item 1A Risk Factors section not found")

    return add_risk_factor_fields(base, risk_text, terms)


def build_rows(
    client: SecClient,
    firms: list[Firm],
    terms: list[str],
    start_year: int,
    end_year: int,
    date_basis: str,
    include_amended: bool,
    limit_firms: int | None,
    dry_run: bool,
) -> list[dict]:
    cik_lookup = ticker_to_cik(client)
    rows: list[dict] = []
    firms_to_process = firms[:limit_firms] if limit_firms else firms

    for firm in firms_to_process:
        ticker_entry = cik_lookup.get(firm.ticker)
        if firm.cik is not None:
            cik = firm.cik
        elif ticker_entry:
            cik = int(ticker_entry["cik_str"])
        else:
            print(f"WARNING: missing CIK for {firm.ticker}", file=sys.stderr)
            continue

        submissions = fetch_submissions(client, cik)
        filings = select_10k_filings(
            client=client,
            firm=firm,
            cik=cik,
            submissions=submissions,
            start_year=start_year,
            end_year=end_year,
            date_basis=date_basis,
            include_amended=include_amended,
        )

        for filing in filings:
            base = filing_base_row(filing, firm)

            if dry_run:
                rows.append(add_dry_run_fields(base))
                continue

            row = extract_row_from_filing(client, filing, base, terms)
            rows.append(row)
            print(
                f"{filing.ticker} {filing.filing_date} {filing.form}: "
                f"{row['extraction_status']}, {row['risk_factor_words']} words, "
                f"{row['tariff_term_count']} tariff-term hits",
                file=sys.stderr,
            )

    return rows


def build_sec_search_rows(
    client: SecClient,
    terms: list[str],
    queries: list[str],
    start_date: str,
    end_date: str,
    existing_accessions: set[str],
    required_terms: set[str],
    dry_run: bool,
) -> list[dict]:
    rows: list[dict] = []
    candidates: dict[str, SearchFiling] = {}

    for query in queries:
        hits = search_sec_filings(
            client=client,
            query=query,
            form="10-K",
            start_date=start_date,
            end_date=end_date,
        )
        print(f"SEC full-text search {query!r}: {len(hits)} candidate 10-Ks", file=sys.stderr)
        for hit in hits:
            filing = search_hit_to_filing(hit, query)
            if not filing or filing.accession_number in existing_accessions:
                continue
            candidates.setdefault(filing.accession_number, filing)

    for filing in sorted(candidates.values(), key=lambda item: (item.filing_date, item.accession_number)):
        sic_description = ""
        try:
            submissions = fetch_submissions(client, filing.cik)
            sic_description = str(submissions.get("sicDescription", "") or "")
        except (urllib.error.HTTPError, json.JSONDecodeError) as exc:
            print(f"WARNING: could not fetch submissions for CIK {filing.cik}: {exc}", file=sys.stderr)

        base = search_filing_base_row(filing, sic_description)
        if dry_run:
            rows.append(add_dry_run_fields(base))
            continue

        row = extract_row_from_filing(client, filing, base, terms)
        if row["extraction_status"] != "success":
            print(
                f"WARNING: skipping SEC full-text candidate {filing.accession_number}: "
                f"{row['failure_reason']}",
                file=sys.stderr,
            )
            existing_accessions.add(filing.accession_number)
            continue

        matched = set(row["tariff_terms_matched"].split("; ")) if row["tariff_terms_matched"] else set()
        if required_terms and not matched.intersection(required_terms):
            continue

        rows.append(row)
        existing_accessions.add(filing.accession_number)
        print(
            f"{filing.ticker or filing.cik} {filing.filing_date} {filing.form} search-hit: "
            f"{row['risk_factor_words']} words, {row['tariff_term_count']} tariff-term hits",
            file=sys.stderr,
        )

    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect 10-K Item 1A Risk Factors from SEC EDGAR."
    )
    parser.add_argument("--firms", type=Path, default=Path("config/trade_exposed_firms.csv"))
    parser.add_argument("--terms", type=Path, default=Path("config/tariff_terms.txt"))
    parser.add_argument(
        "--sec-search-queries",
        type=Path,
        default=Path("config/sec_search_queries.txt"),
        help="Full-text search queries for supplemental SEC-wide 10-K rows.",
    )
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--sec-search-start-date", default="2025-01-01")
    parser.add_argument("--sec-search-end-date", default="2026-12-31")
    parser.add_argument(
        "--date-basis",
        choices=["filing", "report"],
        default="report",
        help="Use filing date year or fiscal report date year for the year filter.",
    )
    parser.add_argument("--output", type=Path, default=Path("data/risk_factors_2022_2025.csv"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", DEFAULT_SEC_USER_AGENT))
    parser.add_argument("--max-rps", type=float, default=8.0)
    parser.add_argument("--include-amended", action="store_true")
    parser.add_argument(
        "--include-sec-search",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append SEC-wide 2025 10-K search hits that contain required exact terms in Item 1A.",
    )
    parser.add_argument("--limit-firms", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.user_agent:
        print(
            "Set SEC_USER_AGENT or pass --user-agent. Use a descriptive value with contact info, "
            f'for example: "{DEFAULT_SEC_USER_AGENT}".',
            file=sys.stderr,
        )
        return 2
    if args.max_rps > 10:
        print("SEC fair-access guidance caps automated access at 10 requests/second.", file=sys.stderr)
        return 2

    firms = read_firms(args.firms)
    terms = read_terms(args.terms)
    search_queries = read_search_queries(args.sec_search_queries)
    client = SecClient(args.user_agent, args.cache_dir, args.max_rps)
    rows = build_rows(
        client=client,
        firms=firms,
        terms=terms,
        start_year=args.start_year,
        end_year=args.end_year,
        date_basis=args.date_basis,
        include_amended=args.include_amended,
        limit_firms=args.limit_firms,
        dry_run=args.dry_run,
    )
    if args.include_sec_search and search_queries and not args.limit_firms:
        rows.extend(
            build_sec_search_rows(
                client=client,
                terms=terms,
                queries=search_queries,
                start_date=args.sec_search_start_date,
                end_date=args.sec_search_end_date,
                existing_accessions={row["accession_number"] for row in rows},
                required_terms=DEFAULT_SEARCH_REQUIRED_TERMS,
                dry_run=args.dry_run,
            )
        )
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

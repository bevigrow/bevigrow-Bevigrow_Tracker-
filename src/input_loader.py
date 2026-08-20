"""
Reads the company list.

Accepts .xlsx, .xls, .csv and .txt. Column names are matched loosely, so
"Company", "company name", "Firma" and "Name" all work.

A .txt file may simply contain one company per line in the format the brief
used:

    Benecke Coffee GmbH & Co. KG - Hamburg, Germany
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from src.logging_setup import get_logger
from src.models import CompanyInput

log = get_logger("input")

# Loose header matching: canonical field -> accepted header spellings
_HEADER_ALIASES = {
    "company": {"company", "companyname", "company name", "name", "firma", "firmenname",
                "business", "organisation", "organization", "account"},
    "city": {"city", "town", "ort", "stadt", "location", "place"},
    "country": {"country", "land", "nation"},
    "website": {"website", "web", "url", "site", "homepage", "domain", "webseite"},
    "notes": {"notes", "note", "comment", "comments", "remark", "remarks", "info"},
}


def _canonical(header: str) -> str | None:
    key = re.sub(r"[^a-z ]", "", (header or "").strip().lower())
    key_nospace = key.replace(" ", "")
    for canon, aliases in _HEADER_ALIASES.items():
        if key in aliases or key_nospace in {a.replace(" ", "") for a in aliases}:
            return canon
    return None


def _split_freeform(line: str) -> CompanyInput | None:
    """Parse 'Company Name - City, Country' (the format in the brief)."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    company, city, country = line, "", ""
    # Split on the LAST " - " so company names containing a hyphen survive.
    if " - " in line:
        company, _, place = line.rpartition(" - ")
        place = place.strip()
        if "," in place:
            city, _, country = place.partition(",")
        else:
            country = place
    return CompanyInput(
        company=company.strip(),
        city=city.strip(),
        country=country.strip(),
    )


def _rows_from_tabular(rows: list[dict]) -> list[CompanyInput]:
    companies: list[CompanyInput] = []
    for i, raw in enumerate(rows, start=2):  # row 1 is the header
        mapped: dict[str, str] = {}
        for header, value in raw.items():
            canon = _canonical(str(header))
            if canon and value is not None:
                text = str(value).strip()
                if text and text.lower() not in {"nan", "none", "null"}:
                    mapped[canon] = text

        name = mapped.get("company", "")
        if not name:
            continue

        # Someone may have pasted "Company - City, Country" into the name column.
        if not mapped.get("country") and " - " in name:
            parsed = _split_freeform(name)
            if parsed:
                mapped.setdefault("city", parsed.city)
                mapped.setdefault("country", parsed.country)
                name = parsed.company

        companies.append(
            CompanyInput(
                company=name,
                city=mapped.get("city", ""),
                country=mapped.get("country", ""),
                website=mapped.get("website", ""),
                notes=mapped.get("notes", ""),
                row_number=i,
            )
        )
    return companies


def load_companies(path: str | Path) -> list[CompanyInput]:
    """Load and de-duplicate the company list from disk."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Company list not found: {path}")

    suffix = path.suffix.lower()
    companies: list[CompanyInput]

    if suffix in {".xlsx", ".xlsm", ".xls"}:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Reading Excel needs pandas + openpyxl. Run: pip install -r requirements.txt"
            ) from exc
        frame = pd.read_excel(path, dtype=str).fillna("")
        companies = _rows_from_tabular(frame.to_dict("records"))

    elif suffix == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(fh, dialect=dialect)
            companies = _rows_from_tabular(list(reader))

    else:  # .txt or anything else: one company per line
        companies = []
        with open(path, "r", encoding="utf-8") as fh:
            for n, line in enumerate(fh, start=1):
                parsed = _split_freeform(line)
                if parsed:
                    parsed.row_number = n
                    companies.append(parsed)

    # De-duplicate inside the file itself (same name twice = one outreach).
    from src.utils import company_key

    seen: set[str] = set()
    deduped: list[CompanyInput] = []
    for c in companies:
        key = company_key(c.company)
        if key in seen:
            log.warning("Duplicate row in input file skipped: %s", c.company)
            continue
        seen.add(key)
        deduped.append(c)

    log.info("Loaded %d companies from %s", len(deduped), path.name)
    return deduped


def write_sample_csv(path: Path) -> None:
    """Create the starter companies.csv so there is always something to run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Company", "City", "Country", "Website", "Notes"])
        writer.writerow(
            ["Benecke Coffee GmbH & Co. KG", "Hamburg", "Germany", "", "Example row - replace"]
        )

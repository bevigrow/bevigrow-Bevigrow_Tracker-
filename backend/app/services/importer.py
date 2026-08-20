"""Turn an uploaded company file into a sending queue.

Three jobs, in order: read whatever columns the file happens to have, split
cells that hold more than one address, and collapse what is genuinely the same
address twice.

The guiding rule is that nothing is invented and nothing is silently dropped. A
blank website stays blank. A row that cannot be emailed is kept in the queue
marked `skipped` with the reason written on it, because a company that
disappears between the spreadsheet and the screen is a company you will spend
an afternoon looking for.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field

from .geo import tidy

log = logging.getLogger("bevigrow.import")

# Deliberately permissive. This decides "is this an address at all", not "will
# it accept mail" — only the mail server knows that, and a rule strict enough
# to argue with a real address is worse than one that lets it through.
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")

# One cell, several addresses: "info@x.com; sales@x.com" or comma/pipe/newline.
ADDRESS_SPLIT = re.compile(r"[;,|/\n\r\t]+| {2,}")

# Legal-entity suffixes, removed only when comparing two names.
_SUFFIXES = {
    "gmbh", "ltd", "limited", "llc", "inc", "incorporated", "bv", "b.v", "nv",
    "srl", "sarl", "sa", "ag", "as", "aps", "oy", "ab", "plc", "pty", "pte",
    "co", "corp", "corporation", "company", "kk", "kabushiki", "llp", "lp",
    "gk", "sl", "spa", "s.p.a", "kg", "ug", "ou", "sro", "doo", "dmcc", "fzco",
    "fze", "trading", "trade",
}

_PUNCT = re.compile(r"[^\w\s]")


def normalize_company(raw: str | None) -> str:
    """Comparison key for a company name.

    Punctuation, case and legal suffixes are noise when deciding whether two
    rows are the same business: "ABC Coffee GmbH", "ABC Coffee, GmbH." and "abc
    coffee" all reduce to `abc coffee`. The original spelling is kept on the
    row — this is only ever the key.
    """
    text = _PUNCT.sub(" ", tidy(raw)).casefold()
    words = [w for w in text.split() if w and w not in _SUFFIXES]
    return " ".join(words) or text.strip()


def normalize_email(raw: str | None) -> str:
    return tidy(raw).casefold()


def domain_of(email: str | None, website: str | None = None) -> str | None:
    """The domain to compare on: from the address first, the website second."""
    if email and "@" in email:
        return email.rsplit("@", 1)[-1].strip().casefold() or None
    if website:
        host = tidy(website).casefold()
        host = re.sub(r"^https?://", "", host)
        host = host.split("/")[0].strip()
        host = re.sub(r"^www\.", "", host)
        return host or None
    return None


# --------------------------------------------------------------- the columns


# Every spelling of a heading seen in the wild, mapped to the field it means.
# Matching is on a normalised header, so "Company Name", "company_name" and
# "COMPANY-NAME" all arrive here as "company name".
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "company_name": (
        "company", "company name", "companyname", "name", "business",
        "business name", "organisation", "organization", "firm", "roaster",
        "importer", "buyer", "supplier", "account",
    ),
    "email": (
        "email", "e mail", "email address", "emails", "mail", "contact email",
        "email 1", "email 2", "email 3", "primary email", "secondary email",
        "alt email", "alternate email", "info email", "general email",
    ),
    "website": ("website", "web", "url", "site", "web address", "webpage", "homepage", "domain"),
    "country": ("country", "nation", "market"),
    "location": ("location", "city", "address", "region", "state", "town", "province"),
    "contact_person": (
        "contact person", "contact", "person", "contact name", "owner",
        "manager", "director", "full name", "first name",
    ),
    "linkedin": ("linkedin", "linked in", "linkedin url", "linkedin profile"),
    "contact_form": ("contact form", "form", "contact page", "contact url", "enquiry form"),
    "phone": (
        "phone", "telephone", "tel", "mobile", "whatsapp", "phone number",
        "contact number", "cell",
    ),
    "category": ("category", "type", "segment", "industry", "business type", "specialty"),
}

_HEADER_CLEAN = re.compile(r"[^a-z0-9]+")


def _normalize_header(raw: str) -> str:
    return _HEADER_CLEAN.sub(" ", (raw or "").strip().casefold()).strip()


def map_headers(headers: list[str]) -> dict[int, str]:
    """Which column means what. Unrecognised columns are kept, not discarded.

    Returns {column index -> field name}. A column that matches nothing maps to
    `extra:<original heading>` and is stored as JSON on the row: the file's
    author put it there deliberately, and the template may well reference it.
    """
    lookup: dict[str, str] = {}
    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            lookup[alias] = field_name

    mapping: dict[int, str] = {}
    for index, header in enumerate(headers):
        key = _normalize_header(header)
        if not key:
            continue
        if key in lookup:
            mapping[index] = lookup[key]
            continue
        # "email 2", "work email", "company website" — a heading that contains
        # a known one. Longest alias wins so "contact email" beats "contact".
        hit = max(
            (alias for alias in lookup if alias in key),
            key=len,
            default=None,
        )
        mapping[index] = lookup[hit] if hit else f"extra:{tidy(header)}"
    return mapping


# ------------------------------------------------------------------ the rows


@dataclass
class ParsedRow:
    """One address, ready to become a queue entry."""

    position: int
    company_name: str
    email: str | None = None
    contact_person: str | None = None
    website: str | None = None
    country: str | None = None
    location: str | None = None
    linkedin: str | None = None
    contact_form: str | None = None
    phone: str | None = None
    category: str | None = None
    extra: dict[str, str] = field(default_factory=dict)
    skip_reason: str | None = None
    # What counts as "the same company" for grouping: the mail domain when
    # there is one, the normalised name otherwise. Set by the parser, because
    # it depends on the other rows around this one.
    group_key: str = ""

    @property
    def normalized_company(self) -> str:
        return self.group_key or normalize_company(self.company_name)

    @property
    def normalized_email(self) -> str:
        return normalize_email(self.email)

    @property
    def domain(self) -> str | None:
        return domain_of(self.email, self.website)


@dataclass
class ImportReport:
    """What the file turned into, in the words the summary will use."""

    rows: list[ParsedRow] = field(default_factory=list)
    file_rows: int = 0
    addresses: int = 0
    companies: int = 0
    multi_address_companies: int = 0
    duplicate_addresses: int = 0
    without_email: int = 0
    invalid_emails: int = 0
    possible_duplicates: list[str] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)


def _read_table(data: bytes, filename: str) -> tuple[list[str], list[list[str]]]:
    """Headers and rows from CSV or XLSX, without touching the filesystem."""
    name = (filename or "").lower()

    if name.endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ValueError(
                "This build cannot read .xlsx files. Save the sheet as CSV and upload that."
            ) from exc
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheet = book.active
        rows = [
            ["" if cell is None else str(cell) for cell in row]
            for row in sheet.iter_rows(values_only=True)
        ]
        book.close()
        if not rows:
            return [], []
        return rows[0], rows[1:]

    # CSV, in whatever encoding a spreadsheet exported. utf-8-sig first because
    # Excel writes a byte-order mark that otherwise becomes part of the first
    # heading, and "﻿Company" matches no alias at all.
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Could not read that file as text. Save it as UTF-8 CSV.")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = list(csv.reader(io.StringIO(text), dialect))
    if not reader:
        return [], []
    return reader[0], reader[1:]


def _addresses_in(cell: str) -> list[str]:
    """Every address in one cell, in order, without repeats."""
    found: list[str] = []
    for piece in ADDRESS_SPLIT.split(cell or ""):
        candidate = tidy(piece).strip("<>()[]\"' ")
        if not candidate:
            continue
        if EMAIL_RE.match(candidate):
            key = candidate.casefold()
            if key not in {f.casefold() for f in found}:
                found.append(candidate)
    return found


def parse(data: bytes, filename: str) -> ImportReport:
    """Read the file into queue rows — one per address.

    A company with three mailboxes becomes three rows sharing a company key, so
    each gets its own email, its own result and its own line in the log, while
    the summary can still say "three addresses at one company".
    """
    headers, raw_rows = _read_table(data, filename)
    if not headers:
        raise ValueError("That file has no header row.")

    mapping = map_headers(headers)
    report = ImportReport()
    report.unmapped_columns = sorted(
        {v.split(":", 1)[1] for v in mapping.values() if v.startswith("extra:")}
    )

    seen_addresses: dict[str, str] = {}          # address -> the group that claimed it
    group_addresses: dict[str, set[str]] = {}    # group key -> its addresses
    names_by_norm: dict[str, set[str]] = {}      # normalised name -> spellings seen
    groups_by_norm: dict[str, set[str]] = {}     # normalised name -> group keys
    position = 0

    for raw in raw_rows:
        values = {"extra": {}}
        emails: list[str] = []
        for index, cell in enumerate(raw):
            field_name = mapping.get(index)
            if not field_name:
                continue
            text = tidy(str(cell)) if cell is not None else ""
            if not text:
                continue
            if field_name == "email":
                emails.extend(_addresses_in(text))
            elif field_name.startswith("extra:"):
                values["extra"][field_name.split(":", 1)[1]] = text
            else:
                values[field_name] = text

        company = values.get("company_name") or ""
        if not company and not emails and not values.get("website"):
            continue  # a blank line in the sheet, not a company
        report.file_rows += 1
        if not company:
            # Filed under something findable rather than refused.
            company = values.get("website") or (emails[0] if emails else "Unnamed company")

        # A company, for grouping purposes, is its mail domain.
        #
        # Grouping by name alone merged "ABC Coffee" in Japan with "ABC Coffee
        # GmbH" in Germany — same words after the legal suffix comes off, two
        # unrelated businesses on two domains. Grouping by domain keeps them
        # apart and still gathers info@ and sales@ at the same firm, whichever
        # way the name was typed on each row.
        norm = normalize_company(company)
        group = domain_of(emails[0] if emails else None, values.get("website")) or norm
        names_by_norm.setdefault(norm, set()).add(company)
        groups_by_norm.setdefault(norm, set()).add(group)
        group_addresses.setdefault(group, set())

        # Addresses that are not addresses: kept, marked, never sent to.
        raw_email_cells = [
            tidy(str(raw[i])) for i, f in mapping.items() if f == "email" and i < len(raw) and raw[i]
        ]
        junk = [c for c in raw_email_cells if c and not _addresses_in(c)]
        if junk:
            report.invalid_emails += 1

        # One place that builds a row, so the two branches below cannot drift.
        def build(email: str | None, skip_reason: str | None = None) -> ParsedRow:
            nonlocal position
            position += 1
            return ParsedRow(
                position=position,
                company_name=company,
                email=email,
                skip_reason=skip_reason,
                contact_person=values.get("contact_person"),
                website=values.get("website"),
                country=values.get("country"),
                location=values.get("location"),
                linkedin=values.get("linkedin"),
                contact_form=values.get("contact_form"),
                phone=values.get("phone"),
                category=values.get("category"),
                extra=dict(values["extra"]),
                group_key=group,
            )

        if not emails:
            report.rows.append(
                build(
                    None,
                    skip_reason=(
                        f"No usable email address in the file (found {junk[0]!r})"
                        if junk
                        else "No email address in the file"
                    ),
                )
            )
            report.without_email += 1
            continue

        for address in emails:
            folded = address.casefold()
            if folded in seen_addresses:
                # The same mailbox twice — in one row, or two rows apart. One
                # mailbox gets one message however many times it is listed.
                report.duplicate_addresses += 1
                continue
            seen_addresses[folded] = group
            group_addresses[group].add(folded)
            report.rows.append(build(address))

    report.addresses = sum(1 for r in report.rows if r.email)
    report.companies = len(group_addresses)
    report.multi_address_companies = sum(1 for v in group_addresses.values() if len(v) > 1)

    # Names that read as the same business but sit on different domains.
    # Reported, never merged: "ABC Coffee" and "ABC Coffee GmbH" may be one
    # firm with two sites or two firms with similar names, and only a person
    # knows which. Guessing wrong either double-sends or drops a customer, so
    # both are queued and the pair is put in front of you instead.
    for norm, groups in groups_by_norm.items():
        if len(groups) > 1:
            spellings = sorted(names_by_norm.get(norm, {norm}))
            report.possible_duplicates.append(
                f"{' / '.join(spellings)}  ({', '.join(sorted(groups))})"
            )

    return report

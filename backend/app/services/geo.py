"""Country names as people actually type them.

Country is free text everywhere in this app, deliberately: a marketplace RFQ
says "Dubai" where the shipping document says "United Arab Emirates", and
refusing either spelling would lose the enquiry. The cost is that one place
arrives written several ways — "japan", "Japan ", "JAPAN" — and a GROUP BY on
the raw column files those as three separate countries, each with a third of
the real number.

Everything that counts or lists countries goes through here so those land in
one bucket, labelled with the spelling most records actually use.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

_SPACES = re.compile(r"\s+")

UNKNOWN = "Unknown"


def tidy(raw: str | None) -> str:
    """The spelling as written, minus padding and doubled spaces."""
    return _SPACES.sub(" ", (raw or "").strip())


def canon(raw: str | None) -> str:
    """Comparison key: case and spacing are not differences between countries."""
    return tidy(raw).casefold()


@dataclass
class CountryRow:
    label: str
    quotes: int = 0
    prospects: int = 0
    value_usd: float = 0.0

    @property
    def total(self) -> int:
        return self.quotes + self.prospects


@dataclass
class CountryTally:
    """Accumulates per-country numbers under one canonical key.

    Callers add rows in whatever spelling the database holds. The label that
    comes back is the spelling behind the most records, so a single stray
    "japan" cannot rename Japan.
    """

    _rows: dict[str, CountryRow] = field(default_factory=dict)
    _spellings: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))

    def add(
        self,
        raw: str | None,
        *,
        quotes: int = 0,
        prospects: int = 0,
        value_usd: float = 0.0,
    ) -> None:
        key = canon(raw)
        row = self._rows.setdefault(key, CountryRow(label=UNKNOWN if not key else tidy(raw)))
        if key:
            self._spellings[key][tidy(raw)] += (quotes + prospects) or 1
        row.quotes += quotes
        row.prospects += prospects
        row.value_usd += value_usd

    def rows(self, *, include_unknown: bool = True) -> list[CountryRow]:
        out: list[CountryRow] = []
        for key, row in self._rows.items():
            if not key:
                if not include_unknown:
                    continue
            else:
                row.label = self._spellings[key].most_common(1)[0][0]
            out.append(row)
        out.sort(key=lambda r: (-r.total, r.label.casefold()))
        return out

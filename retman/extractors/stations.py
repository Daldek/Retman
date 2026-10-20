"""Stations named in a command, read against the offline IMGW station catalog.

Station codes are recognised by their shape and need no catalog. Names are
matched against the catalog the tool keeps in its store (``stations find`` with
``source=store``, an offline lookup), tolerating Polish inflection ("w Poznaniu",
"z Opola", "Nysie Kłodzkiej"). Inflected names are never accepted silently:
Retman asks the user to confirm them (ARCHITECTURE 6.1, W-02). The module imports
no tool; the catalog arrives through ``ExtractionContext.lookup``.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from retman.exceptions import RetmanError
from retman.extractors.base import ExtractionContext, Hint, Match, Reading, TextSource
from retman.extractors.text import Word, fold, words

# More candidates than a question can list: the user must narrow the name down.
MAX_CANDIDATES = 9

# Key of ``ExtractionContext.memo`` under which the loaded ``StationIndex`` is kept.
# A test or ``retman-eval`` may put a prepared index there instead of serving a
# ``stations find`` document through ``ctx.lookup``.
STATION_INDEX_KEY = "imgw_station_index"
# Tool error codes meaning "there is no station catalog (yet)", as opposed to
# a catalog that exists but cannot be read.
_NO_CATALOG_CODES = frozenset({"not_found", "store_unavailable"})

# A code is not part of a longer number (nor of a decimal such as "52.123456789").
_IMGW_CODE_RE = re.compile(r"(?<!\d)(?<!\d[.,])[0-9]{9}(?!\d)(?![.,]\d)")
_WIGOS_CODE_RE = re.compile(
    r"(?<![\w-])0-[0-9]{1,5}-[0-9]{1,5}-[0-9A-Za-z]{1,16}(?![\w-])"
)
_IMGW_CODE_FULL_RE = re.compile(r"[0-9]{9}")
_WIGOS_CODE_FULL_RE = re.compile(r"0-[0-9]{1,5}-[0-9]{1,5}-[0-9A-Z]{1,16}")

PROVIDER_IMGW = "IMGW-PIB"
PROVIDER_CHMI = "CHMI"

# Polish noun and adjective endings (folded); each one that leaves at least three
# letters gives a stem an inflected form of the name may start with.
_ENDINGS = ("iem", "owi", "ach", "ie", "iu", "ia", "a", "e", "y", "i", "u", "o")
# Consonant alternations of the locative ("Warta" - "w Warcie", "Odra" - "Odrze").
_SOFTENED = (
    ("ch", "sz"),
    ("t", "c"),
    ("d", "dz"),
    ("r", "rz"),
    ("k", "c"),
    ("g", "dz"),
)
_MIN_STEM = 3
_MIN_INFLECTED_NAME = 4  # shorter names match exactly only
_MAX_EXTRA_LETTERS = 4  # letters an inflected form may add to the stem

_EXACT = 2
_INFLECTED = 1


@dataclass(frozen=True)
class StationEntry:
    """
    One station of the catalog.

    Parameters
    ----------
    provider : str
        ``"IMGW-PIB"`` or ``"CHMI"`` (the tool's provider identifiers).
    kind : str
        ``"hydro"`` or ``"meteo"``.
    code : str
        Station code: 9 digits (IMGW-PIB) or a WIGOS identifier (CHMI).
    name : str
        Station name as the provider writes it.
    river : str or None
        River of a hydrological station.
    """

    provider: str
    kind: str
    code: str
    name: str
    river: str | None = None
    name_words: tuple[str, ...] = field(default=(), compare=False, repr=False)
    river_words: tuple[str, ...] = field(default=(), compare=False, repr=False)

    @classmethod
    def of(
        cls, provider: str, kind: str, code: str, name: str, river: str | None = None
    ) -> "StationEntry":
        """Entry with the folded words of the name and the river filled in."""
        return cls(
            provider,
            kind,
            code,
            name,
            river,
            tuple(word.text for word in words(fold(name))),
            tuple(word.text for word in words(fold(river))) if river else (),
        )


class StationIndex:
    """
    The station catalog as the extractors see it.

    Parameters
    ----------
    entries : Iterable[StationEntry]
        Stations of the catalog.
    reason : str, optional
        Why the catalog is empty: ``"no_catalog"`` (never built) or
        ``"unreadable"`` (the tool could not read it); ``None`` for a usable one.
    """

    def __init__(
        self, entries: Iterable[StationEntry] = (), reason: str | None = None
    ) -> None:
        self.entries = tuple(entries)
        self.reason = reason if not self.entries else None
        if not self.entries and self.reason is None:
            self.reason = "no_catalog"
        self._by_code = {entry.code: entry for entry in self.entries}
        self._by_first_word: dict[str, list[StationEntry]] = {}
        for entry in self.entries:
            if entry.name_words:
                self._by_first_word.setdefault(entry.name_words[0], []).append(entry)

    def __len__(self) -> int:
        return len(self.entries)

    def by_code(self, code: str) -> StationEntry | None:
        """Station with the given code, if the catalog has it."""
        return self._by_code.get(code)

    def starting_with(self, word: str) -> list[StationEntry]:
        """Stations whose first name word (folded) is ``word`` or an inflected form."""
        found: list[StationEntry] = []
        for first, entries in self._by_first_word.items():
            if _word_match(first, word):
                found.extend(entries)
        return found

    @classmethod
    def from_entries(
        cls, items: Iterable[Mapping[str, Any]], reason: str | None = None
    ) -> "StationIndex":
        """
        Index of the items of a ``stations find`` document (or the same dicts).

        Items without a name or a code are skipped. ``station_code`` is the
        tool's key, ``code`` is accepted too.
        """
        entries = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            code = item.get("station_code", item.get("code"))
            name = item.get("name")
            provider = item.get("provider")
            kind = item.get("kind")
            if not all(isinstance(v, str) and v for v in (code, name, provider, kind)):
                continue
            river = item.get("river")
            entries.append(
                StationEntry.of(
                    str(provider),
                    str(kind),
                    str(code),
                    str(name),
                    river if isinstance(river, str) and river else None,
                )
            )
        return cls(entries, reason)

    @classmethod
    def load(cls, ctx: ExtractionContext) -> "StationIndex":
        """
        Catalog read through ``ctx.lookup`` (offline), cached in ``ctx.memo``.

        A missing store or catalog and an unreadable one give an empty index
        with ``reason`` ``"no_catalog"`` or ``"unreadable"``; planning goes on
        with codes only.
        """
        cached = ctx.memo.get(STATION_INDEX_KEY)
        if isinstance(cached, StationIndex):
            return cached
        index = cls._read(ctx)
        ctx.memo[STATION_INDEX_KEY] = index
        return index

    @classmethod
    def _read(cls, ctx: ExtractionContext) -> "StationIndex":
        # Imported here: the adapters package imports the registry, which
        # imports the extractors.
        from retman.adapters.catalog import CatalogCall

        try:
            document = ctx.lookup(CatalogCall("stations find", {"source": "store"}))
        except RetmanError as err:
            code = getattr(err, "code", None)
            return cls((), "no_catalog" if code in _NO_CATALOG_CODES else "unreadable")
        result = document.get("result") if isinstance(document, Mapping) else None
        items = result.get("items") if isinstance(result, Mapping) else None
        if not isinstance(items, list):
            return cls((), "unreadable")
        return cls.from_entries(items)


@lru_cache(maxsize=4096)
def _stems(word: str) -> tuple[str, ...]:
    """Stems an inflected form of the (folded) name word may start with."""
    stems = {word}
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
            stems.add(word[: -len(ending)])
    for stem in tuple(stems):
        # A fleeting "e": "Mielec" - "w Mielcu", "Kamieniec" - "z Kamieńca"
        if stem.endswith(("ec", "ek")) and len(stem) - 2 >= _MIN_STEM:
            stems.add(stem[:-2] + stem[-1])
        if stem.endswith("iec") and len(stem) - 3 >= _MIN_STEM:
            stems.add(stem[:-3] + "c")
        for plain, soft in _SOFTENED:
            if stem.endswith(plain) and len(stem) - len(plain) >= _MIN_STEM - 1:
                stems.add(stem[: -len(plain)] + soft)
    return tuple(stems)


def _word_match(name_word: str, text_word: str) -> int:
    """``_EXACT``, ``_INFLECTED`` or 0: how a word of the text matches a name word."""
    if text_word == name_word:
        return _EXACT
    if len(name_word) < _MIN_INFLECTED_NAME:
        return 0
    for stem in _stems(name_word):
        if (
            len(stem) >= _MIN_STEM
            and text_word.startswith(stem)
            and len(text_word) - len(stem) <= _MAX_EXTRA_LETTERS
        ):
            return _INFLECTED
    return 0


@dataclass(frozen=True)
class _Hit:
    entry: StationEntry
    first: int  # index of the first word of the name in the text
    last: int  # index of the last word of the name in the text
    score: int  # matched name words plus matched river words
    exact: bool  # every matched word is written exactly as in the catalog
    anchor_exact: bool  # the first name word is written exactly as in the catalog
    used: frozenset[int]  # indices of the words that name the station or its river

    @property
    def rank(self) -> tuple[int, bool]:
        return (self.score, self.exact)


def _hit(entry: StationEntry, text_words: list[Word], first: int) -> _Hit | None:
    """How well the text, starting at word ``first``, names the station."""
    first_match = _word_match(entry.name_words[0], text_words[first].text)
    if not first_match:
        return None
    exact = first_match == _EXACT
    used = [first]
    for name_word in entry.name_words[1:]:
        following = used[-1] + 1
        if following >= len(text_words):
            break
        matched = _word_match(name_word, text_words[following].text)
        if not matched:
            break
        exact = exact and matched == _EXACT
        used.append(following)
    last = used[-1]
    score = len(used)
    # The river tells stations of one name apart ("Brzeg na Odrze"); it needs
    # words of its own, not the ones that already matched the name.
    free = [i for i in range(len(text_words)) if i not in used]
    for river_word in entry.river_words:
        for i in free:
            matched = _word_match(river_word, text_words[i].text)
            if matched:
                exact = exact and matched == _EXACT
                score += 1
                used.append(i)
                free.remove(i)
                break
    return _Hit(
        entry, first, last, score, exact, first_match == _EXACT, frozenset(used)
    )


def _in_scope(entry: StationEntry, scope: Mapping[str, Any]) -> bool:
    provider = scope.get("provider")
    kind = scope.get("kind")
    return (not provider or entry.provider == provider) and (
        not kind or entry.kind == kind
    )


def _station_value(entry: StationEntry) -> dict[str, Any]:
    return {
        "type": "station",
        "provider": entry.provider,
        "kind": entry.kind,
        "code": entry.code,
        "name": entry.name,
        "river": entry.river,
        "in_catalog": True,
    }


def _code_value(code: str, provider: str) -> dict[str, Any]:
    return {
        "type": "station",
        "provider": provider,
        "kind": None,
        "code": code,
        "name": None,
        "river": None,
        "in_catalog": False,
    }


def _entry_reading(entry: StationEntry) -> Reading:
    args = {
        "name": entry.name,
        "provider": entry.provider,
        "code": entry.code,
        "river": entry.river or "",
    }
    if entry.kind == "hydro":
        key = "hydro_river" if entry.river else "hydro"
    else:
        key = "meteo"
    return Reading(_station_value(entry), f"extractors.station.{key}", args)


def _code_reading(code: str, provider: str, index: StationIndex) -> Reading:
    entry = index.by_code(code)
    if entry is not None:
        return _entry_reading(entry)
    return Reading(
        _code_value(code, provider),
        "extractors.station.code_only",
        {"code": code, "provider": provider},
    )


def _code_matches(text: str, index: StationIndex) -> list[Match]:
    found = []
    for pattern, provider, normalize in (
        (_IMGW_CODE_RE, PROVIDER_IMGW, str),
        (_WIGOS_CODE_RE, PROVIDER_CHMI, str.upper),
    ):
        for hit in pattern.finditer(text):
            code = normalize(hit.group())
            found.append(
                Match(
                    hit.start(),
                    hit.end(),
                    (_code_reading(code, provider, index),),
                )
            )
    return found


def _name_matches(
    text: str, index: StationIndex, scope: Mapping[str, Any]
) -> list[Match]:
    text_words = words(fold(text))
    if not text_words or not index.entries:
        return []
    written = [text[word.start : word.end] for word in text_words]
    # Proper names are capitalised when the command is. A lowercase word of a
    # command that capitalises other words ("nowe dane ze stacji Poznań") is
    # not a station name; one typed entirely in lowercase offers no such hint.
    # Acronyms (IMGW, POT) do not count as capitalisation.
    capitalised = any(
        word[:1].isupper() and any(c.islower() for c in word[1:])
        for word in written[1:]
    )
    groups: list[list[_Hit]] = []
    for position, text_word in enumerate(text_words):
        if len(text_word.text) < _MIN_STEM or text_word.text.isdigit():
            continue
        if capitalised and not written[position][:1].isupper():
            continue
        hits = [
            hit
            for entry in index.starting_with(text_word.text)
            if _in_scope(entry, scope)
            if (hit := _hit(entry, text_words, position)) is not None
            # The first word of a command is a verb or a capitalised noun:
            # only its exact spelling counts as a station name
            if hit.anchor_exact or position > 0
        ]
        if hits:
            best = max(hit.rank for hit in hits)
            groups.append([hit for hit in hits if hit.rank == best])
    # Words belong to the best-scoring name only ("Poznań-Ławica" is not also
    # a station called "Ławica")
    groups.sort(key=lambda g: (-g[0].score, not g[0].exact, g[0].first))
    taken: set[int] = set()
    chosen: list[list[_Hit]] = []
    for group in groups:
        used = frozenset().union(*(hit.used for hit in group))
        if used & taken:
            continue
        taken |= used
        chosen.append(group)
    matches = []
    for group in sorted(chosen, key=lambda g: g[0].first):
        start = text_words[group[0].first].start
        end = text_words[max(hit.last for hit in group)].end
        entries = sorted(
            {hit.entry for hit in group}, key=lambda e: (e.name, e.kind, e.code)
        )
        if len(entries) > MAX_CANDIDATES:
            reading = Reading(
                {"type": "station", "code": None, "candidates": len(entries)},
                "extractors.station.too_many",
                {"count": str(len(entries))},
            )
            matches.append(Match(start, end, (reading,)))
            continue
        matches.append(
            Match(
                start,
                end,
                tuple(_entry_reading(entry) for entry in entries),
                confirm=not group[0].exact,
            )
        )
    return matches


def extract_station(text: str, ctx: ExtractionContext) -> list[Match]:
    """
    Stations named in the command: by code, or by name against the catalog.

    * A 9-digit IMGW-PIB code or a WIGOS identifier (ČHMÚ) is read by its shape;
      a code the catalog does not know is accepted and marked as outside the
      catalog.
    * A name is matched word by word against the catalog (folded, so without
      Polish letters it works too), narrowed to ``ctx.scope`` ``provider`` and
      ``kind`` when the dataset is known. The best-scoring stations of one place
      in the text form one match: several stations mean a question, and so does
      any inflected-only match (``Match.confirm``). More than
      ``MAX_CANDIDATES`` stations give a reading the validator rejects with a
      request for a more exact name.
    * Without a catalog only codes are read (see ``explain_station``).

    Parameters
    ----------
    text : str
        Command or answer.
    ctx : ExtractionContext
        Supplies the catalog (``lookup``) and the dataset scope.

    Returns
    -------
    list[Match]
        Spans in order of appearance.

    Examples
    --------
    >>> from datetime import date
    >>> from pathlib import Path
    >>> index = StationIndex.from_entries(
    ...     [{"station_code": "352160330", "name": "POZNAŃ-ŁAWICA",
    ...       "kind": "meteo", "provider": "IMGW-PIB"}]
    ... )
    >>> ctx = ExtractionContext(
    ...     tool="imgwtools", settings={}, project_dir=Path("."), scope={},
    ...     lookup=lambda call: {}, today=date(2026, 10, 19),
    ...     memo={STATION_INDEX_KEY: index},
    ... )
    >>> match = extract_station("opady ze stacji Poznań-Ławica", ctx)[0]
    >>> match.readings[0].value["code"], match.confirm
    ('352160330', False)
    """
    index = StationIndex.load(ctx)
    codes = _code_matches(text, index)
    names = [
        match
        for match in _name_matches(text, index, ctx.scope)
        # The same station named twice ("Poznań, kod 352160330") is one station
        if not any(
            code.start < match.end
            and match.start < code.end
            or any(
                reading.value.get("code") == code.readings[0].value.get("code")
                for reading in match.readings
            )
            for code in codes
        )
    ]
    return sorted(codes + names, key=lambda match: match.start)


def validate_station(value: Any, ctx: ExtractionContext) -> str | None:
    """Translation key of the problem with a station value, or None."""
    if not isinstance(value, dict) or value.get("type") != "station":
        return "extractors.errors.invalid_station"
    code = value.get("code")
    if code is None and isinstance(value.get("candidates"), int):
        return "extractors.errors.station_too_many"
    provider = value.get("provider")
    if not isinstance(code, str) or provider not in (PROVIDER_IMGW, PROVIDER_CHMI):
        return "extractors.errors.invalid_station"
    pattern = _IMGW_CODE_FULL_RE if provider == PROVIDER_IMGW else _WIGOS_CODE_FULL_RE
    if not pattern.fullmatch(code):
        return "extractors.errors.invalid_station"
    scope_provider = ctx.scope.get("provider")
    if scope_provider and scope_provider != provider:
        return "extractors.errors.station_wrong_provider"
    kind = value.get("kind")
    scope_kind = ctx.scope.get("kind")
    if scope_kind and kind and scope_kind != kind:
        return "extractors.errors.station_wrong_kind"
    return None


def explain_station(text: str, ctx: ExtractionContext) -> Hint | None:
    """Why a required station got no reading: the catalog is missing or unreadable."""
    reason = StationIndex.load(ctx).reason
    if reason == "no_catalog":
        return Hint("extractors.hints.station_no_catalog")
    if reason == "unreadable":
        return Hint("extractors.hints.station_catalog_unreadable")
    return None


def describe_station(value: Mapping[str, Any], texts: TextSource) -> str:
    """Plan text of a station value."""
    code = str(value.get("code"))
    provider = str(value.get("provider"))
    if not value.get("in_catalog"):
        return texts.get(
            "extractors.display.station_code", code=code, provider=provider
        )
    kind = "hydro" if value.get("kind") == "hydro" else "meteo"
    return texts.get(
        f"extractors.display.station_{kind}",
        name=str(value.get("name")),
        provider=provider,
        code=code,
    )

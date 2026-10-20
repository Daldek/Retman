"""Measured variables named in a command, checked against the chosen dataset.

IMGWTools exports the variables of one dataset: hydrological ``H`` (water level),
``Q`` (discharge), ``T`` (water temperature), their monthly ``_min/_mean/_max``
forms, and the meteorological ``P``, ``Tmax``, ``Tmin``, ``Tmean``, ``Tground``,
``snow_cover``, ``fresh_snow``. A command names them by code or by Polish words
("przepływ", "stan wody", "temperatura maksymalna"). The dataset the user chose
(``ctx.scope["variables"]``) decides which codes exist: a word that fits several
variables of the dataset is a question, and a variable the dataset does not have
is reported by the validator instead of being dropped.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from retman.exceptions import TranslationError
from retman.extractors.base import ExtractionContext, Match, Reading, TextSource
from retman.extractors.text import fold, words

# Codes the IMGW datasets use (imgwtools.datasets()); the dataset's own list in
# the scope takes precedence, so a new variable needs no change here.
KNOWN_VARIABLES = (
    "H",
    "Q",
    "T",
    "H_min",
    "H_mean",
    "H_max",
    "Q_min",
    "Q_mean",
    "Q_max",
    "T_min",
    "T_mean",
    "T_max",
    "P",
    "Tmax",
    "Tmin",
    "Tmean",
    "Tground",
    "snow_cover",
    "fresh_snow",
)


@dataclass(frozen=True)
class _Family:
    """Variables a Polish name may stand for.

    ``base`` are the codes without a statistic; ``by_statistic`` the codes a
    statistic word ("minimalny", "średni", "maksymalny") narrows them to.
    """

    base: tuple[str, ...]
    by_statistic: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def wanted(self, statistic: str | None) -> tuple[str, ...]:
        if statistic is not None and statistic in self.by_statistic:
            return self.by_statistic[statistic]
        every = self.base + tuple(
            c for codes in self.by_statistic.values() for c in codes
        )
        return tuple(dict.fromkeys(every))


def _stages(letter: str) -> _Family:
    return _Family(
        (letter,),
        {stat: (f"{letter}_{stat}",) for stat in ("min", "mean", "max")},
    )


_FAMILIES: dict[str, _Family] = {
    "stage": _stages("H"),
    "discharge": _stages("Q"),
    "water_temperature": _stages("T"),
    "temperature": _Family(
        ("Tmax", "Tmin", "Tmean", "Tground", "T"),
        {
            "min": ("Tmin", "T_min"),
            "mean": ("Tmean", "T_mean"),
            "max": ("Tmax", "T_max"),
        },
    ),
    "ground": _Family(("Tground",)),
    "precipitation": _Family(("P",)),
    "snow": _Family(("snow_cover", "fresh_snow")),
    "snow_cover": _Family(("snow_cover",)),
    "fresh_snow": _Family(("fresh_snow",)),
}
# Name phrases (folded regex) and the family each stands for; specific phrases
# come before the general words they contain ("temperatura wody" before
# "temperatura"). Statistic words next to the name narrow the family. Only the
# nouns count: "stacje opadowe" names a network, not the variable "opad".
_NAMES = (
    (r"temperatur\w*\s+przygruntow\w*|przygruntow\w*\s+temperatur\w*", "ground"),
    (r"temperatur\w*\s+wod\w*|temp\w*\.?\s+wod\w*", "water_temperature"),
    (r"stan(?:y|ow|ie|u|em)?\s+wod\w*|poziom\w*\s+wod\w*|wodostan\w*", "stage"),
    (r"przeplyw(?:y|u|ow|ach|ami|om|em)?(?!\w)", "discharge"),
    (r"swiez\w*\s+snieg\w*|przyrost\w*\s+snieg\w*", "fresh_snow"),
    (r"pokryw\w*\s+sniezn\w*|grubosc\w*\s+pokryw\w*", "snow_cover"),
    (r"snieg\w*|sniezn\w*", "snow"),
    (r"temperatur\w*", "temperature"),
    (r"opad(?:y|u|ow|ach|ami|om|em)?(?!\w)", "precipitation"),
)
_NAME_RE = re.compile("|".join(f"(?P<n{i}>{p})" for i, (p, _) in enumerate(_NAMES)))
_STATISTIC_STEMS = (
    ("minimaln", "min"),
    ("najnizsz", "min"),
    ("sredni", "mean"),
    ("srednia", "mean"),
    ("srednie", "mean"),
    ("przecietn", "mean"),
    ("maksymaln", "max"),
    ("najwyzsz", "max"),
)
_LITERAL_RE = re.compile(r"(?<![\w.])[A-Za-z][A-Za-z_]*(?!\w)")
# "Q1%", "Q 1 %", "T = 50" are probabilities and return periods, not variables
_NOT_A_CODE_RE = re.compile(r"\s*[=%\d]")


def _scoped(ctx: ExtractionContext) -> tuple[str, ...] | None:
    """Variables of the chosen dataset; None while the dataset is not known."""
    declared = ctx.scope.get("variables")
    if isinstance(declared, list | tuple) and declared:
        return tuple(str(code) for code in declared)
    return None


def _statistic(folded: str, start: int, end: int) -> str | None:
    """Statistic named by the word right before or after the name phrase."""
    neighbours = words(folded[:start])[-1:] + words(folded[end:])[:1]
    for neighbour in neighbours:
        for stem, statistic in _STATISTIC_STEMS:
            if neighbour.text.startswith(stem):
                return statistic
    return None


def _pick(
    family: _Family, statistic: str | None, scoped: tuple[str, ...] | None
) -> list[str]:
    """Codes a name stands for in the dataset; ``[first wanted]`` when none fits."""
    wanted = family.wanted(statistic)
    if scoped is None:
        # Dataset unknown: the plain variable, not every statistic of it
        return list(wanted if statistic in family.by_statistic else family.base)
    chosen = [code for code in wanted if code in scoped]
    # Not a variable of this dataset: the validator tells the user
    return chosen or [wanted[0]]


def _reading(code: str) -> Reading:
    return Reading(code, f"extractors.variables.names.{code}", {"code": code})


def extract_variables(text: str, ctx: ExtractionContext) -> list[Match]:
    """
    Variables named by code or by Polish words, as codes of the dataset.

    A Polish name that fits several variables of the chosen dataset (bare
    "temperatura" for a climate station: ``Tmax``, ``Tmin``, ``Tmean``,
    ``Tground``) gives one match with a reading per variable, so Retman asks. A
    name of a variable the dataset does not have still gives its code, which
    ``validate_variables`` rejects with an explanation. Single-letter codes count
    only as standalone capitals (``H``, ``Q``), never in ``Q1%`` or ``T = 50``.

    Parameters
    ----------
    text : str
        Command or answer.
    ctx : ExtractionContext
        ``ctx.scope["variables"]`` lists the dataset's variables when it is known.

    Returns
    -------
    list[Match]
        One per mention, each reading a variable code (str); a code named twice
        is reported once.

    Examples
    --------
    >>> from datetime import date
    >>> from pathlib import Path
    >>> ctx = ExtractionContext(
    ...     tool="imgwtools", settings={}, project_dir=Path("."),
    ...     scope={"variables": ["H", "Q", "T"]}, lookup=lambda call: {},
    ...     today=date(2026, 10, 19),
    ... )
    >>> [m.readings[0].value for m in extract_variables("przepływy i stany wody", ctx)]
    ['Q', 'H']
    """
    scoped = _scoped(ctx)
    folded = fold(text)
    found: list[Match] = []
    for hit in _NAME_RE.finditer(folded):
        group = next(name for name, value in hit.groupdict().items() if value)
        family = _FAMILIES[_NAMES[int(group[1:])][1]]
        statistic = _statistic(folded, hit.start(), hit.end())
        codes = _pick(family, statistic, scoped)
        found.append(
            Match(hit.start(), hit.end(), tuple(_reading(code) for code in codes))
        )
    known = scoped if scoped is not None else KNOWN_VARIABLES
    by_lowercase = {code.lower(): code for code in known if len(code) > 1}
    for hit in _LITERAL_RE.finditer(text):
        token = hit.group()
        if len(token) == 1:
            code = token if token.isupper() and token in known else None
            if _NOT_A_CODE_RE.match(text, hit.end()):
                code = None
        else:
            code = by_lowercase.get(token.lower())
        if code is not None:
            found.append(Match(hit.start(), hit.end(), (_reading(code),)))
    result: list[Match] = []
    reported: set[str] = set()
    for match in sorted(found, key=lambda m: m.start):
        if len(match.readings) == 1:
            code = match.readings[0].value
            if code in reported:
                continue
            reported.add(code)
        result.append(match)
    return result


def validate_variables(value: Any, ctx: ExtractionContext) -> str | None:
    """Translation key of the problem with a variable code, or None."""
    if not isinstance(value, str) or not value:
        return "extractors.errors.invalid_variable"
    scoped = _scoped(ctx)
    if scoped is not None:
        return None if value in scoped else "extractors.errors.variable_not_in_dataset"
    return None if value in KNOWN_VARIABLES else "extractors.errors.invalid_variable"


def describe_variable(value: Any, texts: TextSource) -> str:
    """Plan text of a variable code: the code and its Polish name."""
    code = str(value)
    try:
        return texts.get(f"extractors.variables.names.{code}", code=code)
    except TranslationError:
        return code

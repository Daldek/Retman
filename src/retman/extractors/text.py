"""Text helpers shared by extractors: folding, word spans and typo tolerance.

Commands are typed fast and often without Polish letters, so extractors compare
folded text (lowercase, no diacritics) and tolerate one typo in longer words
(ADR-009). Folding keeps every character's position, so spans found in folded
text are valid in the original.
"""

import re
import unicodedata
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Word:
    """
    A word of folded text with its position.

    Parameters
    ----------
    text : str
        Letters and digits of the word, folded.
    start, end : int
        Position in the text the word was taken from (``text[start:end]``).
    """

    text: str
    start: int
    end: int


def fold(text: str) -> str:
    """Lowercase without diacritics, keeping every character's position.

    ``ł`` is mapped explicitly: Unicode does not decompose it.

    Examples
    --------
    >>> fold("Układ wyjściowy Křovák")
    'uklad wyjsciowy krovak'
    """
    folded = []
    for char in text:
        lower = char.lower()
        if lower == "ł":
            folded.append("l")
            continue
        base = "".join(
            c
            for c in unicodedata.normalize("NFKD", lower)
            if not unicodedata.combining(c)
        )
        folded.append(base[:1] or lower[:1] or char)
    return "".join(folded)


def words(folded: str) -> list[Word]:
    """Words (runs of ASCII letters and digits) of already folded text.

    Examples
    --------
    >>> [(w.text, w.start, w.end) for w in words("ze stacji poznan-lawica")]
    [('ze', 0, 2), ('stacji', 3, 9), ('poznan', 10, 16), ('lawica', 17, 23)]
    """
    return [
        Word(found.group(), found.start(), found.end())
        for found in _WORD_RE.finditer(folded)
    ]


def damerau(a: str, b: str) -> int:
    """Edit distance counting a swap of neighbouring letters as one edit.

    Examples
    --------
    >>> damerau("wynik", "wyink"), damerau("wynik", "wynika"), damerau("od", "do")
    (1, 1, 1)
    """
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = int(a[i - 1] != b[j - 1])
            rows[i][j] = min(
                rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)
    return rows[len(a)][len(b)]


def starts_within_one_edit(word: str, stem: str, *, min_stem: int = 5) -> bool:
    """Whether ``word`` starts with ``stem`` allowing one typo in the stem.

    Stems shorter than ``min_stem`` letters are never matched with a typo, because
    one letter changes the meaning of short words ("do"/"od").

    Examples
    --------
    >>> starts_within_one_edit("przelic", "przelicz")
    True
    >>> starts_within_one_edit("od", "do")
    False
    """
    if len(stem) < min_stem:
        return False
    return any(
        damerau(word[:length], stem) <= 1
        for length in (len(stem) - 1, len(stem), len(stem) + 1)
    )


def equals_within_one_edit(word: str, target: str, *, min_length: int = 5) -> bool:
    """Whether ``word`` is ``target`` or one typo away from it (long words only).

    Examples
    --------
    >>> equals_within_one_edit("hydrologiczn", "hydrologiczne")
    True
    >>> equals_within_one_edit("maj", "may")
    False
    """
    if word == target:
        return True
    return len(target) >= min_length and damerau(word, target) <= 1

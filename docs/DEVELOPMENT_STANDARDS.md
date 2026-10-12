# Standardy deweloperskie — Retman

**Wersja:** 1.0
**Data:** 2026-10-11
**Status:** Obowiązujący
**Źródło:** standardy Kartografa (`Kartograf/docs/DEVELOPMENT_STANDARDS.md` v3.3), dostosowane do Retmana

> **Nota 1.0 (2026-10-11):** pierwsza wersja, przed powstaniem kodu. Sekcje 5–8
> i 10 opisują docelową konfigurację (`pyproject.toml`, `.editorconfig`,
> `tests/conftest.py`) — powstaje ona razem z pierwszym kodem, zgodnie z tym
> dokumentem. Wszystkie pliki mają końce linii LF, bez wyjątków (5.5).

---

## Spis treści

1. [Git Workflow](#1-git-workflow)
2. [Conventional Commits](#2-conventional-commits)
3. [Code Review](#3-code-review)
4. [Python — nazewnictwo](#4-python--nazewnictwo)
5. [Python — formatowanie (Ruff)](#5-python--formatowanie-ruff)
6. [Python — środowisko i narzędzia](#6-python--środowisko-i-narzędzia)
7. [Python — struktura projektu](#7-python--struktura-projektu)
8. [Python — type hints](#8-python--type-hints)
9. [Python — docstringi i język](#9-python--docstringi-i-język)
10. [Python — testowanie](#10-python--testowanie)
11. [Python — obsługa błędów](#11-python--obsługa-błędów)
12. [Python — logging](#12-python--logging)
13. [Python — HTTP i wydajność](#13-python--http-i-wydajność)
14. [Bezpieczeństwo i prywatność](#14-bezpieczeństwo-i-prywatność)
15. [Workflow sesji i implementacji](#15-workflow-sesji-i-implementacji)
16. [Czego NIE robić](#16-czego-nie-robić)
17. [Typowe zadania](#17-typowe-zadania)
18. [Pre-merge checklist](#18-pre-merge-checklist)

---

## 1. Git Workflow

### 1.1 Branching (Git Flow)

```
main              # Stabilna wersja (tylko merge z develop)
develop           # Aktywny rozwój (DOMYŚLNA GAŁĄŹ ROBOCZA)
feature/<nazwa>   # Nowe funkcjonalności
fix/<nazwa>       # Poprawki błędów
docs/<nazwa>      # Tylko dokumentacja
hotfix/<nazwa>    # Pilne poprawki wydania (branch z main)
```

**Zasady:**
- `main` — tylko stabilny, przetestowany kod
- `develop` — integracja zmian, domyślna gałąź robocza
- `feature/*`, `fix/*`, `docs/*` — branch z `develop`, merge do `develop`
- `hotfix/*` — branch z `main`, merge do `main` i `develop`
- Praca bieżąca ZAWSZE na `develop` albo na gałęzi krótkotrwałej
  z `develop` — nigdy bezpośrednio na `main`

### 1.2 Tagowanie

Tagi `v<X.Y.Z>` (SemVer) przy wydaniach. Tag jest zarazem punktem instalacji
dla testerów (`uv tool install "git+https://github.com/Daldek/Retman@v0.1.0"`,
ARCHITECTURE 9.4), więc nigdy nie przesuwaj ani nie usuwaj opublikowanego tagu.

```bash
git tag -a v0.1.0 -m "Release v0.1.0: pojedyncze operacje z CLI i Pythona"
git push origin v0.1.0
```

Checkpointy robocze (CP) są śledzone tylko w `docs/PROGRESS.md`, bez tagów Git.

Przed wydaniem: testy offline nie zastępują przebiegu `retman-eval` na
konfiguracji domyślnej (ARCHITECTURE 8.2) ani testu instalacji na czystych
systemach (ARCHITECTURE 9.4).

### 1.3 Zasady commitów

- Każda logiczna zmiana = osobny commit
- Commituj często, małymi porcjami
- Commity bez stopki `Co-Authored-By`; autor: `Daldek <git@debever.pl>`

---

## 2. Conventional Commits

### 2.1 Format

```
<type>(<scope>): <opis>

<body>           # opcjonalny

<footer>         # opcjonalny (np. Closes #12)
```

### 2.2 Typy

| Typ | Kiedy |
|-----|-------|
| `feat` | Nowa funkcjonalność |
| `fix` | Poprawka błędu |
| `docs` | Tylko dokumentacja |
| `test` | Dodanie/zmiana testów |
| `refactor` | Refaktoryzacja (bez zmian funkcjonalności) |
| `perf` | Optymalizacja wydajności |
| `style` | Formatowanie (nie wpływa na logikę) |
| `chore` | Config, zależności, build |

### 2.3 Scope — specyficzne dla Retmana

Typ i scope po angielsku (słowa kluczowe Conventional Commits), opis i treść
po polsku (sekcja 9.4). Scope = moduł z ARCHITECTURE 3.1 albo nazwa narzędzia:

```bash
feat(pipeline): dopytywanie o parametr przy niskiej pewności
feat(extractors): rozpoznawanie okresu powtarzalności „raz na N lat”
feat(backends): pewność ze zgodności odpowiedzi w openai_compatible
feat(imgwtools): operacja pobrania danych pomiarowych
fix(workspace): pytanie przy kilku pasujących wynikach
feat(i18n): polskie opisy opcji metody przepływu
feat(doctor): sprawdzenie progów "auto" z backendem innym niż basal
feat(eval): raport błędów powyżej progu pewności
docs(architecture): wybór wejścia z przestrzeni roboczej
test(extractors): zapisy niejednoznaczne prawdopodobieństwa
chore(deps): aktualizacja klienta HTTP
```

---

## 3. Code Review

### 3.1 Proces

```
1. Deweloper tworzy PR
2. Kontrole (uruchamiane lokalnie, komendy w sekcji 6.3):
   ├─ Formatowanie (ruff format --check .)
   ├─ Linting (ruff check .)
   ├─ Type checking (mypy retman/ tests/ bez błędów — sekcja 8.3)
   ├─ Testy offline z pokryciem (pytest -m "not live" --cov)
   └─ Kontrola rozjazdów z API narzędzi (retman-scaffold --check, ARCHITECTURE 3.2.3)
3. Manual review
4. Poprawki, jeśli potrzeba
5. Approval → Merge
```

### 3.2 Co sprawdza reviewer

- **Poprawność** — czy kod działa zgodnie z wymaganiami (PRD W-xx, N-xx)?
- **Zasady projektowe** — ARCHITECTURE 1.1: brak cichego zgadywania, potwierdzenie
  przed wykonaniem, liczby z kodu, nie z modelu
- **Testy** — czy pokrywają nową logikę i przypadki brzegowe?
- **Standardy** — zgodność z tym dokumentem
- **Czytelność** — czy kod jest zrozumiały bez nadmiernych komentarzy?
- **Bezpieczeństwo i prywatność** — sekcja 14

### 3.3 Wymagania PR

- Wszystkie testy przechodzą
- Pokrycie kodu w normie (sekcja 10.1)
- Brak błędów ruff / mypy
- Minimum 1 approval
- Brak konfliktów z target branch
- Dokumentacja zaktualizowana (jeśli potrzeba)

---

## 4. Python — nazewnictwo

### 4.1 Konwencje

| Element | Konwencja | Przykład |
|---------|-----------|----------|
| Zmienne | snake_case + jednostka | `area_km2`, `peak_flow_m3s` |
| Funkcje | snake_case + czasownik | `load_manifest()`, `extract_probability()` |
| Klasy | PascalCase | `Plan`, `DecisionBackend` |
| Stałe | UPPER_SNAKE_CASE | `OUT_OF_SCOPE`, `MAX_OPTIONS` |
| Pliki .py | snake_case | `openai_compatible.py`, `manifest_adapter.py` |
| Identyfikatory operacji, parametrów, opcji, `kind` | snake_case po angielsku | `peak_flow`, `bogdanowicz_stachy`, `catchment_characteristics` |
| Protected | `_prefix` | `self._cache` |
| Private | `__prefix` | `self.__internal_state` |

### 4.2 Jednostki w nazwach zmiennych

**ZAWSZE** dodawaj jednostkę do nazwy zmiennej fizycznej:

```python
# GOOD
area_km2 = 118.4
peak_flow_m3s = 42.7
precipitation_mm = 38.5
timeout_s = 30

# BAD — unit ambiguity
area = 118.4      # km2 or m2?
timeout = 30      # seconds or milliseconds?
```

Prawdopodobieństwo przechowuj zawsze jako ułamek `p` (np. `0.01`), nie procent
(ARCHITECTURE 4.4): `probability = 0.01`, nie `probability_pct = 1`.

### 4.3 Prefiksy semantyczne

| Prefiks | Znaczenie | Przykład w Retmanie |
|---------|-----------|---------------------|
| `extract_*` | Wyciągnięcie wartości z polecenia (ekstraktory) | `extract_probability()`, `extract_coordinates()` |
| `load_*` | Wczytanie pliku (konfiguracja, manifest, tłumaczenia, wynik) | `load_config()`, `load_translations()` |
| `validate_*` | Sprawdzenie poprawności, zgłasza wyjątek | `validate_manifest()` |
| `find_*` | Wyszukanie w przestrzeni roboczej lub rejestrze | `find_results_by_kind()` |
| `build_*` | Złożenie obiektu (plan, wynik, pytanie) | `build_result()` |
| Nazwa operacji | Handler w `retman/tools/<narzędzie>/handlers.py` | `fetch_imgw_data()`, `compute_peak_flow()` |

---

## 5. Python — formatowanie (Ruff)

### 5.1 Konfiguracja

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"
```

### 5.2 Komendy

```bash
# Formatowanie (całe repo; .claude/ wykluczone w pyproject.toml)
ruff format .

# Sprawdzenie (bez zmian)
ruff format --check .

# Linting
ruff check .

# Linting z auto-fix
ruff check --fix .
```

### 5.3 Zasady formatowania

```python
# Line length: 88 characters
# Indentation: 4 spaces (NEVER tabs)

# GOOD — multi-line when exceeds 88 chars
def plan(
    self,
    command: str,
    known: dict[str, object] | None = None,
) -> Plan:
    pass

# BAD — too long
def plan(self, command: str, known: dict[str, object] | None = None, language: str = "pl") -> Plan:
    pass
```

### 5.4 Importy

```python
# Order: stdlib → third-party → local
# Alphabetical within groups
# Blank lines between groups
# Ruff sorts automatically (rule I)

import logging
from pathlib import Path

from retman.core.plan import Plan
from retman.registry.operation import Operation
```

Narzędzia hydrologiczne importuje wyłącznie handler, i to dopiero przy
wykonaniu (ARCHITECTURE 3.2.5) — nigdy na poziomie modułu rdzenia.

### 5.5 Końce linii

Wszystkie pliki mają końce linii **LF, bez wyjątków** — także `docs/DECISIONS.md`.
Ustawienie trzymają `.editorconfig` (`end_of_line = lf`) i `.gitattributes`
(`* text=auto eol=lf`), bo projekt jest rozwijany i testowany także na Windows.
Kontrola: `git ls-files --eol` nie pokazuje `w/crlf`.

---

## 6. Python — środowisko i narzędzia

### 6.1 Środowisko wirtualne

Wymagany Python 3.12+ (`requires-python` w `pyproject.toml`, ARCHITECTURE 9.3, ADR-002).
Środowisko zarządza `uv` — to samo narzędzie, którym instalują się użytkownicy
(ARCHITECTURE 9.4). Jedno środowisko `.venv/` w korzeniu projektu — dla ludzi
i agentów AI:

- Python: `.venv/bin/python` (Windows: `.venv\Scripts\python`)
- CLI: `.venv/bin/retman`

```bash
cd Retman
uv venv --python 3.12
uv pip install -e ".[dev]"

# Narzędzia hydrologiczne — w tym samym środowisku (handlery je importują);
# wersje do testów handlerów są w grupie "tools" w pyproject.toml (ADR-003)
uv pip install --group tools
```

Serwer modelu (basal-serve, LM Studio itd.) nie jest częścią środowiska
Retmana — uruchamia się go osobno (PRD N-10).

### 6.2 Zmienne środowiskowe

Retman nie ma stałych nazw zmiennych z kluczami: klucz API dostawcy jest
w zmiennej, której **nazwę** podaje `api_key_env` w `retman.toml`
(ARCHITECTURE 9.1, rozdz. 10). Wszystkie pozostałe ustawienia są w pliku
centralnym — nie dodawaj zmiennych środowiskowych zmieniających zachowanie
z pominięciem pliku (brak ukrytych wartości domyślnych, PRD N-11).

### 6.3 Komendy: testy, lint, typy

```bash
# Testy offline (domyślna bramka)
.venv/bin/python -m pytest tests/ -v -m "not live"

# Testy z pokryciem (offline)
.venv/bin/python -m pytest tests/ -m "not live" --cov=retman --cov-report=html

# Testy z prawdziwym serwerem modelu (live) — tylko świadomie
.venv/bin/python -m pytest tests/ -m live

# Liczba testów (zamiast liczb w dokumentacji)
.venv/bin/python -m pytest tests/ --collect-only -q -m "not live"

# Linter i formatowanie (całe repo)
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .

# Type checking (sekcja 8.3)
.venv/bin/python -m mypy retman/ tests/

# Kontrola rozjazdów opisów z API narzędzi (ARCHITECTURE 3.2.3)
.venv/bin/retman-scaffold --check

# Ocena jakości decyzji na zbiorze testowym — wymaga działającego serwera modelu
.venv/bin/retman-eval --backend basal
```

Testy są **offline**: `tests/conftest.py` przewraca każdy test otwierający
gniazdo spoza loopbacku; wyjątek mają tylko testy z markerem `live`.
`pyproject.toml` nie odfiltrowuje testów `live` (`addopts` bez `-m`), więc
komenda bez `-m "not live"` łączy się z serwerem modelu. Szczegóły: sekcja 10.4.

### 6.4 Konfiguracja i wyniki podczas pracy

Retman zapisuje wyniki w folderze projektu, w którym go uruchomiono
(`retman-output/`, ARCHITECTURE 5.1), a ustawienia czyta z pliku centralnego
(ARCHITECTURE 9.1). Dlatego:

- **Ręczne uruchomienia CLI** wykonuj w osobnym folderze projektu POZA
  repozytorium i poza `/tmp` — w katalogu wskazanym przez użytkownika,
  np. `<katalog-danych>/retman/<RRRR-MM-DD>-<cel>/`. Gdy katalog jest
  niedostępny, zatrzymaj się i zapytaj zamiast uruchamiać w repo.
- `retman-output/` jest w `.gitignore` — wynik przypadkowego uruchomienia
  w repo nigdy nie trafia do commita.
- **Testy nie dotykają** prawdziwego pliku centralnego ani folderów projektów
  użytkownika: konfiguracja z jawnej ścieżki (`Retman.from_config(path)`),
  wyniki w `tmp_path`.
- Raporty `.md` z przebiegów (np. `retman-eval`, pomiary czasu odpowiedzi,
  ARCHITECTURE 9.2) trafiają do `docs/research/` w repo, z datą w nazwie (sekcja 7.1).

---

## 7. Python — struktura projektu

### 7.1 Retman — flat layout

Pakiet `retman/` leży w korzeniu repo (bez `src/`); testy w `tests/`
(`conftest.py` + `fixtures/`), dokumentacja w `docs/`, konfiguracja narzędzi
w `pyproject.toml`.

Specyfikacje (`docs/specs/`), plany (`docs/plans/`) i raporty z badań
(`docs/research/`) mają w nazwie pliku datę powstania w formacie `YYYY-MM-DD`:
`docs/<katalog>/YYYY-MM-DD-<temat>.md`, np. `docs/specs/2026-10-11-retman-eval.md`.
Data w nazwie się nie zmienia; późniejsze zmiany treści opisuje nagłówek dokumentu
(status, data aktualizacji).

Źródłem prawdy dla struktury modułów jest `docs/ARCHITECTURE.md`, p. 3.1,
a ostatecznie sam katalog `retman/`. Ten dokument nie powiela drzewa modułów.
Nowy moduł umieszczaj zgodnie z ARCHITECTURE i aktualizuj tam jego opis
w tym samym commicie.

Wszystko, co dotyczy konkretnego narzędzia (manifest, handlery, `pl.toml`),
mieszka w `retman/tools/<narzędzie>/` (ARCHITECTURE 3.2.2) — rdzeń nie zna
nazw narzędzi.

### 7.2 Konfiguracja w pyproject.toml

Wszystkie narzędzia deweloperskie konfiguruj w jednym pliku `pyproject.toml`.
Nie twórz osobnych plików konfiguracyjnych (`setup.cfg`, `tox.ini`, `.flake8`
itp.). Wyjątki: `.editorconfig` i `.gitattributes` (sekcja 5.5).

---

## 8. Python — type hints

### 8.1 Styl Python 3.12+

```python
# GOOD — modern syntax
def find_results_by_kind(kind: str) -> list[Result]:
    pass

def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
    pass

def from_config(cls, path: Path | None = None) -> "Retman":
    pass

# BAD — legacy typing
from typing import Dict, List, Optional

def from_config(cls, path: Optional[Path] = None) -> "Retman":
    pass
```

Interfejsy backendów to `typing.Protocol` (ARCHITECTURE 3.3.1); dozwolone
wybory w kodzie to `Literal`.

### 8.2 Wymagane wszędzie

Type hints są wymagane dla:
- wszystkich argumentów funkcji publicznych,
- wartości zwracanych,
- atrybutów klas (dataclass).

### 8.3 Type checking

```bash
.venv/bin/python -m mypy retman/ tests/
```

`mypy retman/ tests/` musi kończyć się bez błędów (konfiguracja `[tool.mypy]`
w `pyproject.toml`, bez `--strict`). Błąd naprawiaj merytorycznie;
`# type: ignore` / `cast` tylko z jednozdaniowym uzasadnieniem w komentarzu,
gdy typowanie biblioteki zewnętrznej jest błędne lub niepełne. Narzędzie bez
stubów trafia do `[[tool.mypy.overrides]]` z `ignore_missing_imports`.

---

## 9. Python — docstringi i język

### 9.1 Styl: NumPy, język: angielski

```python
def extract_probability(text: str, *, multiple: bool = False) -> ProbabilityMatch:
    """
    Extract exceedance probability from a command.

    Parameters
    ----------
    text : str
        Command text in the user's language.
    multiple : bool, optional
        Whether several values are allowed, by default False.

    Returns
    -------
    ProbabilityMatch
        Values as fractions (0.01 for 1%) and ambiguous readings to ask about.

    Raises
    ------
    ValidationError
        If a value is outside 0 < p < 1.

    Examples
    --------
    >>> extract_probability("Q1%").values
    [0.01]
    """
```

Ten sam styl stosujemy w Retmanie, którego oczekujemy od narzędzi
(ARCHITECTURE 3.2.1).

### 9.2 Klasy

```python
class Plan:
    """
    Operation, parameter values and the source of each value.

    A plan must be confirmed with ``confirm()`` before execution.

    Parameters
    ----------
    operation : str
        Operation identifier from the manifest.
    values : dict[str, PlanValue]
        Parameter values with their sources.
    """
```

### 9.3 Komentarze inline

```python
# GOOD — explains "why", not "what"
# basal cannot read exact numbers reliably; values come from extractors
coordinates = extract_coordinates(command)

# Several candidates: always ask, even if one of them is the newest
if len(candidates) > 1:
    ...

# BAD — states the obvious
# Set timeout to 30
timeout_s = 30
```

### 9.4 Język

Reguła obowiązująca (ARCHITECTURE 1.3):

- **Kod** — identyfikatory, nazwy operacji, parametrów i opcji, komentarze,
  docstringi (`retman/`, `tests/`) — po angielsku
- **Teksty dla użytkownika i modelu** — pytania, opisy opcji, komunikaty, plan —
  wyłącznie w plikach tłumaczeń (`retman/i18n/pl.toml`,
  `retman/tools/<narzędzie>/pl.toml`); kod odwołuje się do nich angielskimi
  kluczami. Polski tekst w kodzie = błąd
- **Dane testowe** — polecenia użytkownika w testach i w zbiorze
  `retman/eval/commands.jsonl` są po polsku (to dane wejściowe)
- **Commit messages** — po polsku (Conventional Commits z sekcji 2: typ
  i scope to angielskie słowa kluczowe, opis i treść po polsku)
- **Dokumentacja** — po polsku: `docs/`, `README.md`, `CLAUDE.md` i inne
  pliki `.md`

---

## 10. Python — testowanie

### 10.1 Progi pokrycia

| Warstwa | Wymagane pokrycie | Egzekwowanie |
|---------|-------------------|--------------|
| Cały pakiet (próg globalny) | `fail_under` w `[tool.coverage.report]` (`pyproject.toml`) | automatycznie przy `--cov` |
| Rdzeń (`core/`, `registry/`, `adapters/`, `extractors/`) | **>= 80%** | ręcznie, komenda poniżej |

```bash
.venv/bin/python -m pytest tests/ --cov=retman --cov-report=term -q -p no:cacheprovider -m "not live"
.venv/bin/python -m coverage report --include='retman/core/*,retman/registry/*,retman/adapters/*,retman/extractors/*' --fail-under=80
```

`fail_under` w `pyproject.toml` jest jedynym źródłem progu globalnego — nie
powielaj go w komendach. Odstępstwo od progu rdzenia wymaga wpisu w backlogu
`docs/PROGRESS.md` (moduł + przyczyna).

### 10.2 Nazewnictwo testów

```python
# Pattern: test_<function>_<scenario>[_<expected>]

def test_extract_probability_percent():
    """Test "Q1%" gives 0.01."""

def test_extract_probability_q50_asks():
    """Test "Q50" without % produces a question instead of a value."""

def test_execute_unconfirmed_plan_raises():
    """Test execute() rejects a plan without confirm()."""
```

### 10.3 AAA Pattern (Arrange-Act-Assert)

```python
def test_plan_asks_when_several_catchments(tmp_path):
    # Arrange
    workspace = make_workspace(tmp_path, results=["catchment", "catchment"])
    retman = make_retman(workspace, backend=FakeDecisionBackend({"operation": "peak_flow"}))

    # Act
    plan = retman.plan("Policz Q1% dla tej zlewni")

    # Assert
    assert plan.questions[0].name == "catchment"
    assert len(plan.questions[0].options) == 2
```

### 10.4 Fixtures, atrapy i izolacja

- **Bez GPU i bez serwera modelu:** pipeline testuj z `FakeDecisionBackend`
  z `retman/testing.py` (ARCHITECTURE 8.3), z zadanymi decyzjami
  i pewnościami — w tym poniżej progu, żeby sprawdzić dopytywanie.
- **Ekstraktory** testuj bez modelu, jako czysty kod; każda forma
  z ARCHITECTURE 4.4 ma test, także zapisy niejednoznaczne.
- **Wspólny adapter** testuj na narzędziu-atrapie (manifest + handlery
  w `tests/`), nie na prawdziwym narzędziu.
- **Handlery** testuj na prawdziwych narzędziach z małymi danymi testowymi
  (ARCHITECTURE 3.2.8); test pomija się (`pytest.importorskip`), gdy narzędzie
  nie jest zainstalowane, a CI uruchamia je na najstarszej i najnowszej
  obsługiwanej wersji narzędzia (ARCHITECTURE 3.2.7).
- **Izolacja sieci:** `tests/conftest.py` blokuje każde połączenie spoza
  loopback (autouse); sieć wymaga jawnego markera `@pytest.mark.live`.
- **Fixtury z realnych odpowiedzi:** odpowiedzi basal-serve i serwerów
  zgodnych z API OpenAI w testach backendów buduj z SUROWYCH odpowiedzi
  zapisanych z prawdziwych serwerów (`tests/fixtures/<backend>/`), nie
  z wyobrażenia o formacie.
- **Odporność na kolejność opcji:** testy rozpoznania sprawdzają stabilność
  przy przetasowaniu opcji (ARCHITECTURE 3.4, pkt 3).
- **Komplet tłumaczeń:** test sprawdza, że każda operacja, parametr i opcja
  ma tekst w każdym obsługiwanym języku (ARCHITECTURE 4.2).

---

## 11. Python — obsługa błędów

### 11.1 Wyjątki Retmana

Źródłem prawdy hierarchii wyjątków jest `retman/exceptions.py` — ten dokument
nie powiela listy klas. Zasady:

- Każdy własny wyjątek dziedziczy (bezpośrednio lub pośrednio)
  z `RetmanError` — użytkownik biblioteki łapie wszystkie błędy pakietu
  jednym `except RetmanError`.
- Używaj najwęższej istniejącej klasy (np. `PlanNotConfirmedError`,
  ARCHITECTURE 6.3); nową klasę dodawaj tylko, gdy wywołujący musi ją odróżnić.
- Informacje dla wywołującego przekazuj atrybutami wyjątku, nie przez
  parsowanie komunikatu.
- **Handlery zgłaszają zwykłe wyjątki narzędzia** — wspólny adapter je
  przechwytuje i zwraca `Result(ok=False)` (ARCHITECTURE 3.2.4, pkt 4);
  awaria jednego narzędzia nie blokuje pozostałych.
- Błąd docierający do bariery CLI daje komunikat z pliku tłumaczeń i kod
  wyjścia z ARCHITECTURE 6.4; brak połączenia z modelem podpowiada
  `retman doctor` (ARCHITECTURE 7.2).
- Zawsze zachowuj łańcuch wyjątków: `raise ... from err` (sekcja 11.3).

### 11.2 Walidacja na wejściu

Wartości wyciągnięte z polecenia i odpowiedzi użytkownika sprawdzają te same
walidatory (zakresy `range` z manifestu, `0 < p < 1`, współrzędne w Polsce,
ARCHITECTURE 4.4, 6.1). Wartość niepoprawna to pytanie z wyjaśnieniem
(`question.error`), nie wyjątek — wyjątek jest dla błędów programisty
i środowiska.

### 11.3 Raise from

```python
# GOOD — preserve exception chain
try:
    response = client.post(url, json=payload, timeout=timeout_s)
except HTTPError as err:
    raise BackendConnectionError(url) from err

# BAD — loses original traceback
except HTTPError as err:
    raise BackendConnectionError(url)
```

---

## 12. Python — logging

### 12.1 Konfiguracja

```python
import logging

logger = logging.getLogger(__name__)
```

Log techniczny trafia do katalogu logów użytkownika, a poziom ustawia
`diagnostic_level` w `retman.toml` (ARCHITECTURE 5.4).

### 12.2 Zasady

```python
# DEBUG — development only
logger.debug("Loaded %d operations from %s", count, tool)

# INFO — normal operations
logger.info("Decision backend %s responded in %.2f s", backend, elapsed_s)

# WARNING — unusual but not an error
logger.warning("Tool %s %s outside supported range %s", tool, version, spec)

# ERROR — failure that doesn't crash the app
logger.error("Handler %s failed: %s", handler, exc)
```

- Używaj `%s` formatting w loggerze (lazy evaluation), nie f-stringów.
- **Log techniczny nigdy nie zawiera treści poleceń ani odpowiedzi
  użytkownika** (ARCHITECTURE 5.4, rozdz. 10). Treść poleceń trafia wyłącznie
  do dziennika projektu (`journal.jsonl`) i `result.json`, zgodnie
  z `journal_commands`.

---

## 13. Python — HTTP i wydajność

### 13.1 Priorytet

```
Poprawność > Czytelność > Wydajność
```

### 13.2 Połączenia z modelami

- Backendy rozmawiają z API bezpośrednio przez klienta HTTP z zależności
  podstawowych — bez SDK dostawców i bez pakietu `basal` (ARCHITECTURE 3.3.2).
- Jeden klient (sesja) na backend, ponownie używany między zapytaniami.
- **Każde zapytanie ma jawny timeout** z `timeout_s` w `retman.toml`
  (ARCHITECTURE 9.1) — bez wartości zaszytych w kodzie.

### 13.3 Szybki start

Narzędzia i handlery importuj dopiero przy wykonaniu (ARCHITECTURE 3.2.5) —
start Retmana i planowanie nie mogą zależeć od czasu importu narzędzi.
Czas od polecenia do planu jest mierzony (ARCHITECTURE 9.2, PRD N-07).

---

## 14. Bezpieczeństwo i prywatność

### 14.1 NIGDY

```python
# NEVER hardcode secrets or put API keys in retman.toml, logs or result.json
API_KEY = "sk-1234567890"  # NEVER!

# NEVER commit .env
# .gitignore must contain: .env, *.pem, *.key, retman-output/

# NEVER eval() on user input or model output
eval(model_answer)  # NEVER!

# NEVER execute an operation without a confirmed plan (0.x)
retman.execute(plan)  # plan.confirm() first — otherwise PlanNotConfirmedError
```

### 14.2 ZAWSZE

```python
import os

# ALWAYS read API keys from the environment variable named in the config
api_key = os.environ.get(config.decision.api_key_env)

# ALWAYS treat model output as one of the allowed keys, never as code or a path
if decision.key not in options:
    raise InvalidModelAnswerError(decision.key)

# ALWAYS let handlers write only to their output_dir
out_file = output_dir / "catchment.geojson"
```

### 14.3 Prywatność — specyficzne dla Retmana

- Retman nie wysyła poleceń ani danych poza skonfigurowane backendy;
  domyślna konfiguracja wskazuje wyłącznie na `localhost` (ARCHITECTURE rozdz. 10).
- O tym, gdzie działa model, decyduje użytkownik — kod nie ocenia adresów
  i nie ostrzega; `retman doctor` pokazuje adres każdego modelu.
- Zbieranie poleceń do zbioru testowego jest domyślnie wyłączone
  (`collect_commands`) i wymaga wyraźnej zgody.
- Dziennik projektu jest tylko dopisywany — kod nigdy nie zmienia ani nie
  usuwa jego wpisów (ARCHITECTURE 5.4).

---

## 15. Workflow sesji i implementacji

### 15.1 Początek sesji

```
1. Przeczytaj docs/PROGRESS.md — sekcja "Ostatnia sesja" (blok START)
2. git status + git log --oneline -5
3. Sprawdź gałąź: git branch --show-current (develop albo gałąź z develop)
4. Zrozum zadanie — znajdź relewantne sekcje w PRD.md / ARCHITECTURE.md
5. Zadaj pytania, jeśli coś jest niejasne
```

Kolejność lektury dokumentacji: `docs/PROGRESS.md` (stan i zadania) ->
`docs/PRD.md` (wymagania i zakres wersji) -> `docs/ARCHITECTURE.md`
(architektura, kontrakty) -> `docs/CHANGELOG.md` (historia zmian) ->
`docs/DECISIONS.md` (ADR — co i dlaczego).

### 15.2 Implementacja

```
1. Pisz kod zgodnie z tym dokumentem i zasadami ARCHITECTURE 1.1
2. Type hints (X | None zamiast Optional[X]) — sekcja 8
3. Docstringi NumPy po angielsku; teksty dla użytkownika w pl.toml — sekcja 9
4. Walidacja wartości przez ekstraktory i walidatory, nie przez model — sekcja 11.2
5. Timeout z konfiguracji dla każdego zapytania HTTP — sekcja 13.2
6. raise ... from err (zachowaj łańcuch wyjątków) — sekcja 11.3
```

### 15.3 Testowanie

```
1. Napisz testy (pytest, AAA pattern) — sekcja 10
2. Testy offline: FakeDecisionBackend, atrapy, fixtury z realnych odpowiedzi (10.4)
3. Pokrycie: progi z sekcji 10.1
4. Uruchom: pytest tests/ -v --tb=short -m "not live"
5. Sprawdź bramkę: ruff check ., ruff format --check ., mypy retman/ tests/
6. Zmiany w pytaniach, opisach opcji lub logice decyzji: retman-eval (sekcja 6.3)
```

### 15.4 W trakcie sesji — commity

```
1. Conventional Commits (sekcja 2, opis po polsku — 9.4): feat(extractors): rozpoznawanie „Q 1 %”
2. Commituj często, małe zmiany
3. Aktualizuj docs/CHANGELOG.md na bieżąco — sekcja wersji niewydanej
   (nagłówek "## [X.Y.Z] - Unreleased" na górze pliku)
4. Decyzje projektowe zapisuj w docs/DECISIONS.md (szablon na końcu pliku)
5. W razie wątpliwości — pytaj
```

### 15.5 Koniec sesji

**OBOWIĄZKOWO** zaktualizuj `docs/PROGRESS.md` (sekcja „Ostatnia sesja”,
szablon na końcu pliku):

- co zostało zrobione,
- co jest w trakcie (plik, linia, kontekst),
- następne kroki.

---

## 16. Czego NIE robić

- **Nie edytuj repozytoriów narzędzi** (Hydrograf, Kartograf, IMGWTools, Hydrolog,
  BasicHydraulics) — Retman korzysta tylko z ich publicznego API (PRD N-03)
- **Nie dodawaj modelu, bibliotek ML ani SDK dostawców do zależności** — także
  `basal` (PRD N-10, ARCHITECTURE 9.3)
- **Nie dodawaj ścieżki wykonania bez potwierdzenia planu** (PRD W-05)
- **Nie pozwalaj modelowi podawać liczb** — wartości wyciągają ekstraktory
  (ARCHITECTURE 1.1)
- **Nie wybieraj po cichu** spośród kilku kandydatów — pytaj (ARCHITECTURE 5.3)
- **Nie dodawaj ukrytych wartości domyślnych** — każda wartość jest w `retman.toml`
  (PRD N-11)
- **Nie wpisuj polskich tekstów w kodzie** — tylko pliki tłumaczeń (sekcja 9.4)
- **Nie loguj treści poleceń** w logu technicznym (sekcja 12.2)
- **Nie dodawaj funkcji spoza zakresu wersji** — PRD rozdz. 7 i 9
- **Nie rozstrzygaj sam `[DO UZUPEŁNIENIA]` ani otwartych kwestii** (PRD 11,
  ARCHITECTURE 12) — to decyzje autora
- **Nie zmieniaj architektury** bez konsultacji — decyzje są w `docs/DECISIONS.md`
- **Nie pomijaj testów** — progi pokrycia z sekcji 10.1
- **Nie używaj Optional/Union** — `X | None` i `X | Y`
- **Nie używaj f-stringów w loggerze** — `%s` formatting
- **Nie twórz osobnych plików konfiguracyjnych** — wszystko w `pyproject.toml`
  (wyjątki: sekcja 7.2)
- **Nie łącz się z siecią w testach** — tylko testy `live`
- **Nie uruchamiaj CLI w repozytorium** — sekcja 6.4

---

## 17. Typowe zadania

### 17.1 Nowa operacja narzędzia

```python
# 1. Szkic z dokumentacji narzędzia: retman-scaffold <narzędzie>.<funkcja>
#    (ARCHITECTURE 3.2.3) — wpis w manifeście, szkielet handlera, pola w pl.toml.
# 2. Manifest retman/tools/<narzędzie>/manifest.py: id (unikalne w Retmanie),
#    category, inputs/outputs z rodzajami danych (kind), params z typami
#    choice/free/bool, required/default/multiple/range (ARCHITECTURE 4.1, 4.3).
# 3. Handler w handlers.py: tylko publiczne API narzędzia, wejścia jako pliki,
#    zapis tylko do output_dir, bez input()/print() (ARCHITECTURE 3.2.4).
# 4. pl.toml: label i description operacji, pytania (question dla użytkownika,
#    model_question — „co wymienia polecenie” — dla parametrów choice/bool, ADR-008),
#    opcje z label (dla użytkownika) i description z synonymami i nazwami angielskimi
#    (dla modelu; ARCHITECTURE 4.2, ADR-007); parametry, których może brakować
#    w poleceniu, mają opcję unspecified z samym description (3.4).
# 5. Nowy kind? — sekcja 17.2.
# 6. Testy handlera na prawdziwym narzędziu z małymi danymi (sekcja 10.4).
# 7. Co najmniej 15 poleceń w retman/eval/commands.jsonl, w tym niepełne,
#    niejednoznaczne i spoza zakresu (ARCHITECTURE 8.1); retman-eval.
# 8. Więcej niż 10 opcji w pytaniu o operację (z out_of_scope)? — rozpoznanie
#    dwustopniowe przez category (ARCHITECTURE 3.4, pkt 1).
```

### 17.2 Nowy rodzaj danych (`kind`)

```python
# 1. Wpis w retman/kinds.py: nazwa, format pliku, walidator (ARCHITECTURE 3.2.6).
# 2. Format dobierz tak, żeby GUI narzędzi mogły go wczytać (ARCHITECTURE 12, pkt 7).
# 3. Testy walidatora: poprawny plik i typowe błędy.
# 4. Opis w ARCHITECTURE 3.2.6 w tym samym commicie.
```

### 17.3 Nowy backend modelu

```python
# 1. Klasa w retman/backends/ implementująca DecisionBackend i/lub TextBackend
#    (ARCHITECTURE 3.3.1) — HTTP bezpośrednio, bez SDK dostawcy.
# 2. Pewność: skalibrowana albo logprobs / consistency / none (ARCHITECTURE 3.3.3);
#    progi "auto" z tym backendem to błąd konfiguracji (ARCHITECTURE 6.2).
# 3. Ustawienia w retman.toml z komentarzami w szablonie retman init (9.1).
# 4. Sprawdzenia w retman doctor: adres, odpowiedź, pytanie testowe (7.2).
# 5. Testy offline na fixturach z realnych odpowiedzi serwera (sekcja 10.4).
# 6. retman-eval na nowym backendzie; wynik do docs/research/.
```

---

## 18. Pre-merge checklist

```markdown
- [ ] Testy offline przechodzą (`pytest tests/ -v -m "not live"`; testy
      `live` tylko świadomie: `pytest tests/ -m live`)
- [ ] Pokrycie kodu w normie (sekcja 10.1: `fail_under` + 80% rdzenia)
- [ ] Formatowanie OK (`ruff format --check .`)
- [ ] Linting OK (`ruff check .`)
- [ ] Type hints OK (`mypy retman/ tests/` bez błędów, sekcja 8.3)
- [ ] Kontrola rozjazdów OK (`retman-scaffold --check`)
- [ ] Komplet tłumaczeń (test z sekcji 10.4)
- [ ] `retman-eval` uruchomiony, jeśli zmieniły się pytania, opisy opcji lub logika decyzji
- [ ] Docstringi dla publicznych funkcji/klas
- [ ] Brak hardcoded secrets i treści poleceń w logach
- [ ] Dokumentacja zaktualizowana (PRD / ARCHITECTURE, odsyłacze w obu plikach)
- [ ] PROGRESS.md / CHANGELOG.md zaktualizowane
- [ ] Minimum 1 approval
- [ ] Brak konfliktów z target branch
```

---

**Wersja dokumentu:** 1.0
**Data ostatniej aktualizacji:** 2026-10-12
**Źródło:** `Kartograf/docs/DEVELOPMENT_STANDARDS.md` v3.3

*Odstępstwa od tych standardów wymagają uzasadnienia — w tym dokumencie albo w ADR (`docs/DECISIONS.md`).*

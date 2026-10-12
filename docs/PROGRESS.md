# PROGRESS — Retman

Bieżący stan prac. Stan gałęzi, tagów i `origin` sprawdzaj w gicie
(`git status`, `git log`, `git ls-remote --tags origin`), nie w tym dzienniku.
Szablony wpisów: [Szablony](#szablony).

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| Dokumentacja projektowa (PRD, ARCHITECTURE, DEVELOPMENT_STANDARDS) | ✅ Gotowy | szkic 2026-10-11; ADR-001–005; otwarte kwestie: PRD rozdz. 11, ARCHITECTURE rozdz. 12 |
| Repozytorium (`main`, `develop`, `origin`) | ✅ Gotowy | `main` i `develop` na `origin` |
| Lista pierwszych operacji v0.1 | 🚧 W toku | Kartograf: 4 operacje (ADR-001); brak operacji drugiego narzędzia (PRD 7.1) |
| Szkielet pakietu, `pyproject.toml`, `retman.toml` i `retman init` | ✅ Gotowy | ARCHITECTURE 3.1, 9.1; Python ≥ 3.12 (ADR-002) |
| Ekstraktory (w tym prawdopodobieństwo) | 🚧 W toku | gotowe: `area`, `path`, `result`; brak: prawdopodobieństwo, daty, stacje, liczby z jednostkami |
| Backendy `basal`, `openai_compatible`, `none`; `FakeDecisionBackend` | 🚧 W toku | gotowe: `openai_compatible`, atrapa; `basal` — brak specyfikacji API basal-serve |
| Rdzeń: pipeline, `Plan`, `dialog`, `Result` | ✅ Gotowy | ARCHITECTURE 2, 6, 7.1, 7.3 |
| Rejestr operacji, wspólny adapter, `kinds`, `retman-scaffold` | 🚧 W toku | rejestr, adapter, `kinds` gotowe; `retman-scaffold` nie powstał |
| Przestrzeń robocza, dziennik projektu, ślad audytowy | ✅ Gotowy | ARCHITECTURE 5 |
| CLI, `retman doctor`, `results`, `log` | 🚧 W toku | CLI, `results`, `log`, `init` gotowe; brak `retman doctor` |
| `retman-eval` i zbiór poleceń testowych | 🚧 W toku | kod i szkic zbioru gotowe; czeka: przegląd zbioru przez autora, przebieg na Bieliku 11B (spec. rozdz. 9) |
| CI (Windows, Linux, macOS; test instalacji; wersje narzędzi) | ⏳ Planowany | ARCHITECTURE 3.2.7, 9.4 |

## Checkpointy

### CP0 — Dokumentacja startowa
- **Data:** 2026-10-11
- **Wersja:** — (przed v0.1.0)
- **Zakres:** PRD, architektura, standardy deweloperskie, szablony DECISIONS/PROGRESS/CHANGELOG, README, CLAUDE.md, licencja MIT, konfiguracja repozytorium; pierwszy commit `70857c0`

## Ostatnia sesja

> **START NASTĘPNEJ SESJI (stan 2026-10-12):** praca na `develop` (commity lokalne,
> niewypchnięte). `retman-eval` zaimplementowany wg przyjętej specyfikacji; zbiór
> `retman/eval/commands.jsonl` to szkic agenta. **Najpierw: przegląd zbioru przez autora**
> (spec. 10 pkt 2), potem przebieg na Bieliku 11B w LM Studio (adres podaje użytkownik,
> nie zapisywać), raport do `docs/research/`, strojenie progów i opisów; potem
> `retman doctor`. Niezatwierdzona zmiana użytkownika w `retman/tools/kartograf/pl.toml`
> (`[errors]`: PRG, „shapefile”) — nie z sesji agenta. Decyzje autora: operacja drugiego
> narzędzia (PRD 7.1), plik geometrii, wartości docelowe (PRD W-01, N-07, rozdz. 8),
> ADR wsteczne dla pierwszej sesji, prefiks „Błąd:” i kod 1 dla polecenia spoza zakresu
> w CLI.

### `retman-eval` (2026-10-12)

- **Zlecenie użytkownika:** implementacja `retman-eval` po akceptacji specyfikacji.
- **Decyzje użytkownika:** specyfikacja `docs/specs/retman-eval.md` przyjęta bez zmian.
- **Zrobione:**
  - `OutOfScopeError(RetmanError)` z `operations` (spec. 7); CLI bez zmian (nadal „Błąd:”
    i kod 1 — decyzja autora);
  - `retman/eval/dataset.py` (wczytanie i walidacja wpisów, spec. 2.2, manifesty wszystkich
    narzędzi z `retman/tools/`), `runner.py` (CLI, izolacja w katalogu tymczasowym, licznik
    zapytań do modelu), `metrics.py` (spec. 5), `report.py` (teksty w `[eval]`
    `retman/i18n/pl.toml`); skrypt `retman-eval` w `pyproject.toml`;
  - szkic zbioru: 4 × 15 poleceń Kartografa, 10 `out_of_scope`, 5 `near_miss`; tagi:
    formal 31, colloquial 20, typo 10, incomplete 23, ambiguous 4, complete 33;
  - testy `tests/eval/` (walidacja zbioru i reguły budowy 2.3, miary, krzywa progów,
    izolacja, brak adresu w rekordach) + test `live`;
  - ARCHITECTURE 3.1 (moduły `eval/`), status specyfikacji, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 166 passed, pokrycie 89% (`eval/` 86–99%);
  ruff, mypy czyste. Smoke: `retman-eval` (`main`) na całym zbiorze z
  `FakeDecisionBackend` wybierającym zawsze NMT dla arkusza → raport z wszystkimi
  sekcjami, 75 rekordów, kod 4 (15 naruszeń W-03), brak plików poza katalogiem
  tymczasowym. Przebiegu na modelu nie było.
- **Do przeglądu w zbiorze:** `kartograf-hierarchy-006/-007` (godła PL-2000 i dostępność
  skali zależą od pokrycia GUGiK), `kartograf-cutout-008/-009/-015`,
  `kartograf-bdot-011` (kolejność osi PL-1992 → pytanie), `kartograf-bdot-015` (pytanie
  o format zostawia go nieokreślonym), `near-005` (przycięcie ortofotomapy do wielokąta).

### Etykiety i opisy opcji (2026-10-12)

- **Zlecenie użytkownika:** stan prac; pytanie, dlaczego `pl.toml` obok NMT wymienia DEM
  i „rzeźbę terenu”.
- **Decyzje użytkownika:** opcje rozdzielone jak operacje — `label` dla użytkownika,
  `description` z synonymami i nazwami angielskimi dla modelu, bo w praktyce używa się
  angielskich nazw i skrótów (ADR-007).
- **Zrobione:**
  - `core/pipeline.py`: pytania i plan pokazują `options.<klucz>.label`; model dostaje
    `options.<klucz>.description` (także `unspecified`) — przy poleceniu i przy odpowiedzi
    własnymi słowami; odpowiedź na pytanie o operację model dopasowuje do `description`
    operacji, nie do `label`;
  - `registry/manifest.py`: walidacja wymaga `label` i `description` każdej opcji
    oraz `unspecified.description`;
  - `retman/tools/kartograf/pl.toml`: krótkie etykiety opcji; w opisach dodane DTM,
    orthophoto, PUWG 1992, UTM 33N, Křovák, poziom odniesienia Amsterdam, GPKG/SHP;
  - testy: `test_choice_options_show_labels_and_offer_descriptions_to_model`, przypadek
    opcji z jednym tekstem w `test_validate_manifest_reports_missing_language_option_and_example`;
    fixture `dummy_tool/pl.toml` w nowym schemacie;
  - dokumentacja: ADR-007, ARCHITECTURE 4.2, STANDARDS 17.1, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 143 passed; `ruff check`, `ruff format
  --check`, `mypy retman/ tests/` czyste. Smoke (skrypt z `FakeDecisionBackend`
  na prawdziwych tekstach Kartografa): pytanie pokazuje „1 m”, „5 m (tylko EVRF2007)”,
  plan „Rozdzielczość NMT: 1 m”, model dostał opisy z „NMT/DEM”. Bez modelu na żywo —
  wpływ synonimów na trafność zmierzy `retman-eval`.
- **Przegląd `pl.toml`:** autor zaakceptował treść Kartografa (etykiety, synonimy,
  pytania, `help`, `example`) bez zmian.

### Pionowy przekrój na Kartografie 0.7.2 (2026-10-11)

- **Zlecenie użytkownika:** kontynuacja prac; Kartograf v0.7.2 jako pierwsze narzędzie
  do testowania możliwości Retmana.
- **Decyzje użytkownika:** operacje Kartografa i formy obszaru (ADR-001); Python ≥ 3.12
  (ADR-002); zakres `>=0.7.2,<0.8` i grupa `tools` z tagiem Git (ADR-003); osobny `kind`
  na produkt (ADR-004); kolejność sesji: szkielet + konfiguracja, potem przekrój
  Kartografa; operacje Kartografa bez wartości domyślnych — Retman dopytuje (ADR-006);
  `retman-eval`: na razie LM Studio (basal-serve niedostępny), zbiór jako szkic agenta,
  kod 0 poza naruszeniem W-03 (kod 4), ARCHITECTURE 8 bez zmian (specyfikacja rozdz. 10).
  Adresu serwera LM Studio i ścieżki przestrzeni roboczej agenta nie wolno zapisywać
  w żadnym pliku.
- **Zrobione:**
  - `pyproject.toml`, `.venv` przez `uv` (zainstalowany w `~/.local/bin`), konfiguracja
    ruff (bez plików `.md` — przykłady „BAD” w dokumentacji), mypy, pytest, coverage;
  - `config.py` + szablon, `exceptions.py`, loader tłumaczeń, izolacja sieci w testach;
  - ekstraktory `area`/`path`/`result`; backend `openai_compatible` + `FakeDecisionBackend`;
    `kinds.py`; `retman/tools/kartograf/` (manifest, handlery, `pl.toml`); rejestr,
    adapter, pipeline, plan, dialog, workspace, journal, CLI (subagenci, integracja
    i poprawki w tej sesji);
  - poprawki po smoke: decyzja z `logprobs` = najbardziej prawdopodobna opcja, nie
    wylosowany token (`27c6864`); niska pewność przy `unspecified` → pytanie zamiast
    wartości domyślnej; `label` operacji dla użytkownika oddzielony od `description`
    dla modelu; plan pokazuje odczyt prostokąta jako N/E;
  - badanie LM Studio: `docs/research/2026-10-11-lm-studio-openai-compatible.md`
    (ARCHITECTURE 12 pkt 9);
  - specyfikacja `docs/specs/retman-eval.md`; manifest Kartografa bez `default` (ADR-006);
  - dokumentacja: ADR-001–006, PRD 7.2, ARCHITECTURE 3.1, 3.2.6, 4.1–4.3, 9.2–9.3, 12,
    STANDARDS 5.1, 6.1, 8.1, README, CLAUDE.md, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 142 passed, pokrycie 88% (rdzeń ≥ 84%);
  `pytest -m live` — 6 passed (5 handlerów Kartografa na GUGiK, 1 Bielik 11B);
  `ruff check`, `ruff format --check`, `mypy retman/ tests/` czyste. Smoke CLI
  w folderze projektu poza repo z Bielikiem 11B: NMT 5 m dla N-34-130-D-d-2-4 →
  `ok=False` (GUGiK nie ma 5 m dla arkusza, komunikat Kartografa, exit 1); wycinek NMT dla
  prostokąta WGS84 → GeoTIFF EPSG:2180 1 m, 573×561, 77–90 m (Poznań), exit 0; sesja:
  BDOT10k TERYT 2264 z `z` (zmiana na SHP) → 58 plików `.shp`, `koniec` exit 0;
  polecenie spoza zakresu → lista operacji; bez TTY → exit 2; `results`, `log` działają.
- **Otwarte:**
  - **plik geometrii (SHP/GPKG)**: ekstraktor go rozpoznaje, ale żadna operacja Kartografa
    go nie przyjmuje — `download_pl_cutout(geometry=)` w 0.7.2 jest nieaktywny, a publiczne
    API nie ma funkcji zwracającej prostokąt geometrii (potrzebna np.
    `get_overall_bbox(path, layer=None, target_crs=...)` w `__all__` Kartografa) —
    decyzja autora;
  - backend `basal`: brak specyfikacji API basal-serve i serwera do nagrania fixtur;
    konfiguracja z `backend = "basal"` kończy się komunikatem `backend_unavailable`;
  - Qwen w LM Studio nieprzetestowany (serwer odmówił załadowania — zasoby);
  - `retman-scaffold --check` z bramki (CLAUDE.md) jeszcze nie istnieje;
  - polecenie spoza zakresu jest wypisywane z prefiksem „Błąd:” i kończy się kodem 1 —
    do przemyślenia przy `retman-eval`/UX;
  - Kartograf przy folderze projektu na udziale CIFS zgłasza „database is locked” dla
    cache metadanych w folderze wyniku i pracuje bez cache (zachowanie Kartografa).

### Start projektu: dokumentacja i repozytorium (2026-10-11)

- **Zlecenie użytkownika:** zapoznanie z dokumentacją, weryfikacja i aktualizacja
  dokumentów (subagent na modelu z roli `slow`), README, układ dokumentacji
  wg konwencji Kartografa, `CLAUDE.md`, standardy deweloperskie, inicjalizacja gita.
- **Decyzje użytkownika:**
  - liczba prawdopodobieństwa bez „%”, „Q” i okresu w latach zawsze wywołuje
    pytanie (ARCHITECTURE 4.4);
  - wykonanie bez potwierdzenia wykluczone w wersjach 0.x, nie na stałe
    (PRD 7.3, ARCHITECTURE 1.1, 1.2, 6.3, rozdz. 10);
  - `retman-eval` i zbiór poleceń testowych w pakiecie podstawowym
    (ARCHITECTURE 3.1, 8.1, 8.2, 9.3);
  - bez biblioteki do zapisu TOML: odczyt `tomllib`, `retman init` zapisuje
    z szablonu (ARCHITECTURE 9.3);
  - `DESIGN.md` → `docs/ARCHITECTURE.md`; dokumentacja w `docs/` jak w Kartografie;
  - końce linii LF we wszystkich plikach, bez wyjątków (STANDARDS 5.5);
  - repozytorium `github.com/Daldek/Retman`.
- **Zrobione:**
  - weryfikacja PRD i ARCHITECTURE: m.in. W-15 zależne od `journal_commands`,
    progi `"auto"` tylko z backendem `basal` (inaczej błąd konfiguracji,
    ARCHITECTURE 6.2), LM Studio dla decyzji już w 0.1 (9.4),
    `Retman.from_config()` czyta plik centralny (7.1), `Question.type` zamiast
    `Question.kind`, poprawiony przykład „Q1% i Q10%” (4.4), poprawione odsyłacze;
  - nowe pliki: `README.md`, `CLAUDE.md`, `docs/DEVELOPMENT_STANDARDS.md`,
    szablony `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/CHANGELOG.md`,
    `LICENSE`, `.gitignore`, `.gitattributes`, `.editorconfig`;
  - `git init`: commit `70857c0` na `main`, gałąź `develop`, remote `origin`;
    `<github-user>` w ARCHITECTURE zastąpione adresami `github.com/Daldek/…`;
  - wpis sesji, CP0 i backlog w PROGRESS, sekcja `[0.1.0] - Unreleased`
    w CHANGELOG (commit `8c7657c`);
  - instrukcja założenia repozytorium (`gh repo create` albo github.com/new
    bez README/licencji) — `gh` nie jest zainstalowany na maszynie agenta;
    repozytorium założył i wypchnął użytkownik.
- **Weryfikacja:** odsyłacze `p.`/`rozdz.`/`[W-xx]`/`[N-xx]`/`S-xx` sprawdzone
  skryptem subagenta (brak martwych); brak odwołań do `DESIGN`;
  `git ls-files --eol` bez `w/crlf`; `git ls-remote --heads origin` —
  tylko `develop` (`8c7657c`).
- **Otwarte:** decyzje z Backlogu; push `main`; czy zapisać decyzje
  z tej sesji jako ADR-001… w `docs/DECISIONS.md` (pytanie bez odpowiedzi).
  Override modelu subagentów (`task` → rola `slow`) był tylko na tę sesję,
  niezapisany.

## Backlog

#### Do 0.1.0

Decyzje autora (blokują część implementacji):

- [ ] **Operacja drugiego narzędzia** (PRD 7.1: z co najmniej dwóch narzędzi) —
  Kartograf ustalony w ADR-001; PRD 7.2, 11 pkt 4.
- [x] **Rodzaje danych dla Kartografa** — ADR-004, ARCHITECTURE 3.2.6; pozostałe
  narzędzia otwarte (PRD 11 pkt 8; ARCHITECTURE 12 pkt 7).
- [ ] **Plik geometrii jako obszar** — potrzebna publiczna funkcja Kartografa
  (prostokąt geometrii) albo inna decyzja autora (wpis sesji 2026-10-11, „Otwarte”).
- [ ] **Wartości docelowe**: trafność rozpoznania (W-01), czas odpowiedzi (N-07),
  miary sukcesu — PRD rozdz. 8, 11 pkt 5.
- [x] **Push `main` na `origin`** — `main` na `origin` (`70857c0`).
- [ ] **ADR dla decyzji z pierwszej sesji 2026-10-11** (lista we wpisie „Start projektu”) —
  czy zapisywać wstecznie w `docs/DECISIONS.md`.

Implementacja (kolejność wg ARCHITECTURE rozdz. 11):

- [x] **Szkielet pakietu i konfiguracja** — `pyproject.toml`, `retman/config.py`,
  `tests/conftest.py`, `retman init` (sesja 2026-10-11, przekrój Kartografa).
- [ ] **`retman doctor`** (ARCHITECTURE 7.2) — adres i pytanie testowe modelu, wersje
  narzędzi, komplet tłumaczeń, przestrzeń robocza.
- [ ] **`retman-eval` i zbiór poleceń testowych** — kod gotowy (sesja 2026-10-12);
  czeka przegląd zbioru przez autora, przebieg na Bieliku 11B z raportem
  w `docs/research/`, strojenie progów i opisów opcji (ARCHITECTURE 6.2, 8; spec. rozdz. 9).
- [ ] **Ekstraktor prawdopodobieństwa** z testami wszystkich form z ARCHITECTURE 4.4.
- [ ] **Pozostałe ekstraktory** — współrzędne punktu, liczby z jednostkami, daty,
  stacje (ARCHITECTURE 3.1, 6.1); gotowe: `area`, `path`, `result`.
- [ ] **Backend `basal`** — po uzyskaniu specyfikacji API basal-serve i serwera do
  nagrania fixtur (ARCHITECTURE 3.3, STANDARDS 10.4).
- [x] **Backend `openai_compatible` i `FakeDecisionBackend`** (ARCHITECTURE 3.3, 8.3).
- [x] **Rdzeń** — pipeline, `Plan`, `dialog`, `Result`, `PlanNotConfirmedError`.
- [x] **Rejestr operacji, wspólny adapter, `kinds`** (ARCHITECTURE 3.2, 4.1–4.3).
- [ ] **`retman-scaffold`** — szkice i kontrola rozjazdów (ARCHITECTURE 3.2.3); jest
  w bramce CLAUDE.md, a jeszcze nie istnieje.
- [x] **Przestrzeń robocza, dziennik projektu, ślad audytowy** (ARCHITECTURE 5).
- [x] **CLI, `results`, `log`, `init`** (ARCHITECTURE 6.4, 7.1).
- [ ] **CI** — Windows, Linux, macOS; test instalacji; testy handlerów na
  wersjach narzędzi; kontrola rozjazdów (ARCHITECTURE 3.2.7, 9.4).
- [ ] **Pomiary czasu odpowiedzi** (ARCHITECTURE 9.2) — orientacyjnie z smoke:
  plan z 4 decyzjami Bielika 11B ≈ 7 s (≈ 1,7 s na decyzję).

---

## Szablony

**Status elementu** — wiersz tabeli „Status projektu”; status: `✅ Gotowy`,
`🚧 W toku`, `⏳ Planowany`, `❌ Wstrzymany`:

```markdown
| Element | ✅ Gotowy | wersja, odsyłacze (ADR-XXX, ARCHITECTURE p. X.Y), uwagi |
```

**Checkpoint** — po każdym wydaniu, od najstarszego:

```markdown
### CPN — Tytuł
- **Data:** RRRR-MM-DD
- **Wersja:** vX.Y.Z
- **Zakres:** najważniejsze zmiany; pełna lista: `docs/CHANGELOG.md` [X.Y.Z]
```

**Sesja** — na początku sekcji „Ostatnia sesja” (od najnowszej); stan do
podjęcia w następnej sesji w bloku `START NASTĘPNEJ SESJI` nad wpisami:

```markdown
> **START NASTĘPNEJ SESJI (stan RRRR-MM-DD):** co jest w toku, co zrobić
> najpierw, jakie decyzje czekają na użytkownika.

### Tytuł sesji (RRRR-MM-DD)

- **Zlecenie użytkownika:** czego dotyczyła sesja.
- **Decyzje użytkownika:** ustalenia (ADR-XXX, jeśli powstał).
- **Zrobione:** zmiany z odsyłaczami (pliki, commity, raporty).
- **Weryfikacja:** co uruchomiono i z jakim wynikiem.
- **Otwarte:** co zostało i dlaczego.
```

**Pozycja backlogu** — w podsekcji wersji docelowej; `[x]` po zakończeniu,
z odsyłaczem do miejsca realizacji:

```markdown
#### Do X.Y.Z

- [ ] **Tytuł** — opis, źródło (PRD W-xx / ARCHITECTURE p. X.Y / ADR-XXX).
```
